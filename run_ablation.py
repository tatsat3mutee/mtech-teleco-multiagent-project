"""
Ablation study harness — runs configs A-E from config.ABLATION_CONFIGS
over ground-truth-derived anomalies and evaluates each against the
60-item reference RCA corpus.

Configs:
  A  no_rag           Direct LLM, no retrieval, no agents
  B  rag_only         Vector retrieval stuffed into a single LLM call
  C  single_agent_rag One agent: retrieve + reason + report in one call
  D  multi_agent_rag  Full 4-agent LangGraph pipeline (proposed system)
  E  graph_rag        Full pipeline + GraphRAG retrieval (USE_GRAPH_RAG=1)

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
import json
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


def _anomaly_prompt(anomaly: dict) -> str:
    return (
        f"Account {anomaly.get('account_id')} flagged as {anomaly.get('anomaly_type')} "
        f"(confidence {anomaly.get('confidence', 0):.2f}). "
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
    "rag_only":         lambda a: _run_rag_only(a),
    "single_agent_rag": lambda a: _run_single_agent(a),
    "multi_agent_rag":  lambda a: _run_multi_agent(a, use_graph=False),
    "graph_rag":        lambda a: _run_multi_agent(a, use_graph=True),
}


def _scalar_metrics(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if isinstance(v, (int, float))}


def run_config(name: str, anomalies: list, run_judge: bool) -> dict:
    from src.evaluation.metrics import evaluate_pipeline_results

    cfg = ABLATION_CONFIGS[name]
    print(f"\n=== {cfg['description']} ({len(anomalies)} anomalies) ===")
    runner = _RUNNERS[name]
    results = []
    for i, anomaly in enumerate(anomalies, 1):
        print(f"  [{i}/{len(anomalies)}] {anomaly.get('account_id')} "
              f"({anomaly.get('anomaly_type')})", flush=True)
        try:
            results.append(runner(anomaly))
        except Exception as exc:
            print(f"    FAILED: {exc}")
            results.append({
                "anomaly_data": anomaly,
                "rca_report": {"anomaly_type": "", "root_cause": ""},
                "pipeline_status": "failed",
                "latency_ms": 0.0,
                "retrieval_count": 0,
                "error_message": str(exc),
            })

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

    print(f"  ROUGE-L F1: {metrics.get('rouge_l_f1', 0):.3f} | "
          f"type acc: {metrics.get('anomaly_type_accuracy', 0):.2%} | "
          f"avg latency: {metrics.get('avg_latency_ms', 0):.0f} ms")
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Run the 5-config ablation study.")
    parser.add_argument("--quick", action="store_true",
                        help="3 anomalies per type (15 total) for a fast pass")
    parser.add_argument("--full", action="store_true",
                        help="All 12 anomalies per type (60 total)")
    parser.add_argument("--n", type=int, default=None,
                        help="Cap total anomalies (overrides --quick/--full)")
    parser.add_argument("--configs", type=str, default=",".join(ABLATION_CONFIGS),
                        help="Comma-separated config names "
                             f"(default: {','.join(ABLATION_CONFIGS)})")
    parser.add_argument("--judge", action="store_true",
                        help="Run LLM-as-Judge + faithfulness scoring (extra API calls)")
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
        summary[name] = _scalar_metrics(run_config(name, anomalies, args.judge))

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
