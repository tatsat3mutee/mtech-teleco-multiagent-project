# SPEC: M.Tech Dissertation Delivery Plan
## Multi-Agent RAG for Telecom Billing RCA

> A forward-looking plan for building and evaluating the system over the
> dissertation period: scope, weekly build milestones, deliverables, and quality
> gates.

---

## 0. KEY DECISIONS

| # | Decision | Value |
|---|---|---|
| 1 | Repository | `mtech-teleco-multiagent-project` (private) |
| 2 | Mid-sem milestone tag | `v0.5-midsem` |
| 3 | Final milestone tag | `v1.0-final` |
| 4 | Dissertation format | BITS WILP (Word → PDF), double-spaced, ≤10MB, text-searchable |
| 5 | Authoring tool | MS Word + Grammarly |
| 6 | Build order | Dependency-first: data → detection → retrieval → agents → evaluation → UI |

---

## 1. PROJECT SETUP

### 1.1 Repository
1. Create the private GitHub repository `mtech-teleco-multiagent-project`.
2. Initialise locally and connect the remote:

```powershell
cd mtech-teleco-multiagent-project
git init -b main
git config user.name "<your name>"
git config user.email "<your GitHub email>"
git remote add origin https://github.com/tatsat3mutee/mtech-teleco-multiagent-project.git
```

### 1.2 Starting files

The repository starts with the planning and scaffolding documents:
- `.gitignore`, `LICENSE`, `README.md`, `SPEC.md`
- `docs/DESIGN.md` (design rationale — the primary design document)
- `docs/GRAPHRAG_DESIGN.md` (graph-retrieval design)
- `docs/diagrams/` (architecture and flow diagrams)

### 1.3 First commit
```powershell
git add .
git commit -m "chore: initial project skeleton and design docs"
git push -u origin main
```

---

## 2. WEEK-BY-WEEK BUILD PLAN

### Convention
- Each row is one logical commit (module + its test committed together).
- Run `pytest <test_file>` before committing each test.
- Build in dependency order so each module's prerequisites already exist.

---

### WEEK 1 — Foundation + Data (May 23–29)

| # | Commit msg | Files |
|---|---|---|
| 1 | `chore: project skeleton, requirements, config` | `config.py`, `requirements.txt` (start with: pandas, numpy, scikit-learn, pytest, python-dotenv), `src/__init__.py`, `src/data/__init__.py`, `src/utils/__init__.py`, expand README |
| 2 | `feat: data loader for IBM Telco and Maven datasets` | `src/data/loader.py`, `scripts/__init__.py`, `scripts/download_datasets.py` |
| 3 | `feat: SEBD enterprise billing loader` | `src/data/loader.py` (load_sebd function) |
| 4 | `feat: synthetic anomaly injector with 5 billing anomaly types` | `src/data/anomaly_injector.py` |
| 5 | `feat: data augmentor + utility logging` | `src/data/augmentor.py`, `src/utils/logging.py`, `src/utils/test_data.py` |
| 6 | `test: data pipeline + anomaly injector unit tests` | `tests/__init__.py`, `tests/conftest.py`, `tests/test_data_pipeline.py`, `tests/test_anomaly_injector.py` |
| 7 *(opt)* | `docs: project intro and quick-start in README` | README expansion |

---

### WEEK 2 — Detection + LLM Providers (May 30 – Jun 5)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: IsolationForest anomaly detector with rule pre-filter` | `src/detection/__init__.py`, `src/detection/detector.py` |
| 2 | `feat: Groq LLM provider` | `src/llm/__init__.py` (basic), `src/llm/groq_provider.py` |
| 3 | `feat: Kimi, Gemini, DeepSeek provider fallbacks` | `src/llm/kimi_provider.py`, `src/llm/gemini_provider.py`, `src/llm/deepseek_provider.py` |
| 4 | `feat: LLM provider registry with auto-detect and fallback chain` | expand `src/llm/__init__.py`, root `test_llm.py` smoke script |
| 5 | `feat: rate limiter + response cache utilities` | `src/utils/rate_limit.py`, `src/utils/cache.py`, `src/utils/inference_log.py` |
| 6 | `test: LLM registry + detection smoke tests` | `tests/test_llm_registry.py`, `tests/test_utils.py` |
| 7 *(opt)* | `chore: pin LLM SDK versions (groq, openai, litellm)` | requirements.txt |

