# Components — As-Built Reference

> **As-built implementation reference — not a design document.** Component inventory of the
> system *as currently implemented*. For design intent and rationale see [../DESIGN.md](../DESIGN.md).

## Overview

The system decomposes into 7 packages (~38 modules) under `src/`, two entry-point layers (`pages/` Streamlit, `api/` FastAPI), and shared scripts (`scripts/`) and tests (`tests/`).

```
mtech-teleco-multiagent-project/
├── src/
│   ├── data/          # Data ingestion + anomaly injection (4 modules)
│   ├── detection/     # IsolationForest detector (1 module)
│   ├── rag/           # Retrieval-Augmented Generation stack (6 modules)
│   ├── agents/        # LangGraph multi-agent system (9 modules)
│   ├── evaluation/    # Metrics, LLM-as-Judge, statistical tests (3 modules)
│   ├── llm/           # LLM provider abstraction (5 modules)
│   ├── utils/         # Observability, caching, rate-limiting (8 modules)
│   └── demo/          # Pre-generated demo loader (1 module)
├── pages/             # Streamlit dashboard (5 pages)
├── api/               # FastAPI backend (optional)
├── scripts/           # Setup, build, plotting (6 scripts)
└── tests/             # Pytest suite (13 files, 116 tests)
```

## Package-by-package breakdown

### `src/data/` — Data Ingestion (~560 LOC)

**Core (used in ablation/pipeline):**

| Module | Purpose | Key functions |
|---|---|---|
| `loader.py` | Load IBM Telco churn + Maven telecom datasets; merge into unified schema | `load_ibm_telco()`, `load_maven_telecom()`, `load_combined()`, `get_billing_features()` |
| `anomaly_injector.py` | Inject 5 synthetic billing anomaly types with seed-controlled determinism | `inject_zero_billing()`, `inject_duplicate_charges()`, `inject_usage_spike()`, `inject_cdr_failure()`, `inject_sla_breach()` |

**Secondary (not in evaluated pipeline — UI/demo utilities or future-work stubs):**

| Module | Purpose | Used by | Status |
|---|---|---|---|
| `loader.py` | Loads IBM Telco + Maven + SEBD enterprise billing; normalises to unified schema | run_pipeline step 1, Streamlit Upload page | load_sebd() is the primary demo path for examiner |

> **Honest note for dissertation:** The ablation (Configs A–E, 60-item GT) runs on IBM Telco + Maven merged data with synthetic injection. SEBD exists to demonstrate the system works on a real enterprise billing schema. Frame accordingly in Ch 4.

### `src/detection/` — Anomaly Detection (~280 LOC)

| Module | Purpose | Key functions |
|---|---|---|
| `detector.py` | `BillingAnomalyDetector` class — IsolationForest + rule pre-filter, model persistence | `BillingAnomalyDetector.train_and_evaluate()`, `rule_based_prefilter()` |

### `src/rag/` — Retrieval-Augmented Generation (~700 LOC)

| Module | Purpose | Key functions |
|---|---|---|
| `embedder.py` | Sentence-transformers wrapper (`all-MiniLM-L6-v2`, 384-dim) with lazy loading + cache | `EmbeddingModel.embed_texts()`, `EmbeddingModel.embed_query()` |
| `chunker.py` | Recursive text chunker with configurable size + overlap | `TextChunker.split_text()`, `chunk_document()`, `chunk_file()` |
| `knowledge_base.py` | ChromaDB indexing and retrieval; builds from `data/corpus/rca_playbooks/*.md` | `KnowledgeBase.index_documents()`, `query()`, `search()`, `count()`, `reset()`, `build_knowledge_base()` |
| `hybrid_retriever.py` | BM25 + dense vector retrieval fused via Reciprocal Rank Fusion | `HybridRetriever.search()`, `_bm25_top()`, `_dense_top()` |
| `reranker.py` | Cross-encoder reranking of top-K hybrid results | `Reranker.rerank()`, `Reranker.get_default()` |
| `graph_rag.py` | **Headline novelty.** Entity/relation extraction → NetworkX MultiDiGraph → k-hop BFS retrieval | `GraphRAGBuilder.build_from_playbooks()`, `GraphRAGRetriever.retrieve()`, `khop()`, `save()`, `load()` |

### `src/agents/` — Multi-Agent System (~1,000 LOC)

| Module | Purpose | Key types/functions |
|---|---|---|
| `state.py` | TypedDict schemas for agent state and RCA report | `AnomalyRecord`, `AgentState`, `RCAReport` |
| `prompts.py` | System + user prompts for all 4 agents | `INVESTIGATOR_PROMPT`, `REASONER_PROMPT`, `CRITIC_PROMPT`, `REPORTER_PROMPT` |
| `llm_utils.py` | LiteLLM router with auto provider detection, retry, token counting, health checks | `call_llm()`, `get_active_provider()`, `get_router_health()`, `_get_router()` |
| `swarm_router.py` | Maps each anomaly type to a retrieval strategy (vector_first / graph_first / hybrid) | `get_retrieval_strategy()`, `get_routing_explanation()` |
| `investigator.py` | Formulates KB query from anomaly; retrieves top-K via routed strategy | `investigator_node()` |
| `reasoner.py` | Chain-of-thought hypothesis generation from evidence | `reasoner_node()` |
| `critic.py` | Reviews hypothesis for grounding + hallucination; verdict accept/revise; 1 revision loop | `critic_node()`, `should_revise()` |
| `reporter.py` | Structured JSON RCA output with schema validation | `reporter_node()` |
| `graph.py` | LangGraph StateGraph assembly; wires nodes + 2 conditional edges (critic revise path) | `build_graph()`, `run_pipeline()`, `run_batch_pipeline()` |

