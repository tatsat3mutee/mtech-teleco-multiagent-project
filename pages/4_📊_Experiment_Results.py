"""
Experiment Results Page — Ablation study results viewer.
Data priority: results/ablation/summary.json (real ablation output) →
data/eval/mlflow_results.json (MLflow export) → illustrative placeholder.
Shows: ablation config table (Configs A–E per config.py ABLATION_CONFIGS),
RCA quality charts, latency chart, manual-RCA comparison.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

st.set_page_config(page_title="Experiment Results", page_icon="📊", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none !important; }
    .page-header {
        background: linear-gradient(135deg, #1a6b3c 0%, #2d9e6b 100%);
        padding: 2rem 2.5rem; border-radius: 12px;
        color: white; margin-bottom: 1.5rem;
    }
    .page-header h2 { color: white !important; margin: 0; }
    .page-header p { color: #d0f0e4 !important; margin: 0.3rem 0 0; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 📡 Telecom RCA")
    st.markdown("**Multi-Agent RAG System**")
    st.markdown("---")
    st.page_link("app.py",                              label="🏠  Home")
    st.page_link("pages/1_📊_Upload_Detect.py",         label="📊  Upload & Detect")
    st.page_link("pages/2_🔍_RCA_Viewer.py",            label="🔍  RCA Viewer")
    st.page_link("pages/3_📚_Knowledge_Base.py",        label="📚  Knowledge Base")
    st.page_link("pages/4_📊_Experiment_Results.py",    label="📊  Experiment Results")
    st.page_link("pages/5_📈_Live_Monitoring.py",       label="📈  Live Monitoring")
    st.markdown("---")
    st.caption("MTech Thesis — Tatsat Pandey | 2026")

st.markdown("""
<div class="page-header">
    <h2>📊 Experiment Results</h2>
    <p>Ablation study (Configs A–E) — LLM-Judge · RAGAS · BERTScore · ROUGE-L · Latency</p>
