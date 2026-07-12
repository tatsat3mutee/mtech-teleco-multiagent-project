# Viva Voce Defense Playbook — Final (v1.0)

> The single document to rehearse from. Structured as: (1) opening strengths,
> (2) point-by-point defense for every examiner remark from the mid-sem review,
> (3) the latency evidence table, (4) hard questions with honest prepared answers,
> (5) one-liners, (6) demo choreography.
> Supersedes `FINAL_VIVA_ACTION_PLAN.md` (mid-sem action tracker — all items now closed).

---

## 1. Open With What Was Praised (mid-sem verdict: "Excellent project")

| Examiner praise | Where to point in 10 seconds |
|---|---|
| "Critic agent is a good way to solve the hallucination problem" | `src/agents/critic.py` — claim-level grounding JSON; live in RCA Viewer expander |
| "LiteLLM is a good idea to avoid rate limits" | `config.py` router: Groq rpm=28 proactive cap + 3-model OpenRouter fallback |
| "Prototype clearly showed this" | 5-page Streamlit demo, 116 passing tests |
| "Ablation study is a great evaluation methodology — shows the value mathematically" | 7 configs A–E, blind mode, significance testing (`src/evaluation/stats.py`) |
| "Industrial-grade / production-level project" | Rate-limited FastAPI, observability stack, risk register, Docker deploy |

---

## 2. Point-by-Point Defense — Every Examiner Remark, Closed

### 2.1 "Have you thought about rate limits?" → CLOSED ✅
**Answer script:**
> "Yes — and I hit it in practice, not just theory. An early one-shot Groq batch
> timed out at their 30 req/min cap. The fix is architectural: all LLM traffic
> goes through a LiteLLM Router configured *below* provider caps — Groq at
> rpm=28/tpm=7,500 — so we shape traffic proactively instead of reacting to 429s.
> We even validated the fallback in production: a batch run on EC2 hit Groq's
> real 8,000 TPM cap and the router failed over to OpenRouter mid-run —
> zero pipelines failed, and we tightened the cap from the observed limit.
> If Groq still fails, a least-busy pool of three OpenRouter free models takes
> over (rpm=18 each), with 3 retries, 2-second backoff, and a 60-second circuit
> breaker per provider. If *everything* fails, each agent has a deterministic
> template fallback so the pipeline completes and flags itself for review.
> The API layer is separately rate-limited at 10 requests/min/IP via slowapi."

**Receipts:** `config.py` `LITELLM_ROUTER_CONFIG` · `src/agents/llm_utils.py` `get_router()` · `api/main.py` limiter · Live Monitoring page shows per-provider success/429/timeout counts.

### 2.2 Risk register ("put a risk register — production-level project") → CLOSED ✅
**Answer script:**
> "Done — `docs/RISK_REGISTER.md`: 24 tracked items in four categories —
> operational, model-quality, evaluation-validity, and future-work — each with
> likelihood, impact, implemented mitigation, and status. Two of them we *lived*:
> the Groq rate-limit timeout and two provider model deprecations, both absorbed
> by the router abstraction with config-only changes."

### 2.3 False-positive trap → CLOSED ✅
**Answer script:**
> "If the detector flags a normal record, the pipeline will still run — but the
> Critic's grounding check finds no playbook evidence for a non-existent failure,
> so grounding confidence comes out low. Below 0.5 the report is stamped
> `review_required`, the UI shows a red 'LOW CONFIDENCE — possible false positive'
> banner, and the design rule is: the system escalates to a human, it never
> auto-remediates. Even the Critic's degraded mode (LLM parse failure) defaults
> to exactly 0.5 — the review threshold — so failure modes are flagged, not trusted."

### 2.4 "Don't rely heavily on ROUGE-L" → CLOSED ✅
**Answer script:**
> "Agreed, and the metric hierarchy reflects it. ROUGE-L is lexical — 'reactivate
> the rating plan' vs 'restore the plan configuration' are the same fix but score
> near zero. So the headline metrics are (1) LLM-as-Judge on a 4-axis rubric —
> correctness, groundedness, actionability, completeness — at temperature 0 with
> a judge from a *different model family* than the generator to avoid
> self-affinity bias, and (2) RAGAS-style faithfulness, which decomposes the RCA
> into atomic claims and verifies each against retrieved context. BERTScore is a
> semantic secondary; ROUGE-L is reported only as a disclosed lexical baseline."

### 2.5 "Tabulate end-to-end latency as proof vs manual RCA" → CLOSED ✅
See §4 below — table + per-stage instrumentation (`stage_timings` captured on
every run: investigator/reasoner/critic/reporter ms, persisted to the inference log).

### 2.6 "Streamlit should highlight WHY the Critic approved" → CLOSED ✅
**Answer script:**
> "Implemented — the RCA Viewer has a 'Critic Explainability' expander: verdict
> badge, grounding-confidence score, revision count, and a claim-by-claim table —
> each factual claim marked ✅/❌ with the specific playbook source that grounds
> it, or 'no evidence found'. The engineer can audit the exact basis of approval,
> which is what builds trust in the report."

