"""
Upload & Detect Page — Load billing data and detect anomalies.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from config import PROCESSED_DATA_DIR, RAW_DATA_DIR

st.set_page_config(page_title="Upload & Detect", page_icon="📊", layout="wide")

# ── Custom CSS ──
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    .main .block-container { font-size: 1.05rem; }
    h3 { font-size: 1.5rem !important; }
    .page-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .page-header h2 { color: white !important; margin: 0; font-size: 1.8rem; }
    .page-header p { color: #e0e0e0 !important; margin: 0.3rem 0 0 0; font-size: 1.1rem; }
    div[data-testid="stMetric"] {
        background: #1e1e2f;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label { color: #a0a0b0 !important; font-size: 0.95rem !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.6rem !important; }
    .info-box {
        background: #1e1e2f;
        border-left: 4px solid #667eea;
        padding: 1rem 1.2rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
        color: #e0e0e0;
    }
    .info-box strong { color: #ffffff; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 📡 Telecom RCA")
    st.markdown("**Multi-Agent RAG System**")
    st.caption("Autonomous Root Cause Analysis for Billing Anomalies")
    st.markdown("---")
    st.page_link("app.py", label="🏠  Home")
    st.page_link("pages/1_📊_Upload_Detect.py", label="📊  Upload & Detect")
    st.page_link("pages/2_🔍_RCA_Viewer.py", label="🔍  RCA Viewer")
    st.page_link("pages/3_📚_Knowledge_Base.py", label="📚  Knowledge Base")
    st.page_link("pages/4_📊_Experiment_Results.py", label="📊  Experiment Results")
    st.page_link("pages/5_📈_Live_Monitoring.py", label="📈  Live Monitoring")
    st.markdown("---")
    st.caption("MTech Thesis — Tatsat Pandey | 2026")

st.markdown("""
<div class="page-header">
    <h2>📊 Upload & Detect Anomalies</h2>
    <p>Load the IBM Telco billing dataset and run anomaly detection</p>
