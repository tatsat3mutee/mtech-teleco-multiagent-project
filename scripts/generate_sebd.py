"""
Generate the Synthetic Enterprise Billing Dataset (SEBD).

SEBD is a fully synthetic dataset modeled on a *generic* enterprise-billing
schema (transactions, accounts, service SKUs, segments, fault codes). It uses
no production data and contains no real identifiers — every value is generated
from a seeded RNG, so the output is deterministic and safe to commit.

Run once:
    python scripts/generate_sebd.py --output data/raw/sebd.csv --rows 54000
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# Neutral, generic billing schema — no proprietary names.
SEGMENTS = [f"SEGMENT_{c}" for c in "ABCDEFGHI"]

FAULT_CODES = [
    "UNIT_EMPTY_FAULT",
    "INACTIVE_ACCT_FAULT",
    "SEGMENT_ROUTING_FAULT",
    "SKU_MISSING_FAULT",
    "SUBACCT_INACTIVE_FAULT",
    "SUBACCT_TYPE_FAULT",
]

PROC_STATUS = ["PROCESSED", "PENDING", "FAILED", "RETRIED"]
INPUT_SOURCES = ["BATCH", "STREAM", "MANUAL"]
SUBSCRIPTION_STATES = ["ACTIVE", "SUSPENDED", "CANCELLED", "TRIAL"]


def generate(rows: int = 54000, seed: int = 42) -> pd.DataFrame:
    """Build a synthetic enterprise-billing table with a realistic schema."""
    rng = np.random.default_rng(seed)

    n_accounts = max(1, rows // 60)
    n_skus = max(1, rows // 300)
    n_subaccounts = max(1, rows // 6)

    acc_codes = np.array([f"ACC-{i:04d}" for i in range(n_accounts)])
    skus = np.array([f"SKU-{i:04d}" for i in range(n_skus)])
    sub_accounts = np.array([f"SUB-{i:06d}" for i in range(n_subaccounts)])

    unit_count = rng.integers(1, 500, size=rows)
    # Most billable units track unit_count; a minority diverge (billing faults).
    drift = rng.normal(0, 5, size=rows).astype(int)
    billable_unit_count = np.clip(unit_count + drift, 0, None)

    prev_unit_count = np.clip(
        unit_count + rng.normal(0, 8, size=rows).astype(int), 0, None
    )

    start = np.datetime64("2025-01-01")
    billing_date = start + rng.integers(0, 365, size=rows).astype("timedelta64[D]")
    prev_billing_date = billing_date - np.timedelta64(30, "D")

    account_active = rng.choice([True, False], size=rows, p=[0.92, 0.08])
    # Faults appear on a minority of records; rest are clean (None fault).
    has_fault = rng.random(rows) < 0.12
    fault = np.where(has_fault, rng.choice(FAULT_CODES, size=rows), None)

    df = pd.DataFrame(
        {
            "TXN_ID": np.arange(1, rows + 1),
            "ACC_CODE": rng.choice(acc_codes, size=rows),
            "SVC_SKU": rng.choice(skus, size=rows),
            "SUB_ACCOUNT_ID": rng.choice(sub_accounts, size=rows),
            "UNIT_COUNT": unit_count,
            "BILLABLE_UNIT_COUNT": billable_unit_count,
            "ACCOUNT_ACTIVE": account_active,
            "SUBSCRIPTION_STATE": rng.choice(SUBSCRIPTION_STATES, size=rows),
            "SEGMENT": rng.choice(SEGMENTS, size=rows),
            "PROC_STATUS": rng.choice(PROC_STATUS, size=rows, p=[0.8, 0.1, 0.07, 0.03]),
            "FAULT_CODE": fault,
            "PREV_UNIT_COUNT": prev_unit_count,
            "PREV_BILLING_DATE": prev_billing_date,
            "BILLING_DATE": billing_date,
            "INPUT_SOURCE": rng.choice(INPUT_SOURCES, size=rows),
            "BILLING_RATE": np.round(rng.uniform(0.5, 25.0, size=rows), 2),
            "CONFIG_GROUP": rng.integers(1, 20, size=rows),
        }
    )

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate the synthetic enterprise-billing dataset (SEBD)"
    )
    parser.add_argument("--output", default="data/raw/sebd.csv")
    parser.add_argument("--rows", type=int, default=54000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = generate(rows=args.rows, seed=args.seed)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"SEBD saved to {args.output} ({len(df)} records, {len(df.columns)} columns)")
    print("Fully synthetic. No real identifiers, no production data.")


if __name__ == "__main__":
    main()
