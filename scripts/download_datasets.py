"""
Download datasets for the Telecom Billing RCA project.
IBM Telco Churn dataset (REAL) from IBM's public GitHub repository.
Maven Telecom-style dataset (supplementary, synthetic).
"""
import os
import sys
import urllib.request
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_DATA_DIR, RANDOM_SEED

# Real IBM Telco Customer Churn dataset — public mirror on IBM's GitHub
IBM_TELCO_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d"
    "/master/data/Telco-Customer-Churn.csv"
)


def download_ibm_telco():
    """
    Download the REAL IBM Telco Customer Churn dataset (7,043 records).
    Source: IBM Sample Data Sets — hosted on IBM's public GitHub.
    Original: https://www.kaggle.com/datasets/blastchar/telco-customer-churn
    """
    output_path = RAW_DATA_DIR / "ibm_telco_churn.csv"
    if output_path.exists():
        print(f"IBM Telco dataset already exists at {output_path}")
        return

    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    print(f"Downloading REAL IBM Telco Customer Churn dataset from GitHub...")

    try:
        urllib.request.urlretrieve(IBM_TELCO_URL, str(output_path))
        df = pd.read_csv(output_path)
        print(f"IBM Telco dataset saved to {output_path} ({len(df)} records, REAL data)")
    except Exception as e:
        print(f"Download failed: {e}")
        raise


def download_maven_telecom():
    """Generate a supplementary Maven Analytics Telecom-style dataset (synthetic)."""
    output_path = RAW_DATA_DIR / "maven_telecom_churn.csv"
    if output_path.exists():
        print(f"Maven Telecom dataset already exists at {output_path}")
        return

    print("Generating Maven Telecom-style synthetic dataset...")
    rng = np.random.default_rng(RANDOM_SEED + 1)
    n = 6500

    df = pd.DataFrame({
        "Customer_ID": [f"MVN-{i:05d}" for i in range(n)],
        "Gender": rng.choice(["Male", "Female"], size=n),
        "Age": rng.integers(18, 80, size=n),
        "Married": rng.choice(["Yes", "No"], size=n),
        "Number_of_Dependents": rng.integers(0, 5, size=n),
        "City": rng.choice(["Los Angeles", "San Diego", "San Jose", "San Francisco", "Sacramento"], size=n),
        "Number_of_Referrals": rng.integers(0, 12, size=n),
        "Tenure_in_Months": rng.integers(1, 73, size=n),
        "Phone_Service": rng.choice(["Yes", "No"], size=n, p=[0.9, 0.1]),
        "Avg_Monthly_Long_Distance_Charges": np.round(rng.exponential(15, size=n), 2),
        "Internet_Service": rng.choice(["Yes", "No"], size=n, p=[0.78, 0.22]),
        "Internet_Type": rng.choice(["Fiber Optic", "DSL", "Cable", "None"], size=n),
        "Avg_Monthly_GB_Download": np.round(rng.exponential(20, size=n), 1),
        "Online_Security": rng.choice(["Yes", "No"], size=n),
        "Online_Backup": rng.choice(["Yes", "No"], size=n),
        "Device_Protection_Plan": rng.choice(["Yes", "No"], size=n),
        "Premium_Tech_Support": rng.choice(["Yes", "No"], size=n),
        "Streaming_TV": rng.choice(["Yes", "No"], size=n),
        "Streaming_Movies": rng.choice(["Yes", "No"], size=n),
        "Streaming_Music": rng.choice(["Yes", "No"], size=n),
        "Unlimited_Data": rng.choice(["Yes", "No"], size=n),
        "Contract": rng.choice(["Month-to-Month", "One Year", "Two Year"], size=n),
        "Paperless_Billing": rng.choice(["Yes", "No"], size=n),
        "Payment_Method": rng.choice(["Credit Card", "Bank Withdrawal", "Mailed Check"], size=n),
        "Monthly_Charge": np.round(rng.normal(65, 30, size=n).clip(18, 120), 2),
        "Total_Charges": np.round(rng.normal(2000, 1500, size=n).clip(0, 8000), 2),
        "Total_Extra_Data_Charges": np.round(rng.exponential(10, size=n), 2),
        "Total_Long_Distance_Charges": np.round(rng.exponential(200, size=n), 2),
        "Total_Revenue": np.round(rng.normal(3000, 2000, size=n).clip(0, 12000), 2),
        "Customer_Status": rng.choice(["Stayed", "Churned", "Joined"], size=n, p=[0.73, 0.17, 0.10]),
        "Churn_Category": rng.choice(["Competitor", "Dissatisfaction", "Attitude", "Price", "Other", "No Churn"], size=n),
    })

    df.to_csv(output_path, index=False)
    print(f"Maven Telecom-style dataset saved to {output_path} ({len(df)} records)")


if __name__ == "__main__":
    download_ibm_telco()
    download_maven_telecom()

    # Augment IBM Telco to ~35K records
    from src.data.augmentor import augment_and_save
    augment_and_save(target_size=35_000)

    print("\nAll datasets ready!")