</div>
""", unsafe_allow_html=True)

ABLATION_SUMMARY_PATH = Path(__file__).parent.parent / "results/ablation/summary.json"
MLFLOW_RESULTS_PATH = Path(__file__).parent.parent / "data/eval/mlflow_results.json"

# Single source of truth: config.py ABLATION_CONFIGS keys → viva labels
CONFIG_DESCRIPTIONS = {
    "no_rag":           "Config A — Direct LLM (no RAG, no agents): what does the LLM know alone?",
    "cot_baseline":     "Config A2 — Few-shot Chain-of-Thought (no retrieval)",
    "react_baseline":   "Config A3 — ReAct loop (reason/act/observe + KB search)",
    "rag_only":         "Config B — RAG + LLM (retrieval, no agent decomposition)",
    "single_agent_rag": "Config C — Single Agent + RAG (orchestration, no role decomposition)",
    "multi_agent_rag":  "Config D — Multi-Agent + RAG (proposed 4-agent pipeline with Critic)",
    "graph_rag":        "Config E — Multi-Agent + GraphRAG (headline novelty: causal graph retrieval)",
}

MANUAL_RCA_MINUTES = (65, 120)  # industry manual-RCA baseline (DESIGN.md §1)


def _load_results() -> tuple[dict, str]:
    """Return (results, source). Priority: real ablation summary → MLflow export."""
    if ABLATION_SUMMARY_PATH.exists():
        try:
            with open(ABLATION_SUMMARY_PATH) as f:
                data = json.load(f)
            if data:
                return data, "ablation"
        except Exception:
            pass
    if MLFLOW_RESULTS_PATH.exists():
        try:
            with open(MLFLOW_RESULTS_PATH) as f:
                data = json.load(f)
            configs = data.get("ablation_configs", {})
            if configs:
                return {k: v.get("metrics", {}) for k, v in configs.items()}, "mlflow"
        except Exception:
            pass
    return {}, "none"


results, source = _load_results()

if source == "ablation":
    st.success(
        "Showing **real ablation results** from `results/ablation/summary.json`. "
        "Re-run `python run_ablation.py --full` (judge enabled by default) to refresh.",
        icon="✅",
    )
elif source == "mlflow":
    st.info("Showing MLflow-exported results from `data/eval/mlflow_results.json`.", icon="ℹ️")
else:
    st.warning(
        "No results found. Run `python run_ablation.py --quick` to generate "
        "`results/ablation/summary.json`.",
        icon="⚠️",
    )
    st.stop()

# ── Ablation Config Table ────────────────────────────────────────────────────
st.markdown("### Ablation Configuration Summary (Configs A–E)")

def _fmt(metrics: dict, *keys: str) -> str:
    """Format the first present, non-zero metric among aliases; '—' otherwise."""
    for key in keys:
        val = metrics.get(key)
        if val:
            return f"{val:.3f}"
    return "—"


rows = []
for cfg, metrics in results.items():
    n_total = metrics.get("total_processed")
    n_ok = metrics.get("successful")
    rows.append({
        "Config": cfg,
        "Description": CONFIG_DESCRIPTIONS.get(cfg, cfg),
        "LLM-Judge ↑":  _fmt(metrics, "llm_judge", "judge_correctness_mean"),
        "RAGAS Faithfulness ↑": _fmt(metrics, "ragas_score", "faithfulness_mean"),
        "BERTScore ↑":  _fmt(metrics, "bert_score_f1"),
        "ROUGE-L ↑ (lexical baseline)": _fmt(metrics, "rouge_l_f1"),
        "Type Acc ↑":   _fmt(metrics, "anomaly_type_accuracy"),
        "Success":      f"{n_ok}/{n_total}" if n_total else "—",
        "Latency(ms) ↓": f"{metrics.get('avg_latency_ms', 0):.0f}",
    })

st.dataframe(
    pd.DataFrame(rows),
    hide_index=True,
    width="stretch",
)
st.caption(
    "Primary quality metrics: **LLM-Judge** (correctness/completeness) and "
    "**RAGAS faithfulness** (evidence grounding). ROUGE-L is reported as a lexical "
    "baseline only — it penalises correct paraphrases. Evaluation runs in "
    "**blind mode**: configs receive the detector-estimated anomaly type, "
    "not oracle labels."
)

# ── RCA Quality Charts ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### RCA Quality Metrics")

try:
    import plotly.graph_objects as go

    configs = list(results.keys())
    metrics_to_plot = [
        ("LLM-Judge", "llm_judge", "#e74c3c"),
        ("RAGAS Faithfulness", "faithfulness_mean", "#ff9800"),
        ("BERTScore", "bert_score_f1", "#5b8def"),
        ("ROUGE-L (lexical baseline)", "rouge_l_f1", "#36baa2"),
    ]

    fig = go.Figure()
    for label, key, color in metrics_to_plot:
        vals = [results[c].get(key, 0) for c in configs]
        if any(v > 0 for v in vals):
            fig.add_trace(go.Bar(name=label, x=configs, y=vals, marker_color=color))

    fig.update_layout(
        barmode="group",
        title="RCA Quality — LLM-Judge / RAGAS / BERTScore / ROUGE-L by Configuration",
        xaxis_title="Configuration",
        yaxis_title="Score",
        yaxis_range=[0, 1],
        height=400,
        legend={"orientation": "h", "y": 1.1},
    )
    st.plotly_chart(fig, width="stretch")

except ImportError:
    st.warning("Install plotly for charts: `pip install plotly`")

# ── Detection Metrics Chart (only when detection metrics are present) ────────
_det_metrics = [
    ("Precision", "precision", "#27ae60"),
    ("Recall",    "recall",    "#2980b9"),
    ("F1-Score",  "f1",        "#8e44ad"),
    ("AUC-ROC",   "auc_roc",   "#e67e22"),
]
_has_detection = any(
    results[c].get(key) for c in configs for _, key, _ in _det_metrics
)
if _has_detection:
    st.markdown("---")
    st.markdown("### Anomaly Detection Metrics")
    try:
        import plotly.graph_objects as go

        det_fig = go.Figure()
        for label, key, color in _det_metrics:
            vals = [results[c].get(key, 0) for c in configs]
            det_fig.add_trace(go.Bar(name=label, x=configs, y=vals, marker_color=color))

        det_fig.update_layout(
            barmode="group",
            title="Detection Performance — Precision / Recall / F1 / AUC-ROC by Configuration",
            xaxis_title="Configuration",
            yaxis_title="Score",
            yaxis_range=[0, 1],
            height=400,
            legend={"orientation": "h", "y": 1.1},
        )
        st.plotly_chart(det_fig, width="stretch")

    except ImportError:
        pass

# ── Latency Chart ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Pipeline Latency")

try:
    import plotly.graph_objects as go

    lat_fig = go.Figure(go.Bar(
        x=configs,
        y=[results[c].get("avg_latency_ms", 0) for c in configs],
        marker_color="#667eea",
        text=[f"{results[c].get('avg_latency_ms', 0):.0f}ms" for c in configs],
        textposition="outside",
    ))
    lat_fig.update_layout(
        title="Average Pipeline Latency per Configuration",
        xaxis_title="Configuration",
        yaxis_title="Latency (ms)",
        height=350,
    )
    st.plotly_chart(lat_fig, width="stretch")

except ImportError:
    pass

# ── Manual RCA vs Automated — the examiner's comparison table ────────────────
st.markdown("---")
st.markdown("### ⏱️ Manual RCA vs This System (end-to-end)")

_slowest_ms = max((results[c].get("avg_latency_ms", 0) for c in configs), default=0)
_manual_lo_ms = MANUAL_RCA_MINUTES[0] * 60_000
_reduction = (1 - _slowest_ms / _manual_lo_ms) * 100 if _slowest_ms else 100.0

_COL_TIME = "Time per incident"
comparison_rows = [
    {
        "Approach": "Manual RCA (L1 triage → data pull → invoicing query → hypothesis → write-up)",
        _COL_TIME: f"{MANUAL_RCA_MINUTES[0]}–{MANUAL_RCA_MINUTES[1]} min",
        "Evidence": "Industry MTTR baseline (docs/DESIGN.md §1)",
    },
    {
        "Approach": "This system — slowest measured ablation config",
        _COL_TIME: f"{_slowest_ms/1000:.1f} s",
        "Evidence": "results/ablation/summary.json",
    },
    {
        "Approach": "This system — typical LLM-backed full pipeline",
        _COL_TIME: "~30–90 s",
        "Evidence": "Inference log (per-stage timings, Live Monitoring page)",
    },
]
st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, width="stretch")
st.caption(
    f"Even against the **slowest** measured configuration, investigation time drops "
    f"by **≥{min(_reduction, 99.9):.1f}%** vs the 65-minute lower bound of manual RCA. "
    "Per-stage timings (Investigator / Reasoner / Critic / Reporter) are recorded on "
    "every run — worst-case multi-hop graph traversal is bounded (k=2 BFS, in-memory) "
    "and LLM inference dominates latency, not retrieval."
)

# ── Source Data Info ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("Data Source & Methodology"):
    st.markdown("""
