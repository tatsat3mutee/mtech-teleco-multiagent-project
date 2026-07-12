"""
Main pipeline runner — sets up everything and runs the end-to-end system.
Usage:
    python run_pipeline.py                  # default: IBM Telco + Maven
    python run_pipeline.py --dataset sebd   # enterprise billing (SEBD)
"""
import sys
import os
import json
import time
import argparse
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR,
    ISOLATION_FOREST_PARAMS, RANDOM_SEED,
)


def step_1_generate_datasets():
    """Generate synthetic telecom datasets."""
    print("\n" + "=" * 60)
    print("  STEP 1: Generate Datasets")
    print("=" * 60)

    from scripts.download_datasets import download_ibm_telco, download_maven_telecom
    download_ibm_telco()
    download_maven_telecom()


def step_1_load_sebd():
    """Load the enterprise billing dataset (SEBD)."""
    print("\n" + "=" * 60)
    print("  STEP 1: Load SEBD (Enterprise Billing)")
    print("=" * 60)

    from src.data.loader import load_sebd
    df = load_sebd()
    print(f"  Loaded {len(df):,} records | Anomalies: {df['is_anomaly'].sum():,} ({df['is_anomaly'].mean()*100:.1f}%)")
    return df


def step_2_inject_anomalies():
    """Inject synthetic anomalies into the dataset."""
    print("\n" + "=" * 60)
    print("  STEP 2: Inject Anomalies")
    print("=" * 60)

    from src.data.anomaly_injector import create_labeled_dataset

    # create_labeled_dataset() auto-loads raw IBM Telco (schema with MonthlyCharges
    # /TotalCharges) which the anomaly injector requires. Passing load_combined()
    # here breaks because it lowercases columns to monthly_charges/total_charges.
    labeled_df = create_labeled_dataset()
    return labeled_df


def step_3_train_detector(df: pd.DataFrame):
    """Train and evaluate IsolationForest anomaly detector."""
    print("\n" + "=" * 60)
    print("  STEP 3: Train Anomaly Detector")
    print("=" * 60)

    from src.detection.detector import train_and_evaluate

    # IsolationForest only — DBSCAN removed in v2.0 (see detector.py)
    if_result = train_and_evaluate(df, method="isolation_forest")

    # Log to MLflow
    try:
        from src.mlflow_tracking import log_detection_run
        log_detection_run("isolation_forest", if_result["metrics"], ISOLATION_FOREST_PARAMS)
        print("\nResults logged to MLflow.")
    except Exception as e:
        print(f"\nMLflow logging skipped: {e}")

    return if_result["detector"]


def step_4_build_knowledge_base():
    """Build the RAG knowledge base."""
    print("\n" + "=" * 60)
    print("  STEP 4: Build Knowledge Base")
    print("=" * 60)

    from src.rag.knowledge_base import build_knowledge_base
    kb = build_knowledge_base(force_rebuild=True)
    return kb