---

### WEEK 3 — RAG Foundation + Corpus (Jun 6–12)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: sentence-transformers embedder with lazy loading` | `src/rag/__init__.py`, `src/rag/embedder.py` |
| 2 | `feat: semantic sentence-level chunker` | `src/rag/chunker.py` |
| 3 | `data: add 8 telecom RCA playbooks` | all `data/corpus/rca_playbooks/*.md` |
| 4 | `feat: ChromaDB knowledge base indexing and retrieval` | `src/rag/knowledge_base.py` |
| 5 | `feat: cross-encoder reranker` | `src/rag/reranker.py` |
| 6 | `test: chunker + KB + embedder tests` | `tests/test_chunker.py`, `tests/test_knowledge_base.py` |
| 7 *(opt)* | `docs: KB build instructions in README` | README |

---

### WEEK 4 — Hybrid + GraphRAG + Ground Truth (Jun 13–19)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: hybrid retriever - BM25 + dense + RRF fusion` | `src/rag/hybrid_retriever.py` |
| 2 | `feat: graph RAG with entity/relation extraction + k-hop traversal` | `src/rag/graph_rag.py` |
| 3 | `script: build graph rag - extract entities, build networkx graph` | `scripts/build_graph_rag.py` |
| 4 | `data: 60-item curated ground truth RCAs` | `data/eval/ground_truth_rca/incident_001.json … incident_060.json`, `data/eval/ground_truth_rca/ground_truth_rca_60.json` |
| 5 | `test: hybrid retriever and graph rag tests` | `tests/test_hybrid_retriever.py`, `tests/test_graph_rag.py` |
| 6 | `test: SEBD loader + hybrid retriever tests` | `tests/test_hybrid_retriever.py`, `tests/test_graph_rag.py` |
| 7 | `docs: graphrag design note` | `docs/GRAPHRAG_DESIGN.md` (already scaffolded — fill prose) |

---

### WEEK 5 — Multi-Agent + Mid-Sem Demo (Jun 20–27) **— HEAVY WEEK**

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: agent state schema + prompts for 4 agents` | `src/agents/__init__.py`, `src/agents/state.py`, `src/agents/prompts.py` |
| 2 | `feat: litellm router + llm utils with health checks` | `src/agents/llm_utils.py` |
| 3 | `feat: swarm router + investigator agent` | `src/agents/swarm_router.py`, `src/agents/investigator.py` |
| 4 | `feat: reasoner + critic with revision loop + reporter agents` | `src/agents/reasoner.py`, `src/agents/critic.py`, `src/agents/reporter.py` |
| 5 | `feat: langgraph orchestration with conditional critic edge` | `src/agents/graph.py`, `tests/test_critic_and_tracing.py`, `tests/test_swarm_router.py` |
| 6 | `feat: end-to-end pipeline runner + tracing` | `run_pipeline.py`, `test_pipeline.py`, `src/utils/tracing.py` |
| 7 | `feat: minimal streamlit homepage + rca viewer for midsem demo` | `app.py` (minimal version), `pages/2_🔍_RCA_Viewer.py` (basic version) |
| 8 *(diagrams)* | `docs: architecture, data flow, agent sequence diagrams` | `docs/diagrams/architecture.drawio` + .png, `data_flow.drawio` + .png, `agent_sequence.drawio` + .png |
| 9 *(tag)* | — | `git tag v0.5-midsem && git push --tags` |

**Tip:** Test pipeline a full week before Jun 27. Record 2-min demo video as backup.

---

### WEEK 6 — Evaluation + Observability (Jun 28 – Jul 4)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: rouge-l, bertscore, ragas, detection metrics` | `src/evaluation/__init__.py`, `src/evaluation/metrics.py` |
| 2 | `feat: llm-as-judge with 4-axis likert scoring` | `src/evaluation/llm_judge.py` |
| 3 | `feat: wilcoxon + bootstrap CI + paired-bootstrap stats` | `src/evaluation/stats.py` |
| 4 | `feat: langfuse observability integration` | `src/utils/observability.py` |
| 5 | `feat: mlflow experiment tracking wrapper` | `src/mlflow_tracking.py` |
| 6 | `test: metrics, judge, stats tests` | `tests/test_metrics.py`, `tests/test_llm_judge.py`, `tests/test_stats.py` |
| 7 | `script: export mlflow results to json` | `scripts/export_mlflow_results.py` |

