# How the System Works — End-to-End Explanation (v1.0)

> Narrative walkthrough written for a reviewer reading the repository for the
> first time (the examiner asked for the repo URL — this is the front door).
> Follows one real anomaly from raw CSV to final audited RCA report.
> Companion docs: `docs/ARCHITECTURE_FINAL.md` (structure),
> `docs/RISK_REGISTER.md` (risks), `docs/VIVA_DEFENSE.md` (viva prep).

---

## The Problem, In One Minute

When a telecom customer's bill goes wrong — charged zero, charged twice, a usage
spike, a dropped CDR batch, an SLA breach — a billing engineer today spends
**65–120 minutes** per incident: triaging the alert, pulling account data,
querying the invoicing team, forming a hypothesis, writing it up. Most of that
time is *evidence gathering and recall*, not judgement.

This system automates the evidence-and-hypothesis loop and returns, in seconds,
a structured root-cause report **whose every factual claim has been checked
against documented operational knowledge** — leaving the engineer with only
the judgement step.

---

## Walkthrough: One Anomaly's Journey

We'll follow account `7590-VHVEG`: an active fiber-optic customer, 29 months of
tenure, `TotalCharges` $1,889.50 — but this month's `MonthlyCharges` is **$0.00**.

### Step 0 — Data & injection (offline, `run_pipeline.py`)
Three datasets feed the system: IBM Telco Churn (7,043 customers), Maven Telecom
(7,043), and SEBD (54K synthetic billing events). Because public data contains no
labelled billing anomalies, we **inject** five types at realistic ratios
(zero_billing 3%, duplicate_charge 2%, usage_spike 3%, cdr_failure 1.5%,
sla_breach 2%) with a fixed seed — giving us ground-truth labels to score
detection against, with the known-and-disclosed caveat that injected anomalies
put an *upper bound* on detection metrics.

### Step 1 — Detection (`src/detection/detector.py`)
Two-stage:
1. **Rule prefilter** — deterministic patterns first: `MonthlyCharges == 0 AND
   tenure > 0` is flagged with 100% precision. Cheap, explainable, no ML risk.
2. **IsolationForest** (200 trees, contamination 0.1, seed 42) over scaled
   features catches the non-obvious cases and assigns each an anomaly
   confidence score.

A heuristic then *estimates* the anomaly type from the record's shape. This
estimate is fallible **by design** — the whole downstream pipeline is evaluated
receiving this fallible estimate ("blind mode"), because that's what production
looks like. Our account is flagged: `zero_billing`, confidence 0.95.

### Step 2 — The four-agent pipeline (`src/agents/graph.py`)
The anomaly record enters a LangGraph state machine:

```
investigator → reasoner → critic ─(accept)→ reporter
                   ↑          │
                   └─(revise, max once)┘
```

**Investigator** — first decision: *where to look*. The SWARM router maps
anomaly type → retrieval strategy. `zero_billing` is a **causal-chain** failure
(zero charge ← rating engine ← rate card ← billing-cycle boundary), so it routes
**graph_first**: entities are extracted from the query, matched to nodes in a
NetworkX causal graph built from the playbook corpus (7 entity types, 6 relation
types), and a 2-hop BFS walks the causal neighbourhood; matched nodes map back
to text chunks. Pattern-shaped anomalies (`usage_spike`, `duplicate_charge`,
`sla_breach`) instead route **vector_first** through a hybrid retriever — BM25
lexical + ChromaDB dense (all-MiniLM-L6-v2), fused with Reciprocal Rank Fusion.
Both paths return top-K evidence chunks from the **139-chunk knowledge base**
(8 curated telecom RCA playbooks). The router's reasoning is stored and shown
in the UI ("routing explanation").

**Reasoner** — generates the root-cause hypothesis from anomaly + evidence:
*"Rating engine configuration error: rate card returned null at the billing
cycle boundary; charge leakage 100% for the current cycle."*

