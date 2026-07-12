# Risk Register — Consolidated (v1.0)

> Requested explicitly by the mid-sem examiner (Mohana Murali G.):
> *"Because yours is already an industrial-grade, production-level project —
> put a risk register."*
> This consolidates and extends the risks previously scattered across
> `docs/DESIGN.md` §8 (threats to validity) and `FINAL_REPORT_CONTENT.md`.
> Maps to dissertation §6.3 / Appendix.
>
> **Scales** — Likelihood (L): Low / Medium / High · Impact (I): Low / Medium / High
> **Status**: ✅ Mitigated · 🔶 Partially mitigated · 📋 Accepted & disclosed · 🔭 Future work

---

## A. Operational / Engineering Risks

| ID | Risk | L | I | Mitigation (implemented) | Status | Evidence |
|---|---|---|---|---|---|---|
| **OP-1** | **LLM API rate limits** (Groq 30 rpm / 30K tpm hard caps) exhaust mid-pipeline | H | H | LiteLLM Router with **proactive** rpm/tpm caps below provider limits (28/28,000); `least-busy` fallback across 3 OpenRouter free models (rpm=18 each); retries (3× @2s); 60s provider cooldown after 2 failures | ✅ | `config.py` `LITELLM_ROUTER_CONFIG`, `src/agents/llm_utils.py` — **lived**: Groq one-shot batch timed out early in project → led to this design |
| **OP-2** | **LLM model deprecation** by provider | M | H | Provider-agnostic router abstraction — model swap is a config-only change | ✅ | **Lived twice**: Groq retired Llama-3.3-70B → GPT-OSS-120B swap; OpenRouter retired free DeepSeek → pool updated. Zero agent-code changes |
| **OP-3** | **All LLM providers down** simultaneously | L | H | Deterministic template fallbacks in every agent (Reasoner, Reporter); pipeline completes with `pipeline_status="partial"`, flagged for review | ✅ | `src/agents/reasoner.py` `_build_fallback_hypothesis()`, `reporter.py` `_generate_fallback_report()` |
| **OP-4** | **Critic infinite revision loop** (cost + latency blow-up) | L | H | Hard bound: `critic_attempts ≤ 1` in conditional edge; verdict criteria tuned to revise only on contradiction / thin evidence / ignored better cause | ✅ | `src/agents/critic.py` `should_revise()` |
| **OP-5** | **Graph-traversal latency growth** on complex multi-hop plans | M | M | BFS depth fixed at k=2; in-memory NetworkX (no network I/O); per-stage timing (`investigator_ms`) recorded on every run so any regression is observable; LLM inference — not traversal — dominates latency | ✅ | `src/agents/graph.py` `stage_timings`; latency table in `docs/VIVA_DEFENSE.md` §4 |
| **OP-6** | **API abuse / DoS** on public demo endpoint | M | M | slowapi 10 req/min/IP on `/rca/run`; optional API-key auth; CORS allowlist; input validation (regex, enums, 4 KB payload cap); UUID job IDs (anti-enumeration); job store LRU cap 1,000 + 1h TTL | ✅ | `api/main.py` |
| **OP-7** | **Demo-host state loss** (instance rebuild/teardown) — inference log & ChromaDB are instance-local | L | L | EC2+EBS persists across stop/start; on rebuild, ChromaDB regenerates from the version-controlled corpus in minutes; inference log is demo-scope; MLflow file-store retained for experiments | 📋 | `docs/AWS_DEPLOY.md`, deploy notes |
| **OP-8** | **KB staleness** — playbooks drift from real operations | M | M | KB rebuild is one command (`build_from_corpus(force_rebuild=True)`); UI exposes rebuild button; corpus is version-controlled markdown | 🔶 | `pages/3_📚_Knowledge_Base.py`; automated refresh = future work |

## B. Model-Quality / Hallucination Risks

| ID | Risk | L | I | Mitigation (implemented) | Status | Evidence |
|---|---|---|---|---|---|---|
| **MQ-1** | **LLM hallucination in RCA output** | H | H | Dedicated **Critic agent**: adversarial reviewer with claim-level grounding (every factual claim → grounded flag + evidence source); bounded revision loop feeds specific gaps back to Reasoner; mandatory evidence citations in report | ✅ | `src/agents/critic.py`; claim table shown in RCA Viewer UI |
| **MQ-2** | **Residual hallucination despite Critic** (Critic itself is an LLM) | M | H | Confidence score surfaced to user; `review_required` flag < 0.5; claim-by-claim audit trail in UI lets the engineer verify — system **assists**, never auto-remediates | 🔶 📋 | RCA Viewer "Critic Explainability" expander; disclosed in dissertation |
| **MQ-3** | **False-positive trap** — detector flags a normal record, pipeline still "explains" it | M | M | Absent playbook evidence ⇒ Critic grounding confidence is naturally low ⇒ red **"LOW CONFIDENCE — possible false positive"** banner + `review_required` → human escalation path | ✅ | `pages/2_🔍_RCA_Viewer.py` warning banner; examiner blind-spot #1 |
| **MQ-4** | **Critic degraded mode masks problems** (LLM parse failure → default accept @ 0.5) | L | M | Default confidence 0.5 sits exactly at the review threshold → such runs are flagged rather than silently trusted | ✅ | `src/agents/critic.py` degraded path |

