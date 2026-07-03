"""
Ablation study harness — runs configs from config.ABLATION_CONFIGS
over ground-truth-derived anomalies and evaluates each against the
60-item reference RCA corpus.

Configs:
  A   no_rag           Direct LLM, no retrieval, no agents
  A2  cot_baseline     Few-shot Chain-of-Thought prompting, no retrieval
  A3  react_baseline   ReAct loop (reason -> retrieve -> observe -> answer)
  B   rag_only         Vector retrieval stuffed into a single LLM call
  C   single_agent_rag One agent: retrieve + reason + report in one call
  D   multi_agent_rag  Full 4-agent LangGraph pipeline (proposed system)
  E   graph_rag        Full pipeline + GraphRAG retrieval (USE_GRAPH_RAG=1)

Blind-type evaluation (default): the ground-truth anomaly_type is NOT shown
to any config. Each input carries a detector-style heuristic estimate
(production-faithful — in deployment the type comes from the detector, not
an oracle). Scoring still compares the report's predicted type against the
true GT type. Use --leak-types to reproduce the legacy oracle-type behaviour.

Usage:
  python run_ablation.py --quick               # 3 anomalies per type (15 total)
  python run_ablation.py --n 60                # full ground-truth set
  python run_ablation.py --configs no_rag,graph_rag
  python run_ablation.py --quick --judge       # adds LLM-as-Judge scoring

Outputs:
  results/ablation/<config>_results.json   raw per-anomaly pipeline outputs
  results/ablation/<config>_metrics.json   aggregate evaluation metrics
  results/ablation/summary.json            cross-config comparison table
  MLflow runs (experiment from config.MLFLOW_EXPERIMENT) per config
"""
import argparse
import copy
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import ABLATION_CONFIGS
from src.utils.test_data import anomalies_from_ground_truth

RESULTS_DIR = Path(__file__).parent / "results" / "ablation"

_DIRECT_SYSTEM = (
    "You are a telecom billing root-cause-analysis expert. "
    "Given an anomaly description, respond ONLY with JSON: "
    '{"anomaly_type": "<one of zero_billing|duplicate_charge|usage_spike|'
    'cdr_failure|sla_breach>", "root_cause": "<2-4 sentence root cause>", '
    '"recommendation": "<1-2 sentence fix>"}'
)

_COT_SYSTEM = (
    "You are a telecom billing root-cause-analysis expert. Think step by step: "
    "1) inspect the numeric features, 2) decide which anomaly pattern they match, "
    "3) reason about the most likely system-level cause, 4) propose a fix. "
    "Work through your reasoning, then finish with ONLY a JSON object on the "
    'final line: {"anomaly_type": "<one of zero_billing|duplicate_charge|'
    'usage_spike|cdr_failure|sla_breach>", "root_cause": "<2-4 sentences>", '
    '"recommendation": "<1-2 sentences>"}\n\n'
    "Example:\n"
    "Features: monthly_charges=0.0, total_charges=3200, tenure=41\n"
    "Step 1: charges dropped to zero while the account has a long history.\n"
    "Step 2: active customer + zero invoice matches the zero_billing pattern.\n"
    "Step 3: most likely the rating engine skipped the account this cycle.\n"
    'Final: {"anomaly_type": "zero_billing", "root_cause": "Rating engine '
    'skipped the account during the billing cycle...", "recommendation": '
    '"Re-rate the cycle and re-issue the invoice."}'
)


def _estimate_input_type(anomaly: dict) -> str:
    """Detector-faithful heuristic type estimate (mirrors detector logic).

    Used in blind mode so configs receive a production-realistic (fallible)
    type signal instead of the ground-truth oracle label.
    """
    mc = anomaly.get("monthly_charges")
    tc = anomaly.get("total_charges")
    if tc is None or (isinstance(tc, float) and math.isnan(tc)):
        return "cdr_failure"
    if mc == 0 and tc == 0:
        return "cdr_failure"
    if mc == 0:
        return "zero_billing"
    if mc and mc >= 500:
        return "usage_spike"
    if mc and mc > 200:
        return "duplicate_charge"
    if mc and mc > 150:
        return "sla_breach"
    return "unknown"


def _blind_copy(anomaly: dict) -> dict:
    """Copy for pipeline input with the oracle label replaced by an estimate."""
    blind = copy.deepcopy(anomaly)
    blind["anomaly_type"] = _estimate_input_type(anomaly)
    blind.pop("ground_truth_id", None)  # scoring key must not reach the LLM path
    return blind


