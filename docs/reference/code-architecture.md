# Code Architecture — As-Built Reference

> **As-built implementation reference — not a design document.** Derived from inspection of the
> `src/` tree as currently implemented. For design intent and rationale see [../DESIGN.md](../DESIGN.md).

## 1. Architectural Style

**Event-driven State Machine** — The core pipeline is a LangGraph `StateGraph` where:
- Nodes are stateless processing functions (agents)
- State flows through a `TypedDict` (immutable-by-convention)
- Conditional edges implement revision loops
- The graph is compiled into a deterministic execution plan

Secondary style: **Layered Architecture** with strict unidirectional dependency flow (see `components.md` Layer 0–21).

## 2. Design Patterns Identified

### 2.1 State Machine (via LangGraph StateGraph)

**Location:** `src/agents/graph.py`

```
                ┌─────────────┐
                │ investigator│
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │   reasoner  │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
           ┌────┤    critic   ├────┐
           │    └─────────────┘    │
     revise│                       │accept
           │    ┌─────────────┐    │
           └───►│   reasoner  │    │
                └──────┬──────┘    │
                       │           │
                ┌──────▼──────┐◄───┘
                │   reporter  │
                └─────────────┘
```

- **Pattern:** State Machine with conditional transitions
- **Why:** Enables critic-driven revision without hardcoded loops; graph is serialisable for tracing
- **Implementation:** `build_graph()` → `StateGraph(AgentState)` → `.add_node()` × 4 → `.add_conditional_edges("critic", should_revise, {...})` → `.compile()`

### 2.2 Strategy Pattern (via SWARM Router)

**Location:** `src/agents/swarm_router.py`

- **Pattern:** Strategy — selects retrieval algorithm at runtime based on anomaly type
- **Why:** Different anomaly categories benefit from different retrieval strategies (graph-first for network issues, vector-first for billing errors)
- **Implementation:** `get_retrieval_strategy(anomaly_type: str) → str` returns one of `"vector_first"`, `"graph_first"`, `"hybrid"` used by `investigator_node()`
- **Extension point:** Adding a new strategy requires only a new mapping entry

### 2.3 Chain of Responsibility (LLM Fallback)

**Location:** `src/agents/llm_utils.py` via LiteLLM Router

- **Pattern:** Chain of Responsibility — each LLM provider is tried in priority order; first success wins
- **Why:** Free-tier API keys have rate limits; automatic failover gives resilience without user intervention
- **Chain:** Groq (llama-3.3-70b) → OpenRouter free models (DeepSeek-R1, Llama-3.3-70b, DeepSeek-chat)
- **Implementation:** LiteLLM Router `model_list` with 4 deployment slots aliased "primary" (least-busy routing); `call_llm()` wraps `router.completion()`

### 2.4 Observer Pattern (Tracing & Observability)

**Location:** `src/utils/tracing.py`, `src/utils/observability.py`

- **Pattern:** Observer — agent execution events are published to multiple sinks without coupling
- **Sinks:** JSONL file tracer, Langfuse cloud, MLflow logger
- **Why:** Enables post-hoc debugging (JSONL), live monitoring (Langfuse), and experiment tracking (MLflow) from the same execution
- **Implementation:** Each agent node calls `tracer.log_event()` which appends to JSONL; Langfuse callback is attached to LiteLLM at router level

### 2.5 Facade Pattern (CLI & Pipeline Runners)

**Location:** `src/cli.py`, `run_pipeline.py`, `run_ablation.py`

- **Pattern:** Facade — single entry point hides complex multi-step orchestration
- **Why:** The full pipeline involves 6+ subsystems (data → detection → KB → agents → eval → tracking); CLI exposes 5 subcommands
- **Implementation:**
  - `src/cli.py`: Click-based CLI with `pipeline`, `ablation`, `eval`, `build-kb`, `build-graph` subcommands
  - `run_pipeline.py`: Imports from data, detection, rag, agents, evaluation — wires end-to-end
  - `run_ablation.py`: Iterates configs A–E, toggles features, runs pipeline per config

### 2.6 Factory Pattern (LLM Registry)

**Location:** `src/llm/__init__.py` + per-provider modules

- **Pattern:** Factory — creates the appropriate LLM client based on available API keys
- **Why:** Decouples agent code from provider-specific configuration; supports both providers transparently
- **Implementation:** `src/llm/__init__.py` scans environment for API keys (GROQ_API_KEY, OPENROUTER_API_KEY), builds `model_list` dynamically, returns configured router
- **Providers:** `groq_provider.py`, `openrouter_provider.py`

### 2.7 Template Method (Agent Nodes)

**Location:** `src/agents/{investigator,reasoner,critic,reporter}.py`

- **Pattern:** Template Method — all agent nodes follow the same skeleton:
  1. Extract relevant state fields
  2. Build prompt (system + user)
  3. Call LLM via `call_llm()`
  4. Parse response
  5. Update state dict
  6. Return updated state
