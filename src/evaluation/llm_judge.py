"""
LLM-as-Judge evaluation for generated RCA reports.

Provides two independent evaluation surfaces:

1. Likert-scale quality judgement — scores an RCA on 4 axes (correctness,
   groundedness, actionability, completeness) against a reference RCA on a
   1-5 scale. Uses the configured LLM (Groq or Kimi) when a key is set, else falls back
   to the Groq Llama 3.3 70B generator (bias disclosed in output).

2. RAGAS-style faithfulness & answer-relevancy — custom, framework-free
   implementations that do NOT require the `ragas` package (which pulls in
   heavy deps). Semantics match the RAGAS definitions:

     faithfulness  = atomic_claims_supported_by_context / total_claims
     answer_relev. = cos_sim(question, questions_reverse_generated_from_answer)

The contract is intentionally small so this module can be called from
`metrics.py` and from `run_ablation.py` without side-effects.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    JUDGE_API_KEY,
    JUDGE_BASE_URL,
    JUDGE_MODEL,
    JUDGE_TEMPERATURE,
    JUDGE_FALLBACK_MODEL,
    GROQ_API_KEY,
)

# ────────────────────────────────────────────────────────────────────
# Judge client abstraction
# ────────────────────────────────────────────────────────────────────
# The judge uses any OpenAI-compatible endpoint: OpenAI, Kimi (Moonshot),
# MiniMax, Groq, DeepSeek, etc. Configure via JUDGE_BASE_URL + JUDGE_API_KEY
# in .env. Falls back to Groq SDK if only GROQ_API_KEY is set.

_JUDGE_BACKEND = None  # "openai_compat" | "groq" | "none"
_JUDGE_CLIENT = None


def _get_backend() -> str:
    """Return which backend to use; cached after first call."""
    global _JUDGE_BACKEND
    if _JUDGE_BACKEND is not None:
        return _JUDGE_BACKEND
    if JUDGE_API_KEY:
        _JUDGE_BACKEND = "openai_compat"
    elif GROQ_API_KEY:
        _JUDGE_BACKEND = "groq"
    else:
        _JUDGE_BACKEND = "none"
    return _JUDGE_BACKEND


def _get_oai_client():
    """Lazy OpenAI-compatible client (works for OpenAI/Kimi/MiniMax/etc.)."""
    global _JUDGE_CLIENT
    if _JUDGE_CLIENT is not None:
        return _JUDGE_CLIENT
    from openai import OpenAI
    kwargs = {"api_key": JUDGE_API_KEY}
    if JUDGE_BASE_URL:
        kwargs["base_url"] = JUDGE_BASE_URL
    _JUDGE_CLIENT = OpenAI(**kwargs)
    return _JUDGE_CLIENT


def _call_judge(system: str, user: str, max_retries: int = 3) -> Optional[str]:
    """Call the judge LLM in JSON mode. Returns raw content or None."""
    backend = _get_backend()
    for attempt in range(max_retries):
        try:
            if backend == "openai_compat":
                client = _get_oai_client()
                # Kimi + MiniMax honour response_format=json_object just like OpenAI.
                # If a provider rejects it, the except path retries without it.
                try:
                    resp = client.chat.completions.create(
                        model=JUDGE_MODEL,
                        temperature=JUDGE_TEMPERATURE,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    )
                except Exception as inner:
                    if "response_format" in str(inner).lower():
                        resp = client.chat.completions.create(
                            model=JUDGE_MODEL,
                            temperature=JUDGE_TEMPERATURE,
                            messages=[
                                {"role": "system", "content": system + "\n\nRespond with valid JSON only."},
                                {"role": "user", "content": user},
                            ],
                        )
                    else:
                        raise
                return resp.choices[0].message.content
            elif backend == "groq":
                from langchain_groq import ChatGroq
                from langchain_core.messages import SystemMessage, HumanMessage
                llm = ChatGroq(
                    model=JUDGE_FALLBACK_MODEL,
                    api_key=GROQ_API_KEY,
                    temperature=JUDGE_TEMPERATURE,
                    timeout=30,
                    model_kwargs={"response_format": {"type": "json_object"}},
                )
                resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
                return resp.content
            else:
                return None
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                time.sleep(2 ** attempt * 3)
                continue
            if attempt == max_retries - 1:
                print(f"[judge] call failed: {e}")
                return None
            time.sleep(1)
    return None


def _parse_json(text: str) -> Optional[dict]:
    if text is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        # strip code fences if present
        t = text.strip()
        if t.startswith("```"):
            t = t.strip("`").split("\n", 1)[-1]
            if t.endswith("```"):
                t = t[: -3]
        try:
            return json.loads(t)
        except Exception:
            return None


# ────────────────────────────────────────────────────────────────────
# 1. Likert-scale quality judge
# ────────────────────────────────────────────────────────────────────

LIKERT_SYSTEM = """You are an expert telecom billing engineer acting as an \
impartial evaluator of automatically-generated Root Cause Analysis (RCA) \
reports. You score each RCA on FOUR axes using a 1-5 Likert scale:

