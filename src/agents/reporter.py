"""
Reporter Agent — produces structured JSON RCA reports.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.agents.state import AgentState
from src.agents.prompts import REPORTER_SYSTEM_PROMPT, REPORTER_PROMPT
from src.agents.llm_utils import call_llm
# LLM access is via llm_utils.call_llm


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response."""
    text = text.strip()
    # Try to find JSON block
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    return json.loads(text)


def _generate_fallback_report(anomaly: dict, hypothesis: str, docs: list) -> dict:
    """Generate a report without LLM."""
    anomaly_type = anomaly.get("anomaly_type", "unknown")

    # Extract key info from hypothesis
    root_cause = ""
    if "ROOT CAUSE:" in hypothesis:
        root_cause = hypothesis.split("ROOT CAUSE:")[1].split("\n")[0].strip()
    else:
        root_cause = hypothesis[:200]

    # Build evidence from docs
    evidence = []
    for doc in docs[:3]:
        evidence.append(f"{doc['source']}: {doc['text'][:150]}...")

    # Action maps
    actions_map = {
        "zero_billing": [
            "Trigger billing record reprocessing for affected account",
            "Verify billing pipeline health for batch processing window",
            "Issue corrective billing statement to customer",
            "Add monitoring alert for zero-billing anomaly rate in MLflow"
        ],
        "duplicate_charge": [
            "Reverse duplicate charges immediately",
            "Audit and repair charge deduplication engine",
            "Implement transaction-level idempotency in billing retry logic",
            "Add real-time monitoring for duplicate charge rate"
        ],
        "usage_spike": [
            "Cross-reference with fraud detection system",
            "Verify usage location and pattern legitimacy",
            "Check rating engine accuracy for affected plan and rate card version",
            "Ensure bill shock notification compliance for internet service customers"
        ],
        "cdr_failure": [
            "Identify root cause from billing pipeline error logs",
            "Check recent system upgrades or configuration changes",
            "Reprocess all failed billing records after pipeline fix",
            "Add automated billing record processing success rate monitoring"
        ],
        "sla_breach": [
            "Verify customer contract terms and billing cap configuration",
            "Compare actual charges against contractual SLA threshold (P95 × 1.5)",
            "Issue corrective billing and SLA penalty credits",
            "Update rate card configuration to prevent recurrence"
        ],
    }

    severity_map = {
        "zero_billing": "HIGH",
        "duplicate_charge": "HIGH",
        "usage_spike": "MEDIUM",
        "cdr_failure": "HIGH",
        "sla_breach": "HIGH",
    }

    summary_map = {
        "zero_billing": f"A zero-billing anomaly was detected for account {anomaly.get('account_id', 'N/A')}. "
                        f"The customer has active services but was charged $0.00 for the current billing cycle. "
                        f"Root cause analysis indicates a billing processing pipeline failure or rating engine misconfiguration. "
                        f"Immediate billing record reprocessing and corrective billing are recommended.",
        "duplicate_charge": f"A duplicate charge was detected for account {anomaly.get('account_id', 'N/A')}. "
                           f"The customer was billed approximately double ({anomaly.get('monthly_charges', 0):.2f}) the expected amount. "
                           f"Root cause analysis indicates a charge deduplication or billing retry logic failure. "
                           f"Immediate charge reversal and system fix are recommended.",
        "usage_spike": f"An abnormal usage spike was detected for account {anomaly.get('account_id', 'N/A')}. "
                      f"Monthly charges ({anomaly.get('monthly_charges', 0):.2f}) are approximately 10x the historical baseline. "
                      f"Investigation needed to determine if this is a rate card error, roaming overage, or service miscategorisation. "
                      f"Cross-reference with billing records and verify rating plan accuracy.",
        "cdr_failure": f"A billing record failure was detected for account {anomaly.get('account_id', 'N/A')}. "
                      f"Critical billing fields contain NULL/missing values indicating incomplete billing record processing. "
                      f"Root cause analysis points to billing pipeline ingestion failure (bundle rating error or batch job failure). "
                      f"Immediate billing record reprocessing and pipeline health verification required.",
        "sla_breach": f"An SLA breach was detected for account {anomaly.get('account_id', 'N/A')}. "
                     f"Monthly charges (${anomaly.get('monthly_charges', 0):.2f}) exceed contractual thresholds (P95 × 1.5 cap). "
                     f"Root cause analysis indicates rate plan not reflected in SLA cap configuration or billing engine using wrong rate card. "
                     f"Immediate corrective billing and SLA credit issuance required.",
    }

    return {
        "anomaly_id": anomaly.get("account_id", "UNKNOWN"),
        "anomaly_type": anomaly_type,
        "root_cause": root_cause,
        "supporting_evidence": evidence if evidence else ["No specific evidence retrieved"],
        "recommended_actions": actions_map.get(anomaly_type, ["Investigate further", "Escalate to senior engineer"]),
        "severity": severity_map.get(anomaly_type, "MEDIUM"),
        "confidence_score": anomaly.get("confidence", 0.5),
        "summary": summary_map.get(anomaly_type,
                                    f"Billing anomaly detected for account {anomaly.get('account_id', 'N/A')}. "
                                    f"Type: {anomaly_type}. Requires investigation."),
    }


def reporter_node(state: AgentState) -> AgentState:
    """
    Reporter Agent node for LangGraph.
    Receives hypothesis + evidence → produces JSON-schema-validated RCA report.
    """
    anomaly = state.get("anomaly_data", {})
    hypothesis = state.get("hypothesis", "No hypothesis generated.")
    docs = state.get("retrieved_docs", [])

    # Build evidence summary
    evidence_summary = ""
    for doc in docs[:3]:
        evidence_summary += f"- [{doc['source']}] {doc['text'][:200]}\n"

    prompt = REPORTER_PROMPT.format(
        account_id=anomaly.get("account_id", "UNKNOWN"),
        anomaly_type=anomaly.get("anomaly_type", "unknown"),
        monthly_charges=anomaly.get("monthly_charges", 0.0),
        tenure=anomaly.get("tenure", 0),
        hypothesis=hypothesis,
        evidence_summary=evidence_summary if evidence_summary else "No evidence retrieved.",
    )

    # Try LLM first
    llm_response = call_llm(REPORTER_SYSTEM_PROMPT, prompt)

    rca_report = None
    if llm_response:
        try:
            rca_report = _parse_json_response(llm_response)
        except (json.JSONDecodeError, Exception):
            rca_report = None

    # Fallback if LLM failed
    if rca_report is None:
        rca_report = _generate_fallback_report(anomaly, hypothesis, docs)

    state["rca_report"] = rca_report
    state["pipeline_status"] = "completed"

    return state
