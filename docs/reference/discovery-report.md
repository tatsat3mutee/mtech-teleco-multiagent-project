# As-Built Reference — System Summary

> **As-built implementation reference — not a design document.** This file inventories the
> system *as currently implemented*, kept for the implementation chapter and reproducibility
> appendix. For design intent, rationale, and rejected alternatives see [../DESIGN.md](../DESIGN.md).
> Measured evaluation results are reported in the dissertation's results chapter, not here.

## 1. What it is

A reproducible, production-style multi-agent investigation system that:
1. Ingests telecom billing data (IBM Telco churn, Maven telecom, SEBD enterprise billing).
2. Synthetically injects 5 billing anomaly classes for evaluation: zero-billing, duplicate charges, usage spikes, CDR failures, SLA breaches.
3. Detects suspicious billing rows using IsolationForest + rule pre-filter.
4. Retrieves grounding evidence from 8 telecom RCA playbooks via a hybrid retriever (BM25 + dense + reciprocal rank fusion) augmented with a knowledge graph (GraphRAG).
5. Orchestrates four LLM agents — **Investigator → Reasoner → Critic → Reporter** — using LangGraph with a conditional critic revision loop.
6. Produces a structured JSON RCA report (root cause, evidence chunks, severity, recommended actions).
7. Evaluates output with ROUGE-L, BERTScore, RAGAS faithfulness, 4-axis LLM-as-Judge, and statistical tests (bootstrap CI + Wilcoxon paired-rank).
8. Tracks every run in MLflow and Langfuse; serves via Streamlit (5 pages) and optional FastAPI (SSE streaming).

## 2. Headline research novelty

**GraphRAG over telecom domain playbooks** combined with **multi-agent investigation that includes a critic revision loop** and **anomaly-type-aware SWARM routing**. The ablation study (5 configurations, A=No-RAG → E=GraphRAG+4-Agent) on 60 hand-curated ground-truth incidents quantifies the contribution of each component with paired-bootstrap significance testing.

## 3. Why it matters

- Telecom operators lose 1–3% of revenue to billing errors that go undiagnosed; manual RCA averages 4–8 engineer-hours per incident.
- LLM-only RCA hallucinates causes (no grounding) and isn't auditable.
- Vanilla RAG can't follow multi-hop relationships (CDR → Service → SLA → Refund Policy) — that's where GraphRAG earns its place.
- A critic loop makes the output defensible: every hypothesis is reviewed for grounding before being reported.

## 4. Project shape (high level)

| Dimension | Value |
|---|---|
| Lines of code (Python) | ~8,000 production + ~1,600 test |
| Source modules | 38 across 7 packages (`data`, `detection`, `rag`, `agents`, `evaluation`, `llm`, `utils`) |
| Streamlit pages | 5 |
| FastAPI endpoints | 4 (POST /rca/run, GET /rca/status, SSE /rca/stream, GET /health) |
| Tests | 114 across 13 files (offline-safe via mock LLM fixtures) |
| Datasets supported | 3 (IBM Telco, Maven, SEBD enterprise billing) |
| Domain playbooks | 8 markdown RCA documents |
| Ground truth corpus | 60 hand-curated incident RCAs |
| LLM providers wired | 2 (Groq, OpenRouter) via LiteLLM Router — 4 model deployment slots |
| Evaluation metrics | ROUGE-L, BERTScore, RAGAS faithfulness, LLM-as-Judge (4 axes), detection F1/ROC-AUC |
| Statistical tests | Bootstrap 95% CI, paired-bootstrap p-values, Wilcoxon signed-rank |
| Ablation configurations | 5 (A: No-RAG, B: RAG-only, C: Single-agent, D: 4-agent, E: GraphRAG + 4-agent) |
| Deployment | Docker Compose, Heroku Procfile, optional VPS with nginx |

## 5. Defensible contributions (use these in Abstract + Ch 1 §1.5)

1. **Domain-grounded multi-agent RAG architecture** for telecom billing RCA with a formal critic quality gate.
2. **GraphRAG layer** that materialises entity/relation structure from 8 RCA playbooks and enables multi-hop retrieval.
3. **SWARM routing** mapping each anomaly type to an appropriate retrieval strategy (vector-first, graph-first, hybrid).
4. **60-item curated ground truth** for telecom billing RCA — reusable evaluation benchmark.
5. **5-configuration ablation study** with paired-bootstrap significance — quantifies each architectural decision.
6. **Production-grade observability**: per-call cost, latency, token count, multi-provider fallback, Langfuse traces.
7. **Reproducibility**: 87 offline-safe tests + Docker Compose + MLflow tracking = full re-run from clean clone.

## 6. Honest limitations (use in Ch 7 §7.2)

- Ground truth is hand-curated by one author; no inter-annotator agreement study.
- LLM-as-Judge has known bias (favours longer, more verbose outputs).
- Synthetic anomaly injection may not reflect real-world distribution shift.
- GraphRAG taxonomy is hand-curated, not learned.
- Evaluation on English playbooks only; no multilingual generalisation tested.
- No live A/B test with telecom operators; results are offline only.

## 7. Plan from here

See [../../SPEC.md](../../SPEC.md) §2 for the 9-week week-by-week commit plan.
