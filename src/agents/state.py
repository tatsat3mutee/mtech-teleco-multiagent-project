"""
Agent state schema for the multi-agent RCA pipeline.
Defines the typed state that flows through the LangGraph StateGraph.
"""
from typing import TypedDict, List, Optional, Any


class AnomalyRecord(TypedDict, total=False):
    """A single anomaly record from the detector."""
    account_id: str
    anomaly_type: str
    confidence: float
    tenure: float
    monthly_charges: float
    total_charges: float
    features: dict
    raw_data: dict


class RetrievedDocument(TypedDict):
    """A document retrieved from the knowledge base."""
    text: str
    source: str
    relevance_score: float
    metadata: dict


class RCAReport(TypedDict, total=False):
    """Structured Root Cause Analysis report."""
    anomaly_id: str
    anomaly_type: str
    root_cause: str
    supporting_evidence: List[str]
    recommended_actions: List[str]
    severity: str
    confidence_score: float
    summary: str


class AgentState(TypedDict, total=False):
    """
    Complete state passed through the LangGraph pipeline.
    Each agent reads from and writes to this shared state.
    """
    # Input
    anomaly_data: AnomalyRecord

    # Investigator Agent output
    retrieval_query: str
    retrieved_docs: List[RetrievedDocument]
    retrieval_count: int

    # Reasoning Agent output
    hypothesis: str
    reasoning_chain: str

    # Critic Agent output
    critic_verdict: str        # "accept" | "revise"
    critic_reasons: List[str]
    critic_confidence: float
    critic_claims: List[dict]  # [{"claim": str, "grounded": bool, "evidence": str|None}]
    critic_attempts: int

    # Reporter Agent output
    rca_report: RCAReport

    # SWARM routing metadata (set by investigator via swarm_router)
    retrieval_strategy: str      # "graph_first" | "vector_first"
    routing_explanation: str     # human-readable routing decision

    # Pipeline metadata
    pipeline_status: str
    error_message: str
    latency_ms: float
    model_name: str
