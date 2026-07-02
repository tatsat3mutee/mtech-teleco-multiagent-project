"""
LangGraph StateGraph orchestration for the multi-agent RCA pipeline.
Flow: Investigator → Reasoner → Critic → (revise→Reasoner | proceed→Reporter) → END

Includes:
- Langfuse tracing (per-pipeline trace, per-node spans)
- Node-level error recovery (graceful degradation to partial results)
"""
import logging
import time
from pathlib import Path
from typing import List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.investigator import investigator_node
from src.agents.reasoner import reasoner_node
from src.agents.reporter import reporter_node
from src.agents.critic import critic_node, should_revise
from src.utils.observability import trace_pipeline, create_span

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for the multi-agent pipeline."""
    workflow = StateGraph(AgentState)

    workflow.add_node("investigator", investigator_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("reporter", reporter_node)

    workflow.set_entry_point("investigator")

    # Linear flow: investigator → reasoner
    workflow.add_edge("investigator", "reasoner")

    # Reasoner → Critic
    workflow.add_edge("reasoner", "critic")

    # Critic loops back to reasoner for one revision, then proceeds to reporter
    workflow.add_conditional_edges(
        "critic",
        should_revise,
        {
            "revise": "reasoner",
            "proceed": "reporter",
        },
    )

    workflow.add_edge("reporter", END)

    return workflow.compile()


def run_pipeline(anomaly_record: dict) -> dict:
    """
    Run the complete multi-agent RCA pipeline for a single anomaly.

    Args:
        anomaly_record: dict with keys: account_id, anomaly_type, confidence,
                       monthly_charges, total_charges, tenure, features

    Returns:
        Complete agent state including rca_report.
    """
    graph = build_graph()
    anomaly_id = anomaly_record.get("account_id", "unknown")
    anomaly_type = anomaly_record.get("anomaly_type", "unknown")

    initial_state: AgentState = {
        "anomaly_data": anomaly_record,
        "retrieved_docs": [],
        "retrieval_count": 0,
        "pipeline_status": "started",
    }

    start_time = time.time()
    result: dict = {}

    with trace_pipeline(anomaly_id, anomaly_type) as trace:
        try:
            for step_output in graph.stream(initial_state):
                for node_name, node_state in step_output.items():
                    # Create Langfuse span per node
                    span = create_span(trace, node_name)
                    result.update(node_state)
                    span.end()

            result["latency_ms"] = (time.time() - start_time) * 1000
            result["trace_id"] = getattr(trace, "id", None)

        except Exception as e:
            logger.error(f"Pipeline error at node: {e}")
            result = {**initial_state, **result}
            result["pipeline_status"] = "partial"
            result["error_message"] = str(e)
            result["latency_ms"] = (time.time() - start_time) * 1000
            result["trace_id"] = getattr(trace, "id", None)

    return result


def run_batch_pipeline(anomaly_records: List[dict]) -> List[dict]:
    """Run the pipeline for a batch of anomalies."""
    results = []
    for i, record in enumerate(anomaly_records):
        logger.info(f"Processing anomaly {i+1}/{len(anomaly_records)}: "
                    f"{record.get('account_id', 'N/A')} ({record.get('anomaly_type', 'unknown')})")
        result = run_pipeline(record)
        results.append(result)
    return results


if __name__ == "__main__":
    # Test with a sample anomaly
    test_anomaly = {
        "account_id": "CUST-00123",
        "anomaly_type": "zero_billing",
        "confidence": 0.95,
        "monthly_charges": 0.0,
        "total_charges": 2500.0,
        "tenure": 36,
        "features": {"InternetService": "Fiber optic", "Contract": "Two year"},
    }

    print("Running multi-agent RCA pipeline...")
    result = run_pipeline(test_anomaly)

    print(f"\nPipeline Status: {result.get('pipeline_status')}")
    print(f"Latency: {result.get('latency_ms', 0):.0f}ms")
    print(f"Retrieved Docs: {result.get('retrieval_count', 0)}")

    rca = result.get("rca_report", {})
    if rca:
        import json
        print(f"\nRCA Report:")
        print(json.dumps(rca, indent=2))
