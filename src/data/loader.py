"""
Dataset loader for IBM Telco and Maven Telecom churn datasets.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import RAW_DATA_DIR, RANDOM_SEED


def load_ibm_telco(filepath: Path = None) -> pd.DataFrame:
    """Load and clean the IBM Telco Customer Churn dataset."""
    if filepath is None:
        filepath = RAW_DATA_DIR / "ibm_telco_churn.csv"

    if not filepath.exists():
        raise FileNotFoundError(
            f"IBM Telco dataset not found at {filepath}. "
            "Run `python scripts/download_datasets.py` first."
        )

    df = pd.read_csv(filepath)

    # Clean TotalCharges — contains spaces for new customers
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["TotalCharges"] = df["TotalCharges"].fillna(0.0)

    # Ensure numeric types
    df["MonthlyCharges"] = df["MonthlyCharges"].astype(float)
    df["tenure"] = df["tenure"].astype(int)
    df["SeniorCitizen"] = df["SeniorCitizen"].astype(int)

    # Encode Churn as binary
    df["Churn_Binary"] = (df["Churn"] == "Yes").astype(int)

    return df


def load_maven_telecom(filepath: Path = None) -> pd.DataFrame:
    """Load and clean the Maven Analytics Telecom Churn dataset."""
    if filepath is None:
        filepath = RAW_DATA_DIR / "maven_telecom_churn.csv"

    if not filepath.exists():
        raise FileNotFoundError(
            f"Maven Telecom dataset not found at {filepath}. "
            "Run `python scripts/download_datasets.py` first."
        )

    df = pd.read_csv(filepath)

    # Standardize column names
    df.columns = df.columns.str.strip().str.replace(" ", "_")

    # Handle missing values
    for col in df.select_dtypes(include=[np.number]).columns:
        df[col] = df[col].fillna(df[col].median())

    return df


def load_combined(
    ibm_path: Path = None,
    maven_path: Path = None,
    random_state: int = None,
) -> pd.DataFrame:
    """
    Load IBM Telco + Maven Analytics datasets and merge into one DataFrame.
    Harmonises column names so downstream code sees a unified schema.
    Returns ~14K rows with columns:
        customer_id, tenure, monthly_charges, total_charges, contract,
        internet_service, streaming_flag, churn, churn_reason, source
    """
    if random_state is None:
        random_state = RANDOM_SEED

    ibm = load_ibm_telco(ibm_path)

    # ── Normalise IBM columns ──────────────────────────────────────────────────
    ibm_norm = pd.DataFrame({
        "customer_id":      ibm["customerID"],
        "tenure":           ibm["tenure"],
        "monthly_charges":  ibm["MonthlyCharges"],
        "total_charges":    ibm["TotalCharges"],
        "contract":         ibm["Contract"],
        "internet_service": ibm["InternetService"],
        "streaming_flag":   (
            (ibm.get("StreamingTV", "") == "Yes") |
            (ibm.get("StreamingMovies", "") == "Yes")
        ).astype(int),
        "churn":            ibm["Churn_Binary"],
        "churn_reason":     np.nan,
        "source":           "ibm_telco",
    })

    # ── Normalise Maven columns (best-effort, tolerates missing cols) ──────────
    try:
        maven = load_maven_telecom(maven_path)
        maven_col_map = {
            "Customer_ID":        "customer_id",
            "Tenure_in_Months":   "tenure",
            "Monthly_Charge":     "monthly_charges",
            "Total_Charges":      "total_charges",
            "Contract":           "contract",
            "Internet_Type":      "internet_service",
            "Churn_Category":     "churn_reason",
            "Churn_Value":        "churn",
        }
        maven_norm = maven.rename(columns={
            k: v for k, v in maven_col_map.items() if k in maven.columns
        })
        # Ensure all required columns exist
        for col in ibm_norm.columns:
            if col not in maven_norm.columns:
                maven_norm[col] = np.nan
        maven_norm["source"] = "maven"
        maven_norm["streaming_flag"] = 0

        combined = pd.concat(
            [ibm_norm[ibm_norm.columns], maven_norm[ibm_norm.columns]],
            ignore_index=True,
        )
    except (FileNotFoundError, Exception):
        # Maven dataset not available — return IBM only
        combined = ibm_norm.copy()

    # ── Coerce numeric types ───────────────────────────────────────────────────
    combined["monthly_charges"] = pd.to_numeric(combined["monthly_charges"], errors="coerce").fillna(0.0)
    combined["total_charges"]   = pd.to_numeric(combined["total_charges"],   errors="coerce").fillna(0.0)
    combined["tenure"]          = pd.to_numeric(combined["tenure"],          errors="coerce").fillna(0).astype(int)
    combined["is_anomaly"]      = 0
    combined["anomaly_type"]    = "normal"

    return combined.reset_index(drop=True)


def load_sebd(filepath: Path = None) -> pd.DataFrame:
    """
    Load the Synthetic Enterprise Billing Dataset (SEBD).

    Maps SEBD columns to the normalised schema expected by the detector:
        tenure, monthly_charges, total_charges, customer_id, contract,
        internet_service, is_anomaly, anomaly_type, source

    SEBD anomalies are identified by PROC_STATUS == 'EXCLUDED' or 'FAILED'
    and FAULT_CODE being non-empty.
    """
    if filepath is None:
        filepath = RAW_DATA_DIR / "sebd.csv"

    if not filepath.exists():
        raise FileNotFoundError(
            f"SEBD dataset not found at {filepath}. "
            "Run `python scripts/generate_sebd.py` to create it."
        )

    df = pd.read_csv(filepath)

    # Map to normalised schema
    result = pd.DataFrame({
        "customer_id":      df["ACC_CODE"] + ":" + df["SUB_ACCOUNT_ID"],
        "tenure":           df["TENURE_MONTHS"].astype(int),
        "monthly_charges":  pd.to_numeric(df["MONTHLY_AMOUNT"], errors="coerce").fillna(0.0),
        "total_charges":    pd.to_numeric(df["TOTAL_BILLED"], errors="coerce").fillna(0.0),
        "contract":         df["SUBSCRIPTION_STATE"],
        "internet_service": df["SVC_SKU"],
        "streaming_flag":   0,
        "churn":            (df["SUBSCRIPTION_STATE"] == "CANCELLED").astype(int),
        "churn_reason":     df["FAULT_CODE"],
        "source":           "sebd",
    })

    # Mark anomalies: records with fault codes are anomalous
    result["is_anomaly"] = (df["FAULT_CODE"].fillna("").str.len() > 0).astype(int)
    result["anomaly_type"] = df["FAULT_CODE"].replace("", "normal").fillna("normal")

    # Map SEBD fault codes to pipeline anomaly types for agent routing
    fault_to_type = {
        "UNIT_EMPTY_FAULT":       "zero_billing",
        "INACTIVE_ACCT_FAULT":    "sla_breach",
        "SEGMENT_ROUTING_FAULT":  "usage_spike",
        "SKU_MISSING_FAULT":      "cdr_failure",
        "SUBACCT_INACTIVE_FAULT": "duplicate_charge",
        "SUBACCT_TYPE_FAULT":     "duplicate_charge",
    }
    result["anomaly_type"] = result["anomaly_type"].map(
        lambda x: fault_to_type.get(x, x)
    )

    # Preserve original SEBD columns for agent context
    result["fault_code"] = df["FAULT_CODE"].fillna("")
    result["segment"] = df["SEGMENT"]
    result["proc_status"] = df["PROC_STATUS"]
    result["unit_count"] = df["UNIT_COUNT"]
    result["billing_rate"] = df["BILLING_RATE"]
    result["account_active"] = df["ACCOUNT_ACTIVE"]

    return result.reset_index(drop=True)


def get_billing_features(df: pd.DataFrame, dataset_type: str = "ibm") -> pd.DataFrame:
    """Extract billing-relevant features for anomaly detection."""
    if dataset_type == "ibm":
        feature_cols = ["tenure", "MonthlyCharges", "TotalCharges"]

        # Encode categorical features relevant to billing
        billing_df = df[feature_cols].copy()

        # Derive features
        billing_df["charges_per_month"] = np.where(
            df["tenure"] > 0,
            df["TotalCharges"] / df["tenure"],
            df["MonthlyCharges"],
        )
        billing_df["tenure_bucket"] = pd.cut(
            df["tenure"], bins=[0, 12, 24, 48, 72, 100],
            labels=["0-12", "12-24", "24-48", "48-72", "72+"],
        )

        # Has active services indicator
        service_cols = [c for c in df.columns if "Service" in c or "service" in c]
        if service_cols:
            billing_df["active_services"] = (
                df[service_cols].apply(lambda x: x == "Yes").sum(axis=1)
            )
        else:
            billing_df["active_services"] = 1

        # Contract type encoding
        if "Contract" in df.columns:
            billing_df["contract_month"] = (df["Contract"] == "Month-to-month").astype(int)

        return billing_df

    elif dataset_type == "maven":
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        return df[numeric_cols].copy()

    else:
        raise ValueError(f"Unknown dataset_type: {dataset_type}")