1. correctness    — Does the stated root cause actually explain the anomaly?
2. groundedness   — Is the reasoning traceable to the supplied evidence/context \
(no hallucination)?
3. actionability  — Are the recommended actions concrete, specific, and \
implementable by a billing ops team?
4. completeness   — Does the RCA cover root cause + supporting evidence + \
actions + severity without important omissions?

Scale: 1 = very poor, 2 = poor, 3 = acceptable, 4 = good, 5 = excellent.

Return STRICT JSON only, no prose. Schema:
{"correctness": int, "groundedness": int, "actionability": int,
 "completeness": int, "rationale": "<=40 words"}"""


LIKERT_USER_TEMPLATE = """ANOMALY TYPE: {anomaly_type}

REFERENCE (ground-truth) ROOT CAUSE:
{reference}

CANDIDATE RCA TO SCORE:
Root cause: {candidate_root_cause}
Supporting evidence: {candidate_evidence}
Recommended actions: {candidate_actions}
Severity: {candidate_severity}

RETRIEVED CONTEXT USED BY THE CANDIDATE (for groundedness check):
{context}

Score the candidate now. Return JSON only."""


def likert_judge(
    anomaly_type: str,
    candidate: dict,
    reference: str,
    retrieved_context: str,
) -> Dict[str, float]:
    """Return {correctness, groundedness, actionability, completeness, rationale, backend}.

    Values are ints 1-5 (or 0 on failure). `backend` is a string.
    """
    user = LIKERT_USER_TEMPLATE.format(
        anomaly_type=anomaly_type,
        reference=(reference or "")[:1200],
        candidate_root_cause=(candidate.get("root_cause") or "")[:1200],
        candidate_evidence=str(candidate.get("supporting_evidence") or "")[:800],
        candidate_actions=str(candidate.get("recommended_actions") or "")[:800],
        candidate_severity=candidate.get("severity") or "N/A",
        context=(retrieved_context or "")[:2500],
    )
    raw = _call_judge(LIKERT_SYSTEM, user)
    parsed = _parse_json(raw) or {}
    return {
        "correctness": int(parsed.get("correctness", 0) or 0),
        "groundedness": int(parsed.get("groundedness", 0) or 0),
        "actionability": int(parsed.get("actionability", 0) or 0),
        "completeness": int(parsed.get("completeness", 0) or 0),
        "rationale": str(parsed.get("rationale", ""))[:400],
        "backend": _get_backend(),
    }


# ────────────────────────────────────────────────────────────────────
# 2. Custom RAGAS-style faithfulness & answer relevancy
# ────────────────────────────────────────────────────────────────────

CLAIM_EXTRACT_SYSTEM = """You extract atomic, verifiable factual claims from \
a Root Cause Analysis. One claim per line. No opinions or recommendations. \
Return STRICT JSON: {"claims": ["claim 1", "claim 2", ...]}"""


CLAIM_VERIFY_SYSTEM = """You verify whether each atomic claim is directly \
supported by the supplied context. For each claim output 1 if the context \
entails or clearly implies the claim, else 0. Return STRICT JSON: \
{"verdicts": [0 or 1, ...]} in the same order as the claims."""


def faithfulness(rca_text: str, retrieved_context: str) -> Dict[str, float]:
    """RAGAS-style faithfulness = supported_claims / total_claims, in [0,1]."""
    if not rca_text or not retrieved_context:
        return {"faithfulness": 0.0, "n_claims": 0, "n_supported": 0}

    raw = _call_judge(
        CLAIM_EXTRACT_SYSTEM,
        f"RCA TEXT:\n{rca_text[:2500]}\n\nExtract atomic claims now.",
    )
    claims = (_parse_json(raw) or {}).get("claims", []) or []
    claims = [c for c in claims if isinstance(c, str) and c.strip()][:20]
    if not claims:
        return {"faithfulness": 0.0, "n_claims": 0, "n_supported": 0}

    verify_user = (
        f"CONTEXT:\n{retrieved_context[:3000]}\n\n"
        f"CLAIMS (in order):\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
        + "\n\nReturn verdicts JSON."
    )
    raw2 = _call_judge(CLAIM_VERIFY_SYSTEM, verify_user)
    verdicts = (_parse_json(raw2) or {}).get("verdicts", []) or []
    # Normalise length
    verdicts = [int(v) for v in verdicts if v in (0, 1, True, False)]
    if len(verdicts) < len(claims):
        verdicts += [0] * (len(claims) - len(verdicts))
    verdicts = verdicts[: len(claims)]

    n_supported = sum(verdicts)
    return {
        "faithfulness": n_supported / len(claims),
        "n_claims": len(claims),
        "n_supported": n_supported,
    }


QUESTION_GEN_SYSTEM = """Given an RCA answer, generate 3 concise diagnostic \
questions whose answer would be exactly this RCA. Return STRICT JSON: \
{"questions": ["q1", "q2", "q3"]}"""


def _embed(texts: List[str]) -> Optional["np.ndarray"]:
    """Lazy load sentence-transformers; reuse config model."""
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        from config import EMBEDDING_MODEL_NAME
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        vecs = model.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs)
    except Exception as e:
        print(f"[judge] embedding failed: {e}")
        return None


def answer_relevancy(original_question: str, rca_text: str) -> Dict[str, float]:
    """RAGAS-style answer relevancy: mean cos-sim between original question and
    questions reverse-generated from the answer. Range ~[−1, 1], usually [0, 1]."""
    if not rca_text or not original_question:
        return {"answer_relevancy": 0.0, "n_generated": 0}
    raw = _call_judge(
        QUESTION_GEN_SYSTEM,
        f"RCA ANSWER:\n{rca_text[:2500]}\n\nGenerate 3 questions now.",
    )
    qs = (_parse_json(raw) or {}).get("questions", []) or []
    qs = [q for q in qs if isinstance(q, str) and q.strip()][:3]
    if not qs:
        return {"answer_relevancy": 0.0, "n_generated": 0}
    vecs = _embed([original_question] + qs)
    if vecs is None or len(vecs) < 2:
        return {"answer_relevancy": 0.0, "n_generated": len(qs)}
    import numpy as np
    ref = vecs[0]
    sims = [float(np.dot(ref, v)) for v in vecs[1:]]
    return {"answer_relevancy": float(np.mean(sims)), "n_generated": len(qs)}


# ────────────────────────────────────────────────────────────────────
# 3. Batch helper
# ────────────────────────────────────────────────────────────────────

def judge_batch(
    results: List[dict],
    gt_lookup: Dict[str, dict],
    run_likert: bool = True,
    run_faithfulness: bool = True,
    run_relevancy: bool = True,
    verbose: bool = True,
) -> List[dict]:
    """Attach judge scores to each result dict in-place and return the list.

    `results` items are expected to follow run_pipeline() output shape:
      { anomaly_data: {...}, rca_report: {...}, retrieved_docs: [...],
        retrieval_query: str, ... }
    `gt_lookup` maps anomaly_type -> ground-truth record.
    """
    for i, r in enumerate(results):
        anomaly_type = r.get("anomaly_data", {}).get("anomaly_type", "")
        gt = gt_lookup.get(anomaly_type, {})
        rca = r.get("rca_report", {}) or {}
        retrieved_docs = r.get("retrieved_docs", []) or []
        context = "\n---\n".join(
            d if isinstance(d, str) else json.dumps(d) for d in retrieved_docs
        )[:6000]
        rca_text = rca.get("root_cause", "") or rca.get("summary", "")
        question = r.get("retrieval_query") or f"What is the root cause of {anomaly_type}?"

        scores = {"judge_backend": _get_backend()}
        if run_likert and gt:
            scores["likert"] = likert_judge(anomaly_type, rca, gt.get("root_cause", ""), context)
        if run_faithfulness:
            scores["faithfulness"] = faithfulness(rca_text, context)
        if run_relevancy:
            scores["answer_relevancy"] = answer_relevancy(question, rca_text)

        r["judge_scores"] = scores
        if verbose:
            ll = scores.get("likert", {})
            f_ = scores.get("faithfulness", {})
            ar = scores.get("answer_relevancy", {})
            print(
                f"  [{i+1}/{len(results)}] {anomaly_type}  "
                f"likert=C{ll.get('correctness', 0)}/G{ll.get('groundedness', 0)}/"
                f"A{ll.get('actionability', 0)}/Cm{ll.get('completeness', 0)}  "
                f"faith={f_.get('faithfulness', 0):.2f}  "
                f"ar={ar.get('answer_relevancy', 0):.2f}"
            )
    return results


def aggregate_judge_scores(results: List[dict]) -> dict:
    """Aggregate per-result judge scores to means."""
    import numpy as np
    agg = {}
    likert_keys = ["correctness", "groundedness", "actionability", "completeness"]
    for k in likert_keys:
        vals = [r.get("judge_scores", {}).get("likert", {}).get(k, 0) for r in results]
        vals = [v for v in vals if v > 0]
        agg[f"judge_{k}_mean"] = float(np.mean(vals)) if vals else 0.0
        agg[f"judge_{k}_n"] = len(vals)
    faith = [
        r.get("judge_scores", {}).get("faithfulness", {}).get("faithfulness", 0.0)
        for r in results
    ]
    ar = [
        r.get("judge_scores", {}).get("answer_relevancy", {}).get("answer_relevancy", 0.0)
        for r in results
    ]
    agg["faithfulness_mean"] = float(np.mean(faith)) if faith else 0.0
    agg["answer_relevancy_mean"] = float(np.mean(ar)) if ar else 0.0
    agg["judge_backend"] = _get_backend()
    return agg
