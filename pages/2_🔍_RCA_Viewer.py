"""
RCA Viewer Page — Generate and view Root Cause Analysis reports.
"""
import streamlit as st
import pandas as pd
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from config import PROCESSED_DATA_DIR

st.set_page_config(page_title="RCA Viewer", page_icon="🔍", layout="wide")

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
    st.page_link("pages/4_�_Experiment_Results.py", label="📊  Experiment Results")
    st.page_link("pages/5_�📈_Live_Monitoring.py", label="📈  Live Monitoring")
    st.markdown("---")
    st.caption("MTech Thesis — Tatsat Pandey | 2026")

st.markdown("""
<div class="page-header">
    <h2>🔍 Root Cause Analysis Viewer</h2>
    <p>Select an anomaly and generate a detailed RCA report using the multi-agent pipeline</p>
</div>
""", unsafe_allow_html=True)

# ── Load Anomalies ──
anomalies_df = st.session_state.get("detected_anomalies", None)

if anomalies_df is None:
    labeled_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
    if labeled_path.exists():
        df = pd.read_csv(labeled_path)
        anomalies_df = df[df["is_anomaly"] == 1] if "is_anomaly" in df.columns else df.head(20)
        st.info("Loaded anomalies from labeled dataset. Run detection on **Upload & Detect** for live results.")
    else:
        st.warning("No anomalies available. Go to **Upload & Detect** first.")
        st.stop()

st.markdown(f"**{len(anomalies_df):,} anomalies** available for analysis")

# ── Filters ──
st.markdown("---")
f1, f2 = st.columns([1, 1])
with f1:
    if "anomaly_type" in anomalies_df.columns:
        types = ["All"] + sorted([t for t in anomalies_df["anomaly_type"].unique() if t != "normal"])
        selected_type = st.selectbox("Filter by Type", types)
        if selected_type != "All":
            anomalies_df = anomalies_df[anomalies_df["anomaly_type"] == selected_type]
with f2:
    max_display = st.slider("Max records", 5, 50, 20)

# Display table
display_cols = ["customerID", "MonthlyCharges", "TotalCharges", "tenure"]
if "anomaly_type" in anomalies_df.columns:
    display_cols.append("anomaly_type")
if "anomaly_confidence" in anomalies_df.columns:
    display_cols.append("anomaly_confidence")
available_cols = [c for c in display_cols if c in anomalies_df.columns]
st.dataframe(anomalies_df[available_cols].head(max_display), width='stretch')

# ── RCA Generation ──
st.markdown("---")
st.markdown("### Generate RCA Report")

anomaly_options = []
for idx, row in anomalies_df.head(max_display).iterrows():
    cid = row.get("customerID", f"Row-{idx}")
    atype = row.get("anomaly_type", "unknown")
    charges = row.get("MonthlyCharges", 0)
    anomaly_options.append(f"{cid} | {atype} | ${charges:.2f}/mo")

