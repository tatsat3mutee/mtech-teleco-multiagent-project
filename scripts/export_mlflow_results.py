"""
Export MLflow experiment runs to JSON for cloud display (no MLflow server needed).
Reads from local mlruns/ directory and writes data/eval/mlflow_results.json.

Usage:
    python scripts/export_mlflow_results.py
    python scripts/export_mlflow_results.py --experiment-name "ablation_study"
    python scripts/export_mlflow_results.py --output data/eval/mlflow_results.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def export_runs(experiment_name: str = None, output_path: Path = None) -> dict:
    try:
        import mlflow
    except ImportError:
        print("mlflow not installed — run: pip install mlflow")
        sys.exit(1)

    if output_path is None:
        output_path = Path(__file__).parent.parent / "data/eval/mlflow_results.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = mlflow.tracking.MlflowClient()

    # Find experiments
    experiments = client.search_experiments()
    if experiment_name:
        experiments = [e for e in experiments if e.name == experiment_name]

    if not experiments:
        print(f"No experiments found{' matching ' + experiment_name if experiment_name else ''}.")
        result = {"experiments": [], "total_runs": 0}
        output_path.write_text(json.dumps(result, indent=2))
        return result

    all_runs = []
    for exp in experiments:
        runs = client.search_runs(
            experiment_ids=[exp.experiment_id],
            order_by=["start_time DESC"],
            max_results=200,
        )
        for run in runs:
            all_runs.append({
                "run_id": run.info.run_id,
                "experiment_name": exp.name,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                "params": dict(run.data.params),
                "metrics": dict(run.data.metrics),
                "tags": {k: v for k, v in run.data.tags.items()
                         if not k.startswith("mlflow.")},
            })

    # Derive ablation summary if ablation configs present
    ablation_configs = {}
    for run in all_runs:
        cfg = run["params"].get("config_name") or run["tags"].get("config_name")
        if cfg and cfg not in ablation_configs:
            ablation_configs[cfg] = {
                "config_name": cfg,
                "description": run["params"].get("config_description", cfg),
                "metrics": {
                    "rouge_l_f1":    run["metrics"].get("rouge_l_f1", 0.0),
                    "bert_score_f1": run["metrics"].get("bert_score_f1", 0.0),
                    "ragas_score":   run["metrics"].get("ragas_score", 0.0),
                    "llm_judge":     run["metrics"].get("llm_judge_score", 0.0),
                    "precision":     run["metrics"].get("detection_precision", 0.0),
                    "recall":        run["metrics"].get("detection_recall", 0.0),
                    "f1":            run["metrics"].get("detection_f1", 0.0),
                    "auc_roc":       run["metrics"].get("auc_roc", 0.0),
                    "avg_latency_ms": run["metrics"].get("avg_latency_ms", 0.0),
                },
            }

    result = {
        "exported_at": str(Path(output_path).stat().st_mtime if output_path.exists() else "now"),
        "total_runs": len(all_runs),
        "experiments": [
            {
                "name": exp.name,
                "experiment_id": exp.experiment_id,
                "run_count": sum(1 for r in all_runs if r["experiment_name"] == exp.name),
            }
            for exp in experiments
        ],
        "ablation_configs": ablation_configs,
        "runs": all_runs,
    }

    output_path.write_text(json.dumps(result, indent=2))
    print(f"Exported {len(all_runs)} runs from {len(experiments)} experiments → {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Export MLflow runs to JSON")
    parser.add_argument("--experiment-name", default=None,
                        help="Filter to a specific experiment name")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: data/eval/mlflow_results.json)")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    export_runs(experiment_name=args.experiment_name, output_path=output)


if __name__ == "__main__":
    main()