---

### WEEK 7 — Ablation + CLI (Jul 5–11)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: cli for pipeline, ablation, eval commands` | `src/cli.py` |
| 2 | `feat: demo result loader for pre-generated outputs` | `src/demo/__init__.py`, `src/demo/demo_loader.py` |
| 3 | `feat: ablation runner with 5 configurations` | `run_ablation.py` |
| 4 | `feat: re-eval ablation on 60-item ground truth` | `reeval_ablation.py` |
| 5 | `script: synthetic sebd dataset + plots` | `scripts/generate_sebd.py`, `scripts/generate_demo_results.py`, `scripts/plot_results.py` |
| 6 | `results: initial ablation run on 15 items` | `ablation_results.json` (small), `ablation_log.txt` |
| 7 | `model: trained isolation forest snapshot` | `models/isolation_forest_model.joblib` |

---

### WEEK 8 — Full UI + API + Docker + CI (Jul 12–18)

| # | Commit msg | Files |
|---|---|---|
| 1 | `feat: full streamlit upload-detect page` | `pages/1_📊_Upload_Detect.py` |
| 2 | `feat: knowledge base browser page` | `pages/3_📚_Knowledge_Base.py` |
| 3 | `feat: experiment results + live monitoring pages` | `pages/4_📊_Experiment_Results.py`, `pages/5_📈_Live_Monitoring.py`, polish `app.py` |
| 4 | `feat: fastapi backend with /rca endpoints + sse streaming` | `api/__init__.py`, `api/main.py` |
| 5 | `chore: dockerfile + docker-compose (4-service: streamlit, api, redis, mlflow)` | `Dockerfile`, `docker-compose.yml`, `Procfile`, `runtime.txt` |
| 6 | `chore: vps deployment scripts, nginx, .env template with Neon Postgres` | `deploy/nginx.conf`, `deploy/setup_vps.sh`, `.env.example` |
| 7 | `ci: github actions for pytest + lint + deploy` | `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `.github/workflows/deploy.yml` |

---

### WEEK 9 — Final Ablation + Dissertation Polish (Jul 19–27)

| # | Commit msg | Files |
|---|---|---|
| 1 | `results: full 60-item ablation across 5 configs with p-values` | refreshed `ablation_results.json`, `pipeline_results.json`, `ablation_output*.txt` |
| 2 | `docs: architecture, abstract, references, limitations` | `docs/01_THESIS_STRUCTURE.md`, `02_ABSTRACT.md`, `05_REFERENCES.md`, `06_TOOLS_AND_STACK.md`, `07_COST_ANALYSIS.md`, `08_LIMITATIONS.md`, `09_SYSTEM_ARCHITECTURE.md` |
| 3 | `docs: week-wise implementation log + prep guide` | `docs/03_WEEK_WISE_IMPLEMENTATION.md`, `docs/10_DISSERTATION_REVIEW_RESUME_AND_PREP_GUIDE.md`, `docs/COMMANDS_AND_DEPLOYMENT.md`, `docs/PROJECT_UNDERSTANDING_GUIDE.md` |
| 4 | `diagrams: er diagram + deployment diagram + png exports` | `docs/diagrams/er_diagram.drawio` + png, `deployment.drawio` + png |
| 5 | `docs: viva Q&A and BITS cover pages` | `docs/VIVA_QA.md` (fill answers), `docs/BITS_COVER_TITLE_ACKNOWLEDGEMENTS.md`, `docs/BITS_MID_SEM_OUTLINE_REPORT.md` (final) |
| 6 | `fix: final bug fixes from dry-runs` | small fixes across modules |
| 7 *(tag)* | — | `git tag v1.0-final && git push --tags` |

---

## 3. OFFLINE DELIVERABLES (NOT in repo)

### 3.1 Mid-Sem (by Jun 27)
- **Mid-Sem Report PDF** — rewrite `docs/BITS_MID_SEM_OUTLINE_REPORT.md` (from old repo) in Word, your voice, ≤10MB, text-searchable
- **Mid-Sem PPT** — 10–12 slides (outline §4.1)
- **2-min demo screen recording** — backup if live demo fails

### 3.2 Final (by Jul 27)
- **Dissertation PDF** — BITS WILP format (§4.2), ~80–120 pages, ≤10MB
- **Final Defense PPT** — 18–22 slides (outline §4.3)
- **3 demo dry-runs** with screen recording backup

---

## 4. DOCUMENT OUTLINES

### 4.1 Mid-Sem PPT (10–12 slides)
1. Title + student/supervisor/date
2. Problem statement (3 bullets, telecom billing pain points)
3. Objectives & scope
4. Literature gap (1 line per area)
5. Proposed architecture (embed `architecture.png`)
6. Datasets + 5 anomaly types
7. Detection results so far (table)
8. RAG + multi-agent design (embed `agent_sequence.png`)
9. Live demo screenshot
10. Progress against plan + remaining work
11. Risks + next-phase plan
12. Q&A

### 4.2 BITS Dissertation Structure (Word → PDF)
9×11, double-spaced, 1" margins, Times New Roman 12pt, ≤10MB, text-searchable.

1. **Cover page** (Appendix A format)
2. **Title page** (Appendix B)
3. **Acknowledgements** — Head of Org → Supervisor → Examiner → Mentor → Others
4. **Abstract sheet** (Appendix C, ≤200 words, keywords)
5. **TOC** (decimal numbering 1, 1.1, 1.1.1)
6. **List of figures / tables / abbreviations**
7. **Ch 1 Introduction** — problem, motivation, objectives, scope, contributions, report structure
8. **Ch 2 Literature Review** — RAG evolution, multi-agent LLMs, GraphRAG, billing anomaly detection (25–40 cited refs)
9. **Ch 3 System Design** — architecture, agent state, data model (figures: architecture, data_flow, agent_sequence)
10. **Ch 4 Implementation** — tech stack, module-by-module, key code snippets (figures: er_diagram, deployment)
11. **Ch 5 Evaluation Methodology** — datasets, ground truth, metrics, ablation design, statistical tests
12. **Ch 6 Results & Discussion** — tables, plots, per-anomaly breakdown, significance, baseline comparison
13. **Ch 7 Conclusions, Limitations, Future Work**
14. **References** — IEEE or APA, 25–40 entries
15. **Appendices** — A: code samples, B: full ablation results, C: GT samples, D: deployment guide

### 4.3 Final Defense PPT (18–22 slides)
1 Title • 2 Agenda • 3 Problem & motivation • 4 Objectives • 5 Lit review summary • 6 Architecture • 7 Data pipeline • 8 Detection module • 9 RAG variants • 10 **GraphRAG novelty** • 11 Multi-agent design • 12 **Critic revision loop** • 13 SWARM routing • 14 Evaluation methodology • 15 Detection results • 16 Ablation results (5 configs) • 17 LLM-as-Judge results • 18 Statistical significance • 19 Demo screenshots • 20 Limitations & future work • 21 Contributions summary • 22 Q&A

---

## 5. DIAGRAMS

The diagrams are maintained as Mermaid sources under `docs/diagrams/` and render
directly on GitHub.

| File | Shows | Dissertation location |
|---|---|---|
| `architecture.md` | 5-layer stack: Data / Detection / RAG / Agents / UI+Deploy | Ch 3 §3.1 figure |
| `data_flow.md` | CDR → injection → detection → KB query → multi-agent → report | Ch 3 §3.2 figure |
| `agent_sequence.md` | LangGraph nodes + edges + critic revision conditional | Ch 3 §3.3 + Ch 4 figure |
| `er_diagram.md` | GraphRAG entity/relation schema | Ch 4 §4.5 figure |
| `deployment.md` | Docker-compose topology + external API deps | Ch 4 §4.10 figure |

---

## 6. AI USE DISCLOSURE

AI tools are used in line with institutional policy and disclosed where required.
The distinction maintained throughout:

| Task | AI assistance |
|---|---|
| Diagram structure, chapter outlines, BibTeX/DOI lookup | Used as a drafting aid; verified manually |
| Code | Authored and reviewed by me; I understand and can explain every module |
| Dissertation prose, commit messages, viva answers | Written by me in my own voice |

---

## 8. BUILD DISCIPLINE

1. Never commit a file before its dependencies are committed.
2. Run `pytest <test_file>` before committing each test.
3. Stage related files together: a module and its test as one commit.
4. Push from the VS Code Source Control panel or the Git CLI.
5. Verify `git config user.name` and `user.email` match your GitHub identity.

---

## 9. VERIFICATION GATES

| Gate | When | How |
|---|---|---|
| Weekly tests green | End of each week | `pytest -q` (only files committed so far) |
| Pipeline runs e2e | End W5 | `python run_pipeline.py` → valid RCA report on demo input |
| Ablation runs | End W7 | `python run_ablation.py --quick` → JSON parses |
| Deployment works | End W8 | `docker-compose up` → Streamlit + API both reachable |
| Full eval matches | End W9 | `python reeval_ablation.py` numbers match dissertation Ch 6 |
| PDF format | Pre-submit | <10MB, text-searchable (Notepad paste test) |
| Tags pushed | Milestones | `git tag` visible on GitHub releases |

---

## 10. TOOLS (CONFIRMED)

- ✅ draw.io VS Code extension (`hediet.vscode-drawio`)
- ✅ Context7 MCP (for up-to-date LangGraph/ChromaDB/sentence-transformers/RAGAS/LiteLLM docs when writing Lit Review and References)
- VS Code + Git CLI / Source Control panel (manual pushes)
- MS Word + Grammarly (chapter authoring)
- PowerPoint (PPTs)
- Pandoc or Word "Save as PDF" (final PDF export)
- ZeroGPT / GPTZero (AI-score self-check, free tier)
- OBS Studio or Windows Game Bar (demo recording)

---

## 11. DEPLOYMENT ARCHITECTURE

### Production Stack (docker-compose — 4 services)

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host (VPS)                         │
│                                                             │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────┐     │
│   │  Streamlit  │  │  FastAPI     │  │   MLflow      │     │
│   │  :8501      │  │  :8000       │  │   :5000       │     │
│   │  (5 pages)  │  │  (REST API)  │  │  (tracking)   │     │
│   └──────┬──────┘  └──────┬───────┘  └───────────────┘     │
│          │                 │                                 │
│   ┌──────┴─────────────────┴───────┐                        │
│   │         Redis :6379             │  ← rate limit +       │
│   │       (cache / sessions)        │    response cache     │
│   └─────────────────────────────────┘                        │
│                                                             │
│   Volumes: chroma_data, mlflow_data, redis_data             │
│   Network: rca_net (bridge)                                 │
│   Nginx reverse proxy :80/:443 in front                     │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌────────────────────────┐
│ External LLM    │          │ Neon.tech PostgreSQL   │
│ APIs:           │          │ (inference log)        │
│  • Groq         │          │ Free tier, serverless  │
│  • Gemini       │          │ Auto-suspend on idle   │
│  • DeepSeek     │          └────────────────────────┘
│  • Kimi         │                     │
└─────────────────┘          ┌────────────────────────┐
                             │ Langfuse Cloud         │
                             │ (observability/traces) │
                             └────────────────────────┘
```