### `src/evaluation/` — Metrics & Statistical Tests (~700 LOC)

| Module | Purpose | Key functions |
|---|---|---|
| `metrics.py` | ROUGE-L, BERTScore, detection metrics, multi-reference GT loader | `load_ground_truth()`, `detection_metrics()`, `compute_rouge_l()`, `compute_bert_score()`, `context_recall()`, `context_precision()`, `mrr_at_k()`, `evaluate_pipeline_results()` |
| `llm_judge.py` | LLM-as-Judge with 4-axis Likert scoring + RAGAS faithfulness | `likert_judge()`, `faithfulness()`, `_call_judge()` |
| `stats.py` | Bootstrap 95% CI, paired-bootstrap p-value, Wilcoxon signed-rank | `bootstrap_ci()`, `paired_bootstrap_pvalue()`, `wilcoxon_paired()`, `compare_configs()` |

### `src/llm/` — Provider Abstraction (~270 LOC)

| Module | Purpose |
|---|---|
| `__init__.py` | Registry + auto-detect + fallback chain (Groq → OpenRouter) |
| `groq_provider.py` | Groq API client configuration |
| `openrouter_provider.py` | OpenRouter API client configuration (free DeepSeek/Llama models) |

### `src/utils/` — Observability & Utilities (~680 LOC)

| Module | Purpose |
|---|---|
| `observability.py` | Langfuse integration for distributed tracing |
| `tracing.py` | JSONL event tracer for per-agent step observability with latency + token cost |
| `logging.py` | Structured logging configuration |
| `rate_limit.py` | Token-bucket rate limiter (configurable RPM, default 450) |
| `cache.py` | Response caching for deterministic offline tests |
| `inference_log.py` | Structured logging for every LLM inference call |
| `test_data.py` | Fallback templates when no LLM key is present (enables offline tests) |

### `src/demo/` — Demo Utilities

| Module | Purpose |
|---|---|
| `demo_loader.py` | Loads pre-generated demo RCA reports for fast Streamlit demo without live LLM calls |

### Entry points

| Path | Purpose |
|---|---|
| `app.py` | Streamlit homepage + nav to 5 pages; loads secrets; triggers cold-start KB build |
| `pages/1_📊_Upload_Detect.py` | CSV upload → run detector → flag anomalies |
| `pages/2_🔍_RCA_Viewer.py` | Anomaly picker → run multi-agent pipeline → render RCA report |
| `pages/3_📚_Knowledge_Base.py` | Browse indexed playbook chunks, search KB, view similarity scores |
| `pages/4_📊_Experiment_Results.py` | Render ablation comparison tables + plots + p-values |
| `pages/5_📈_Live_Monitoring.py` | Per-call latency + token cost + rolling success rate |
| `api/main.py` | FastAPI app: POST `/rca/run`, GET `/rca/status/{id}`, SSE `/rca/stream/{id}`, rate limit, CORS, optional bearer auth |
| `run_pipeline.py` | CLI: end-to-end pipeline (data → detect → KB → agents → eval); supports `--dataset sebd` |
| `src/cli.py` | Top-level CLI with subcommands `pipeline`, `ablation`, `eval`, `build-kb`, `build-graph` |

### Scripts

| Script | Purpose |
|---|---|
| `download_datasets.py` | Download IBM Telco + Maven datasets to `data/raw/` |
| `build_graph_rag.py` | Extract entities + relations from playbooks → pickle NetworkX graph |
| `generate_demo_results.py` | Pre-generate demo RCA outputs for Streamlit fast-path |
| `export_mlflow_results.py` | Export MLflow run metrics to a flat JSON for plotting |
| `generate_sebd.py` | Synthetic billing dataset generator with anonymisation |
| `plot_results.py` | Publication-ready matplotlib figures for dissertation |

## Dependency layering

```
Layer 0:  config.py, requirements.txt, .gitignore
Layer 1:  src/utils/{logging, test_data, cache, rate_limit, inference_log}
Layer 2:  src/data/{loader, anomaly_injector, augmentor}
Layer 3:  src/detection/detector
Layer 4:  src/llm/{providers + registry}
Layer 5:  src/rag/{embedder, chunker}
Layer 6:  data/corpus/rca_playbooks/*.md (8 docs)
Layer 7:  src/rag/{knowledge_base, reranker, hybrid_retriever, graph_rag}
Layer 8:  src/agents/{state, prompts, llm_utils}
Layer 9:  src/agents/{swarm_router, investigator}
Layer 10: src/agents/{reasoner, critic, reporter}
Layer 11: src/agents/graph (LangGraph orchestration)
Layer 12: src/evaluation/{metrics, llm_judge, stats}
Layer 13: src/utils/{tracing, observability}, src/mlflow_tracking
Layer 14: src/cli, src/demo/demo_loader
Layer 15: run_pipeline.py
Layer 16: api/main.py
Layer 17: app.py, pages/*
Layer 18: tests/* (cross-cuts all layers)
Layer 19: Dockerfile, docker-compose.yml, deploy/*, .github/workflows/test.yml
Layer 20: scripts/* (most depend on Layer 7+)
Layer 21: Result artifacts — models/isolation_forest_model.joblib, pipeline_results.json
```

This layering is the basis for the week-by-week commit plan in [`SPEC.md`](../../SPEC.md) §2.