def _anomaly_prompt(anomaly: dict) -> str:
    return (
        f"Account {anomaly.get('account_id')} flagged as {anomaly.get('anomaly_type')} "
        f"by the anomaly detector (heuristic estimate — may be wrong; confidence "
        f"{anomaly.get('confidence', 0):.2f}). "
        f"monthly_charges={anomaly.get('monthly_charges')}, "
        f"total_charges={anomaly.get('total_charges')}, "
        f"tenure={anomaly.get('tenure')} months, "
        f"features={json.dumps(anomaly.get('features', {}), default=str)}. "
        "Identify the most likely root cause."
    )


def _parse_report(raw: str, anomaly: dict) -> dict:
    """Parse LLM JSON output; fall back to wrapping raw text."""
    if raw:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                parsed.setdefault("anomaly_type", "")
                parsed.setdefault("root_cause", "")
                return parsed
        except (ValueError, TypeError):
            pass
    return {"anomaly_type": "", "root_cause": (raw or "").strip()}


def _retrieve_docs(query: str, k: int = 4) -> list:
    from src.rag.knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    return kb.search(query, n_results=k)


def _run_no_rag(anomaly: dict) -> dict:
    from src.agents.llm_utils import call_llm
    t0 = time.time()
    raw = call_llm(_DIRECT_SYSTEM, _anomaly_prompt(anomaly), trace_name="ablation_no_rag")
    return {
        "anomaly_data": anomaly,
        "rca_report": _parse_report(raw, anomaly),
        "retrieval_count": 0,
        "pipeline_status": "completed" if raw else "failed",
        "latency_ms": (time.time() - t0) * 1000,
    }


def _run_cot(anomaly: dict) -> dict:
    """Few-shot chain-of-thought baseline — no retrieval, structured reasoning."""
    from src.agents.llm_utils import call_llm
    t0 = time.time()
    raw = call_llm(_COT_SYSTEM, _anomaly_prompt(anomaly), trace_name="ablation_cot")
    # CoT output has reasoning lines then a final JSON line — parse from the tail
    report = None
    if raw:
        for line in reversed(raw.strip().splitlines()):
            line = line.strip().lstrip("Final:").strip()
            if line.startswith("{"):
                report = _parse_report(line, anomaly)
                break
    if report is None:
        report = _parse_report(raw, anomaly)
    return {
        "anomaly_data": anomaly,
        "rca_report": report,
        "retrieval_count": 0,
        "pipeline_status": "completed" if raw else "failed",
        "latency_ms": (time.time() - t0) * 1000,
    }


def _run_react(anomaly: dict, max_steps: int = 3) -> dict:
    """ReAct baseline — iterative Thought/Action(Search)/Observation loop.

    The model may issue SEARCH[query] actions (served by the same KB as other
    configs) and must finish with FINAL[{json}].
    """
    from src.agents.llm_utils import call_llm
    t0 = time.time()
    system = (
        "You are a telecom billing RCA expert using the ReAct pattern. "
        "On each turn respond with EITHER:\n"
        "Thought: <reasoning>\nAction: SEARCH[<query max 12 words>]\n"
        "OR, when confident:\n"
        "Thought: <reasoning>\nAction: FINAL[{\"anomaly_type\": \"<zero_billing|"
        "duplicate_charge|usage_spike|cdr_failure|sla_breach>\", \"root_cause\": "
        "\"<2-4 sentences>\", \"recommendation\": \"<1-2 sentences>\"}]"
    )
    transcript = _anomaly_prompt(anomaly)
    docs_seen = 0
    raw_final = None
    for _ in range(max_steps):
        raw = call_llm(system, transcript, trace_name="ablation_react")
        if not raw:
            break
        if "FINAL[" in raw:
            raw_final = raw.split("FINAL[", 1)[1]
            raw_final = raw_final.rsplit("]", 1)[0] if "]" in raw_final else raw_final
            break
        if "SEARCH[" in raw:
            query = raw.split("SEARCH[", 1)[1].split("]", 1)[0][:120]
            docs = _retrieve_docs(query, k=3)
            docs_seen += len(docs)
            obs = "\n".join(d["text"][:400] for d in docs) or "(no results)"
            transcript += f"\n\n{raw}\nObservation: {obs}\n\nContinue."
        else:
            # Model neither searched nor finalised — nudge once, then stop
            transcript += f"\n\n{raw}\n\nRespond with SEARCH[...] or FINAL[...] only."
    report = _parse_report(raw_final, anomaly) if raw_final else {"anomaly_type": "", "root_cause": ""}
    return {
        "anomaly_data": anomaly,
        "rca_report": report,
        "retrieval_count": docs_seen,
        "pipeline_status": "completed" if raw_final else "failed",
        "latency_ms": (time.time() - t0) * 1000,
    }