## C. Evaluation-Validity Risks (threats to validity)

| ID | Risk | L | I | Mitigation | Status | Evidence |
|---|---|---|---|---|---|---|
| **EV-1** | **Injected anomalies too separable** → inflated detection metrics | M | M | Detection metrics reported as **upper bound**; thesis claim rests on RCA quality, not detection accuracy | 📋 | `docs/DESIGN.md` §8 R1 |
| **EV-2** | **SLA-breach label leakage** (threshold derived from same quantile detector observes) | M | M | Disclosed; per-type detection claims withheld for this class | 📋 | DESIGN.md R2 |
| **EV-3** | **Churn features ≠ production billing KPIs** | H | M | Declared scope limit; SEBD synthetic track provides richer billing schema | 📋 | DESIGN.md R3 |
| **EV-4** | **Single-author ground truth → circularity** | M | H | GT corpus (60 items) authored **independently of injection rules**; SME review named as future work | 🔶 | DESIGN.md R4 |
| **EV-5** | **Over-reliance on ROUGE-L** (lexical metric penalises valid paraphrases) | H | H | Metric hierarchy inverted: **LLM-as-Judge + RAGAS faithfulness are headline**, BERTScore secondary, ROUGE-L disclosed as lexical baseline only | ✅ | `src/evaluation/llm_judge.py`; examiner blind-spot #2 |
| **EV-6** | **LLM-judge bias** (verbosity bias, self-affinity) | M | M | Temperature 0.0; explicit 4-axis rubric; **judge model family ≠ generator family** (Llama-3.3 judges GPT-OSS output) | ✅ | `config.py` judge block |
| **EV-7** | **Small eval sample** (60 items, 12/type) | M | M | Bootstrap 95% CIs, paired bootstrap p-values, Wilcoxon signed-rank, BH-FDR correction; per-type claims withheld | ✅ | `src/evaluation/stats.py` |
| **EV-8** | **Type leakage in ablation** (feeding oracle anomaly type to configs) | M | H | **Blind mode is default** — configs receive detector-estimated type; oracle mode requires explicit `--leak-types` flag and is labelled legacy | ✅ | `run_ablation.py` |
| **EV-9** | **Pilot-run artefacts** — current quick-run numbers have known anomalies (BERTScore silently equal to ROUGE-L; sub-second latencies indicate fallback-path runs) | H | M | Disclosed pre-emptively; final 60-item judge-enabled ablation re-run scheduled before submission; defense answer prepared | 🔶 | `docs/VIVA_DEFENSE.md` §6 hard questions |
| **EV-10** | **Hand-curated graph taxonomy** rather than learned extraction | M | L | Declared scope; learned entity/relation extraction named future work | 📋 | `docs/GRAPHRAG_DESIGN.md` §8 |

## D. Strategic / Long-Term (future-work register)

| ID | Item | Note |
|---|---|---|
| **FW-1** | **OCR invoice ingestion** — extract structured data from historical invoice PDFs, removing the invoicing-team routing hop (examiner suggestion; reduces human-in-the-loop and end-to-end resolution latency) | Dissertation Ch. 6 |
| **FW-2** | Neo4j (or similar) persistent graph store for production-scale corpora | GRAPHRAG_DESIGN §8 |
| **FW-3** | Learned entity/relation extraction replacing hand-curated taxonomy | GRAPHRAG_DESIGN §8 |
| **FW-4** | SME review of ground-truth corpus | EV-4 follow-up |
| **FW-5** | Automated KB refresh from live incident tickets | OP-8 follow-up |
| **FW-6** | Multilingual playbook support (currently English-only) | DESIGN.md §2.3 |

---

## Register Summary

- **24 risks tracked**: 8 operational, 4 model-quality, 10 evaluation-validity, 6 future-work items.
- **2 risks were lived, not hypothetical** (OP-1 rate-limit timeout, OP-2 model deprecation ×2) — and their mitigations were validated in production use.
- Governing principle: **the system assists and escalates; it never auto-remediates** (MQ-2/MQ-3), and **every quality claim is bounded by disclosed validity limits** (EV-*).
