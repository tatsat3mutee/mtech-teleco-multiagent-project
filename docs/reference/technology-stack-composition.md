# Technology Stack Composition — As-Built Reference

> **As-built implementation reference — not a design document.** Version constraints and EOL
> timeline as currently pinned. For design intent see [../DESIGN.md](../DESIGN.md).

## 1. Runtime Environment

| Component | Version | EOL / Support | Notes |
|---|---|---|---|
| Python | 3.12 | Oct 2028 (end of security fixes) | PEP 695 generic syntax; native asyncio improvements |
| pip | 24.x | Rolling | Used for all package management |
| OS (dev) | Windows 11 | — | Author's primary environment |
| OS (deploy) | Linux (Docker: python:3.12-slim) | — | Reproducibility target |

## 2. Core Dependencies — Version Constraints

### ML / Data Stack

| Package | Pinned range | Latest (May 2026) | EOL risk | Breaking change risk |
|---|---|---|---|---|
| `pandas` | ≥2.0, <3.0 | 2.2.x | None (active) | pandas 3.0 will drop `inplace=` — not used here |
| `numpy` | ≥1.24, <2.0 | 1.26.x | None | numpy 2.0 changes dtype defaults; pin <2.0 is safe |
| `scikit-learn` | ≥1.3, <2.0 | 1.5.x | None | IsolationForest API stable since 1.0 |
| `scipy` | ≥1.11, <2.0 | 1.13.x | None | `wilcoxon` signature unchanged |
| `joblib` | ≥1.3, <2.0 | 1.4.x | None | Model persistence format stable |
| `networkx` | ≥3.2, <4.0 | 3.3.x | None | MultiDiGraph API stable |

### LLM Ecosystem

| Package | Pinned range | Latest | Stability | Notes |
|---|---|---|---|---|
| `langgraph` | ≥0.2, <1.0 | 0.2.x | **Pre-1.0** | API may change; StateGraph is stable enough for our use |
| `langchain-core` | (transitive) | 0.3.x | Rapid iteration | We only use message types + prompt templates |
| `litellm` | ≥1.40 | 1.60+ | Rapid iteration | Unified router; new providers added weekly |
| `openai` | ≥1.40, <2.0 | 1.50+ | Stable | Used for OpenRouter OpenAI-compat endpoint |
| `langchain-groq` | ≥1.0 | 1.x | Stable | Optional; used in judge |

### RAG / NLP

| Package | Pinned range | Latest | Stability | Notes |
|---|---|---|---|---|
| `chromadb` | ≥0.5, <1.0 | 0.5.x | **Pre-1.0, beta** | SQLite backend; persistence format may change on 1.0 |
| `sentence-transformers` | ≥2.2, <3.0 | 2.7.x | Stable | `all-MiniLM-L6-v2` model frozen |
| `rank-bm25` | ≥0.2.2, <1.0 | 0.2.x | Stable (unmaintained) | Simple; unlikely to break |
| `pymupdf` | ≥1.23, <2.0 | 1.24.x | Stable | PDF extraction only |

### Evaluation

| Package | Pinned range | Latest | Stability | Notes |
|---|---|---|---|---|
| `rouge-score` | ≥0.1.2, <1.0 | 0.1.x | Stable (unmaintained) | Google's implementation; frozen |
| `bert-score` | ≥0.3.13, <1.0 | 0.3.x | Stable | Uses `roberta-large` by default |
| `mlflow` | ≥2.10, <3.0 | 2.14.x | Stable | Tracking API unchanged since 2.0 |

### Observability

| Package | Pinned range | Latest | Stability | Notes |
|---|---|---|---|---|
| `langfuse` | ≥2.0 | 2.40+ | Active | Cloud SaaS; SDK stable |

### UI / API

| Package | Pinned range | Latest | Stability | Notes |
|---|---|---|---|---|
| `streamlit` | ≥1.30, <2.0 | 1.36.x | Stable | Multi-page app API stable since 1.28 |
| `fastapi` | ≥0.110, <1.0 | 0.111.x | **Pre-1.0** | Starlette-based; our use is simple |
| `uvicorn` | ≥0.27, <1.0 | 0.30.x | Stable | ASGI server |

### Testing

| Package | Pinned range | Latest | Notes |
|---|---|---|---|
| `pytest` | ≥8.0, <9.0 | 8.2.x | Standard |
| `pytest-cov` | ≥4.1, <6.0 | 5.x | Coverage reporting |

## 3. Known Compatibility Constraints

| Issue | Impact | Mitigation |
|---|---|---|
| **Pydantic v1 vs v2 coexistence** | `langchain-core` uses Pydantic v1 shim (`pydantic.v1`); LangGraph uses v2 internally | Pin langchain ecosystem together; don't mix v1/v2 in our code |
| **tiktoken requires Rust** | `tiktoken` (transitive via litellm/openai) needs Rust toolchain at install time | Docker image uses `python:3.12-slim` + build-essential; works |
| **sentence-transformers → torch** | Pulls in `torch` (~2.5 GB); dominates venv size | CPU-only torch sufficient; could use `--index-url` for smaller install |
| **chromadb SQLite version** | Requires SQLite ≥3.35; some older Linux images have 3.31 | Docker base image has 3.45+; not a problem |
| **litellm duplicate in requirements.txt** | Listed twice (lines 22 and 55) | Harmless; pip deduplicates; clean up in W1 |

## 4. Upgrade Checklist (priority order)

If upgrading post-submission:

| Priority | Package | Action | Risk |
|---|---|---|---|
| 1 | `chromadb` → 1.0 | Test persistence migration; may need re-index | Medium — format change |
| 2 | `langgraph` → 1.0 | Review StateGraph API changes | Low — our usage is simple |
| 3 | `numpy` → 2.0 | Run full test suite; check dtype behaviour | Low |
| 4 | `pandas` → 3.0 | Remove any `inplace=True` (none used) | Low |
| 5 | `fastapi` → 1.0 | Review breaking changes | Low — our routes are simple |

## 5. Docker Image Size Breakdown

| Component | Approx. size | Notes |
|---|---|---|
| `python:3.12-slim` base | ~150 MB | |
| `torch` (CPU) | ~800 MB | Via sentence-transformers |
| `sentence-transformers` + model | ~200 MB | `all-MiniLM-L6-v2` = 80 MB |
| `chromadb` + deps | ~100 MB | |
| Everything else | ~300 MB | |
| **Total image** | **~1.5 GB** | Could reduce to ~1 GB with torch CPU-only index |

## 6. Reproducibility Constraints

- `requirements.txt` uses range pins (≥X, <Y) — for exact reproduction, freeze with `pip freeze > requirements-frozen.txt`
- Model weights (`all-MiniLM-L6-v2`) downloaded at runtime or Docker build time — version is fixed by model name
- ChromaDB index is deterministic given same corpus + same embedding model
- Random seed = 42 everywhere (config.py)
