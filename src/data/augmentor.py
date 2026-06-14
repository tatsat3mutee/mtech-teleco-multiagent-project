"""
Data augmentation for the IBM Telco dataset.
Uses statistical oversampling with controlled Gaussian noise to expand
the dataset while preserving distributional properties.

Technique: ROSE-style (Random Over-Sampling Examples) —
    for each new record, sample a real record and add column-wise
    Gaussian noise scaled to per-column standard deviation.

This is a standard, legitimate augmentation method widely used in
imbalanced-data and small-dataset ML research.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import RANDOM_SEED, RAW_DATA_DIR

# Columns that should stay unchanged when adding noise
CATEGORICAL_COLS = [
    "customerID", "gender", "SeniorCitizen", "Partner", "Dependents",
    "PhoneService", "MultipleLines", "InternetService", "OnlineSecurity",
    "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV",
    "StreamingMovies", "Contract", "PaperlessBilling", "PaymentMethod",
    "Churn",
]

# Numeric columns that receive Gaussian noise
NUMERIC_COLS = ["tenure", "MonthlyCharges", "TotalCharges"]

# Noise scale (fraction of per-column std): 0.05 = 5% of std
NOISE_SCALE = 0.05


def augment_ibm_telco(
    df: pd.DataFrame,
    target_size: int = 35_000,
    noise_scale: float = NOISE_SCALE,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """
    Augment the IBM Telco dataset to `target_size` records.

    For each new record:
     1. Randomly sample an existing record (with replacement).
     2. Keep all categorical columns intact.
     3. Add N(0, sigma * noise_scale) noise to numeric columns.
     4. Clip numeric columns to valid ranges.
     5. Assign a new unique customerID.

    Returns the combined (original + augmented) DataFrame.
    """
    rng = np.random.default_rng(seed)
    n_original = len(df)
    n_needed = max(0, target_size - n_original)

    if n_needed == 0:
        return df.copy()

    # Compute per-column std for noise
    stds = {}
    for col in NUMERIC_COLS:
        if col in df.columns:
            stds[col] = df[col].std()

    # Sample base records
    sample_idx = rng.choice(n_original, size=n_needed, replace=True)
    augmented = df.iloc[sample_idx].copy().reset_index(drop=True)

    # Add Gaussian noise to numeric columns
    for col in NUMERIC_COLS:
        if col in augmented.columns and col in stds:
            noise = rng.normal(0, stds[col] * noise_scale, size=n_needed)
            augmented[col] = augmented[col].astype(float) + noise

    # Clip to valid ranges
    if "tenure" in augmented.columns:
        augmented["tenure"] = augmented["tenure"].clip(lower=0).round().astype(int)
    if "MonthlyCharges" in augmented.columns:
        augmented["MonthlyCharges"] = augmented["MonthlyCharges"].clip(lower=0).round(2)
    if "TotalCharges" in augmented.columns:
        augmented["TotalCharges"] = augmented["TotalCharges"].clip(lower=0).round(2)

    # Assign unique customerIDs
    augmented["customerID"] = [f"AUG-{i:06d}" for i in range(n_needed)]

    # Combine original + augmented
    combined = pd.concat([df, augmented], ignore_index=True)

    return combined


def augment_and_save(
    target_size: int = 35_000,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """Load IBM Telco, augment to target_size, save to raw dir."""
    from src.data.loader import load_ibm_telco

    df = load_ibm_telco()
    print(f"Original IBM Telco: {len(df):,} records")

    combined = augment_ibm_telco(df, target_size=target_size, seed=seed)
    output_path = RAW_DATA_DIR / "ibm_telco_augmented.csv"
    combined.to_csv(output_path, index=False)

    print(f"Augmented dataset: {len(combined):,} records → {output_path}")
    print(f"  Original: {len(df):,} | Augmented: {len(combined) - len(df):,}")
    return combined


if __name__ == "__main__":
    augment_and_save()
