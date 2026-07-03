"""
Live Monitoring page — view every UI inference logged to inferences.db.
Showcases "production-readiness" telemetry for the thesis viva.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from src.utils.inference_log import fetch_recent, stats

st.set_page_config(page_title="Live Monitoring", page_icon="📈", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    .page-header {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 2rem 2.5rem; border-radius: 12px; color: white;
        margin-bottom: 1.5rem;
    }
    .page-header h2 { color: white !important; margin: 0; font-size: 1.8rem; }
    .page-header p { color: #e0ffe0 !important; margin: 0.3rem 0 0 0; font-size: 1.1rem; }
    div[data-testid="stMetric"] {
        background: #1e1e2f; border: 1px solid #333; border-radius: 10px; padding: 12px 16px;
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
    st.page_link("pages/4_📊_Experiment_Results.py", label="📊  Experiment Results")
    st.page_link("pages/5_📈_Live_Monitoring.py", label="📈  Live Monitoring")

st.markdown("""
<div class="page-header">
    <h2>📈 Live Inference Monitoring</h2>
    <p>Every RCA generation is logged to SQLite — view recent calls, latency, and per-type stats</p>
</div>
""", unsafe_allow_html=True)

# Refresh control
col_a, col_b = st.columns([1, 6])
with col_a:
    if st.button("🔄 Refresh", width="stretch"):
        st.rerun()
with col_b:
    st.caption("Data source: `inferences.db` (SQLite). Logged from Upload→Detect and RCA Viewer pages.")

# Aggregate stats
s = stats()
total = s["total"]
avg_lat = s["avg_latency_ms"]

# Extended telemetry (tokens, review rate, provider events) — best-effort
_tok_total, _review_rate, _prov = None, None, {}
try:
    from src.utils.inference_log import _conn as _ilog_conn, provider_stats
    with _ilog_conn() as _c:
        _row = _c.execute(
            "SELECT SUM(prompt_tokens), SUM(completion_tokens), "
            "AVG(CASE WHEN review_required IS NOT NULL THEN review_required END) "
            "FROM inferences").fetchone()
        if _row:
            _p, _co, _rr = _row
            if _p or _co:
                _tok_total = (_p or 0) + (_co or 0)
            _review_rate = _rr
    _prov = provider_stats()
except Exception:
    pass

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.metric("Total Inferences", f"{total:,}")
with m2:
    st.metric("Avg Latency", f"{avg_lat:.0f} ms" if avg_lat else "—")
with m3:
    st.metric("Anomaly Types Seen", len(s["by_type"]))
with m4:
    st.metric("Total Tokens", f"{_tok_total:,}" if _tok_total else "—",
              help="Prompt + completion tokens across all logged inferences")
with m5:
    st.metric("Review-Required Rate",
              f"{_review_rate:.1%}" if _review_rate is not None else "—",
              help="Share of RCAs the Critic flagged as low-confidence "
                   "(possible false positives routed to manual review)")

if _prov:
    with st.expander("🛡️ Provider Resilience (LLM router events)"):
        _rows = []
        for _group, _events in _prov.items():
            _ok = _events.get("success", 0)
            _fail = sum(v for k, v in _events.items() if k != "success")
            _rows.append({
                "Provider group": _group,
                "Success": _ok,
                "Rate-limit": _events.get("rate_limit", 0),
                "Timeout": _events.get("timeout", 0),
                "Other errors": _events.get("error", 0),
                "Success rate": f"{_ok / max(_ok + _fail, 1):.1%}",
            })
        st.dataframe(pd.DataFrame(_rows), hide_index=True, width="stretch")

if total == 0:
    st.info("No inferences logged yet. Run an RCA from the **🔍 RCA Viewer** page to populate this dashboard.")
    st.stop()

st.markdown("### Per-type performance")
by_type_df = pd.DataFrame(s["by_type"])
if not by_type_df.empty:
    by_type_df["avg_latency_ms"] = by_type_df["avg_latency_ms"].round(0)
    st.dataframe(by_type_df, width="stretch", hide_index=True)

st.markdown("### Recent inferences (last 50)")
recent = fetch_recent(50)
if recent:
    df = pd.DataFrame(recent)
    # Order columns nicely
    cols = [c for c in [
        "timestamp", "anomaly_id", "anomaly_type", "severity",
        "latency_ms", "confidence", "provider", "model", "source", "root_cause"
    ] if c in df.columns]
    df = df[cols]
    if "latency_ms" in df:
        df["latency_ms"] = df["latency_ms"].round(0)
    if "confidence" in df:
        df["confidence"] = df["confidence"].round(3)
    if "root_cause" in df:
        df["root_cause"] = df["root_cause"].astype(str).str.slice(0, 120) + "..."
    st.dataframe(df, width="stretch", hide_index=True, height=480)
else:
    st.info("No rows.")

st.markdown("---")
st.caption(
    "💡 This page demonstrates **observability** for production deployments — "
    "every inference is auditable, latency is tracked, and per-anomaly-type performance "
    "can be compared over time. Backing store: lightweight SQLite (`inferences.db`)."
)
