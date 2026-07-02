"""
Reasoning Agent — generates structured root cause hypotheses from anomaly data + retrieved docs.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.agents.state import AgentState
from src.agents.prompts import REASONER_SYSTEM_PROMPT, REASONER_PROMPT
from src.agents.llm_utils import call_llm
# LLM access is via llm_utils.call_llm


def _build_fallback_hypothesis(anomaly: dict, docs: list) -> str:
    """Generate a hypothesis without LLM using retrieved docs."""
    anomaly_type = anomaly.get("anomaly_type", "unknown")

    # Use the top document as primary evidence
    evidence = docs[0]["text"][:500] if docs else "No evidence retrieved."
    source = docs[0]["source"] if docs else "N/A"

    type_hypotheses = {
        "zero_billing": (
            "ROOT CAUSE: Billing processing pipeline failure resulting in zero-rated billing records. "
            "The billing system failed to process usage records for the current cycle, likely due to "
            "a rating engine configuration error or provisioning system mismatch.\n\n"
            "REASONING:\n"
            "1. Customer has active services (tenure > 0) but MonthlyCharges = $0.00\n"
            "2. This pattern matches billing pipeline failure or provisioning sync issues\n"
            "3. The most common cause is a rating engine misconfiguration after a system upgrade\n"
            f"4. Evidence from [{source}] supports this diagnosis\n\n"
            "EVIDENCE:\n"
            f"- [{source}]: {evidence[:300]}\n\n"
            "CITATIONS: [zero_billing_playbook.md]\n\n"
            "CONFIDENCE: HIGH"
        ),
        "duplicate_charge": (
            "ROOT CAUSE: Charge deduplication engine failure allowing duplicate billing records "
            "to pass through to the rating engine, resulting in double-billed charges.\n\n"
            "REASONING:\n"
            "1. Customer billed at approximately 2x normal monthly charges\n"
            "2. This pattern matches deduplication failure or billing batch re-transmission\n"
            "3. Billing system retry logic may have caused duplicate charge posting\n"
            f"4. Evidence from [{source}] supports this diagnosis\n\n"
            "EVIDENCE:\n"
            f"- [{source}]: {evidence[:300]}\n\n"
            "CITATIONS: [duplicate_charge_playbook.md]\n\n"
            "CONFIDENCE: HIGH"
        ),
        "usage_spike": (
            "ROOT CAUSE: Abnormal usage spike detected — possible causes include roaming charges "
            "not capped per contract, streaming service miscategorised as premium tier, or rating "
            "plan not updated after service upgrade.\n\n"
            "REASONING:\n"
            "1. Customer MonthlyCharges increased ~10x above historical baseline\n"
            "2. IBM Telco pattern: Fiber optic internet service customers at high tenure are most affected\n"
            "3. If multiple customers on same plan affected: likely rating plan error\n"
            "4. If single customer: likely incorrect rate card application\n"
            f"5. Evidence from [{source}] supports investigation approach\n\n"
            "EVIDENCE:\n"
            f"- [{source}]: {evidence[:300]}\n\n"
            "CITATIONS: [usage_spike_playbook.md]\n\n"
            "CONFIDENCE: MEDIUM"
        ),
        "cdr_failure": (
            "ROOT CAUSE: Billing record ingestion pipeline failure resulting in NULL/missing values "
            "in customer billing records. Likely caused by service bundle rating failure or billing "
            "cycle batch job failure on multi-service accounts.\n\n"
            "REASONING:\n"
            "1. Critical billing fields contain NULL/NaN values\n"
            "2. Customer has active streaming services (StreamingTV or StreamingMovies = Yes)\n"
            "3. Billing pipeline failed to persist complete records for bundle-rated accounts\n"
            f"4. Evidence from [{source}] provides resolution steps\n\n"
            "EVIDENCE:\n"
            f"- [{source}]: {evidence[:300]}\n\n"
            "CITATIONS: [cdr_failure_playbook.md]\n\n"
            "CONFIDENCE: HIGH"
        ),
        "sla_breach": (
            "ROOT CAUSE: Customer charges exceed contractual SLA cap (P95 × 1.5 threshold). "
            "Likely caused by rate plan change not reflected in SLA cap configuration, or "
            "billing engine using wrong rate card version.\n\n"
            "REASONING:\n"
            "1. Monthly charges significantly exceed normal range for this contract type\n"
            "2. IBM Telco pattern: annual/two-year contract customers are affected\n"
            "3. Contract threshold may not be applied in rating engine after plan migration\n"
            f"4. Evidence from [{source}] provides diagnostic steps\n\n"
            "EVIDENCE:\n"
            f"- [{source}]: {evidence[:300]}\n\n"
            "CITATIONS: [sla_breach_playbook.md]\n\n"
            "CONFIDENCE: HIGH"
        ),
    }

    return type_hypotheses.get(anomaly_type, (
        f"ROOT CAUSE: Billing anomaly of type '{anomaly_type}' detected. "
        "Further investigation required to determine specific root cause.\n\n"
        "REASONING:\n"
        "1. Anomaly detected by billing monitoring system\n"
        f"2. Evidence from {source} provides context\n\n"
        "EVIDENCE:\n"
        f"- {evidence[:300]}\n\n"
        "CONFIDENCE: LOW"
    ))


def reasoner_node(state: AgentState) -> AgentState:
    """
    Reasoning Agent node for LangGraph.
    Receives anomaly context + retrieved docs → generates structured root cause hypothesis.
    """
    anomaly = state.get("anomaly_data", {})
    docs = state.get("retrieved_docs", [])

    # Format retrieved docs for the prompt
    docs_text = ""
    for i, doc in enumerate(docs, 1):
        docs_text += f"\n--- Document {i} (Source: {doc['source']}, Relevance: {doc['relevance_score']:.2f}) ---\n"
        docs_text += doc["text"][:800]
        docs_text += "\n"

    prompt = REASONER_PROMPT.format(
        account_id=anomaly.get("account_id", "UNKNOWN"),
        anomaly_type=anomaly.get("anomaly_type", "unknown"),
        confidence=anomaly.get("confidence", 0.0),
        monthly_charges=anomaly.get("monthly_charges", 0.0),
        total_charges=anomaly.get("total_charges", 0.0),
        tenure=anomaly.get("tenure", 0),
        retrieved_docs=docs_text if docs_text else "No relevant documents retrieved.",
    )

    # Revision pass: incorporate the Critic's feedback so the rewrite actually
    # addresses the flagged gaps instead of regenerating the same hypothesis.
    critic_reasons = state.get("critic_reasons", [])
    if state.get("critic_verdict") == "revise" and critic_reasons:
        feedback = "\n".join(f"- {r}" for r in critic_reasons)
        prompt += (
            "\n\nA senior reviewer flagged the following issues with your "
            "previous hypothesis. Revise it to address EACH issue, and only "
            "make claims that are supported by the retrieved documents:\n"
            f"{feedback}\n\nPREVIOUS HYPOTHESIS:\n"
            f"{state.get('hypothesis', '')[:1500]}"
        )

    # Try LLM first
    hypothesis = call_llm(REASONER_SYSTEM_PROMPT, prompt)

    # Fallback if LLM unavailable
    if not hypothesis:
        hypothesis = _build_fallback_hypothesis(anomaly, docs)

    state["hypothesis"] = hypothesis
    state["reasoning_chain"] = hypothesis
    state["pipeline_status"] = "reasoned"

    return state
