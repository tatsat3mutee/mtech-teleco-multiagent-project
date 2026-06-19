"""
SWARM-inspired dynamic routing for the Investigator agent.
Selects retrieval strategy (graph_first vs vector_first) based on anomaly type.

Rationale (academic):
- zero_billing and cdr_failure involve multi-hop causal chains:
    anomaly → billing system component → error code → remediation step.
  The knowledge graph pre-encodes these chains; graph traversal is more precise.
- usage_spike, duplicate_charge, sla_breach are pattern-matching problems:
    "show me all cases where X charge pattern arose from Y root cause."
  Broad vector + lexical search covers these better than graph traversal.

Reference: Shinn et al., "SWARM: Scalable Agent Orchestration", 2024.
"""
from __future__ import annotations
from typing import Literal

RetrievalStrategy = Literal["graph_first", "vector_first"]

# Anomaly types that benefit from graph traversal (multi-hop causal reasoning)
_GRAPH_FIRST_TYPES: frozenset[str] = frozenset({"zero_billing", "cdr_failure"})

# Anomaly types that benefit from broad semantic/lexical search
_VECTOR_FIRST_TYPES: frozenset[str] = frozenset({"usage_spike", "duplicate_charge", "sla_breach"})


def get_retrieval_strategy(anomaly_type: str) -> RetrievalStrategy:
    """
    Return retrieval strategy for a given anomaly type.

    graph_first:  graph traversal (2-hop BFS) → then vector search for remaining slots
    vector_first: dense + BM25 hybrid search → then graph for causal enrichment
    Unknown types default to vector_first (safe fallback, never raises).
    """
    if anomaly_type in _GRAPH_FIRST_TYPES:
        return "graph_first"
    return "vector_first"


def get_routing_explanation(anomaly_type: str) -> str:
    """Return human-readable explanation of routing decision. Used in RCA report UI."""
    strategy = get_retrieval_strategy(anomaly_type)
    if strategy == "graph_first":
        return (
            f"Anomaly type '{anomaly_type}' requires multi-hop causal reasoning "
            "(billing system → component → error code → fix). "
            "Graph-first traversal selected: seeds the knowledge graph at the anomaly node "
            "and follows causal edges via 2-hop BFS."
        )
    if anomaly_type in _VECTOR_FIRST_TYPES:
        return (
            f"Anomaly type '{anomaly_type}' is best matched via semantic pattern search. "
            "Vector-first retrieval selected: dense + BM25 hybrid with RRF fusion "
            "across all RCA playbook content."
        )
    return (
        f"Unknown anomaly type '{anomaly_type}' — defaulting to vector-first retrieval. "
        "Dense + BM25 hybrid search selected as the safe fallback strategy."
    )