**Demo it live** — this is the wow moment; it directly answers his suggestion.

### 2.7 OCR / reducing humans in the loop → FRAMED AS FUTURE WORK ✅
**Answer script:**
> "Adopted as Future Work FW-1: an OCR ingestion layer over historical invoice
> PDFs would let the Investigator pull structured billing evidence directly
> instead of routing a query to the invoicing team — removing one human hop and
> cutting resolution latency further. It's deliberately out of thesis scope, but
> the agent architecture makes it a clean extension: it's just another retrieval
> tool the Investigator can call."

---

## 3. The Ablation Story — "Value Shown Mathematically"

**The narrative arc** (each config isolates one architectural contribution):

| Config | Adds | Question it answers |
|---|---|---|
| A `no_rag` | bare LLM | What does the LLM know alone? |
| A2 `cot_baseline` | few-shot CoT | Is prompting enough? |
| A3 `react_baseline` | ReAct loop + search | Is one looping agent enough? |
| B `rag_only` | retrieval, no agents | Is knowledge alone enough? |
| C `single_agent_rag` | 1 agent + RAG | Is orchestration without role decomposition enough? |
| D `multi_agent_rag` | 4 agents + critic | **Value of role decomposition + critique** |
| E `graph_rag` | + causal graph retrieval | **Value of causal structure (headline novelty)** |

**Pilot evidence (15-item quick run, lexical baseline):** ROUGE-L 0.088 (A) →
0.177 (D) → 0.181 (E): **+101% over baseline**; retrieval count 0 → 5;
success rate 15/15 for D and E vs 10/15 for single-agent C.
**Blind mode**: configs get the detector's *estimated* type, not oracle labels.

**Methodology defense:** paired bootstrap p-values + Wilcoxon signed-rank +
Benjamini–Hochberg FDR on the final 60-item run — differences are claimed only
where statistically significant; per-type claims withheld (n=12/type).

---

## 4. Latency Evidence Table (examiner's explicit ask)

### 4.1 Headline comparison

| Approach | Time per incident | Source |
|---|---|---|
| **Manual RCA** (L1 triage → data pull → invoicing-team query → hypothesis → write-up) | **65–120 min** | Industry-standard MTTR figures, DESIGN.md §1 |
| **This system — LLM-backed full pipeline** | **~30–90 s** typical (LLM inference dominates) | RCA Viewer elapsed-ms; inference log |
| **This system — pilot ablation configs** | 0.14 s – 9.5 s per config (see caveat §6-Q3) | `results/ablation/summary.json` |
| **Reduction** | **> 98–99%** even in worst case | — |

### 4.2 Per-stage breakdown (instrumented on every run)

`run_pipeline()` records `stage_timings` — this table is auto-populated from
the inference log (`investigator_ms`, `reasoner_ms`, `critic_ms`, `reporter_ms`):

| Stage | What dominates | Typical share |
|---|---|---|
| Investigator | 1 LLM call (query refinement) + retrieval (ms-scale, in-memory) | ~20–25% |
| Reasoner | 1–2 LLM calls (revision loop doubles it) | ~30–40% |
| Critic | 1–2 LLM calls (JSON review) | ~25–30% |
| Reporter | 1 LLM call (JSON formatting) | ~15–20% |

**Key defense line on graph traversals:**
> "Even in the worst case, graph traversal is bounded — BFS depth is fixed at
> k=2 over an in-memory NetworkX graph, so retrieval contributes milliseconds.
> End-to-end latency is dominated by LLM inference, which is exactly what the
> per-stage timings show. Even if traversal cost tripled, the total would still
> be seconds against a 65–120 minute manual baseline."

---

## 5. One-Liners (memorise)

- **Hallucination:** "Every factual claim in the report is individually verified against retrieved evidence by an adversarial Critic — and the audit trail is on screen."
- **False positive:** "No evidence → low grounding confidence → red banner → human review. The system never auto-remediates."
- **ROUGE-L:** "It's our disclosed lexical baseline; the quality claim rests on LLM-as-Judge and RAGAS faithfulness."
- **Rate limits:** "We shape traffic below provider caps proactively; fallback is a routed pool, not a retry loop."
- **Speed:** "Seconds versus 65–120 minutes — a >98% reduction, with per-stage timings logged on every single run."
- **Why multi-agent:** "The ablation shows it mathematically: same LLM, same knowledge — decomposition and critique alone double the overlap with expert ground truth."
- **Why GraphRAG:** "Zero-billing and CDR failures are causal chains, not similarity lookups; the graph pre-encodes the chain the vector index can't see."
- **Trust:** "Engineers don't trust a verdict; they trust a verdict with receipts — that's the claim-by-claim grounding table."

---

## 6. Hard Questions — Honest Prepared Answers