</div>
""", unsafe_allow_html=True)

# ── Data Loading ──
df = None
labeled_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
augmented_path = RAW_DATA_DIR / "ibm_telco_augmented.csv"
raw_path = RAW_DATA_DIR / "ibm_telco_churn.csv"

if labeled_path.exists():
    df = pd.read_csv(labeled_path)
    st.success(f"✅ Loaded **{len(df):,}** records from labeled dataset.")
elif augmented_path.exists():
    df = pd.read_csv(augmented_path)
    st.info(f"Loaded {len(df):,} augmented records. Run anomaly injection below to create labeled data.")
elif raw_path.exists():
    df = pd.read_csv(raw_path)
    st.info(f"Loaded {len(df):,} raw records. Run anomaly injection below to create labeled data.")
else:
    st.markdown("""
    <div class="info-box">
        <strong>No dataset found.</strong> Click below to download the IBM Telco dataset and augment to ~35K records.
    </div>
    """, unsafe_allow_html=True)
    if st.button("⬇️  Download & Augment Dataset", type="primary"):
        with st.spinner("Downloading IBM Telco dataset and augmenting to ~35K records..."):
            from scripts.download_datasets import download_ibm_telco, download_maven_telecom
            download_ibm_telco()
            download_maven_telecom()
            from src.data.augmentor import augment_and_save
            augment_and_save()
            st.success("Dataset downloaded and augmented! Refreshing...")
            st.rerun()

if df is not None:
    st.markdown("---")

    # ── Data Overview ──
    st.markdown("### Data Overview")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Records", f"{len(df):,}")
    with c2:
        st.metric("Features", len(df.columns))
    with c3:
        if "is_anomaly" in df.columns:
            st.metric("Anomalies", f"{int(df['is_anomaly'].sum()):,}")
        else:
            st.metric("Anomalies", "—")
    with c4:
        if "anomaly_type" in df.columns:
            n_types = df["anomaly_type"].nunique() - (1 if "normal" in df["anomaly_type"].values else 0)
            st.metric("Anomaly Types", n_types)
        else:
            st.metric("Anomaly Types", "—")

    with st.expander("Preview Data Sample"):
        st.dataframe(df.head(20), width='stretch')

    # ── Anomaly Injection ──
    if "is_anomaly" not in df.columns:
        st.markdown("---")
        st.markdown("### 💉 Inject Anomalies for Evaluation")
        st.caption("Injects 5 anomaly types (duplicate charge, CDR failure, usage spike, SLA breach, zero billing) into real billing records for evaluation.")
        if st.button("▶️  Inject Anomalies", type="primary"):
            with st.spinner("Injecting anomalies into billing records..."):
                from src.data.anomaly_injector import inject_all_anomalies
                df = inject_all_anomalies(df)
                df.to_csv(PROCESSED_DATA_DIR / "anomalies_labeled.csv", index=False)
                st.success(f"Injected {int(df['is_anomaly'].sum()):,} anomalies across 5 types.")
                st.rerun()

    # ── Anomaly Detection ──
    st.markdown("---")
    st.markdown("### 🔍 Run Anomaly Detection")

    col_a, col_b = st.columns([1, 2])
    with col_a:
        method = st.selectbox("Detection Method", ["isolation_forest"])
    with col_b:
        st.markdown("")  # visual spacer
        st.markdown("")
        detect_button = st.button("🚀  Run Detection", type="primary", use_container_width=True)

    if detect_button:
        with st.spinner("Running anomaly detection..."):
            from src.detection.detector import BillingAnomalyDetector

            detector = BillingAnomalyDetector(method=method)
            required_cols = ["tenure", "MonthlyCharges", "TotalCharges"]
            missing = [c for c in required_cols if c not in df.columns]

            if missing:
                st.error(f"Missing required columns: {missing}")
            else:
                detector.fit(df)
                result_df = detector.predict(df)
                detector.save()

                detected_count = int(result_df["predicted_anomaly"].sum())
                st.success(f"Detection complete — found **{detected_count:,}** anomalies.")

                if "is_anomaly" in df.columns:
                    metrics = detector.evaluate(df)
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Precision", f"{metrics['precision']:.3f}")
                    with m2:
                        st.metric("Recall", f"{metrics['recall']:.3f}")
                    with m3:
                        st.metric("F1-Score", f"{metrics['f1_score']:.3f}")
                    with m4:
                        if "roc_auc" in metrics:
                            st.metric("ROC-AUC", f"{metrics['roc_auc']:.3f}")

                st.markdown("#### Detected Anomalies")
                anomalies_df = result_df[result_df["predicted_anomaly"] == 1]

                if "anomaly_type" in anomalies_df.columns:
                    st.bar_chart(anomalies_df["anomaly_type"].value_counts())

                    # Plotly heatmap: anomaly_type × Contract distribution
                    if "Contract" in anomalies_df.columns:
                        try:
                            import plotly.express as px
                            import pandas as _pd
                            pivot = _pd.crosstab(
                                anomalies_df["anomaly_type"],
                                anomalies_df["Contract"],
                            )
                            fig = px.imshow(
                                pivot,
                                title="Anomaly Type × Contract Distribution",
                                color_continuous_scale="Blues",
                                text_auto=True,
                                labels={"x": "Contract Type", "y": "Anomaly Type", "color": "Count"},
                            )
                            fig.update_layout(height=350, margin=dict(t=50, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                        except ImportError:
                            pass

                display_cols = ["customerID", "MonthlyCharges", "TotalCharges", "tenure", "anomaly_confidence", "predicted_anomaly"]
                if "anomaly_type" in anomalies_df.columns:
                    display_cols.append("anomaly_type")

                st.dataframe(
                    anomalies_df[display_cols].head(50).sort_values("anomaly_confidence", ascending=False),
                    width='stretch',
                )

                st.session_state["detected_anomalies"] = anomalies_df
                st.session_state["full_dataset"] = result_df

    # ── Anomaly Distribution ──
    if "anomaly_type" in df.columns:
        st.markdown("---")
        st.markdown("### 📊 Anomaly Distribution")
        st.bar_chart(df["anomaly_type"].value_counts())

        # Heatmap: anomaly_type × Contract for the full labeled dataset
        if "Contract" in df.columns:
            try:
                import plotly.express as px
                pivot = pd.crosstab(
                    df[df["anomaly_type"] != "normal"]["anomaly_type"],
                    df[df["anomaly_type"] != "normal"]["Contract"],
                )
                if not pivot.empty:
                    fig = px.imshow(
                        pivot,
                        title="Anomaly Type × Contract Distribution (Full Dataset)",
                        color_continuous_scale="Teal",
                        text_auto=True,
                        labels={"x": "Contract Type", "y": "Anomaly Type", "color": "Count"},
                    )
                    fig.update_layout(height=350, margin=dict(t=50, b=20))
                    st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                pass

        with st.expander("Per-Type Statistics"):
            for atype in sorted(df["anomaly_type"].unique()):
                if atype == "normal":
                    continue
                subset = df[df["anomaly_type"] == atype]
                st.markdown(f"**{atype}** — {len(subset)} records")
                st.dataframe(subset[["MonthlyCharges", "TotalCharges", "tenure"]].describe().round(2))