def _run_rag_only(anomaly: dict) -> dict:
    from src.agents.llm_utils import call_llm
    t0 = time.time()
    query = f"{anomaly.get('anomaly_type')} billing anomaly root cause telecom"
    docs = _retrieve_docs(query)
    context = "\n\n".join(d["text"][:800] for d in docs)
    prompt = _anomaly_prompt(anomaly) + "\n\nRelevant playbook excerpts:\n" + context
    raw = call_llm(_DIRECT_SYSTEM, prompt, trace_name="ablation_rag_only")
    return {
        "anomaly_data": anomaly,
        "rca_report": _parse_report(raw, anomaly),
        "retrieval_count": len(docs),
        "pipeline_status": "completed" if raw else "failed",
        "latency_ms": (time.time() - t0) * 1000,
    }


def _run_single_agent(anomaly: dict) -> dict:
    """One agent that plans its own retrieval query, then reasons + reports."""
    from src.agents.llm_utils import call_llm
    t0 = time.time()
    plan = call_llm(
        "You generate one concise search query (max 15 words) for a telecom RCA "
        "knowledge base. Respond with the query only.",
        _anomaly_prompt(anomaly),
        trace_name="ablation_single_agent_plan",
    )
    query = (plan or f"{anomaly.get('anomaly_type')} billing root cause").strip()
    docs = _retrieve_docs(query)
    context = "\n\n".join(d["text"][:800] for d in docs)
    prompt = (
        _anomaly_prompt(anomaly)
        + "\n\nEvidence you retrieved:\n" + context
        + "\n\nReason step by step internally, then output ONLY the JSON."
    )
    raw = call_llm(_DIRECT_SYSTEM, prompt, trace_name="ablation_single_agent")
    return {
        "anomaly_data": anomaly,
        "rca_report": _parse_report(raw, anomaly),
        "retrieval_count": len(docs),
        "pipeline_status": "completed" if raw else "failed",
        "latency_ms": (time.time() - t0) * 1000,
    }


def _run_multi_agent(anomaly: dict, use_graph: bool) -> dict:
    from src.agents.graph import run_pipeline
    prev = os.environ.get("USE_GRAPH_RAG")
    os.environ["USE_GRAPH_RAG"] = "1" if use_graph else "0"
    try:
        result = run_pipeline(anomaly)
    finally:
        if prev is None:
            os.environ.pop("USE_GRAPH_RAG", None)
        else:
            os.environ["USE_GRAPH_RAG"] = prev
    # Normalise status naming for the evaluator
    if result.get("pipeline_status") in ("reported", "complete", "completed"):
        result["pipeline_status"] = "completed"
    result.setdefault("anomaly_data", anomaly)
    return result


_RUNNERS = {
    "no_rag":           lambda a: _run_no_rag(a),
    "cot_baseline":     lambda a: _run_cot(a),
    "react_baseline":   lambda a: _run_react(a),
    "rag_only":         lambda a: _run_rag_only(a),
    "single_agent_rag": lambda a: _run_single_agent(a),
    "multi_agent_rag":  lambda a: _run_multi_agent(a, use_graph=False),
    "graph_rag":        lambda a: _run_multi_agent(a, use_graph=True),
}


def _scalar_metrics(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if isinstance(v, (int, float))}


