"""
MLflow experiment tracking integration.
Logs anomaly detection runs, agent pipeline runs, and evaluation metrics.
"""
import json
import time
from typing import List, Dict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME, LLM_MODEL


def setup_mlflow():
    """Initialize MLflow tracking."""
    import mlflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    return mlflow


def log_detection_run(method: str, metrics: dict, params: dict = None):
    """Log an anomaly detection training/evaluation run."""
    mlflow = setup_mlflow()
    with mlflow.start_run(run_name=f"detection_{method}"):
        mlflow.log_param("method", method)
        if params:
            mlflow.log_params(params)

        mlflow.log_metric("precision", metrics.get("precision", 0))
        mlflow.log_metric("recall", metrics.get("recall", 0))
        mlflow.log_metric("f1_score", metrics.get("f1_score", 0))
        if "roc_auc" in metrics:
            mlflow.log_metric("roc_auc", metrics["roc_auc"])

        # Log confusion matrix as artifact
        cm = metrics.get("confusion_matrix", [])
        if cm:
            mlflow.log_text(json.dumps(cm, indent=2), "confusion_matrix.json")


def log_pipeline_run(anomaly_record: dict, result: dict):
    """Log a single agent pipeline run."""
    mlflow = setup_mlflow()
    with mlflow.start_run(run_name=f"rca_{anomaly_record.get('account_id', 'unknown')}"):
        # Parameters
        mlflow.log_param("account_id", anomaly_record.get("account_id", "unknown"))
        mlflow.log_param("anomaly_type", anomaly_record.get("anomaly_type", "unknown"))
        mlflow.log_param("model_name", LLM_MODEL)

        # Metrics
        mlflow.log_metric("latency_ms", result.get("latency_ms", 0))
        mlflow.log_metric("retrieval_count", result.get("retrieval_count", 0))

        rca = result.get("rca_report", {})
        if rca:
            mlflow.log_metric("confidence_score", rca.get("confidence_score", 0))

        # Status
        mlflow.log_param("pipeline_status", result.get("pipeline_status", "unknown"))

        # Artifacts
        if rca:
            mlflow.log_text(json.dumps(rca, indent=2), "rca_report.json")

        if result.get("hypothesis"):
            mlflow.log_text(result["hypothesis"], "hypothesis.txt")

        if result.get("retrieval_query"):
            mlflow.log_text(result["retrieval_query"], "retrieval_query.txt")


def log_evaluation_run(eval_metrics: dict, config_name: str = "multi_agent_rag"):
    """Log evaluation metrics for a configuration."""
    mlflow = setup_mlflow()
    with mlflow.start_run(run_name=f"eval_{config_name}"):
        mlflow.log_param("configuration", config_name)
        mlflow.log_param("model_name", LLM_MODEL)

        for key, value in eval_metrics.items():
            if isinstance(value, (int, float)):
                mlflow.log_metric(key, value)
            elif isinstance(value, str):
                mlflow.log_param(key, value)

        mlflow.log_text(json.dumps(eval_metrics, indent=2, default=str), "eval_metrics.json")


def log_batch_pipeline(results: List[dict]):
    """Log a batch of pipeline results."""
    mlflow = setup_mlflow()
    with mlflow.start_run(run_name="batch_rca"):
        mlflow.log_param("batch_size", len(results))
        mlflow.log_param("model_name", LLM_MODEL)

        # Aggregate metrics
        latencies = [r.get("latency_ms", 0) for r in results]
        completed = sum(1 for r in results if r.get("pipeline_status") == "completed")

        mlflow.log_metric("avg_latency_ms", sum(latencies) / max(len(latencies), 1))
        mlflow.log_metric("max_latency_ms", max(latencies) if latencies else 0)
        mlflow.log_metric("success_rate", completed / max(len(results), 1))
        mlflow.log_metric("total_processed", len(results))

        # Save all results as artifact
        summary = []
        for r in results:
            rca = r.get("rca_report", {})
            summary.append({
                "account_id": r.get("anomaly_data", {}).get("account_id", "N/A"),
                "anomaly_type": r.get("anomaly_data", {}).get("anomaly_type", "N/A"),
                "status": r.get("pipeline_status", "N/A"),
                "latency_ms": r.get("latency_ms", 0),
                "severity": rca.get("severity", "N/A"),
                "root_cause": rca.get("root_cause", "N/A")[:200],
            })

        mlflow.log_text(json.dumps(summary, indent=2), "batch_summary.json")
