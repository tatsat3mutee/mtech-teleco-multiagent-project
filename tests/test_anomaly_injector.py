"""Tests for src.data.anomaly_injector — deterministic, fast, offline."""
import numpy as np
import pandas as pd
import pytest

from src.data.anomaly_injector import (
    inject_zero_billing,
    inject_duplicate_charges,
    inject_usage_spike,
    inject_cdr_failure,
    inject_sla_breach,
)


def _base_df(n: int = 1000) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    df = pd.DataFrame({
        "customerID": [f"C{i:05d}" for i in range(n)],
        "MonthlyCharges": rng.uniform(20, 120, size=n),
        "TotalCharges": rng.uniform(100, 8000, size=n),
        "tenure": rng.integers(1, 72, size=n),
    })
    df["anomaly_type"] = "normal"
    df["is_anomaly"] = 0
    return df


class TestInjectors:
    def test_zero_billing_sets_monthly_to_zero(self):
        rng = np.random.default_rng(0)
        df = inject_zero_billing(_base_df(), rng, ratio=0.05)
        zb = df[df["anomaly_type"] == "zero_billing"]
        assert len(zb) == 50
        assert (zb["MonthlyCharges"] == 0.0).all()
        assert (zb["is_anomaly"] == 1).all()

    def test_duplicate_charges_adds_rows(self):
        rng = np.random.default_rng(0)
        before = len(_base_df())
        df = inject_duplicate_charges(_base_df(), rng, ratio=0.02)
        assert len(df) == before + int(before * 0.02)
        dup = df[df["anomaly_type"] == "duplicate_charge"]
        assert (dup["is_anomaly"] == 1).all()

    def test_usage_spike_multiplies_charges(self):
        rng = np.random.default_rng(0)
        base = _base_df()
        original_means = base["MonthlyCharges"].mean()
        df = inject_usage_spike(base.copy(), rng, ratio=0.03)
        sp = df[df["anomaly_type"] == "usage_spike"]
        assert len(sp) == 30
        assert sp["MonthlyCharges"].mean() > original_means * 5

    def test_cdr_failure_introduces_nan(self):
        rng = np.random.default_rng(0)
        df = inject_cdr_failure(_base_df(), rng, ratio=0.015)
        cf = df[df["anomaly_type"] == "cdr_failure"]
        assert len(cf) == 15
        assert cf["TotalCharges"].isna().all()

    def test_sla_breach_raises_charges_above_p95(self):
        rng = np.random.default_rng(0)
        base = _base_df()
        p95 = base["MonthlyCharges"].quantile(0.95)
        df = inject_sla_breach(base.copy(), rng, ratio=0.02)
        sla = df[df["anomaly_type"] == "sla_breach"]
        assert len(sla) == 20
        assert (sla["MonthlyCharges"] > p95).all()

    def test_deterministic_under_same_seed(self):
        rng1 = np.random.default_rng(7)
        rng2 = np.random.default_rng(7)
        d1 = inject_zero_billing(_base_df(), rng1, ratio=0.03)
        d2 = inject_zero_billing(_base_df(), rng2, ratio=0.03)
        idx1 = sorted(d1[d1["anomaly_type"] == "zero_billing"].index.tolist())
        idx2 = sorted(d2[d2["anomaly_type"] == "zero_billing"].index.tolist())
        assert idx1 == idx2
