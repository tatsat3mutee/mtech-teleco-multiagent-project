"""
Knowledge base tests — playbook count, retrieval quality, jargon check.
Tests run without any external dependencies (no ChromaDB, no LLM).
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PLAYBOOK_DIR = Path(__file__).parent.parent / "data/corpus/rca_playbooks"

FORBIDDEN_TERMS = [
    "3GPP TS 32",
    "CDR Collector",
    "mediation device",
    "ETSI TS 101",
    "ITU-T E.860",
]

REQUIRED_PLAYBOOKS = [
    "zero_billing_playbook.md",
    "duplicate_charge_playbook.md",
    "usage_spike_playbook.md",
    "cdr_failure_playbook.md",
    "sla_breach_playbook.md",
    "telecom_billing_overview.md",
    "incident_response_framework.md",
    "revenue_assurance.md",
]


def test_playbook_count():
    """At least 8 playbook markdown files must exist."""
    if not PLAYBOOK_DIR.exists():
        pytest.skip("Playbook directory not found")
    playbooks = list(PLAYBOOK_DIR.glob("*.md"))
    assert len(playbooks) >= 8, (
        f"Expected ≥8 playbooks, found {len(playbooks)}: {[p.name for p in playbooks]}"
    )


def test_required_playbooks_present():
    """Each required playbook file must exist."""
    if not PLAYBOOK_DIR.exists():
        pytest.skip("Playbook directory not found")
    for name in REQUIRED_PLAYBOOKS:
        path = PLAYBOOK_DIR / name
        assert path.exists(), f"Required playbook missing: {name}"


def test_no_cdr_jargon():
    """No playbook may contain forbidden CDR/3GPP jargon strings."""
    if not PLAYBOOK_DIR.exists():
        pytest.skip("Playbook directory not found")
    violations = []
    for md_path in sorted(PLAYBOOK_DIR.glob("*.md")):
        content = md_path.read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            if term in content:
                violations.append(f"{md_path.name}: contains '{term}'")
    assert len(violations) == 0, "Forbidden jargon found:\n" + "\n".join(violations)


def test_playbooks_reference_ibm_fields():
    """Each playbook must reference at least one IBM Telco dataset field."""
    ibm_fields = [
        "MonthlyCharges", "TotalCharges", "tenure", "Contract",
        "InternetService", "StreamingTV", "StreamingMovies",
        "monthly_charges", "total_charges",
    ]
    if not PLAYBOOK_DIR.exists():
        pytest.skip("Playbook directory not found")
    missing = []
    for name in REQUIRED_PLAYBOOKS:
        path = PLAYBOOK_DIR / name
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if not any(field in content for field in ibm_fields):
            missing.append(name)
    assert len(missing) == 0, (
        f"Playbooks with no IBM Telco field references: {missing}"
    )


def test_retrieval_returns_results():
    """KnowledgeBase.search() returns ≥1 result for each anomaly type query."""
    try:
        from src.rag.knowledge_base import KnowledgeBase
    except ImportError:
        pytest.skip("KnowledgeBase not importable — check dependencies")

    kb = KnowledgeBase()
    if kb.count == 0:
        pytest.skip("Knowledge base is empty — build it first: KnowledgeBase().build_from_corpus()")

    queries = [
        "zero billing active customer rating engine configuration",
        "duplicate charge billing deduplication retry idempotency",
        "usage spike Fiber optic internet service rate card",
        "billing record failure streaming service bundle NaN charges",
        "SLA breach annual contract monthly charges cap",
    ]
    for query in queries:
        results = kb.search(query, n_results=3)
        assert len(results) >= 1, f"No results returned for query: '{query}'"
