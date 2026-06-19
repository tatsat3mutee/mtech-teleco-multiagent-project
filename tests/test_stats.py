"""Tests for src.evaluation.stats."""
import pytest

from src.evaluation.stats import (
    bootstrap_ci,
    paired_bootstrap_pvalue,
    wilcoxon_paired,
    compare_configs,
)


class TestBootstrapCI:
    def test_mean_close_to_sample_mean(self):
        mean, lo, hi = bootstrap_ci([0.1, 0.2, 0.3, 0.4, 0.5], n_boot=2000)
        assert mean == pytest.approx(0.3, rel=1e-6)
        assert lo < mean < hi

    def test_handles_empty(self):
        mean, lo, hi = bootstrap_ci([], n_boot=100)
        assert (mean, lo, hi) == (0.0, 0.0, 0.0)

    def test_single_value(self):
        mean, lo, hi = bootstrap_ci([0.7], n_boot=500)
        assert mean == lo == hi == pytest.approx(0.7)

    def test_ignores_nan(self):
        mean, *_ = bootstrap_ci([0.5, float("nan"), 0.5], n_boot=500)
        assert mean == pytest.approx(0.5)


class TestPairedBootstrap:
    def test_identical_series_large_pvalue(self):
        a = [0.3, 0.4, 0.5, 0.6]
        p = paired_bootstrap_pvalue(a, a, n_boot=2000)
        assert p > 0.5

    def test_clearly_different_series_small_pvalue(self):
        a = [0.8, 0.9, 0.85, 0.95, 0.9]
        b = [0.1, 0.2, 0.15, 0.05, 0.1]
        p = paired_bootstrap_pvalue(a, b, n_boot=4000)
        assert p < 0.05

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            paired_bootstrap_pvalue([0.1, 0.2], [0.3, 0.4, 0.5])


class TestWilcoxon:
    def test_no_scipy_does_not_crash(self):
        out = wilcoxon_paired([0.1, 0.2, 0.3], [0.4, 0.5, 0.6])
        assert "pvalue" in out and "statistic" in out

    def test_all_equal_returns_nonsignificant(self):
        out = wilcoxon_paired([0.3, 0.3, 0.3], [0.3, 0.3, 0.3])
        assert out["pvalue"] == 1.0


class TestCompareConfigs:
    def test_baseline_has_zero_delta(self):
        scores = {
            "A": [0.1, 0.2, 0.3],
            "B": [0.4, 0.5, 0.6],
        }
        out = compare_configs(scores, baseline_key="A")
        assert out["A"]["delta_vs_baseline"] == 0.0
        assert out["B"]["delta_vs_baseline"] == pytest.approx(0.3)

    def test_missing_baseline_raises(self):
        with pytest.raises(KeyError):
            compare_configs({"A": [0.1]}, baseline_key="Z")