def step_5_run_agent_pipeline(detector, df: pd.DataFrame, limit: int = 10, dataset: str = "combined"):
    """Run the multi-agent RCA pipeline on detected anomalies."""
    print("\n" + "=" * 60)
    print("  STEP 5: Run Multi-Agent RCA Pipeline")
    print("=" * 60)

    from src.agents.graph import run_pipeline

    # Get anomalous records
    anomalies = detector.get_anomalous_records(df)
    anomalies = anomalies.head(limit)
    print(f"\nProcessing {len(anomalies)} anomalies...\n")

    results = []
    for idx, row in anomalies.iterrows():
        if dataset == "sebd":
            record = {
                "account_id": str(row.get("customer_id", f"ROW-{idx}")),
                "anomaly_type": str(row.get("anomaly_type", row.get("estimated_type", "unknown"))),
                "confidence": float(row.get("anomaly_confidence", 0.5)),
                "monthly_charges": float(row.get("monthly_charges", 0)),
                "total_charges": float(row.get("total_charges", 0)) if pd.notna(row.get("total_charges")) else 0.0,
                "tenure": int(row.get("tenure", 0)),
                "features": {
                    "fault_code": str(row.get("fault_code", "")),
                    "segment": str(row.get("segment", "")),
                    "proc_status": str(row.get("proc_status", "")),
                    "unit_count": str(row.get("unit_count", "")),
                    "billing_rate": str(row.get("billing_rate", "")),
                    "account_active": str(row.get("account_active", "")),
                    "contract": str(row.get("contract", "")),
                },
            }
        else:
            record = {
                "account_id": str(row.get("customerID", f"ROW-{idx}")),
                "anomaly_type": str(row.get("anomaly_type", row.get("estimated_type", "unknown"))),
                "confidence": float(row.get("anomaly_confidence", 0.5)),
                "monthly_charges": float(row.get("MonthlyCharges", 0)),
                "total_charges": float(row.get("TotalCharges", 0)) if pd.notna(row.get("TotalCharges")) else 0.0,
                "tenure": int(row.get("tenure", 0)),
                "features": {
                    col: str(row[col]) for col in ["Contract", "InternetService", "PaymentMethod"]
                    if col in row.index
                },
            }

        print(f"Processing: {record['account_id']} ({record['anomaly_type']})...", end=" ")

        result = run_pipeline(record)
        rca = result.get("rca_report", {})

        status = "OK" if result.get("pipeline_status") == "completed" else "FAIL"
        print(f"{status} ({result.get('latency_ms', 0):.0f}ms)")

        results.append(result)

        # Free-tier pacing: each anomaly consumes ~3-5K tokens across 4-6 LLM calls,
        # while Groq allows 8K TPM and OpenRouter free models share upstream capacity.
        # A short pause lets the per-minute token window recover, so the router paces
        # instead of cascading 429s. Override with RCA_BATCH_DELAY_S=0 on paid tiers.
        _delay = float(os.environ.get("RCA_BATCH_DELAY_S", "20"))
        if _delay > 0 and idx != anomalies.index[-1]:
            time.sleep(_delay)

    # Log batch to MLflow
    try:
        from src.mlflow_tracking import log_batch_pipeline
        log_batch_pipeline(results)
    except Exception:
        pass

    return results


def step_6_evaluate(results):
    """Evaluate pipeline results."""
    print("\n" + "=" * 60)
    print("  STEP 6: Evaluation")
    print("=" * 60)

    from src.evaluation.metrics import evaluate_pipeline_results, print_evaluation_report

    metrics = evaluate_pipeline_results(results)
    print_evaluation_report(metrics)

    # Log to MLflow
    try:
        from src.mlflow_tracking import log_evaluation_run
        log_evaluation_run(metrics, "multi_agent_rag")
    except Exception:
        pass

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Telecom Billing RCA Pipeline")
    parser.add_argument(
        "--dataset", choices=["combined", "sebd"], default="combined",
        help="Dataset to use: 'combined' (IBM+Maven, default) or 'sebd' (enterprise billing)"
    )
    parser.add_argument("--limit", type=int, default=10, help="Max anomalies to process")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  TELECOM BILLING RCA - FULL PIPELINE")
    print(f"  Multi-Agent RAG System | Dataset: {args.dataset.upper()}")
    print("=" * 60)

    start = time.time()

    if args.dataset == "sebd":
        # SEBD path: load pre-labeled enterprise billing data
        labeled_df = step_1_load_sebd()
    else:
        # Default path: download public datasets + inject anomalies
        step_1_generate_datasets()
        labeled_df = step_2_inject_anomalies()

    # Step 3: Train Detector
    detector = step_3_train_detector(labeled_df)

    # Step 4: Knowledge Base
    kb = step_4_build_knowledge_base()

    # Step 5: Agent Pipeline
    results = step_5_run_agent_pipeline(detector, labeled_df, limit=args.limit, dataset=args.dataset)

    # Step 6: Evaluation
    metrics = step_6_evaluate(results)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"  PIPELINE COMPLETE - Total time: {elapsed:.1f}s")
    print(f"{'=' * 60}")

    # Save summary
    summary = {
        "total_time_seconds": round(elapsed, 1),
        "records_processed": len(results),
        "success_rate": metrics.get("successful", 0) / max(metrics.get("total_processed", 1), 1),
        "avg_latency_ms": metrics.get("avg_latency_ms", 0),
        "anomaly_type_accuracy": metrics.get("anomaly_type_accuracy", 0),
    }

    summary_path = Path("pipeline_results.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to {summary_path}")

    return results, metrics


if __name__ == "__main__":
    main()