### Storage Backends

| Store | Purpose | Backend | Cost |
|-------|---------|---------|------|
| ChromaDB | Vector store (384-dim, all-MiniLM-L6-v2) | Docker volume | $0 |
| MLflow | Experiment tracking + artifacts | SQLite in Docker volume | $0 |
| Redis | Rate limiting, LLM response cache | Docker container | $0 |
| PostgreSQL | Inference audit log (timestamps, tokens, scores) | Neon.tech free tier | $0 |
| Langfuse | LLM call tracing, cost tracking | Cloud free tier | $0 |

### Why This Stack

- **Redis** — sub-ms cache lookups for repeated LLM queries; sliding-window rate limiter to stay within Groq's 30 RPM free tier
- **PostgreSQL (Neon)** — structured inference log for the Live Monitoring page; survives container restarts; serverless = no idle cost
- **4-container split** — Streamlit and FastAPI scale independently; MLflow stays read-heavy; Redis is ephemeral-ok

### Deployment Options

| Target | Command | Notes |
|--------|---------|-------|
| Local dev | `docker compose up --build` | All 4 services on localhost |
| VPS (Hetzner/DigitalOcean) | `bash deploy/setup_vps.sh` | Nginx + Let's Encrypt auto-TLS |
| Railway / Render | Connect GitHub repo | Uses `Procfile` (single-container Streamlit-only mode) |

