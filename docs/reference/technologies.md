# Technologies — As-Built Reference

> **As-built implementation reference — not a design document.** Stack inventory as currently
> pinned. Verify versions with `pip freeze`. For design intent see [../DESIGN.md](../DESIGN.md).

## Runtime

| Item | Version | Why this choice |
|---|---|---|
| Python | 3.12 | Native asyncio, PEP 695 generic syntax, sentence-transformers + LangGraph compatibility |
| OS (dev) | Windows 11 | Author's primary dev environment |
| OS (deploy) | Linux (Docker / Heroku / VPS) | Reproducibility and CI |

## Core ML / NLP libraries

| Library | Version (target) | Role |
|---|---|---|
| `sentence-transformers` | 2.7+ | Embedder (`all-MiniLM-L6-v2`, 384-dim) |
| `chromadb` | 0.5+ | Persistent vector store at `chroma_db/` |
| `rank_bm25` | 0.2+ | Sparse retrieval for hybrid + RRF |
| `networkx` | 3.3+ | GraphRAG storage (MultiDiGraph) |
| `scikit-learn` | 1.5+ | IsolationForest + rule pre-filter + train/test split |
| `pandas` | 2.2+ | Tabular CDR + billing manipulation |
| `numpy` | 1.26+ | Numerics |
| `joblib` | 1.4+ | Model persistence (`models/*.joblib`) |
| `nltk` | 3.8+ | Sentence tokenisation in chunker |

## LLM ecosystem

| Library | Version | Role |
|---|---|---|
| `langgraph` | 0.2+ | Multi-agent StateGraph orchestration |
| `langchain-core` | 0.3+ | Prompt + message abstractions |
| `litellm` | 1.40+ | Unified provider router with fallback |
| `groq` | 0.9+ | Groq SDK (primary; llama-3.3-70b-versatile) |
| `openai` | 1.30+ | Used for OpenRouter via OpenAI-compatible endpoint |
| `tiktoken` | 0.7+ | Token counting for cost tracking |

**LLM provider fallback chain** (see `src/agents/llm_utils.py`):
1. Groq (`llama-3.3-70b-versatile`) — primary; fastest, free tier (28 RPM)
2. OpenRouter (`deepseek/deepseek-r1:free`) — fallback slot 2
3. OpenRouter (`meta-llama/llama-3.3-70b-instruct:free`) — fallback slot 3
4. OpenRouter (`deepseek/deepseek-chat:free`) — fallback slot 4

If all slots fail, `src/utils/test_data.py` provides deterministic mock responses so offline tests don't break.

## Evaluation

| Library | Version | Role |
|---|---|---|
| `rouge-score` | 0.1+ | ROUGE-L F1 |
| `bert-score` | 0.3+ | BERTScore F1 (semantic similarity) |
| `ragas` | 0.1+ | Faithfulness metric for RAG |
| `scipy` | 1.13+ | Wilcoxon signed-rank, bootstrap helpers |

**4-axis LLM-as-Judge** (own implementation in `src/evaluation/llm_judge.py`):
1. Grounding — every claim cited from evidence?
2. Consistency — internal contradictions?
3. Completeness — covers root cause + recommendations?
4. Actionability — concrete next steps?

## Observability

| Library | Version | Role |
|---|---|---|
| `mlflow` | 2.14+ | Experiment tracking; results in `mlruns/` |
| `langfuse` | 2.40+ | Distributed LLM tracing (optional, SaaS) |
| Custom JSONL tracer | n/a | `src/utils/tracing.py` — per-agent step trace at `traces/` |

## UI & API

| Library | Version | Role |
|---|---|---|
| `streamlit` | 1.36+ | 5-page dashboard (`app.py`, `pages/`) |
| `fastapi` | 0.111+ | Optional REST + SSE backend (`api/main.py`) |
| `uvicorn` | 0.30+ | ASGI server |
| `sse-starlette` | 2.1+ | Server-sent events streaming |

## DevOps

| Tool | Role |
|---|---|
| `pytest` + `pytest-cov` | Test runner; 116 tests, 13 files; offline-safe via mock LLM |
| `pytest-asyncio` | Async test support for FastAPI |
| Docker + docker-compose | Reproducible deployment |
| GitHub Actions (`.github/workflows/test.yml`) | CI on push (pytest matrix) |
| Heroku (`Procfile`, `runtime.txt`) | Demo deployment target |
| nginx (`deploy/nginx.conf`) | VPS reverse proxy with SSE pass-through |

## Layering summary (matches `components.md` dependency layering)

```
Foundation:  Python 3.12 + pandas/numpy/scikit-learn
Storage:     ChromaDB (vector) + NetworkX (graph) + joblib (models) + MLflow (experiments)
NLP:         sentence-transformers + rank_bm25 + nltk
Orchestrate: LangGraph + LiteLLM + (Groq | OpenRouter)
Evaluate:    rouge-score + bert-score + ragas + scipy
Surface:     Streamlit + FastAPI + uvicorn + sse-starlette
DevOps:      pytest + Docker + GitHub Actions + nginx + Langfuse
```

## Choice rationale (defensible in viva)

- **`all-MiniLM-L6-v2`** over BGE/E5: smaller (80 MB), CPU-fast, 384-dim (compact ChromaDB), strong baseline. Acknowledged trade-off: BGE-base would lift retrieval ~3-5 nDCG points but doubles RAM and latency — not justified for prototype.
- **ChromaDB** over Pinecone/Weaviate: local, zero infra cost, persistable on disk, fits dissertation reproducibility constraint.
- **LangGraph** over CrewAI/AutoGen: explicit state machine, deterministic edges (including conditional critic loop), much easier to test and trace per-agent.
- **LiteLLM** over direct SDKs: unified retry + fallback + cost tracking out of the box; swap providers without code changes.
- **MLflow + Langfuse** dual tracking: MLflow for offline reproducibility (artifacts + metrics versioned), Langfuse for LLM-specific tracing (token cost, span timing).