- **Why:** Consistent structure enables tracing, testing, and adding new agents
- **Variation:** Critic adds a `should_revise()` decision function; Reporter adds JSON schema validation

### 2.8 Repository Pattern (Knowledge Base)

**Location:** `src/rag/knowledge_base.py`

- **Pattern:** Repository — abstracts persistence + query behind a domain interface
- **Why:** Hides ChromaDB implementation details; could swap to FAISS/Pinecone without changing callers
- **Implementation:** `KnowledgeBase` class with `index_documents()`, `query()`, `search()`, `count()`, `reset()`

### 2.9 Composite Pattern (Hybrid Retriever)

**Location:** `src/rag/hybrid_retriever.py`

- **Pattern:** Composite — combines BM25 (sparse) + dense vector retrievers into a single `search()` interface
- **Why:** RRF fusion gives better recall than either method alone (demonstrated in ablation B vs C)
- **Implementation:** `HybridRetriever.search()` calls `_bm25_top()` + `_dense_top()` then fuses via RRF scores

## 3. Architectural Decisions (ADRs)

| # | Decision | Rationale | Trade-off |
|---|---|---|---|
| ADR-1 | LangGraph over raw Python loops | Serialisable graph, built-in state checkpointing, conditional edges | Adds dependency; pre-1.0 API risk |
| ADR-2 | ChromaDB over FAISS | Persistence built-in, metadata filtering, no C compilation | Slower than FAISS for large N; pre-1.0 |
| ADR-3 | LiteLLM over direct OpenAI SDK | Unified interface for 4 providers; automatic fallback; token counting | Extra abstraction layer; rapid iteration |
| ADR-4 | CPU-only inference | No GPU requirement for reproducibility; project is I/O-bound (LLM calls) | Embedding + BERTScore slower (~2s vs 0.5s) |
| ADR-5 | Hybrid BM25+Dense over dense-only | Better recall for exact terminology (billing codes, error strings) | Slightly more complex; needs corpus in memory |
| ADR-6 | NetworkX over Neo4j for GraphRAG | Zero infrastructure; pickle persistence; sufficient for 200-node graph | Won't scale to millions of nodes |
| ADR-7 | IsolationForest over deep learning | Interpretable; fast; works on tabular; no GPU needed | Misses temporal patterns (LSTM would help) |
| ADR-8 | Streamlit over React | Rapid prototyping; Python-only; 5 pages in ~400 LOC total | Less control over UI; no real-time WebSocket |

## 4. Code Quality Metrics

| Metric | Value | Notes |
|---|---|---|
| Total LOC (src/) | ~4,470 | Excluding tests, scripts, pages |
| Avg module size | ~118 LOC | Healthy; no god-files |
| Largest module | `src/agents/graph.py` (~180 LOC) | Still reasonable |
| Smallest module | `src/demo/demo_loader.py` (~40 LOC) | Single responsibility |
| Cyclomatic complexity | Low | Most functions are linear; only `should_revise()` and `get_retrieval_strategy()` have branching |
| Test coverage target | 116 tests across 13 files | Focus on unit + integration; no E2E browser tests |

## 5. Cross-cutting Concerns

| Concern | Implementation | Location |
|---|---|---|
| Configuration | `config.py` with `python-dotenv` for secrets | Root |
| Logging | Structured Python logging | `src/utils/logging.py` |
| Rate limiting | Token-bucket (450 RPM default) | `src/utils/rate_limit.py` |
| Caching | In-memory response cache for deterministic offline tests | `src/utils/cache.py` |
| Error handling | LLM call retry (3× with backoff) via LiteLLM; graceful degradation with fallback templates | `src/utils/test_data.py` |
| Reproducibility | `RANDOM_SEED=42` everywhere; deterministic chunking | `config.py` |

## 6. Data Flow Diagram

```
CSV Upload / CLI
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  Data Loader│────►│ Anomaly      │
│  (loader.py)│     │ Injector     │
└─────────────┘     └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Detector    │──── models/*.joblib
                    │(IsoForest)   │
                    └──────┬───────┘
                           │ flagged anomalies
                    ┌──────▼───────┐
                    │ SWARM Router │
                    └──────┬───────┘
                           │ strategy selection
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ BM25+Vec │ │ GraphRAG │ │  Hybrid  │
        │ Retriever│ │ Retriever│ │   Both   │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             └─────────────┼────────────┘
                           │ evidence chunks
                    ┌──────▼───────┐
                    │ Investigator │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Reasoner   │◄──── revision loop
                    └──────┬───────┘         │
                           │                 │
                    ┌──────▼───────┐         │
                    │    Critic    │─────────┘
                    └──────┬───────┘
                           │ accept
                    ┌──────▼───────┐
                    │   Reporter   │
                    └──────┬───────┘
                           │ RCA JSON
                    ┌──────▼───────┐
                    │  Evaluation  │──── metrics, judge scores
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Streamlit     MLflow       Langfuse
         Dashboard     Tracking     Traces
```
