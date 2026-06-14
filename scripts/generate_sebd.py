"""
Generate Synthetic Enterprise Billing Dataset (SEBD).
Takes an internal billing CSV, removes all real identifiers, renames fields.
Run once: python scripts/generate_sebd.py --input <path> --output data/raw/sebd.csv
Output CSV is safe to commit. Source CSV must never be committed.
"""
import argparse
import pandas as pd
import numpy as np
from pathlib import Path


FIELD_RENAME = {
    "BGW_RECORD_ID":        "TXN_ID",
    "ENTERPRISE":           "ACC_CODE",
    "HVS_LICENSE":          "SVC_SKU",
    "SUBACCOUNT":           "SUB_ACCOUNT_ID",
    "LICENSE_COUNT":        "UNIT_COUNT",
    "LICENSE_COUNT_DETAIL": "BILLABLE_UNIT_COUNT",
    "BILLING_ACTIVE":       "ACCOUNT_ACTIVE",
    "DEVICE_BILLING_TYPE":  "SUBSCRIPTION_STATE",
    "ENTERPRISE_GROUP":     "SEGMENT",
    "STATUS":               "PROC_STATUS",
    "ERROR_DESCRIPTION":    "FAULT_CODE",
    "COMPARE_COUNT":        "PREV_UNIT_COUNT",
    "COMPARE_DATE":         "PREV_BILLING_DATE",
    "SOURCE":               "INPUT_SOURCE",
    "UNIQUE_ID":            "SERVICE_KEY",
    "RATE":                 "BILLING_RATE",
    "ENCRYPTED":            "DATA_FLAG",
    "XML_GROUP":            "CONFIG_GROUP",
}

FAULT_CODE_RENAME = {
    "LicenseEmptyOrE911":               "UNIT_EMPTY_FAULT",
    "BillingActiveNotTrue":             "INACTIVE_ACCT_FAULT",
    "EnterpriseGroupIsNotApplicable":   "SEGMENT_ROUTING_FAULT",
    "PBI_NOT_FOUND":                    "SKU_MISSING_FAULT",
    "0005-Sub Account is inactive":     "SUBACCT_INACTIVE_FAULT",
    "0006-Sub Account type is invalid": "SUBACCT_TYPE_FAULT",
}

SEGMENT_RENAME = {
    "MASS MARKET/FILTER": "SEGMENT_A",
    "MASS MARKET":        "SEGMENT_B",
    "CALNET":             "SEGMENT_C",
    "CANCELLED":          "SEGMENT_D",
    "FLORIDA":            "SEGMENT_E",
    "MASS MARKET/EGW":    "SEGMENT_F",
    "MASS MARKET/CUSTOM": "SEGMENT_G",
    "HVS LITE":           "SEGMENT_H",
    "FED/GOV":            "SEGMENT_I",
}


def anonymise(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    df = df.rename(columns=FIELD_RENAME)

    if "ACC_CODE" in df.columns:
        enterprises = df["ACC_CODE"].dropna().unique()
        enc_map = {e: f"ACC-{i:04d}" for i, e in enumerate(sorted(enterprises))}
        df["ACC_CODE"] = df["ACC_CODE"].map(enc_map)

    if "SVC_SKU" in df.columns:
        skus = df["SVC_SKU"].dropna().unique()
        sku_map = {s: f"SKU-{i:04d}" for i, s in enumerate(sorted(skus))}
        df["SVC_SKU"] = df["SVC_SKU"].map(sku_map)

    if "SUB_ACCOUNT_ID" in df.columns:
        subs = df["SUB_ACCOUNT_ID"].dropna().unique()
        sub_map = {s: f"SUB-{i:06d}" for i, s in enumerate(sorted(subs))}
        df["SUB_ACCOUNT_ID"] = df["SUB_ACCOUNT_ID"].map(sub_map)

    if "SERVICE_KEY" in df.columns:
        df["SERVICE_KEY"] = df["SERVICE_KEY"].apply(
            lambda x: "+".join([f"ANON{i:04d}" for i in range(len(str(x).split("+")))]) if pd.notna(x) else x
        )

    if "FAULT_CODE" in df.columns:
        df["FAULT_CODE"] = df["FAULT_CODE"].map(
            lambda x: FAULT_CODE_RENAME.get(x, x) if pd.notna(x) else x
        )

    if "SEGMENT" in df.columns:
        df["SEGMENT"] = df["SEGMENT"].map(
            lambda x: SEGMENT_RENAME.get(x, "SEGMENT_OTHER") if pd.notna(x) else x
        )

    df["TXN_ID"] = range(1, len(df) + 1)

    return df


def main():
    parser = argparse.ArgumentParser(description="Anonymise internal billing CSV → SEBD")
    parser.add_argument("--input",  required=True, help="Path to internal billing CSV")
    parser.add_argument("--output", default="data/raw/sebd.csv")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"Loading {args.input}...")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} records, {len(df.columns)} columns")

    df_anon = anonymise(df, seed=args.seed)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df_anon.to_csv(args.output, index=False)
    print(f"SEBD saved to {args.output} ({len(df_anon)} records)")
    print("Safe to commit. No real identifiers remain.")


if __name__ == "__main__":
    main()
