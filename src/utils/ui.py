"""
Shared responsive CSS for the Streamlit UI.

Injected by app.py and every page AFTER their own style blocks. All rules use
!important so they win over the per-page fixed-size CSS regardless of order.

Breakpoints:
  ≤ 900px (tablet) — 4/5-column grids wrap to 2-up; card padding tightens
  ≤ 640px (mobile) — everything stacks to a single column; headers/fonts scale
Always-on           — overflow safety for dataframes, headers, long tokens
"""
import streamlit as st

_RESPONSIVE_CSS = """
<style>
/* ═══════════ Always-on overflow safety (all viewports) ═══════════ */
div[data-testid="stDataFrame"] {
    overflow-x: auto !important;
    max-width: 100% !important;
}
.page-header, .bs-hero {
    max-width: 100% !important;
    overflow-wrap: break-word !important;
    box-sizing: border-box !important;
}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {
    word-break: break-word !important;
    overflow-wrap: break-word !important;
}
.main .block-container { overflow-x: hidden !important; }

/* ═══════════ Tablet ≤ 900px: grids wrap 2-up ═══════════ */
@media (max-width: 900px) {
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.6rem !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 calc(50% - 0.6rem) !important;
        min-width: calc(50% - 0.6rem) !important;
    }
    .bs-card { padding: 0.85rem 1rem !important; }
    .page-header { padding: 1.4rem 1.5rem !important; }
    .bs-hero { padding: 1.25rem 1.4rem !important; }
}

/* ═══════════ Mobile ≤ 640px: stack to one column ═══════════ */
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    /* Page headers / hero: compact padding, scaled type */
    .page-header, .bs-hero { padding: 1rem 1.1rem !important; }
    .page-header h2, .bs-hero-title {
        font-size: 1.25rem !important;
        line-height: 1.3 !important;
    }
    .page-header p, .bs-hero-subtitle {
        font-size: 0.92rem !important;
        line-height: 1.45 !important;
    }

    /* Metric cards: smaller value type so numbers fit */
    div[data-testid="stMetric"] { padding: 0.7rem 0.8rem !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
    }

    /* Home-page activity feed: stack each row vertically */
    .bs-activity {
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 0.25rem !important;
    }
    .bs-activity > * { min-width: 0 !important; margin-left: 0 !important; }

    /* Chips & pills: allow wrapping instead of overflow */
    .stApp .bs-chip, .bs-pill {
        white-space: normal !important;
        word-break: break-word !important;
    }

    /* Tabs: tighter so 3-4 tabs fit without horizontal scroll */
    button[data-baseweb="tab"] {
        padding: 0.35rem 0.6rem !important;
        font-size: 0.85rem !important;
    }

    /* Buttons: keep a thumb-friendly tap target */
    .stButton button { min-height: 44px !important; }

    /* Content gutter */
    .main .block-container {
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
}
</style>
"""


def inject_responsive_css() -> None:
    """Append the shared responsive stylesheet to the current page."""
    st.markdown(_RESPONSIVE_CSS, unsafe_allow_html=True)
