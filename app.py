"""
Streamlit Dashboard — Backstage-style service catalog home page.
Multi-Agent RAG System for Telecom Billing RCA.
"""
import streamlit as st
import sys
import json as _json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))


def load_secrets() -> None:
    """Push Streamlit Cloud secrets into os.environ for downstream config.py reads."""
    import os
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
        for key in ("GROQ_API_KEY", "OPENROUTER_API_KEY"):
            if key in secrets and not os.environ.get(key):
                os.environ[key] = secrets[key]
    except Exception:
        pass  # Not on Streamlit Cloud or secrets not configured — env vars take precedence


def ensure_knowledge_base() -> None:
    """Build ChromaDB knowledge base on cold start if it doesn't exist yet."""
    from pathlib import Path as _Path
    chroma_dir = _Path(__file__).parent / "chroma_db"
    if chroma_dir.exists() and any(chroma_dir.iterdir()):
        return
    try:
        from src.rag.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        kb.build_from_corpus()
        st.toast("Knowledge base built successfully.", icon="✅")
    except Exception as exc:
        st.warning(f"Knowledge base cold-start failed: {exc}")


load_secrets()
ensure_knowledge_base()


st.set_page_config(
    page_title="Telecom RCA Platform · Multi-Agent RAG",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────────────────────────
# Backstage-inspired CSS
# ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stHeader"] { background: #14171c !important; border-bottom: 1px solid #2f3640; }
    [data-testid="stToolbar"] button { color: #a0a8b3 !important; }

    :root {
        --bg-primary: #1b1f23;
        --bg-card: #232931;
        --bg-card-hover: #2a313a;
        --border: #2f3640;
        --accent: #36baa2;
        --accent-2: #ff9800;
        --accent-3: #5b8def;
        --text-primary: #f5f6fa;
        --text-secondary: #a0a8b3;
        --text-muted: #6b7280;
    }

    .stApp, body { background-color: var(--bg-primary) !important; color: var(--text-primary) !important; }
    .stApp p, .stApp li, .stApp span, .stApp div, .stApp label { color: var(--text-primary); }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text-primary) !important; }
    .stApp a { color: var(--accent-3); }
    .stApp code { background: #14171c; color: var(--accent); padding: 0.1rem 0.3rem; border-radius: 3px; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }

    section[data-testid="stSidebar"] {
        background-color: #14171c;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--accent) !important;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-bottom: 0;
    }
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        background: transparent;
        border-radius: 6px;
        padding: 0.5rem 0.75rem;
        color: var(--text-secondary) !important;
        font-size: 0.95rem;
    }
    section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
        background: var(--bg-card);
        color: var(--text-primary) !important;
    }

    .bs-hero {
        background: linear-gradient(135deg, #1b1f23 0%, #2a313a 100%);
        border: 1px solid var(--border);
        border-left: 4px solid var(--accent);
        border-radius: 8px;
        padding: 1.75rem 2rem;
        margin-bottom: 1.5rem;
    }
    .bs-hero-kind {
        color: var(--accent);
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 0.4rem;
    }
    .bs-hero-title {
        color: #ffffff !important;
        font-size: 1.85rem;
        font-weight: 700;
        margin: 0 0 0.4rem 0;
        line-height: 1.2;
        text-shadow: none;
    }
    .bs-hero-subtitle {
        color: #d1d5db !important;
        font-size: 1.0rem;
        margin: 0;
        line-height: 1.5;
    }
    .bs-hero-pills { margin-top: 1rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }

    .bs-pill {
        display: inline-block;
        background: rgba(54, 186, 162, 0.12);
        color: var(--accent);
        border: 1px solid rgba(54, 186, 162, 0.4);
        padding: 0.2rem 0.7rem;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        font-family: 'SF Mono', Consolas, monospace;
    }
    .bs-pill-warn { background: rgba(255,152,0,0.12); color: var(--accent-2); border-color: rgba(255,152,0,0.4); }
    .bs-pill-info { background: rgba(91,141,239,0.12); color: var(--accent-3); border-color: rgba(91,141,239,0.4); }
    .bs-pill-mute { background: var(--bg-card); color: var(--text-secondary); border: 1px solid var(--border); }

    .bs-section {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        margin: 1.6rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--border);
    }

    .bs-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        height: 100%;
        transition: border-color 0.15s;
    }
    .bs-card:hover { border-color: var(--accent); }
    .bs-card-icon { font-size: 1.4rem; margin-bottom: 0.4rem; }
    .bs-card-title {
        color: var(--text-primary);
        font-size: 1.05rem;
        font-weight: 600;
        margin: 0 0 0.3rem 0;
    }
    .bs-card-kind {
        color: var(--text-muted);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .bs-card-desc {
        color: var(--text-secondary);
        font-size: 0.9rem;
        line-height: 1.45;
        margin-bottom: 0.6rem;
    }
    .bs-card-meta {
        font-size: 0.78rem;
        color: var(--text-muted);
        font-family: 'SF Mono', Consolas, monospace;
        border-top: 1px solid var(--border);
        padding-top: 0.5rem;
        margin-top: 0.4rem;
    }

    div[data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
    }
    div[data-testid="stMetric"] label {
        color: var(--text-muted) !important;
        font-size: 0.75rem !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-size: 1.7rem !important;
        font-weight: 700;
    }

    div[data-testid="stHorizontalBlock"] { align-items: stretch !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div { height: 100%; }

    .bs-link {
        display: inline-block;
        background: var(--bg-card);
        border: 1px solid var(--border);
        color: var(--text-primary) !important;
        padding: 0.55rem 1rem;
        border-radius: 6px;
        font-size: 0.88rem;
        font-weight: 500;
        text-decoration: none !important;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
        transition: all 0.15s;
    }
    .bs-link:hover { border-color: var(--accent); color: var(--accent) !important; }
    .bs-link-primary { background: var(--accent); color: #0d1116 !important; border-color: var(--accent); }
    .bs-link-primary:hover { background: #2a9885; color: #0d1116 !important; border-color: #2a9885; }

    .bs-activity {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.7rem 1rem;
        margin-bottom: 0.4rem;
        font-family: 'SF Mono', Consolas, monospace;
        font-size: 0.85rem;
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }
    .bs-activity-time { color: var(--text-muted); min-width: 10rem; }
    .bs-activity-id { color: var(--accent); min-width: 8rem; }
    .bs-activity-type { color: var(--accent-3); min-width: 7rem; }
    .bs-activity-lat { color: var(--text-secondary); margin-left: auto; }

    div[data-baseweb="tab-list"] {
        background: transparent;
        border-bottom: 1px solid var(--border);
        gap: 0.3rem;
    }
    button[data-baseweb="tab"] {
        color: var(--text-muted) !important;
        background: transparent !important;
        border-radius: 4px 4px 0 0 !important;
        padding: 0.5rem 1.1rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────
# Sidebar
# ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## TELECOM RCA")
    st.caption("Multi-Agent RAG Platform")
    st.markdown("---")
    st.page_link("app.py",                              label="🏠  Overview")
    st.page_link("pages/1_📊_Upload_Detect.py",         label="📊  Detect")
    st.page_link("pages/2_🔍_RCA_Viewer.py",            label="🔍  Investigate")
    st.page_link("pages/3_📚_Knowledge_Base.py",        label="📚  Knowledge")
    st.page_link("pages/4_📊_Experiment_Results.py",    label="📊  Experiments")
    st.page_link("pages/5_📈_Live_Monitoring.py",       label="📈  Monitoring")
    st.markdown("---")

    # ── System Status ──────────────────────────────────────────────────
    st.markdown("**System Status**")

    # Active LLM provider
    try:
        from src.agents.llm_utils import get_active_provider
        active_provider = get_active_provider()
        provider_icon = "🟢" if active_provider != "none" else "🔴"
        st.caption(f"LLM {provider_icon}  `{active_provider}`")
    except Exception:
        st.caption("LLM ⚪  `unavailable`")

    # KB chunk count
    try:
        from src.rag.knowledge_base import KnowledgeBase as _KB
        _kb_count = _KB().count
        st.caption(f"KB 🗂️  `{_kb_count} chunks`" if _kb_count else "KB ⚪  `not built`")
    except Exception:
        st.caption("KB ⚪  `unavailable`")

    # Redis cache status
    try:
        from src.utils.cache import cache_available
        redis_ok = cache_available()
        st.caption(f"Redis {'🟢' if redis_ok else '⚪'}  `{'connected' if redis_ok else 'offline'}`")
    except Exception:
        st.caption("Redis ⚪  `unavailable`")

    # Demo mode indicator
    try:
        from src.demo.demo_loader import is_demo_mode
        if is_demo_mode():
            st.caption("Mode 🎭  `demo (no API keys)`")
        else:
            st.caption("Mode 🚀  `live`")
    except Exception:
        pass

    st.markdown("---")
    st.caption("**Owner**  ·  Tatsat Pandey")
    st.caption("**Program**  ·  MTech DSE · 2026")
    st.caption("**Lifecycle**  ·  `research prototype`")

# ────────────────────────────────────────────────────────────────────
# Runtime data
# ────────────────────────────────────────────────────────────────────
try:
    from src.rag.knowledge_base import KnowledgeBase
    kb_count = KnowledgeBase().count
except Exception:
    kb_count = 0

try:
    import pandas as pd
    from config import PROCESSED_DATA_DIR
    labeled_path = PROCESSED_DATA_DIR / "anomalies_labeled.csv"
    if labeled_path.exists():
        df = pd.read_csv(labeled_path)
        total_records = len(df)
        anomaly_count = int(df["is_anomaly"].sum()) if "is_anomaly" in df.columns else 0
    else:
        total_records, anomaly_count = 0, 0
except Exception:
    total_records, anomaly_count = 0, 0

try:
    from config import MODELS_DIR, LLM_PROVIDER, LLM_MODEL
    model_exists = (MODELS_DIR / "isolation_forest_model.joblib").exists()
except Exception:
    model_exists = False
    LLM_PROVIDER, LLM_MODEL = "unknown", "unknown"

try:
    from src.utils.inference_log import fetch_recent, stats as infer_stats
    recent_inferences = fetch_recent(8)
    infer_summary = infer_stats()
except Exception:
    recent_inferences, infer_summary = [], {"total": 0, "avg_latency_ms": None}

# ────────────────────────────────────────────────────────────────────
# Hero
# ────────────────────────────────────────────────────────────────────
status_pill = '<span class="bs-pill">● operational</span>' if model_exists else '<span class="bs-pill bs-pill-warn">● detector not trained</span>'

st.markdown(f"""
<div class="bs-hero">
    <div class="bs-hero-kind">PLATFORM · System</div>
    <h1 class="bs-hero-title">Multi-Agent RAG for Telecom Billing RCA</h1>
    <p class="bs-hero-subtitle">
        Autonomous diagnosis of billing anomalies — usage spikes, zero-billing, duplicate charges,
        CDR failures, SLA breaches — using a LangGraph-orchestrated pipeline of four specialized
        LLM agents grounded by vector retrieval and GraphRAG over a curated telecom knowledge base.
    </p>
    <div class="bs-hero-pills">
        {status_pill}
        <span class="bs-pill bs-pill-info">llm · {LLM_PROVIDER}/{LLM_MODEL}</span>
        <span class="bs-pill bs-pill-mute">version · 1.0.0</span>
        <span class="bs-pill bs-pill-mute">tier · 1</span>
        <span class="bs-pill bs-pill-mute">domain · telecom-billing</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Quick links — MLflow link only when running locally
import os as _os
_is_local = not _os.environ.get("STREAMLIT_RUNTIME_ENV") and "STREAMLIT_SHARING" not in _os.environ
_mlflow_link = '<a class="bs-link" href="http://127.0.0.1:5000" target="_blank">📊  MLflow experiments ↗</a>' if _is_local else ''
st.markdown(f"""
<a class="bs-link bs-link-primary" href="/RCA_Viewer" target="_self">▶  Run an investigation</a>
{_mlflow_link}
<a class="bs-link" href="https://github.com/tatsat3mutee/mtech-teleco-multiagent-project" target="_blank">⧉  Repository ↗</a>
<a class="bs-link" href="/Live_Monitoring" target="_self">📈  Live monitoring</a>
""", unsafe_allow_html=True)

# Health metrics
st.markdown('<div class="bs-section">System Health</div>', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.metric("KB Chunks", f"{kb_count:,}")
with c2: st.metric("Records Loaded", f"{total_records:,}")
with c3: st.metric("Anomalies", f"{anomaly_count:,}")
with c4: st.metric("Detector", "READY" if model_exists else "TRAIN")
with c5: st.metric("Inferences", f"{infer_summary['total']:,}")

# Service Catalog — agents
st.markdown('<div class="bs-section">Service Catalog · Agent Pipeline</div>', unsafe_allow_html=True)
cards = [
    {"icon": "🔎", "kind": "Component · Agent", "title": "Investigator",
     "desc": "Hybrid retriever (BM25 + dense + cross-encoder reranker) over a curated KB of RCA playbooks, SLA contracts, and historical incidents.",
     "meta": "owner: tatsat · stage: rag"},
    {"icon": "🧠", "kind": "Component · Agent", "title": "Reasoner",
     "desc": "Synthesizes retrieved context with anomaly features to produce structured root-cause hypotheses with explicit evidence chains and confidence scoring.",
     "meta": "owner: tatsat · stage: reasoning"},
    {"icon": "🛡️", "kind": "Component · Agent", "title": "Critic",
     "desc": "Independent validator that re-checks JSON schema, refusal patterns, and evidence-grounding before the report is published.",
     "meta": "owner: tatsat · stage: validation"},
    {"icon": "📋", "kind": "Component · Agent", "title": "Reporter",
     "desc": "Validates and emits machine-readable JSON RCA reports with severity, recommended actions, and audit metadata for downstream ticketing.",
     "meta": "owner: tatsat · stage: output"},
]
cols = st.columns(4)
for col, c in zip(cols, cards):
    with col:
        st.markdown(f"""
        <div class="bs-card">
            <div class="bs-card-icon">{c['icon']}</div>
            <div class="bs-card-kind">{c['kind']}</div>
            <div class="bs-card-title">{c['title']}</div>
            <div class="bs-card-desc">{c['desc']}</div>
            <div class="bs-card-meta">{c['meta']}</div>
        </div>
        """, unsafe_allow_html=True)

# Service Catalog — data + infra
st.markdown('<div class="bs-section">Service Catalog · Data & Infra</div>', unsafe_allow_html=True)
infra = [
    {"icon": "🗂", "kind": "Resource · Vector DB", "title": "ChromaDB",
     "desc": f"Embedding store backing the RAG retriever. {kb_count:,} chunks indexed via sentence-transformers (all-MiniLM-L6-v2).",
     "meta": "type: vector-store · backend: sqlite"},
    {"icon": "📦", "kind": "Resource · Dataset", "title": "Telco Billing Corpus",
     "desc": "IBM Telco (7K) + Maven Telecom (7K) + SEBD Enterprise Billing (54K). Labeled anomalies across 5 types.",
     "meta": "records: 68k · types: 5"},
    {"icon": "🤖", "kind": "Resource · ML Model", "title": "IsolationForest + Rule Pre-filter",
     "desc": "Unsupervised anomaly detector with rule-based pre-filter. Trained on tenure, monthly_charges, total_charges.",
     "meta": "framework: scikit-learn"},
    {"icon": "📊", "kind": "Resource · Tracking", "title": "MLflow",
     "desc": "Experiment tracking for every ablation run: metrics, params, artifacts. File-store at <code>mlruns/</code>.",
     "meta": "ui: localhost:5000"},
]
cols = st.columns(4)
for col, c in zip(cols, infra):
    with col:
        st.markdown(f"""
        <div class="bs-card">
            <div class="bs-card-icon">{c['icon']}</div>
            <div class="bs-card-kind">{c['kind']}</div>
            <div class="bs-card-title">{c['title']}</div>
            <div class="bs-card-desc">{c['desc']}</div>
            <div class="bs-card-meta">{c['meta']}</div>
        </div>
        """, unsafe_allow_html=True)

# Recent activity
st.markdown('<div class="bs-section">Recent Activity · Last 8 Inferences</div>', unsafe_allow_html=True)
if recent_inferences:
    for r in recent_inferences:
        ts = (r.get("timestamp", "") or "")[:19].replace("T", " ")
        st.markdown(f"""
        <div class="bs-activity">
            <span class="bs-activity-time">{ts}</span>
            <span class="bs-activity-id">{r.get('anomaly_id', '—')}</span>
            <span class="bs-activity-type">{r.get('anomaly_type', '—')}</span>
            <span>severity={r.get('severity', '—')}</span>
            <span class="bs-activity-lat">{(r.get('latency_ms') or 0):.0f} ms · {r.get('provider', '?')}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="bs-activity" style="justify-content: center; color: var(--text-muted);">
        No inferences yet — run one from <strong>🔍 Investigate</strong> to populate this feed.
    </div>
    """, unsafe_allow_html=True)

# Documentation tabs
st.markdown('<div class="bs-section">Documentation</div>', unsafe_allow_html=True)
tab_about, tab_arch, tab_stack, tab_results = st.tabs(["About", "Architecture", "Tech Stack", "Ablation Results"])

with tab_about:
    st.markdown("""
    **Problem.** Billing anomalies in telecom networks — usage spikes, zero-billing, duplicate charges,
    CDR failures, SLA breaches — are routinely *detected* but diagnosing the *root cause* remains a
    manual, time-intensive process requiring senior engineering expertise. This is the
    detection→resolution gap.

    **Solution.** A multi-agent RAG system that autonomously investigates each anomaly:
    an Investigator retrieves grounding context from a curated KB, a Reasoner synthesizes hypotheses
    with explicit evidence chains, a Critic checks grounding and consistency, and a Reporter emits
    validated JSON RCA reports.

    **Evaluation.** Five-config ablation (no-RAG, RAG-only, single-agent+RAG, multi-agent+RAG,
    multi-agent+GraphRAG), scored on ROUGE-L, BERTScore, type-accuracy, RAGAS-style metrics, and
    LLM-as-Judge. Statistical significance is assessed via bootstrap confidence intervals,
    paired-bootstrap, and Wilcoxon signed-rank testing.

    **Reproducibility.** Configurable OpenAI-compatible LLM backend (Groq/OpenRouter),
    file-backed MLflow tracking, deterministic seeded test set, and 87-test pytest suite.
    """)

with tab_arch:
    st.code("""
┌─────────────────────────────────────────────────────────────────┐
│  L5  UI & Monitoring          Streamlit + MLflow + SQLite       │
├─────────────────────────────────────────────────────────────────┤
│  L4  Agent Orchestration      LangGraph StateGraph              │
│      Investigator → Reasoner → Critic → Reporter                │
├─────────────────────────────────────────────────────────────────┤
│  L3  RAG Engine               Hybrid (BM25 + dense + reranker)  │
│                                ChromaDB · sentence-transformers │
├─────────────────────────────────────────────────────────────────┤
│  L2  Anomaly Detection        IsolationForest + Rule Pre-filter │
├─────────────────────────────────────────────────────────────────┤
│  L1  Data Ingestion           Pandas · NumPy · Augmentation     │
├─────────────────────────────────────────────────────────────────┤
│  L0  LLM Backend              Groq (primary) · OpenRouter (fallback)      │
│                                LiteLLM Router — auto rate-limit failover   │
└─────────────────────────────────────────────────────────────────┘
    """, language="text")

with tab_stack:
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("""
        | Component | Technology |
        |-----------|------------|
        | LLM (primary) | Groq · openai/gpt-oss-120b |
        | LLM (fallback) | OpenRouter · DeepSeek R1 / Llama 3.3 (free) |
        | Agents | LangGraph StateGraph |
        | Vector DB | ChromaDB (sqlite-backed) |
        | Embeddings | sentence-transformers (MiniLM-L6) |
        | Detection | scikit-learn (IsolationForest) |
        """)
    with t2:
        st.markdown("""
        | Component | Technology |
        |-----------|------------|
        | Tracking | MLflow (file-store) |
        | UI | Streamlit |
        | Monitoring | SQLite (`inferences.db`) |
        | Eval | ROUGE-L · BERTScore · LLM-Judge |
        | Stats | Paired-bootstrap · Wilcoxon |
        | Tests | pytest (116 tests) |
        """)

with tab_results:
    try:
        ablation_path = Path(__file__).parent / "ablation_results.json"
        if ablation_path.exists():
            with open(ablation_path) as f:
                abl = _json.load(f)
            st.markdown(f"**Model:** `{abl.get('model', 'N/A')}` · **Test set:** 15 anomalies · **Logged to:** MLflow")
            rows = []
            for cfg_key, cfg_data in abl["configs"].items():
                m = cfg_data["metrics"]
                rows.append({
                    "Config": cfg_data["description"],
                    "ROUGE-L": f"{m['rouge_l_f1']:.3f}",
                    "BERTScore": f"{m['bert_score_f1']:.3f}",
                    "Type Acc": f"{m['type_accuracy']:.0%}",
                    "Latency": f"{m['avg_latency_ms']:.0f}ms",
                })
            import pandas as _pd
            st.dataframe(_pd.DataFrame(rows), width='stretch', hide_index=True)
        else:
            st.info("Ablation results not available. Run `python run_ablation.py`.")
    except Exception as e:
        st.warning(f"Could not load ablation results: {e}")

