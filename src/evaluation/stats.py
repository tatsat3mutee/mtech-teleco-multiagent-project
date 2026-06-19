"""
Statistical significance tests for ablation comparisons.

Provides:
- bootstrap_ci: percentile bootstrap 95% CI for a metric
- paired_bootstrap_pvalue: two-sided p-value for H0: mean(a) == mean(b), paired
- wilcoxon_paired: Wilcoxon signed-rank wrapper (scipy)

Usage:
    from src.evaluation.stats import bootstrap_ci, paired_bootstrap_pvalue
    lo, hi = bootstrap_ci(scores, ci=0.95, n_boot=10_000)
    p = paired_bootstrap_pvalue(config_d_scores, config_c_scores)
"""
from __future__ import annotations

from typing import Sequence, Tuple
import numpy as np

_RNG_SEED = 42


def bootstrap_ci(
    values: Sequence[float],
    ci: float = 0.95,
    n_boot: int = 10_000,
    seed: int = _RNG_SEED,
) -> Tuple[float, float, float]:
    """Return (mean, lower, upper) percentile-bootstrap CI of the mean."""
    a = np.asarray(values, dtype=float)
    a = a[~np.isnan(a)]
    if a.size == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    boot_means = a[idx].mean(axis=1)
    lo_q = (1 - ci) / 2
    hi_q = 1 - lo_q
    return float(a.mean()), float(np.quantile(boot_means, lo_q)), float(np.quantile(boot_means, hi_q))


def paired_bootstrap_pvalue(
    a: Sequence[float],
    b: Sequence[float],
    n_boot: int = 10_000,
    seed: int = _RNG_SEED,
) -> float:
    """Two-sided paired-bootstrap p-value for H0: mean(a) - mean(b) == 0.

    Requires len(a) == len(b); items assumed paired by index.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError(f"paired arrays must match: {a.shape} vs {b.shape}")
    diffs = a - b
    observed = diffs.mean()
    centered = diffs - observed
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diffs.size, size=(n_boot, diffs.size))
    boot = centered[idx].mean(axis=1)
    # two-sided
    p = (np.sum(np.abs(boot) >= abs(observed)) + 1) / (n_boot + 1)
    return float(p)


def wilcoxon_paired(a: Sequence[float], b: Sequence[float]) -> dict:
    """Wilcoxon signed-rank test via scipy. Returns {statistic, pvalue} or zeros."""
    try:
        from scipy.stats import wilcoxon
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        if a.shape != b.shape or a.size < 2:
            return {"statistic": 0.0, "pvalue": 1.0}
        # Drop pairs where both equal (no signed rank)
        mask = a != b
        if mask.sum() < 2:
            return {"statistic": 0.0, "pvalue": 1.0}
        res = wilcoxon(a[mask], b[mask], zero_method="wilcox", alternative="two-sided")
        return {"statistic": float(res.statistic), "pvalue": float(res.pvalue)}
    except Exception as e:
        print(f"[stats] wilcoxon failed: {e}")
        return {"statistic": 0.0, "pvalue": 1.0}


def compare_configs(
    per_item_scores: dict,
    baseline_key: str = "no_rag",
) -> dict:
    """Pairwise comparisons of each config against baseline_key.

    Args:
        per_item_scores: {config_name: [score_per_item, ...]} with equal lengths.
        baseline_key: which config acts as the null baseline.

    Returns:
        {config_name: {mean, ci_low, ci_high, delta_vs_baseline, p_bootstrap,
                       p_wilcoxon}}
    """
    if baseline_key not in per_item_scores:
        raise KeyError(f"baseline '{baseline_key}' not in scores: "
                       f"{list(per_item_scores)}")
    baseline = per_item_scores[baseline_key]
    out = {}
    for name, vals in per_item_scores.items():
        mean, lo, hi = bootstrap_ci(vals)
        entry = {"mean": mean, "ci_low": lo, "ci_high": hi, "n": len(vals)}
        if name == baseline_key:
            entry.update({"delta_vs_baseline": 0.0, "p_bootstrap": 1.0,
                          "p_wilcoxon": 1.0})
        else:
            if len(vals) == len(baseline):
                entry["delta_vs_baseline"] = float(np.mean(vals) - np.mean(baseline))
                entry["p_bootstrap"] = paired_bootstrap_pvalue(vals, baseline)
                entry["p_wilcoxon"] = wilcoxon_paired(vals, baseline)["pvalue"]
            else:
                entry.update({"delta_vs_baseline": float(np.mean(vals) - np.mean(baseline)),
                              "p_bootstrap": float("nan"),
                              "p_wilcoxon": float("nan"),
                              "note": "unpaired — lengths differ"})
        out[name] = entry
    return out