if anomaly_options:
    sel_col, btn_col = st.columns([3, 1])
    with sel_col:
        selected = st.selectbox("Select anomaly to investigate", anomaly_options)
    with btn_col:
        st.markdown("")
        st.markdown("")
        generate_btn = st.button("🚀  Generate RCA", type="primary", use_container_width=True)

    selected_idx = anomaly_options.index(selected)
    selected_row = anomalies_df.head(max_display).iloc[selected_idx]

    # Selected anomaly details
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("Customer", selected_row.get("customerID", "N/A"))
    with d2:
        st.metric("Type", selected_row.get("anomaly_type", "unknown"))
    with d3:
        st.metric("Monthly Charges", f"${selected_row.get('MonthlyCharges', 0):.2f}")
    with d4:
        st.metric("Tenure", f"{selected_row.get('tenure', 0)} mo")

    if generate_btn:
        start_time = time.time()

        anomaly_record = {
            "account_id": str(selected_row.get("customerID", f"ROW-{selected_idx}")),
            "anomaly_type": str(selected_row.get("anomaly_type",
                                selected_row.get("estimated_type", "unknown"))),
            "confidence": float(selected_row.get("anomaly_confidence", 0.5)),
            "monthly_charges": float(selected_row.get("MonthlyCharges", 0)),
            "total_charges": float(selected_row.get("TotalCharges", 0))
                             if pd.notna(selected_row.get("TotalCharges")) else 0.0,
            "tenure": int(selected_row.get("tenure", 0)),
            "features": {
                col: str(selected_row[col]) for col in ["Contract", "InternetService", "PaymentMethod"]
                if col in selected_row.index
            },
        }

        STEP_LABELS = {
            "investigator": "🔍 Investigator — querying knowledge base",
            "reasoner":     "🧠 Reasoner — generating hypothesis",
            "critic":       "⚖️  Critic — verifying grounding",
            "reporter":     "📄 Reporter — generating RCA report",
        }

        import os as _os
        api_base = _os.environ.get("RCA_API_URL", "http://localhost:8000")

        def _run_via_api(anomaly: dict) -> dict:
            """Submit to FastAPI and poll with step progress indicator."""
            import requests as _req
            resp = _req.post(f"{api_base}/rca/run", json=anomaly, timeout=10)
            resp.raise_for_status()
            job_id = resp.json()["job_id"]

            with st.status("Running multi-agent pipeline...", expanded=True) as status_box:
                seen_steps = set()
                for _ in range(300):   # 5-minute timeout
                    time.sleep(1)
                    poll = _req.get(f"{api_base}/rca/status/{job_id}", timeout=5)
                    poll.raise_for_status()
                    data = poll.json()

                    for step in data.get("completed_steps", []):
                        if step not in seen_steps:
                            status_box.write(STEP_LABELS.get(step, step))
                            seen_steps.add(step)

                    if data["status"] == "complete":
                        status_box.update(label="Pipeline complete!", state="complete")
                        return data["result"]
                    if data["status"] == "failed":
                        raise RuntimeError(data.get("error", "Pipeline failed"))

            raise TimeoutError("Pipeline did not complete within 5 minutes")

        def _run_direct(anomaly: dict) -> dict:
            """Fallback: run pipeline in-process with manual step indicators."""
            from src.agents.graph import run_pipeline as _rp
            with st.status("Running multi-agent pipeline...", expanded=True) as status_box:
                status_box.write(STEP_LABELS["investigator"])
                _r = _rp(anomaly)
                status_box.write(STEP_LABELS["reasoner"])
                status_box.write(STEP_LABELS["critic"])
                status_box.write(STEP_LABELS["reporter"])
                status_box.update(label="Pipeline complete!", state="complete")
            return _r

        try:
            # Try FastAPI first; fall back to direct execution
            try:
                import requests as _req
                _req.get(f"{api_base}/health", timeout=2)
                result = _run_via_api(anomaly_record)
            except Exception:
                result = _run_direct(anomaly_record)

            elapsed = (time.time() - start_time) * 1000
            rca = result.get("rca_report", {})

            if rca:
                st.success(f"RCA generated in {elapsed:.0f}ms")

                # Log to SQLite for live monitoring dashboard
                try:
                    from src.utils.inference_log import log_inference
                    log_inference(
                        anomaly_id=rca.get("anomaly_id", anomaly_record.get("account_id", "N/A")),
                        anomaly_type=anomaly_record.get("anomaly_type", "unknown"),
                        severity=rca.get("severity", "N/A"),
                        root_cause=rca.get("root_cause", "N/A"),
                        confidence=anomaly_record.get("confidence", 0.0),
                        latency_ms=elapsed,
                        source="ui_single",
                    )
                except Exception:
                    pass

                st.markdown("---")
                st.markdown("## 📋 RCA Report")

                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    st.metric("Anomaly ID", rca.get("anomaly_id", "N/A"))
                with r2:
                    st.metric("Type", rca.get("anomaly_type", "N/A"))
                with r3:
                    severity = rca.get("severity", "N/A")
                    icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")
                    st.metric("Severity", f"{icon} {severity}")
                with r4:
                    st.metric("Confidence", f"{rca.get('confidence_score', 0):.0%}")

                st.markdown("#### Root Cause")
                st.info(rca.get("root_cause", "No root cause determined."))

                st.markdown("#### Summary")
                st.write(rca.get("summary", "No summary available."))

                col_ev, col_act = st.columns(2)
                with col_ev:
                    st.markdown("#### Supporting Evidence")
                    for i, ev in enumerate(rca.get("supporting_evidence", []), 1):
                        st.markdown(f"{i}. {ev}")
                with col_act:
                    st.markdown("#### Recommended Actions")
                    for i, act in enumerate(rca.get("recommended_actions", []), 1):
                        st.markdown(f"{i}. {act}")

                # SWARM routing metadata
                routing = result.get("routing_explanation", "")
                if routing:
                    with st.expander("🔀 SWARM Routing Decision"):
                        st.info(routing)

                # Retrieved docs
                docs = result.get("retrieved_docs", [])
                if docs:
                    st.markdown("#### Retrieved Documents")
                    for doc in docs:
                        with st.expander(f"📄 {doc.get('source', 'Unknown')} — relevance {doc.get('relevance_score', 0):.2f}"):
                            st.write(doc.get("text", ""))

                # Raw JSON & Metadata
                tab_json, tab_meta, tab_export = st.tabs(["Raw JSON", "Pipeline Metadata", "Export"])
                with tab_json:
                    st.json(rca)
                with tab_meta:
                    st.write(f"**Status:** {result.get('pipeline_status', 'N/A')}")
                    st.write(f"**Latency:** {elapsed:.0f}ms")
                    st.write(f"**Retrieval Strategy:** {result.get('retrieval_strategy', 'N/A')}")
                    st.write(f"**Retrieval Query:** {result.get('retrieval_query', 'N/A')}")
                    st.write(f"**Documents Retrieved:** {result.get('retrieval_count', 0)}")
                with tab_export:
                    st.markdown("**Export RCA Report as PDF**")
                    try:
                        from fpdf import FPDF
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Helvetica", "B", 14)
                        pdf.cell(0, 10,
                                 f"RCA Report — {rca.get('anomaly_type', 'N/A')} "
                                 f"[{rca.get('anomaly_id', 'N/A')}]",
                                 ln=True)
                        pdf.set_font("Helvetica", size=10)
                        pdf.cell(0, 8, f"Severity: {rca.get('severity', 'N/A')} | "
                                       f"Confidence: {rca.get('confidence_score', 0):.0%} | "
                                       f"Latency: {elapsed:.0f}ms",
                                 ln=True)
                        pdf.ln(4)
                        for label, key in [
                            ("Root Cause", "root_cause"),
                            ("Summary", "summary"),
                        ]:
                            pdf.set_font("Helvetica", "B", 11)
                            pdf.cell(0, 8, label, ln=True)
                            pdf.set_font("Helvetica", size=10)
                            pdf.multi_cell(0, 6, str(rca.get(key, "N/A")))
                            pdf.ln(2)
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.cell(0, 8, "Supporting Evidence", ln=True)
                        pdf.set_font("Helvetica", size=10)
                        for i, ev in enumerate(rca.get("supporting_evidence", []), 1):
                            pdf.multi_cell(0, 6, f"{i}. {ev}")
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.cell(0, 8, "Recommended Actions", ln=True)
                        pdf.set_font("Helvetica", size=10)
                        for i, act in enumerate(rca.get("recommended_actions", []), 1):
                            pdf.multi_cell(0, 6, f"{i}. {act}")
                        pdf_bytes = bytes(pdf.output())
                        fname = f"rca_{rca.get('anomaly_id', 'report')}.pdf"
                        st.download_button(
                            "⬇️  Download PDF",
                            data=pdf_bytes,
                            file_name=fname,
                            mime="application/pdf",
                        )
                    except ImportError:
                        st.info("PDF export requires fpdf2. Install: `pip install fpdf2`")
                        st.download_button(
                            "⬇️  Download JSON",
                            data=json.dumps(rca, indent=2),
                            file_name=f"rca_{rca.get('anomaly_id', 'report')}.json",
                            mime="application/json",
                        )

                st.session_state["last_rca_result"] = result
            else:
                st.error("Pipeline completed but no RCA report was generated.")

        except Exception as e:
            st.error(f"Pipeline error: {str(e)}")
            st.info("Make sure the knowledge base is built. Run: `python src/cli.py --setup`")

    # ── Batch RCA ──
    st.markdown("---")
    st.markdown("### Batch RCA Generation")

    b1, b2 = st.columns([1, 2])
    with b1:
        batch_limit = st.number_input("Anomalies to process", min_value=1, max_value=50, value=5)
    with b2:
        st.markdown("")
        st.markdown("")
        batch_btn = st.button("📦  Run Batch RCA", type="primary", use_container_width=True)

    if batch_btn:
        with st.spinner(f"Processing {batch_limit} anomalies..."):
            from src.agents.graph import run_pipeline

            batch_results = []
            progress = st.progress(0)

            for i, (idx, row) in enumerate(anomalies_df.head(batch_limit).iterrows()):
                progress.progress((i + 1) / batch_limit)
                record = {
                    "account_id": str(row.get("customerID", f"ROW-{idx}")),
                    "anomaly_type": str(row.get("anomaly_type", "unknown")),
                    "confidence": float(row.get("anomaly_confidence", 0.5)),
                    "monthly_charges": float(row.get("MonthlyCharges", 0)),
                    "total_charges": float(row.get("TotalCharges", 0)) if pd.notna(row.get("TotalCharges")) else 0.0,
                    "tenure": int(row.get("tenure", 0)),
                    "features": {},
                }
                try:
                    result = run_pipeline(record)
                    rca = result.get("rca_report", {})
                    batch_results.append({
                        "Account": record["account_id"],
                        "Type": record["anomaly_type"],
                        "Severity": rca.get("severity", "N/A"),
                        "Root Cause": rca.get("root_cause", "N/A")[:100],
                        "Latency": f"{result.get('latency_ms', 0):.0f}ms",
                    })
                    try:
                        from src.utils.inference_log import log_inference
                        log_inference(
                            anomaly_id=record["account_id"],
                            anomaly_type=record["anomaly_type"],
                            severity=rca.get("severity", "N/A"),
                            root_cause=rca.get("root_cause", "N/A"),
                            confidence=record.get("confidence", 0.0),
                            latency_ms=float(result.get("latency_ms", 0)),
                            source="ui_batch",
                        )
                    except Exception:
                        pass
                except Exception as e:
                    batch_results.append({
                        "Account": record["account_id"],
                        "Type": record["anomaly_type"],
                        "Severity": "ERROR",
                        "Root Cause": str(e)[:100],
                        "Latency": "—",
                    })

            st.success(f"Processed {len(batch_results)} anomalies.")
            st.dataframe(pd.DataFrame(batch_results), width='stretch')
