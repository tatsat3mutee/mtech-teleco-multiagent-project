"""
Synthetic anomaly injection into telecom billing datasets.
Implements 5 anomaly types with seed-controlled reproducibility.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import RANDOM_SEED, ANOMALY_RATIOS, PROCESSED_DATA_DIR


def inject_zero_billing(df: pd.DataFrame, rng: np.random.Generator, ratio: float) -> pd.DataFrame:
    """Set monthly charges to 0 for random active customers (dual-schema aware)."""
    charge_col = "monthly_charges" if "monthly_charges" in df.columns else "MonthlyCharges"
    candidates = df[df[charge_col] > 0].index.tolist()
    n = min(int(len(df) * ratio), len(candidates))
    if n == 0:
        return df
    selected = rng.choice(candidates, size=n, replace=False)
    df.loc[selected, charge_col] = 0.0
    df.loc[selected, "anomaly_type"] = "zero_billing"
    df.loc[selected, "is_anomaly"] = 1
    return df


def inject_duplicate_charges(df: pd.DataFrame, rng: np.random.Generator, ratio: float) -> pd.DataFrame:
    """Duplicate billing rows with doubled charges."""
    n = int(len(df) * ratio)
    selected_idx = rng.choice(df.index.tolist(), size=n, replace=False)
    duplicates = df.loc[selected_idx].copy()
    duplicates["MonthlyCharges"] = duplicates["MonthlyCharges"] * 2
    duplicates["anomaly_type"] = "duplicate_charge"
    duplicates["is_anomaly"] = 1
    duplicates.index = range(len(df), len(df) + len(duplicates))
    df = pd.concat([df, duplicates], ignore_index=True)
    return df


def inject_usage_spike(df: pd.DataFrame, rng: np.random.Generator, ratio: float) -> pd.DataFrame:
    """Multiply charges by 10x — only for internet service customers (not 'No')."""
    charge_col = "monthly_charges" if "monthly_charges" in df.columns else "MonthlyCharges"
    total_col = "total_charges" if "total_charges" in df.columns else "TotalCharges"
    inet_col = "internet_service" if "internet_service" in df.columns else "InternetService"

    base = df[df["is_anomaly"] == 0]
    if inet_col in df.columns:
        candidates = base[
            ~base[inet_col].isin(["No", "None", "no", "none"])
        ].index.tolist()
        if not candidates:
            candidates = base.index.tolist()
    else:
        candidates = base.index.tolist()

    n = min(int(len(df) * ratio), len(candidates))
    if n == 0:
        return df
    selected = rng.choice(candidates, size=n, replace=False)
    df.loc[selected, charge_col] = df.loc[selected, charge_col] * 10
    if total_col in df.columns:
        df.loc[selected, total_col] = df.loc[selected, total_col] * 5
    df.loc[selected, "anomaly_type"] = "usage_spike"
    df.loc[selected, "is_anomaly"] = 1
    return df


def inject_cdr_failure(df: pd.DataFrame, rng: np.random.Generator, ratio: float) -> pd.DataFrame:
    """Introduce NaN charges — only for streaming service customers."""
    total_col = "total_charges" if "total_charges" in df.columns else "TotalCharges"
    stream_col = "streaming_flag" if "streaming_flag" in df.columns else None

    base = df[df["is_anomaly"] == 0]
    if stream_col and stream_col in df.columns:
        candidates = base[base[stream_col] == 1].index.tolist()
    elif "StreamingTV" in df.columns:
        candidates = base[
            (base["StreamingTV"] == "Yes") | (base.get("StreamingMovies", pd.Series()) == "Yes")
        ].index.tolist()
    else:
        candidates = base.index.tolist()

    if not candidates:
        candidates = base.index.tolist()

    n = min(int(len(df) * ratio), len(candidates))
    if n == 0:
        return df
    selected = rng.choice(candidates, size=n, replace=False)
    if total_col in df.columns:
        df.loc[selected, total_col] = np.nan
    df.loc[selected, "anomaly_type"] = "cdr_failure"
    df.loc[selected, "is_anomaly"] = 1
    return df


def inject_sla_breach(df: pd.DataFrame, rng: np.random.Generator, ratio: float) -> pd.DataFrame:
    """
    Set charges to P95×1.5 cap — only for non-Month-to-month contract customers.
    Fixed cap (not random) so the breach threshold is deterministic and testable.
    """
    charge_col = "monthly_charges" if "monthly_charges" in df.columns else "MonthlyCharges"
    contract_col = "contract" if "contract" in df.columns else "Contract"

    p95 = df[charge_col].quantile(0.95)
    sla_cap = p95 * 1.5

    base = df[df["is_anomaly"] == 0]
    if contract_col in df.columns:
        candidates = base[
            ~base[contract_col].str.contains("Month", case=False, na=False)
        ].index.tolist()
        if not candidates:
            candidates = base.index.tolist()
    else:
        candidates = base.index.tolist()

    n = min(int(len(df) * ratio), len(candidates))
    if n == 0:
        return df
    selected = rng.choice(candidates, size=n, replace=False)
    df.loc[selected, charge_col] = sla_cap
    df.loc[selected, "anomaly_type"] = "sla_breach"
    df.loc[selected, "is_anomaly"] = 1
    return df


def inject_all_anomalies(
    df: pd.DataFrame,
    seed: int = RANDOM_SEED,
    ratios: dict = None,
) -> pd.DataFrame:
    """
    Inject all 5 anomaly types into the dataset.
    Returns DataFrame with 'is_anomaly' and 'anomaly_type' columns.
    """
    if ratios is None:
        ratios = ANOMALY_RATIOS

    rng = np.random.default_rng(seed)

    # Initialize anomaly columns
    df = df.copy()
    df["is_anomaly"] = 0
    df["anomaly_type"] = "normal"

    # Inject in order
    df = inject_zero_billing(df, rng, ratios["zero_billing"])
    df = inject_duplicate_charges(df, rng, ratios["duplicate_charge"])
    df = inject_usage_spike(df, rng, ratios["usage_spike"])
    df = inject_cdr_failure(df, rng, ratios["cdr_failure"])
    df = inject_sla_breach(df, rng, ratios["sla_breach"])

    return df


def create_labeled_dataset(df: pd.DataFrame = None, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Full pipeline: inject anomalies and save labeled dataset.
    If df is None, auto-loads IBM Telco + Maven combined dataset.
    """
    if df is None:
        from src.data.loader import load_ibm_telco
        df = load_ibm_telco()
    labeled_df = inject_all_anomalies(df, seed=seed)

    # Save
    output_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
    labeled_df.to_csv(output_path, index=False)
    print(f"Labeled dataset saved to {output_path}")
    print(f"Total records: {len(labeled_df)}")
    print(f"Anomalies: {labeled_df['is_anomaly'].sum()} ({labeled_df['is_anomaly'].mean()*100:.1f}%)")
    print(f"\nAnomaly type distribution:")
    print(labeled_df["anomaly_type"].value_counts())

    return labeled_df


if __name__ == "__main__":
    from loader import load_ibm_telco
    df = load_ibm_telco()
    create_labeled_dataset(df)