**Evaluation Dataset:** 60 ground truth incidents (data/eval/ground_truth_rca/),
12 per anomaly type, authored independently of the anomaly-injection rules.

**Ablation configs** (single source of truth: `config.py ABLATION_CONFIGS`):
A `no_rag` · A2 `cot_baseline` · A3 `react_baseline` · B `rag_only` ·
C `single_agent_rag` · D `multi_agent_rag` (proposed) · E `graph_rag` (headline).
All configs share the same LLM and knowledge base — differences are attributable
to architecture alone. **Blind mode** by default (detector-estimated types).

**Metric hierarchy (deliberate):**
1. **LLM-Judge** — 4-axis Likert (correctness / groundedness / actionability /
   completeness), independent judge model family, temperature 0
2. **RAGAS faithfulness** — atomic claim verification against retrieved context
3. **BERTScore F1** — semantic similarity baseline
4. **ROUGE-L F1** — lexical baseline only (penalises correct paraphrases)

**Statistics:** bootstrap 95% CIs, paired bootstrap p-values, Wilcoxon
signed-rank, Benjamini–Hochberg FDR (`src/evaluation/stats.py`).

**Pipeline:** `run_ablation.py` → `results/ablation/*.json` (+ MLflow) → this page.

**Refresh:** `python run_ablation.py --full` (judge on by default), then reload.
    """)