def run_config(name: str, anomalies: list, run_judge: bool, blind: bool = True) -> dict:
    from src.evaluation.metrics import evaluate_pipeline_results

    cfg = ABLATION_CONFIGS[name]
    print(f"\n=== {cfg['description']} ({len(anomalies)} anomalies, "
          f"{'blind' if blind else 'ORACLE-LEAK'} types) ===")
    runner = _RUNNERS[name]
    results = []
    for i, anomaly in enumerate(anomalies, 1):
        print(f"  [{i}/{len(anomalies)}] {anomaly.get('account_id')} "
              f"({anomaly.get('anomaly_type')})", flush=True)
        pipeline_input = _blind_copy(anomaly) if blind else anomaly
        try:
            result = runner(pipeline_input)
        except Exception as exc:
            print(f"    FAILED: {exc}")
            result = {
                "anomaly_data": pipeline_input,
                "rca_report": {"anomaly_type": "", "root_cause": ""},
                "pipeline_status": "failed",
                "latency_ms": 0.0,
                "retrieval_count": 0,
                "error_message": str(exc),
            }
        # Restore ground-truth keys for scoring; keep the blind input type
        # visible for transparency.
        ad = result.setdefault("anomaly_data", {})
        ad["input_type"] = pipeline_input.get("anomaly_type", "")
        ad["anomaly_type"] = anomaly.get("anomaly_type", "")
        ad["ground_truth_id"] = anomaly.get("ground_truth_id")
        results.append(result)

    metrics = evaluate_pipeline_results(results, run_judge=run_judge)
    metrics["config"] = name

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{name}_results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    (RESULTS_DIR / f"{name}_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8")

    # MLflow logging (best-effort; offline-safe)
    try:
        from src.mlflow_tracking import log_evaluation_run
        log_evaluation_run(_scalar_metrics(metrics), config_name=name)
    except Exception as exc:
        print(f"  [mlflow] skipped: {exc}")

    # Headline metrics first (LLM-Judge + RAGAS-style faithfulness, per
    # evaluation design); ROUGE-L last as the lexical baseline only.
    parts = []
    if metrics.get("llm_judge_score"):
        parts.append(f"LLM-Judge: {metrics['llm_judge_score']:.3f}")
    if metrics.get("faithfulness_mean"):
        parts.append(f"faithfulness: {metrics['faithfulness_mean']:.3f}")
    parts.append(f"type acc: {metrics.get('anomaly_type_accuracy', 0):.2%}")
    parts.append(f"avg latency: {metrics.get('avg_latency_ms', 0):.0f} ms")
    parts.append(f"ROUGE-L (lexical baseline): {metrics.get('rouge_l_f1', 0):.3f}")
    print("  " + " | ".join(parts))
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Run the 7-config ablation study "
                                                 "(A/A2/A3 baselines + B/C/D/E).")
    parser.add_argument("--quick", action="store_true",
                        help="3 anomalies per type (15 total) for a fast pass")
    parser.add_argument("--full", action="store_true",
                        help="All 12 anomalies per type (60 total)")
    parser.add_argument("--n", type=int, default=None,
                        help="Cap total anomalies (overrides --quick/--full)")
    parser.add_argument("--configs", type=str, default=",".join(ABLATION_CONFIGS),
                        help="Comma-separated config names "
                             f"(default: {','.join(ABLATION_CONFIGS)})")
    parser.add_argument("--judge", dest="judge", action="store_true", default=True,
                        help="Run LLM-as-Judge + RAGAS-style faithfulness scoring "
                             "(DEFAULT ON — primary quality metrics per evaluation design)")
    parser.add_argument("--no-judge", dest="judge", action="store_false",
                        help="Skip judge/faithfulness scoring (lexical metrics only; "
                             "NOT sufficient for headline quality claims)")
    parser.add_argument("--leak-types", action="store_true",
                        help="LEGACY: pass ground-truth anomaly_type to configs "
                             "(oracle labels; inflates type accuracy). Default is "
                             "blind detector-estimated types.")
    args = parser.parse_args()

    names = [c.strip() for c in args.configs.split(",") if c.strip()]
    unknown = [c for c in names if c not in ABLATION_CONFIGS]
    if unknown:
        parser.error(f"Unknown config(s): {unknown}. Valid: {list(ABLATION_CONFIGS)}")

    limit = 3 if args.quick and not args.full else 12
    anomalies = anomalies_from_ground_truth(limit_per_type=limit)
    if args.n:
        anomalies = anomalies[: args.n]

    print(f"Ablation study: {len(names)} configs x {len(anomalies)} anomalies "
          f"(judge={'on' if args.judge else 'off'})")

    summary = {}
    t0 = time.time()
    for name in names:
        summary[name] = _scalar_metrics(
            run_config(name, anomalies, args.judge, blind=not args.leak_types))

    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # Statistical comparison of headline config vs baselines (best-effort)
    try:
        from src.evaluation.stats import compare_configs  # noqa: F401
        print("\nPer-item scores saved in *_metrics.json -> use "
              "src/evaluation/stats.py (bootstrap CI, Wilcoxon) for significance.")
    except ImportError:
        pass

    print(f"\nDone in {(time.time() - t0) / 60:.1f} min. "
          f"Results in {RESULTS_DIR}")
    print("Export for the dashboard: python scripts/export_mlflow_results.py")


if __name__ == "__main__":
    main()