**Critic** — the hallucination firewall. A separately-prompted adversarial
reviewer ("senior billing SRE reviewing a junior engineer's RCA") receives the
hypothesis and the *same evidence* and must return strict JSON: a verdict
(`accept`/`revise`), reasons, a confidence score, and — crucially — a
**claim-by-claim grounding table**: every factual claim extracted, marked
grounded/ungrounded, with the exact evidence source named. If the verdict is
`revise`, the Critic's specific objections are fed back into the Reasoner's
prompt and the hypothesis is regenerated — **exactly once** (hard bound, no
loops). If evidence is thin — say the detector false-positived on a healthy
record and no playbook matches — grounding confidence comes out low, and below
0.5 the run is stamped `review_required`: red banner in the UI, human
escalation, never auto-remediation.

**Reporter** — formats the accepted hypothesis into the final JSON: root cause,
supporting evidence (with sources), recommended actions, severity, confidence,
summary.

### Step 3 — What comes out
One JSON object per incident containing the RCA report **plus full telemetry**:
end-to-end `latency_ms`, per-stage `stage_timings` (investigator/reasoner/
critic/reporter), token usage, retrieval strategy and count, the complete critic
block (verdict, reasons, confidence, claims, attempts), and `review_required`.
Everything an auditor — or an examiner — could ask for is in the artifact itself.

### Step 4 — Where it's seen
- **RCA Viewer** (Streamlit): the report, plus the **"⚖️ Critic Explainability"**
  expander — verdict badge, confidence, revision count, and the ✅/❌ claim
  table with evidence sources. This is why an engineer can *trust* the report:
  it's a verdict with receipts.
- **Live Monitoring**: aggregate telemetry from the inference log — latency,
  tokens, review-required rate, per-provider rate-limit/fallback events.
- **FastAPI** (`/rca/run`, 10 req/min/IP, SSE progress streaming) for
  programmatic use.

---

## The Plumbing That Makes It Reliable

**Rate limits (lived problem → architecture).** An early Groq batch run hit the
30 req/min cap and timed out. Fix: every LLM call goes through a LiteLLM Router
capped *below* provider limits (Groq rpm=28/tpm=28K), with a least-busy fallback
pool of three OpenRouter free models, retries with backoff, and per-provider
60-second circuit breakers. Model deprecations (it happened twice) are config
edits, not code changes. Total failure of all providers degrades to
deterministic template output flagged for review — the pipeline never crashes.

**Observability.** Four layers: Langfuse (every prompt/response, per-session),
MLflow (experiments), a SQLite/PostgreSQL inference log (production telemetry
incl. per-stage ms), and JSONL step traces. 116 automated tests run offline.

---

## How We Know It Works (evaluation design)

Seven **ablation configurations** isolate each architectural claim: bare LLM →
chain-of-thought → ReAct → RAG-only → single-agent → **multi-agent (proposed)**
→ **multi-agent + GraphRAG (headline)**. All configs share the same LLM and the
same knowledge base — so any difference is attributable to *architecture*.

Scoring hierarchy (deliberate): **LLM-as-Judge** (4-axis rubric, independent
judge model family, temperature 0) and **RAGAS-style faithfulness** (atomic
claim verification) lead; BERTScore is the semantic baseline; **ROUGE-L is
reported only as a disclosed lexical baseline** because it penalises correct
paraphrases. Claims of difference are gated by paired bootstrap tests, Wilcoxon
signed-rank, and Benjamini–Hochberg FDR correction over a 60-incident
ground-truth corpus (12 per type, authored independently of the injection rules).

Pilot signal: ROUGE-L overlap with expert ground truth **doubles** (0.088 →
0.181) going from bare LLM to the full graph-augmented multi-agent system, with
15/15 completion vs 10/15 for the single-agent variant.

And the number the examiner asked to see: **65–120 minutes manual → seconds to
~1.5 minutes automated**, per-stage timings logged on every run — a >98%
reduction in investigation time even in the worst case.

---

## What It Deliberately Does *Not* Do

- It does **not** auto-remediate — low-confidence output escalates to a human.
- It does **not** claim detection-metric generality — injected anomalies are an
  upper bound, disclosed.
- It does **not** hide its failure modes — 24-item risk register
  (`docs/RISK_REGISTER.md`), two entries of which were lived and mitigated.

## Where It Goes Next (future work)

OCR ingestion of historical invoice PDFs (removing the invoicing-team routing
hop — examiner's suggestion), Neo4j-backed persistent graph, learned
entity/relation extraction, SME-reviewed ground truth, automated KB refresh.
