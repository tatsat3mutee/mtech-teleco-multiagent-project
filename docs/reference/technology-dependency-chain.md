# Technology Dependency Chain — As-Built Reference

> **As-built implementation reference — not a design document.** Transitive dependency footprint
> derived from `requirements.txt`. For design intent see [../DESIGN.md](../DESIGN.md).

## 1. Direct Dependencies (requirements.txt)

Total: **36 direct packages** (deduplicated — litellm and langfuse listed twice in source file).

### Grouped by function

```
ML/Data (7):       pandas, numpy, scikit-learn, scipy, matplotlib, seaborn, joblib
LLM/Agents (7):   langchain, langchain-community, langchain-openai, langchain-groq,
                   langgraph, openai, litellm
RAG (4):           chromadb, sentence-transformers, rank-bm25, networkx
PDF (1):           pymupdf
Tracking (1):      mlflow
UI (3):            streamlit, plotly, fpdf2
Evaluation (2):    rouge-score, bert-score
Utilities (4):     python-dotenv, tqdm, joblib, requests
Observability (1): langfuse
API (4):           fastapi, uvicorn, httpx, slowapi
DB/Cache (2):      redis, psycopg2-binary
Testing (2):       pytest, pytest-cov
```

## 2. Heavy Transitive Dependencies

| Direct package | Transitive pull-in | Approx. size | Impact |
|---|---|---|---|
| `sentence-transformers` | `torch` (CPU), `transformers`, `huggingface-hub`, `tokenizers`, `safetensors` | ~1.2 GB | **Dominates** venv + Docker |
| `bert-score` | `torch` (shared), `transformers` (shared) | Shared with above | Reuses same torch install |
| `chromadb` | `onnxruntime`, `tokenizers`, `posthog`, `httptools` | ~200 MB | onnxruntime is the heavy one |
| `mlflow` | `sqlalchemy`, `alembic`, `flask`, `gunicorn`, `protobuf`, `pyarrow` | ~300 MB | Many unused server deps |
| `streamlit` | `tornado`, `click`, `altair`, `pydeck`, `watchdog`, `blinker` | ~150 MB | |
| `langchain` | `pydantic` (v1 compat shim), `tenacity`, `aiohttp`, `jsonpatch` | ~50 MB | |
| `litellm` | `tiktoken`, `click`, `jinja2`, `importlib-metadata` | ~80 MB | tiktoken needs Rust at build |
| `scipy` | — (numpy only) | ~40 MB | Relatively light |
| `plotly` | `kaleido` (optional, not installed) | ~30 MB | |

## 3. Full Dependency Tree (simplified)

```
requirements.txt
├── pandas ─── numpy
├── numpy
├── scikit-learn ─── numpy, scipy, joblib, threadpoolctl
├── scipy ─── numpy
├── matplotlib ─── numpy, pillow, contourpy, fonttools, cycler, kiwisolver
├── seaborn ─── pandas, matplotlib
│
├── langchain ─── langchain-core ─── pydantic(v1 shim), tenacity, jsonpatch, PyYAML
├── langchain-community ─── langchain-core
├── langchain-openai ─── openai, tiktoken
├── langchain-groq ─── groq, langchain-core
├── langgraph ─── langchain-core, langgraph-sdk
├── openai ─── httpx, pydantic, anyio, distro
├── litellm ─── openai, tiktoken, click, jinja2, importlib-metadata, aiohttp
│
├── chromadb ─── onnxruntime, numpy, httptools, posthog, tenacity, overrides
├── sentence-transformers ─── torch, transformers, huggingface-hub, tqdm, scikit-learn
│   └── torch ─── (largest single package ~800MB CPU)
├── rank-bm25 ─── numpy
├── networkx
│
├── pymupdf
│
├── mlflow ─── sqlalchemy, alembic, flask, gunicorn, protobuf, cloudpickle, pyarrow
│
├── streamlit ─── tornado, click, altair, pydeck, toml, watchdog, blinker, cachetools
├── plotly ─── tenacity
├── fpdf2
│
├── rouge-score ─── nltk, absl-py, numpy
├── bert-score ─── torch (shared), transformers (shared), matplotlib
│
├── python-dotenv
├── tqdm
├── joblib
├── requests ─── urllib3, certifi, charset-normalizer, idna
│
├── langfuse ─── httpx, pydantic, backoff
│
├── fastapi ─── starlette, pydantic, anyio
├── uvicorn ─── click, h11, httptools
├── httpx ─── anyio, certifi, httpcore, idna, sniffio
├── slowapi ─── limits, starlette
│
├── redis
├── psycopg2-binary
│
├── pytest ─── pluggy, iniconfig, packaging
└── pytest-cov ─── coverage
```

## 4. Shared Dependencies (deduplication opportunities)

These packages are pulled by multiple direct deps:

| Package | Required by |
|---|---|
| `numpy` | pandas, scikit-learn, scipy, matplotlib, chromadb, sentence-transformers, bert-score, rank-bm25 |
| `pydantic` | langchain-core, openai, fastapi, litellm, langfuse, chromadb |
| `torch` | sentence-transformers, bert-score |
| `httpx` | openai, litellm, langfuse, fastapi (test client) |
| `tenacity` | langchain-core, chromadb, plotly |
| `click` | litellm, uvicorn, streamlit |
| `tiktoken` | langchain-openai, litellm |
| `aiohttp` | langchain, litellm |

## 5. Upgrade Order (respecting dependency DAG)

When upgrading, respect this order to avoid breakage:

```
1. numpy                (everything depends on it)
2. scipy, pandas        (depend on numpy)
3. scikit-learn         (depends on numpy, scipy)
4. torch                (independent; sentence-transformers depends on it)
5. sentence-transformers, bert-score  (depend on torch)
6. pydantic             (langchain, fastapi, openai all depend on it)
7. langchain-core       (depends on pydantic)
8. langchain, langchain-openai, langchain-groq, langchain-community
9. langgraph            (depends on langchain-core)
10. openai, litellm     (depend on pydantic, httpx)
11. chromadb            (independent heavy dep)
12. mlflow              (independent)
13. streamlit, fastapi  (independent of ML stack)
14. Everything else     (leaf packages)
```

## 6. Install Size Breakdown

| Category | Installed size | % of total |
|---|---|---|
| PyTorch (CPU) | ~800 MB | 35% |
| sentence-transformers + model | ~200 MB | 9% |
| MLflow + deps | ~300 MB | 13% |
| ChromaDB + onnxruntime | ~200 MB | 9% |
| Streamlit + deps | ~150 MB | 7% |
| Everything else combined | ~600 MB | 27% |
| **Total venv** | **~2.3 GB** | 100% |

## 7. Minimisation Strategies (not implemented — future work)

| Strategy | Savings | Trade-off |
|---|---|---|
| CPU-only torch via `--index-url` | ~600 MB | Already CPU-only; just smaller wheel |
| Replace `mlflow` with JSON logging | ~300 MB | Lose experiment UI |
| Replace `chromadb` with `faiss-cpu` | ~150 MB | Lose persistence simplicity |
| Remove `psycopg2-binary` + `redis` | ~20 MB | Only used in optional production path |

## 8. Known Duplicate in requirements.txt

```
Line 16: litellm>=1.40.0,<2.0
Line 55: litellm>=1.40.0
Line 44: langfuse>=2.40.0,<3.0
Line 56: langfuse>=2.0.0
```

Both litellm and langfuse are listed twice with slightly different version constraints. pip resolves by intersecting ranges (takes the tighter one). Harmless but should be deduplicated for cleanliness in W1.