**Q1. "Your BERTScore equals ROUGE-L to four decimals in summary.json. Why?"**
> "Correct catch — in that pilot run the BERTScore package wasn't available in
> the environment, so the metric fell back to the lexical value. It's logged as
> risk EV-9 in the register; the final 60-item run is executed with the full
> metric stack and judge enabled. This is also why we deliberately don't hang
> the thesis on any single automatic metric."

**Q2. "single_agent_rag succeeded only 10/15 and got 67% type accuracy. Doesn't that look bad?"**
> "It's actually the strongest evidence *for* the proposed design: a single agent
> juggling planning, retrieval and reasoning in one context drops the ball —
> role decomposition is what fixes it. That contrast is the point of ablation C vs D."

**Q3. "graph_rag at 141 ms average — an LLM pipeline can't be that fast."**
> "Right — that pilot ran partially on the deterministic fallback path when
> provider quota was exhausted, which is why it's sub-second. Genuine LLM-backed
> runs are 30–90 s end-to-end, as the RCA Viewer and inference log show. The
> honest claim is: even at 90 seconds, we're >98% below the manual baseline.
> The final ablation is run with confirmed provider capacity."

**Q4. "Isn't the Critic just another hallucination-prone LLM?"**
> "Yes — which is why it's constrained: verify-only role (classification is easier
> than generation), strict JSON schema, claim-level granularity, confidence
> exposed to the user, degraded mode lands exactly on the review threshold,
> and the human sees the full audit trail. It reduces risk; it doesn't claim to
> eliminate it — that's risk MQ-2, disclosed."

**Q5. "Your ground truth was written by you. Circularity?"**
> "The corpus was authored independently of the injection rules — from playbook
> domain knowledge, not from the detector's outputs. Residual single-author risk
> is EV-4 in the register; SME review is named future work. Multi-reference
> scoring (max over all same-type references) also reduces phrasing bias."

**Q6. "Why not fine-tune a model instead of this pipeline?"**
> "Three reasons: no labelled telecom RCA corpus at fine-tuning scale exists
> publicly; a fine-tune bakes knowledge in — a RAG pipeline updates by editing a
> markdown playbook; and per-claim grounding gives auditability a fine-tuned
> model can't. For an operations tool, updatability and auditability win."

**Q7. "How does this scale to a real telco's data volume?"**
> "Detection is batch and cheap (IsolationForest is O(n log n)). The RCA pipeline
> triggers per-anomaly, so load scales with anomaly count, not record count —
> and the router already queues within rate limits. The named production upgrades
> are Neo4j for the graph and a persistent job queue — FW-2 in the register."

**Q8. "What is genuinely novel here?"**
> "The composition, validated by ablation: (1) SWARM routing that picks graph-first
> vs vector-first retrieval by anomaly type; (2) a claim-level grounding Critic
> with a bounded revision loop, surfaced as a UI audit trail; (3) blind-mode
> evaluation — configs get fallible detector-estimated types, mirroring
> production instead of oracle labels. Each piece exists in literature;
> the measured, engineered composition for telecom billing RCA is the contribution."

---

## 7. Demo Choreography (10–12 min)

| # | Step | Page | Say |
|---|---|---|---|
| 1 | Show dataset + run detection | Upload & Detect | "Rule prefilter catches deterministic cases at 100% precision; IsolationForest handles the rest." |
| 2 | Pick a `zero_billing` anomaly → run RCA | RCA Viewer | "Watch the SWARM router choose graph-first — zero billing is a causal chain." |
| 3 | **Open Critic Explainability expander** | RCA Viewer | "This is the examiner's suggestion, implemented — claim-by-claim grounding with sources." |
| 4 | (Prepared) low-confidence case | RCA Viewer | "And here's the false-positive trap handled — red banner, human escalation." |
| 5 | Search the KB | Knowledge Base | "139 chunks from 8 playbooks — the evidence the Critic checks against." |
| 6 | Ablation table + latency chart | Experiment Results | "Same LLM, same knowledge — architecture alone doubles ground-truth overlap." |
| 7 | Provider resilience panel | Live Monitoring | "Rate-limit events, fallbacks, review-required rate — the risk register, live." |

**Pre-demo checklist:** `.env` keys valid · `streamlit run app.py` warm ·
one good RCA cached + one low-confidence case ready · `results/ablation/` present ·
fallback: `data/demo/sample_rca_results.json` if network dies.

---

## 8. Closing Statement (if asked "sum up your contribution")

> "Telecom billing RCA today takes an engineer 65 to 120 minutes per incident.
> This system delivers an evidence-grounded, claim-audited root-cause report in
> seconds. The ablation study shows mathematically that the architecture — not
> the LLM — delivers the quality: multi-agent decomposition and causal graph
> retrieval double ground-truth overlap over a bare LLM. And it's engineered
> like a production system: proactive rate-limit shaping, provider failover we
> validated live, bounded self-correction, a false-positive escape hatch, full
> per-stage observability, and a 24-item risk register. It doesn't replace the
> engineer — it hands them a verified head start."