### Environment Variables (complete list)

See `.env.example` for all vars. Critical ones:

| Var | Required | Purpose |
|-----|----------|---------|
| `GROQ_API_KEY` | ≥1 LLM key | Primary LLM provider |
| `GEMINI_API_KEY` | optional | Fallback #2 |
| `DEEPSEEK_API_KEY` | optional | Fallback #3 |
| `KIMI_API_KEY` | optional | Fallback #4 |
| `DATABASE_URL` | optional | Neon.tech PostgreSQL connection string |
| `LANGFUSE_PUBLIC_KEY` | optional | Observability tracing |
| `LANGFUSE_SECRET_KEY` | optional | Observability tracing |
| `REDIS_URL` | auto in Docker | Override only for external Redis |

---

## 11. PATTERNS BORROWED FROM `gen-reverse-engineering`

The gen-reverse-engineering orchestrator inspired this project's *as-built reference* discipline. We don't run it (it's for legacy modernization), but we adopt its **artifact pattern**: a small set of structured Markdown files that decompose the system. These live under `docs/reference/` and serve as raw material for dissertation Chapters 1, 3, 4.

| Borrowed pattern | Where used | Why useful |
|---|---|---|
| `components.md` style breakdown | `docs/reference/components.md` | Feeds dissertation Ch 3 System Design and Ch 4 Implementation |
| `technologies.md` stack inventory | `docs/reference/technologies.md` | Feeds dissertation Ch 4 Tech Stack and References chapter |
| `integrations.md` API catalog | `docs/reference/integrations.md` | Feeds dissertation Ch 4 §APIs and the FastAPI module description |
| `discovery-report.md` executive summary | `docs/reference/discovery-report.md` | Feeds dissertation Ch 1 Introduction and the Abstract |
| Technology stack composition | `docs/reference/technology-stack-composition.md` | Feeds Ch 4 version constraints discussion + reproducibility appendix |
| Dependency chain analysis | `docs/reference/technology-dependency-chain.md` | Feeds Ch 4 deployment considerations + Docker image justification |
| Code architecture patterns | `docs/reference/code-architecture.md` | Feeds Ch 3 §Design Patterns; direct viva material |
| Validation summary | `docs/reference/VALIDATION_SUMMARY.md` | Internal QA — ensures all artifacts are accurate and complete |
| `research/<tech>/technology-research-report.md` per-tech research | `docs/reference/research/` (you create as needed in W9 for Lit Review) | Structured format for Ch 2 Literature Review entries |
| Parallel analyzer execution model | N/A here | Conceptually similar to how the multi-agent system works (parallel investigators) — worth citing in dissertation as "production-inspired design pattern" |

**Do NOT** invoke the actual gen-reverse-engineering agent on this repo — it's designed for legacy code modernization and would generate noise. The artifact *shape* is what's valuable.

---

## 12. HANDOFF NOTES (for new chat / implementation mode)

Open this SPEC in any new chat. The agent should:
1. **First action**: confirm Day-0 setup is done (archived old repo, new repo exists, sibling folder structure, git identity configured). If not, walk user through §1.
2. **W1 starting commit**: help generate the contents of `config.py`, `requirements.txt` skeleton, and the `src/data/__init__.py` files matching what's in `RAGML_source/`. User pastes, edits docstring, commits.
3. **Reference `RAGML_source/` for all file content** — do not rewrite from scratch.
4. **Never run `git push` via tool calls** — only suggest commands for the user to run.
5. **Each week's checklist** is in §2 above — follow exactly.

See `docs/HANDOFF.md` for the suggested first message to a new chat.

---

## 13. OPEN BUFFER PLANS

- **If a week slips**: compress later weeks. Never backdate commits.
- **If mid-sem demo breaks live**: play the 2-min recording instead.
- **If examiner asks why initial bulk commits in old archived repo**: "Local prototyping work; consolidated and restarted in this clean repo for clarity."
- **If GraphRAG entity extraction is slow on the day**: pre-bake `data/graph_rag/kb_graph.pkl` locally, commit as W9 result artifact, skip live rebuild in demo.
