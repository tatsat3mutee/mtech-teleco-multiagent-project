"""
CLI interface for the Multi-Agent RAG RCA System.
Usage: python -m src.cli --input anomaly_record.json
       python -m src.cli --csv data/processed/anomalies_labeled.csv --limit 10
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PROCESSED_DATA_DIR, RAW_DATA_DIR


def setup_system():
    """Initialize all system components."""
    print("=" * 60)
    print("  Telecom Billing RCA — Multi-Agent System")
    print("=" * 60)

    # Step 1: Ensure datasets exist
    print("\n[1/4] Checking datasets...")
    ibm_path = RAW_DATA_DIR / "ibm_telco_churn.csv"
    if not ibm_path.exists():
        print("  Generating datasets...")
        from scripts.download_datasets import download_ibm_telco, download_maven_telecom
        download_ibm_telco()
        download_maven_telecom()
    else:
        print("  Datasets found.")

    # Step 2: Ensure labeled dataset exists
    print("\n[2/4] Checking labeled anomaly dataset...")
    labeled_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
    if not labeled_path.exists():
        print("  Injecting anomalies...")
        from src.data.loader import load_ibm_telco
        from src.data.anomaly_injector import create_labeled_dataset
        df = load_ibm_telco()
        create_labeled_dataset(df)
    else:
        print("  Labeled dataset found.")

    # Step 3: Ensure knowledge base is built
    print("\n[3/4] Checking knowledge base...")
    from src.rag.knowledge_base import build_knowledge_base
    kb = build_knowledge_base()
    print(f"  Knowledge base: {kb.count} documents indexed.")

    # Step 4: Train anomaly detector
    print("\n[4/4] Checking anomaly detector...")
    from config import MODELS_DIR
    model_path = MODELS_DIR / "isolation_forest_model.joblib"
    if not model_path.exists():
        print("  Training detector...")
        import pandas as pd
        from src.detection.detector import train_and_evaluate
        df = pd.read_csv(PROCESSED_DATA_DIR / "anomalies_labeled.csv")
        train_and_evaluate(df, method="isolation_forest")
    else:
        print("  Trained model found.")

    print("\n" + "=" * 60)
    print("  System ready!")
    print("=" * 60)


def run_single_anomaly(anomaly_json: str):
    """Run the pipeline on a single anomaly record."""
    from src.agents.graph import run_pipeline

    record = json.loads(anomaly_json)
    result = run_pipeline(record)

    print(f"\nPipeline Status: {result.get('pipeline_status')}")
    print(f"Latency: {result.get('latency_ms', 0):.0f}ms")

    rca = result.get("rca_report", {})
    if rca:
        print("\n" + "=" * 60)
        print("  ROOT CAUSE ANALYSIS REPORT")
        print("=" * 60)
        print(json.dumps(rca, indent=2))
    return result


def run_from_csv(csv_path: str, limit: int = 5):
    """Detect anomalies from CSV and run RCA pipeline."""
    import pandas as pd
    from src.detection.detector import BillingAnomalyDetector
    from src.agents.graph import run_pipeline

    df = pd.read_csv(csv_path)
    print(f"\nLoaded {len(df)} records from {csv_path}")

    # Detect anomalies
    detector = BillingAnomalyDetector(method="isolation_forest")
    try:
        detector.load()
    except FileNotFoundError:
        print("No trained model found. Training...")
        detector.fit(df)
        detector.save()

    anomalies = detector.get_anomalous_records(df)
    print(f"Detected {len(anomalies)} anomalies")

    if limit:
        anomalies = anomalies.head(limit)
        print(f"Processing first {limit} anomalies...\n")

    results = []
    for idx, row in anomalies.iterrows():
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

        print(f"\n{'─' * 50}")
        print(f"Anomaly: {record['account_id']} | Type: {record['anomaly_type']}")
        print(f"{'─' * 50}")

        result = run_pipeline(record)
        rca = result.get("rca_report", {})

        if rca:
            print(f"  Severity: {rca.get('severity', 'N/A')}")
            print(f"  Root Cause: {rca.get('root_cause', 'N/A')[:100]}...")
            print(f"  Latency: {result.get('latency_ms', 0):.0f}ms")

        results.append(result)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  BATCH SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total anomalies processed: {len(results)}")
    completed = sum(1 for r in results if r.get("pipeline_status") == "completed")
    print(f"  Successfully analyzed: {completed}")
    avg_latency = sum(r.get("latency_ms", 0) for r in results) / max(len(results), 1)
    print(f"  Average latency: {avg_latency:.0f}ms")

    return results


def main():
    parser = argparse.ArgumentParser(description="Telecom Billing RCA System")
    parser.add_argument("--setup", action="store_true", help="Initialize system (download data, build KB, train model)")
    parser.add_argument("--input", type=str, help="JSON string of anomaly record")
    parser.add_argument("--csv", type=str, help="Path to CSV file with billing data")
    parser.add_argument("--limit", type=int, default=5, help="Max anomalies to process from CSV")

    args = parser.parse_args()

    if args.setup:
        setup_system()
    elif args.input:
        run_single_anomaly(args.input)
    elif args.csv:
        run_from_csv(args.csv, limit=args.limit)
    else:
        # Default: setup + run on labeled dataset
        setup_system()
        labeled_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
        if labeled_path.exists():
            run_from_csv(str(labeled_path), limit=5)


if __name__ == "__main__":
    main()
