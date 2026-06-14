"""
Generate pre-computed RCA results for demo mode (2 per anomaly type = 10 total).
Saves to data/demo/sample_rca_results.json so the app works without API keys.

Usage:
    python scripts/generate_demo_results.py
    python scripts/generate_demo_results.py --output data/demo/sample_rca_results.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_ANOMALIES = [
    {"account_id": "DEMO-7590-VHVEG", "anomaly_type": "zero_billing",       "confidence": 0.95, "monthly_charges": 0.0,   "total_charges": 1889.5, "tenure": 29, "features": {"Contract": "Two year",     "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-5575-GNVDE", "anomaly_type": "zero_billing",       "confidence": 0.92, "monthly_charges": 0.0,   "total_charges": 2570.1, "tenure": 39, "features": {"Contract": "One year",      "InternetService": "DSL"}},
    {"account_id": "DEMO-3668-QPYBK", "anomaly_type": "duplicate_charge",   "confidence": 0.88, "monthly_charges": 159.0, "total_charges": 4316.0, "tenure": 53, "features": {"Contract": "Two year",     "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-9237-HQITU", "anomaly_type": "duplicate_charge",   "confidence": 0.85, "monthly_charges": 147.5, "total_charges": 3982.5, "tenure": 47, "features": {"Contract": "One year",      "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-1452-KIOVK", "anomaly_type": "usage_spike",        "confidence": 0.82, "monthly_charges": 890.5, "total_charges": 6120.3, "tenure": 68, "features": {"Contract": "Two year",     "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-7795-CFOCW", "anomaly_type": "usage_spike",        "confidence": 0.79, "monthly_charges": 765.2, "total_charges": 5430.7, "tenure": 71, "features": {"Contract": "Two year",     "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-5129-JLPIS", "anomaly_type": "cdr_failure",        "confidence": 0.91, "monthly_charges": 0.0,   "total_charges": 3450.0, "tenure": 46, "features": {"Contract": "Month-to-month", "InternetService": "Fiber optic", "StreamingTV": "Yes"}},
    {"account_id": "DEMO-2816-TBYJR", "anomaly_type": "cdr_failure",        "confidence": 0.87, "monthly_charges": 0.0,   "total_charges": 2890.4, "tenure": 38, "features": {"Contract": "One year",      "InternetService": "DSL", "StreamingMovies": "Yes"}},
    {"account_id": "DEMO-4367-NUYAO", "anomaly_type": "sla_breach",         "confidence": 0.83, "monthly_charges": 185.5, "total_charges": 8450.2, "tenure": 60, "features": {"Contract": "Two year",     "InternetService": "Fiber optic"}},
    {"account_id": "DEMO-3115-CZMZD", "anomaly_type": "sla_breach",         "confidence": 0.80, "monthly_charges": 172.3, "total_charges": 7890.1, "tenure": 55, "features": {"Contract": "One year",      "InternetService": "Fiber optic"}},
]

DEMO_RCA_TEMPLATES = {
    "zero_billing": {
        "root_cause": "Rating engine configuration error: MonthlyCharges billed as $0.00 despite active Fiber optic service (tenure {tenure} months). Rate card for this customer's plan returned null rate on the billing cycle boundary.",
        "summary": "Customer account shows zero MonthlyCharges despite being an established Fiber optic subscriber. IsolationForest confidence {confidence:.0%}. Primary hypothesis: rating engine failed to apply the standard rate card at cycle boundary. Recommended action: audit rate configuration and reprocess the current billing cycle.",
        "severity": "HIGH",
        "supporting_evidence": [
            "IBM Telco median MonthlyCharges for Fiber optic: $89.30 — zero charges indicate 100% charge leakage",
            "TotalCharges > 0 confirms prior billing history; anomaly limited to current cycle",
            "rule_based_prefilter: MonthlyCharges=0 AND tenure>0 → 100% precision flag",
        ],
        "recommended_actions": [
            "Audit rating engine configuration for this account's plan code",
            "Reprocess billing cycle with corrected rate card",
            "Verify billing pipeline timeout thresholds for cycle-boundary processing",
        ],
    },
    "duplicate_charge": {
        "root_cause": "Billing retry idempotency failure: MonthlyCharges of ${monthly_charges:.2f} is approximately 2× the expected amount (${expected:.2f}). A retry in the payment processing pipeline applied charges twice without checking for prior successful execution.",
        "summary": "Customer account shows MonthlyCharges ≈ 2× historical average. TotalCharges/tenure ratio confirms the anomaly is isolated to this cycle. IsolationForest confidence {confidence:.0%}. Primary hypothesis: payment retry without idempotency key applied charges twice.",
        "severity": "HIGH",
        "supporting_evidence": [
            "TotalCharges/tenure ratio shows sudden spike in current cycle vs. stable prior history",
            "Two-year contract customer — stable billing history makes double-charge statistically anomalous",
            "Duplicate charge pattern matches idempotency failure signature in billing retry logs",
        ],
        "recommended_actions": [
            "Reverse the duplicate charge component from the current billing cycle",
            "Audit payment retry logic — add idempotency key validation",
            "Issue credit to customer for the overcharged amount",
        ],
    },
    "usage_spike": {
        "root_cause": "Rate card misconfiguration: MonthlyCharges of ${monthly_charges:.2f} exceeds P95 threshold (${p95:.2f}) by {multiplier:.1f}×. Fiber optic internet service rated at international premium rate instead of standard domestic rate for this established account.",
        "summary": "Long-tenure Fiber optic customer (tenure {tenure} months) shows MonthlyCharges 5–10× above historical baseline. IsolationForest confidence {confidence:.0%}. Primary hypothesis: incorrect rate card applied — streaming or internet usage categorised as premium international tier.",
        "severity": "MEDIUM",
        "supporting_evidence": [
            "IBM Telco P95 for Fiber optic Two-year contract: $107.40 — current charges exceed this by >1.5×",
            "tenure > 18 months: established account with stable prior charge history",
            "Usage spike pattern consistent with rate card misapplication, not genuine usage increase",
        ],
        "recommended_actions": [
            "Identify which rate rule applied the premium rate for this account",
            "Revert to standard domestic rate card",
            "Reprocess billing cycle and issue credit for the difference",
        ],
    },
    "cdr_failure": {
        "root_cause": "Billing record ingestion pipeline failure: MonthlyCharges = NaN for active streaming bundle subscriber (tenure {tenure} months). Pipeline timeout during multi-component bundle rating left charge record incomplete.",
        "summary": "Streaming service customer (StreamingTV or StreamingMovies active) shows null MonthlyCharges. IsolationForest confidence {confidence:.0%}. SWARM routing: graph_first — billing system → ingestion pipeline → bundle rating engine is a multi-hop causal chain. Primary hypothesis: pipeline timeout on multi-component bundle.",
        "severity": "HIGH",
        "supporting_evidence": [
            "StreamingTV/StreamingMovies active: multi-component billing records are more vulnerable to pipeline timeouts",
            "TotalCharges > 0 and tenure > 0 confirm active account with prior complete billing history",
            "Billing record failure signature: NaN MonthlyCharges with active streaming services",
        ],
        "recommended_actions": [
            "Check billing pipeline execution logs for timeout events on the affected billing cycle",
            "Reprocess billing records for all streaming bundle accounts in the affected batch",
            "Increase pipeline timeout threshold for multi-component bundle accounts",
        ],
    },
    "sla_breach": {
        "root_cause": "Contract rate cap not applied: MonthlyCharges of ${monthly_charges:.2f} exceeds the P95×1.5 breach threshold (${threshold:.2f}) for a Two-year contract customer. Rate configuration was not updated at contract renewal, allowing uncapped charges.",
        "summary": "Two-year contract customer (tenure {tenure} months) billed above contractual cap. IsolationForest confidence {confidence:.0%}. SWARM routing: vector_first — pattern matched against contract rate configuration playbook. Primary hypothesis: rate plan not reflected in billing configuration at contract renewal.",
        "severity": "HIGH",
        "supporting_evidence": [
            "Contract = 'Two year' or 'One year': contractual billing cap enforcement required",
            "MonthlyCharges > P95×1.5 = $161.10 threshold for Fiber optic Two-year contract cohort",
            "Overbilled contract customers churn at 3.2× baseline rate — immediate remediation required",
        ],
        "recommended_actions": [
            "Pull contract terms and verify contractual rate ceiling in CRM",
            "Audit billing configuration for this account's plan code — compare against contract",
            "Apply correct contract rate retroactively from divergence date and issue refund",
        ],
    },
}


def _make_rca(anomaly: dict) -> dict:
    atype = anomaly["anomaly_type"]
    template = DEMO_RCA_TEMPLATES.get(atype, DEMO_RCA_TEMPLATES["zero_billing"])
    fmt_args = {
        "tenure": anomaly["tenure"],
        "confidence": anomaly["confidence"],
        "monthly_charges": anomaly["monthly_charges"],
        "expected": anomaly["monthly_charges"] / 2,
        "p95": 107.40,
        "threshold": 107.40 * 1.5,
        "multiplier": anomaly["monthly_charges"] / max(anomaly["monthly_charges"] / 8, 1),
    }
    return {
        "anomaly_id": anomaly["account_id"],
        "anomaly_type": atype,
        "severity": template["severity"],
        "confidence_score": anomaly["confidence"],
        "root_cause": template["root_cause"].format(**fmt_args),
        "summary": template["summary"].format(**fmt_args),
        "supporting_evidence": template["supporting_evidence"],
        "recommended_actions": template["recommended_actions"],
    }


def generate(output_path: Path = None) -> None:
    if output_path is None:
        output_path = Path(__file__).parent.parent / "data/demo/sample_rca_results.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for anomaly in SAMPLE_ANOMALIES:
        try:
            from src.agents.graph import run_pipeline
            result = run_pipeline(anomaly)
            results.append(result)
            print(f"  Pipeline result: {anomaly['account_id']} ({anomaly['anomaly_type']})")
        except Exception as exc:
            print(f"  Pipeline unavailable ({exc}) — using template for {anomaly['account_id']}")
            results.append({
                "anomaly_data": anomaly,
                "anomaly_type": anomaly["anomaly_type"],
                "rca_report": _make_rca(anomaly),
                "pipeline_status": "demo",
                "retrieval_strategy": "graph_first" if anomaly["anomaly_type"] in ("zero_billing", "cdr_failure") else "vector_first",
                "retrieval_count": 3,
                "revision_count": 0,
            })

    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved {len(results)} demo results → {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate pre-computed demo RCA results")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    generate(Path(args.output) if args.output else None)


if __name__ == "__main__":
    main()
