"""Tests for evaluation.metrics."""
import pytest

from src.evaluation.metrics import (
    compute_rouge_l,
    context_precision,
    context_recall,
    mrr_at_k,
    anomaly_type_match,
    load_ground_truth,
)


class TestRougeL:
    def test_identical_strings_score_1(self):
        out = compute_rouge_l("the cdr pipeline failed", "the cdr pipeline failed")
        assert out["fmeasure"] == pytest.approx(1.0, rel=1e-6)

    def test_disjoint_strings_score_0(self):
        out = compute_rouge_l("alpha beta gamma", "delta epsilon zeta")
        assert out["fmeasure"] == 0.0

    def test_empty_hypothesis_is_safe(self):
        out = compute_rouge_l("", "reference text here")
        assert 0.0 <= out["fmeasure"] <= 1.0

    def test_partial_overlap_is_between_0_and_1(self):
        out = compute_rouge_l("the cdr pipeline failed", "the billing pipeline failed")
        assert 0.0 < out["fmeasure"] < 1.0


class TestTypeMatch:
    def test_exact(self):
        assert anomaly_type_match("zero_billing", "zero_billing")

    def test_whitespace_and_case_tolerant(self):
        assert anomaly_type_match("  Zero_Billing ", "zero_billing")

    def test_different_types_do_not_match(self):
        assert not anomaly_type_match("zero_billing", "duplicate_charge")


class TestRetrievalMetrics:
    def test_precision_and_recall_all_relevant(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b", "c"]
        assert context_precision(retrieved, relevant) == pytest.approx(1.0)
        assert context_recall(retrieved, relevant) == pytest.approx(1.0)

    def test_precision_partial(self):
        retrieved = ["a", "b", "x"]
        relevant = ["a", "b"]
        assert context_precision(retrieved, relevant) == pytest.approx(2 / 3)

    def test_recall_partial(self):
        retrieved = ["a"]
        relevant = ["a", "b", "c"]
        assert context_recall(retrieved, relevant) == pytest.approx(1 / 3)

    def test_precision_empty_retrieved(self):
        assert context_precision([], ["a"]) == 0.0

    def test_recall_empty_relevant(self):
        assert context_recall(["a"], []) == 0.0

    def test_mrr_first_hit_wins(self):
        assert mrr_at_k(["x", "y", "target"], ["target"], k=5) == pytest.approx(1 / 3)

    def test_mrr_first_position(self):
        assert mrr_at_k(["target", "y"], ["target"], k=5) == 1.0

    def test_mrr_no_hit(self):
        assert mrr_at_k(["x", "y"], ["z"], k=5) == 0.0


class TestGroundTruth:
    def test_loader_returns_list(self):
        gt = load_ground_truth()
        assert isinstance(gt, list)
        assert len(gt) >= 15  # tolerate both 15- and 60-item files

    def test_expected_types_present(self):
        gt = load_ground_truth()
        types = {row["anomaly_type"] for row in gt}
        assert types == {
            "zero_billing", "duplicate_charge", "usage_spike",
            "cdr_failure", "sla_breach",
        }

    def test_each_row_has_required_fields(self):
        gt = load_ground_truth()
        required = {"anomaly_id", "anomaly_type", "root_cause"}
        for row in gt:
            assert required.issubset(row.keys()), f"missing fields: {row}"

    def test_unique_ids(self):
        gt = load_ground_truth()
        ids = [row["anomaly_id"] for row in gt]
        assert len(ids) == len(set(ids))
