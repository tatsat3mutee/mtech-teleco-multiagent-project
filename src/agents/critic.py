"""
Critic node — reviews the Reasoner's hypothesis against retrieved evidence and
decides whether the pipeline should loop back for broader retrieval.

Outputs are written to AgentState:
    critic_verdict      : "accept" | "revise"
    critic_reasons      : list[str]  — gaps / contradictions flagged
    critic_confidence   : float in [0, 1]
    critic_claims       : list[dict] — per-claim grounding breakdown
                          [{"claim": str, "grounded": bool, "evidence": str|None}]
    critic_attempts     : int  — how many times critic has run (cap to avoid loops)

Routing contract: the graph's conditional edge after `critic` returns
"revise" only when verdict="revise" AND critic_attempts<=1; otherwise "proceed".

Offline/degraded mode: if the LLM call fails, critic defaults to "accept" with
confidence 0.5, so the pipeline always terminates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.agents.llm_utils import call_llm

CRITIC_SYSTEM = (
    "You are a senior telecom billing SRE reviewing a junior engineer's RCA "
    "hypothesis. Return JSON ONLY with keys: verdict ('accept' or 'revise'), "
    "reasons (array of short strings), confidence (0-1 float), and claims "
    "(array of objects, one per factual claim in the hypothesis, each with "
    "keys: claim (short string), grounded (true/false — is this claim "
    "traceable to the retrieved evidence?), evidence (the evidence source "
    "name that supports it, or null if ungrounded)). Flag the "
    "hypothesis as 'revise' ONLY if (a) the hypothesis contradicts the "
    "retrieved evidence, (b) the evidence is too thin to support the claim, "
    "or (c) a more likely root cause is visible in the evidence but ignored. "
    "Otherwise accept."
)


def _parse_json(text: str):
    if text is None:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[-1]
        if t.endswith("```"):
            t = t[:-3]
    try:
        return json.loads(t)
    except Exception:
        # fall back to brace-scan
        lo = t.find("{")
        hi = t.rfind("}")
        if lo >= 0 and hi > lo:
            try:
                return json.loads(t[lo : hi + 1])
            except Exception:
                return None
        return None


def _parse_claims(parsed: dict) -> list:
    """Extract per-claim grounding breakdown; tolerate any malformed shape."""
    claims = []
    for item in (parsed.get("claims") or [])[:10]:
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("claim", "")).strip()
        if not claim_text:
            continue
        evidence = item.get("evidence")
        claims.append({
            "claim": claim_text[:300],
            "grounded": bool(item.get("grounded", False)),
            "evidence": str(evidence)[:200] if evidence else None,
        })
    return claims


def critic_node(state: dict) -> dict:
    """Review reasoner output. Mutates state in-place and returns it."""
    state["critic_attempts"] = state.get("critic_attempts", 0) + 1

    hypothesis = state.get("hypothesis") or state.get("reasoning_chain") or ""
    rca = state.get("rca_report") or {}
    anomaly = state.get("anomaly_data", {})
    docs = state.get("retrieved_docs", []) or []
    evidence = "\n\n".join(
        f"[{i}] {d.get('source', '?')}: {d.get('text', '')[:400]}"
        for i, d in enumerate(docs[:5])
    )

    # Degraded mode guard
    if not hypothesis and not rca:
        state["critic_verdict"] = "accept"
        state["critic_reasons"] = ["no hypothesis to review"]
        state["critic_confidence"] = 0.5
        state["critic_claims"] = []
        return state

    user = (
        f"ANOMALY TYPE: {anomaly.get('anomaly_type', '?')}\n"
        f"ACCOUNT: {anomaly.get('account_id', '?')}\n\n"
        f"PROPOSED HYPOTHESIS:\n{hypothesis}\n\n"
        f"RCA REPORT SUMMARY:\n{json.dumps(rca, default=str)[:1500]}\n\n"
        f"RETRIEVED EVIDENCE:\n{evidence or '(none)'}\n\n"
        "Respond with JSON only."
    )

    raw = call_llm(CRITIC_SYSTEM, user, temperature=0.0)
    parsed = _parse_json(raw) if raw else None

    if not isinstance(parsed, dict):
        state["critic_verdict"] = "accept"
        state["critic_reasons"] = ["critic-llm-unavailable"]
        state["critic_confidence"] = 0.5
        state["critic_claims"] = []
        return state

    verdict = str(parsed.get("verdict", "accept")).strip().lower()
    state["critic_verdict"] = "revise" if verdict == "revise" else "accept"
    state["critic_reasons"] = list(parsed.get("reasons", []))[:6]
    state["critic_claims"] = _parse_claims(parsed)
    try:
        state["critic_confidence"] = float(parsed.get("confidence", 0.5))
    except Exception:
        state["critic_confidence"] = 0.5
    return state


def should_revise(state: dict) -> str:
    """Conditional router for LangGraph — at most one revise loop."""
    if state.get("critic_verdict") == "revise" and state.get("critic_attempts", 0) <= 1:
        return "revise"
    return "proceed"
