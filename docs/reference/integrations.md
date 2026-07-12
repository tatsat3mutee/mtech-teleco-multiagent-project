# Integrations — As-Built Reference

> **As-built implementation reference — not a design document.** APIs, message channels and
> external services as currently implemented. For design intent see [../DESIGN.md](../DESIGN.md).

## 1. Internal API surface (FastAPI)

Implemented in [`api/main.py`](../../api/main.py) (after week 8). All endpoints are JSON over HTTPS, optional bearer token auth, CORS open in dev / domain-locked in prod.

| Method | Path | Purpose | Auth | Response |
|---|---|---|---|---|
| `GET` | `/health` | Liveness probe; reports KB status, LLM provider health | none | `{"status":"ok","providers":{...}}` |
| `POST` | `/rca/run` | Trigger pipeline for a single anomaly record; returns request_id | optional bearer | `{"request_id":"uuid"}` |
| `GET` | `/rca/status/{request_id}` | Poll status: queued / running / done / failed | optional bearer | `{"status":"...","result":{...}}` |
| `GET` | `/rca/stream/{request_id}` | Server-sent events stream of per-agent step events | optional bearer | `text/event-stream` |

**SSE event schema** (one JSON object per `data:` line):
```json
{ "step": "investigator", "status": "ok", "tokens": 312, "latency_ms": 480 }
{ "step": "reasoner",     "status": "ok", "tokens": 540, "latency_ms": 720 }
{ "step": "critic",       "status": "revise", "tokens": 220, "latency_ms": 410 }
{ "step": "reasoner",     "status": "ok", "tokens": 510, "latency_ms": 700, "revision": 1 }
{ "step": "critic",       "status": "accept", "tokens": 180, "latency_ms": 380 }
{ "step": "reporter",     "status": "ok", "tokens": 260, "latency_ms": 520 }
{ "step": "done",         "report": { ... } }
```

Rate limit: token-bucket via `src/utils/rate_limit.py` (default 450 RPM, configurable per env).

## 2. External LLM provider APIs

All routed through `litellm` (see [`src/llm/__init__.py`](../../src/llm/__init__.py)).

| Provider | Endpoint | Model used | Auth | Role |
|---|---|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` | Primary (28 RPM) |
| OpenRouter | `https://openrouter.ai/api/v1` | `deepseek/deepseek-r1:free` | `OPENROUTER_API_KEY` | Fallback slot 2 |
| OpenRouter | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct:free` | `OPENROUTER_API_KEY` | Fallback slot 3 |
| OpenRouter | `https://openrouter.ai/api/v1` | `deepseek/deepseek-chat:free` | `OPENROUTER_API_KEY` | Fallback slot 4 |

**Fallback trigger conditions** (handled by LiteLLM Router inside `src/agents/llm_utils.call_llm()`):
- 429 (rate limited)
- 5xx (provider outage)
- Network timeout > 30 s
- Empty / malformed response
- Token budget exceeded (8 k context)

On all four providers failing, the system returns deterministic mock content from `src/utils/test_data.py` so the pipeline and tests stay green offline.

## 3. Local data stores

| Store | Path | Format | Lifecycle |
|---|---|---|---|
| ChromaDB vector store | `chroma_db/` | SQLite + parquet (per Chroma) | Built once from `data/corpus/rca_playbooks/*.md`, persisted, rebuilt only on corpus change |
| GraphRAG NetworkX graph | `data/graph_rag/graph.pkl` | pickle | Built by `scripts/build_graph_rag.py`; rebuilt on playbook change |
| Trained detectors | `models/isolation_forest_model.joblib` | joblib | Built by `run_pipeline.py`; versioned via MLflow artifacts |
| MLflow tracking | `mlruns/` | MLflow standard layout | Append-only per experiment run |
| Trace log | `traces/*.jsonl` | one JSON object per line | Append-only per request |

## 4. External observability

| Service | Library | Auth | Use |
|---|---|---|---|
| Langfuse Cloud | `langfuse` | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (default `https://cloud.langfuse.com`) | Distributed traces of LLM calls, per-token cost, span timing — disabled if keys absent |
| MLflow | local server or remote | — | Experiment tracking; `MLFLOW_TRACKING_URI` env var (defaults to local `mlruns/`) |

## 5. Dataset sources

| Dataset | URL | Format | Loader |
|---|---|---|---|
| IBM Telco Customer Churn | [kaggle.com/datasets/blastchar/telco-customer-churn](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) | CSV | `src/data/loader.load_ibm_telco()` |
| Maven Telecom Customer Churn | [mavenanalytics.io](https://mavenanalytics.io/data-playground) | CSV | `src/data/loader.load_maven_telecom()` |
| SEBD Enterprise Billing | Synthetic (from real schema) | CSV | `src/data/loader.load_sebd()` |

All datasets stored under `data/raw/` (gitignored). Download script: `scripts/download_datasets.py`; SEBD via `scripts/generate_sebd.py`.

## 6. Deployment topology

```
                      ┌──────────────────────┐
                      │  GitHub (CI: tests)  │
                      └──────────┬───────────┘
                                 │ git push
                                 ▼
              ┌───────────────────────────────────┐
              │   Docker host  (AWS EC2 / VPS)    │
              │                                   │
              │  ┌────────────┐   ┌────────────┐  │
              │  │ Streamlit  │   │ FastAPI    │  │
              │  │ (port 8501)│   │ (port 8000)│  │
              │  └─────┬──────┘   └─────┬──────┘  │
              │        │                 │        │
              │        └─────────┬───────┘        │
              │                  ▼                │
              │   ┌──────────────────────────┐    │
              │   │ chroma_db/ (volume)      │    │
              │   │ mlruns/    (volume)      │    │
              │   │ data/      (volume)      │    │
              │   └──────────────────────────┘    │
              └────────────────┬──────────────────┘
                               │ HTTPS outbound
       ┌───────────────────────┬───────┴───────────────────────┐
       ▼                       ▼                               ▼
   Groq API            OpenRouter API                  Langfuse Cloud
 (llama-3.3-70b)  (DeepSeek-R1 / Llama-3.3 / chat)      (trace sink)
```

Nginx (`deploy/nginx.conf`) terminates TLS in front of Streamlit + FastAPI with `proxy_buffering off` for SSE pass-through.
