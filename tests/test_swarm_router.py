"""
Tests for SWARM-inspired retrieval routing logic.
No external dependencies — pure Python logic only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.swarm_router import get_retrieval_strategy, get_routing_explanation


def test_graph_first_types():
    """zero_billing and cdr_failure must route to graph_first."""
    assert get_retrieval_strategy("zero_billing") == "graph_first"
    assert get_retrieval_strategy("cdr_failure") == "graph_first"


def test_vector_first_types():
    """usage_spike, duplicate_charge, sla_breach must route to vector_first."""
    assert get_retrieval_strategy("usage_spike") == "vector_first"
    assert get_retrieval_strategy("duplicate_charge") == "vector_first"
    assert get_retrieval_strategy("sla_breach") == "vector_first"


def test_unknown_type_fallback():
    """Unknown anomaly type falls back to vector_first — never raises."""
    result = get_retrieval_strategy("mystery_anomaly_type")
    assert result == "vector_first"


def test_routing_explanation_nonempty():
    """Every known type returns a non-empty, non-whitespace explanation string."""
    types = ["zero_billing", "cdr_failure", "usage_spike", "duplicate_charge", "sla_breach"]
    for t in types:
        explanation = get_routing_explanation(t)
        assert isinstance(explanation, str)
        assert len(explanation.strip()) > 10


def test_unknown_type_explanation_mentions_unknown():
    """Explanation for unknown type mentions 'Unknown' or 'default'."""
    explanation = get_routing_explanation("mystery_type")
    assert "Unknown" in explanation or "default" in explanation
