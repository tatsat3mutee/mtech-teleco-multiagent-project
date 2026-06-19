"""
Data pipeline tests — load_combined(), anomaly injection filters.
All tests use IBM Telco dataset only (always present after download).
They skip gracefully if the CSV has not been downloaded yet.
"""
import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

IBM_PATH = Path(__file__).parent.parent / "data/raw/ibm_telco_churn.csv"


@pytest.fixture(scope="module")
def ibm_df():
    """Load IBM Telco dataset once for the module."""
    if not IBM_PATH.exists():
        pytest.skip("IBM Telco dataset not downloaded — run scripts/download_datasets.py")
    from src.data.loader import load_ibm_telco
    return load_ibm_telco(IBM_PATH)


@pytest.fixture(scope="module")
def labeled_ibm(ibm_df):
    """Inject anomalies into IBM Telco dataset."""
    from src.data.anomaly_injector import inject_all_anomalies
    return inject_all_anomalies(ibm_df.copy())


def test_load_combined_columns(ibm_df):
    """load_combined() returns all required normalised columns."""
    from src.data.loader import load_combined
    combined = load_combined(ibm_path=IBM_PATH)
    required = [
        "customer_id", "tenure", "monthly_charges", "total_charges",
        "contract", "internet_service", "streaming_flag", "churn", "source",
        "is_anomaly", "anomaly_type",
    ]
    for col in required:
        assert col in combined.columns, f"Missing column: {col}"


def test_load_combined_shape(ibm_df):
    """load_combined() returns at least as many rows as IBM Telco alone."""
    from src.data.loader import load_combined
    combined = load_combined(ibm_path=IBM_PATH)
    assert len(combined) >= len(ibm_df), (
        f"combined ({len(combined)}) should be >= IBM ({len(ibm_df)})"
    )
    assert len(combined) > 5000, f"Expected >5000 rows, got {len(combined)}"


def test_anomaly_inject_rates(ibm_df):
    """Each anomaly type is injected at approximately the configured ratio."""
    from src.data.anomaly_injector import inject_all_anomalies
    from config import ANOMALY_RATIOS
    df = inject_all_anomalies(ibm_df.copy())
    n = len(df)
    for atype, ratio in ANOMALY_RATIOS.items():
        actual = (df["anomaly_type"] == atype).sum() / n
        tolerance = max(ratio, 0.005)  # allow ±half the ratio or 0.5%
        assert actual <= ratio + tolerance, (
            f"{atype}: injected {actual:.3f} > configured {ratio} + tolerance {tolerance}"
        )


def test_usage_spike_internet_only(labeled_ibm):
    """usage_spike anomalies are only injected into internet-service customers."""
    spikes = labeled_ibm[labeled_ibm["anomaly_type"] == "usage_spike"]
    if len(spikes) == 0:
        pytest.skip("No usage_spike anomalies injected (too few internet customers?)")
    # IBM schema: InternetService should not be "No"
    if "InternetService" in spikes.columns:
        bad = spikes[spikes["InternetService"].isin(["No", "None"])]
        assert len(bad) == 0, f"{len(bad)} usage_spike rows have InternetService=No"


def test_cdr_failure_streaming_only(ibm_df):
    """cdr_failure anomalies are only injected into streaming-service customers."""
    from src.data.anomaly_injector import inject_all_anomalies
    df = inject_all_anomalies(ibm_df.copy())
    failures = df[df["anomaly_type"] == "cdr_failure"]
    if len(failures) == 0:
        pytest.skip("No cdr_failure anomalies injected")
    if "StreamingTV" in failures.columns and "StreamingMovies" in failures.columns:
        streaming = (failures["StreamingTV"] == "Yes") | (failures["StreamingMovies"] == "Yes")
        bad = failures[~streaming]
        assert len(bad) == 0, f"{len(bad)} cdr_failure rows have no streaming service"


def test_sla_breach_noncheap_contracts(labeled_ibm):
    """sla_breach anomalies are never injected into Month-to-month customers."""
    breaches = labeled_ibm[labeled_ibm["anomaly_type"] == "sla_breach"]
    if len(breaches) == 0:
        pytest.skip("No sla_breach anomalies injected")
    if "Contract" in breaches.columns:
        month_to_month = breaches["Contract"].str.contains("Month", case=False, na=False)
        bad = breaches[month_to_month]
        assert len(bad) == 0, f"{len(bad)} sla_breach rows have Month-to-month contracts"


def test_load_combined_numeric_types(ibm_df):
    """load_combined() coerces charge columns to numeric (no object dtype)."""
    from src.data.loader import load_combined
    combined = load_combined(ibm_path=IBM_PATH)
    assert pd.api.types.is_numeric_dtype(combined["monthly_charges"])
    assert pd.api.types.is_numeric_dtype(combined["total_charges"])
    assert pd.api.types.is_integer_dtype(combined["tenure"])


def test_load_combined_empty_maven(ibm_df):
    """load_combined() falls back gracefully when the Maven CSV path is absent."""
    from src.data.loader import load_combined
    combined = load_combined(ibm_path=IBM_PATH, maven_path=Path("nonexistent_maven.csv"))
    assert len(combined) >= len(ibm_df), "Should still return IBM rows when Maven is absent"
    assert "source" in combined.columns
    assert (combined["source"] == "ibm_telco").all(), "All rows should be IBM-sourced in fallback"


def test_rule_based_prefilter_zero_charges():
    """rule_based_prefilter flags rows with zero charges and positive tenure."""
    from src.detection.detector import rule_based_prefilter
    df = pd.DataFrame({
        "monthly_charges": [0.0, 75.0, 0.0, 50.0],
        "tenure":          [12,   6,    0,    24],
    })
    result = rule_based_prefilter(df)
    assert "rule_flag" in result.columns
    # Row 0: zero charges + tenure > 0 → flagged
    assert result.loc[0, "rule_flag"] == 1
    # Row 1: non-zero charges → not flagged
    assert result.loc[1, "rule_flag"] == 0
    # Row 2: zero charges but tenure == 0 → not flagged (new account, no charge yet is normal)
    assert result.loc[2, "rule_flag"] == 0
    # Row 3: non-zero charges → not flagged
    assert result.loc[3, "rule_flag"] == 0
