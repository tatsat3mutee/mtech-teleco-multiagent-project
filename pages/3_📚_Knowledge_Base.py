"""
Knowledge Base Browser — Browse indexed documents and search the RAG corpus.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from config import RCA_PLAYBOOKS_DIR, CORPUS_DIR

st.set_page_config(page_title="Knowledge Base", page_icon="📚", layout="wide")

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
    st.page_link("pages/4_📊_Experiment_Results.py", label="📊  Experiment Results")
    st.page_link("pages/5_📈_Live_Monitoring.py", label="📈  Live Monitoring")
    st.markdown("---")
    st.caption("MTech Thesis — Tatsat Pandey | 2026")

st.markdown("""
<div class="page-header">
    <h2>📚 Knowledge Base Browser</h2>
    <p>Browse and search the RAG corpus used by the Investigator Agent</p>
</div>
""", unsafe_allow_html=True)

# ── KB Status ──
try:
    from src.rag.knowledge_base import KnowledgeBase, build_knowledge_base
    kb = KnowledgeBase()
    kb_count = kb.count
except Exception as e:
    kb_count = 0
    st.warning(f"Knowledge base not initialized: {e}")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Total Chunks", kb_count)
with c2:
    playbook_count = len(list(RCA_PLAYBOOKS_DIR.glob("*.md"))) if RCA_PLAYBOOKS_DIR.exists() else 0
    st.metric("Playbooks", playbook_count)
with c3:
    try:
        sources = kb.get_all_sources()
        st.metric("Source Documents", len(sources))
    except Exception:
        st.metric("Source Documents", 0)

# ── Build/Rebuild ──
st.markdown("---")
b1, b2 = st.columns(2)
with b1:
    if st.button("🔨  Build Knowledge Base", type="primary", width="stretch"):
        with st.spinner("Building knowledge base..."):
            kb = build_knowledge_base(force_rebuild=False)
            st.success(f"Ready — {kb.count} chunks indexed.")
            st.rerun()
with b2:
    if st.button("🔄  Rebuild from Scratch", width="stretch"):
        with st.spinner("Rebuilding knowledge base..."):
            kb = build_knowledge_base(force_rebuild=True)
            st.success(f"Rebuilt — {kb.count} chunks indexed.")
            st.rerun()

# ── Search ──
st.markdown("---")
st.markdown("### Search Knowledge Base")

s1, s2 = st.columns([3, 1])
with s1:
    search_query = st.text_input("Search query", placeholder="e.g., zero billing root cause CDR failure")
with s2:
    search_k = st.slider("Results", 1, 20, 5)

if search_query:
    if kb_count > 0:
        results = kb.search(search_query, n_results=search_k)
        st.markdown(f"**{len(results)} results**")
        for i, r in enumerate(results, 1):
            pct = r["relevance_score"] * 100
            with st.expander(f"#{i} — {r['source']}  ({pct:.1f}% relevance)", expanded=(i <= 2)):
                st.markdown(f"**Source:** `{r['source']}` | **Score:** {r['relevance_score']:.4f}")
                st.write(r["text"])
                if r.get("metadata"):
                    st.json(r["metadata"])
    else:
        st.warning("Knowledge base is empty. Click **Build Knowledge Base** first.")

# ── Playbooks ──
st.markdown("---")
st.markdown("### RCA Playbooks")

if RCA_PLAYBOOKS_DIR.exists():
    playbooks = sorted(RCA_PLAYBOOKS_DIR.glob("*.md"))
    if playbooks:
        for pb in playbooks:
            with st.expander(f"📄 {pb.stem.replace('_', ' ').title()}"):
                st.markdown(pb.read_text(encoding="utf-8"))
    else:
        st.info("No playbooks found. Run system setup first.")
else:
    st.info("Playbooks directory not found.")

# ── Indexed Sources ──
st.markdown("---")
st.markdown("### Indexed Sources")
if kb_count > 0:
    try:
        sources = kb.get_all_sources()
        for src in sources:
            st.markdown(f"- 📄 `{src}`")
    except Exception as e:
        st.warning(f"Could not retrieve sources: {e}")
else:
    st.info("No documents indexed yet.")
