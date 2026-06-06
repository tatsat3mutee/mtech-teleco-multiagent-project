# Diagrams

This folder will hold 5 `.drawio` diagrams plus their `.png` exports. Use the
`hediet.vscode-drawio` extension to edit `.drawio` files inline in VS Code,
then right-click → **Export As** → **PNG** to generate the embedded figures
for the dissertation.

## Diagram inventory

| File | Shows | Dissertation location | Build week |
|---|---|---|---|
| `architecture.drawio` (+`.png`) | 5-layer stack: Data → Detection → RAG → Agents → UI+Deploy | Ch 3 §3.1 | W5 |
| `data_flow.drawio` (+`.png`) | CDR → injection → detection → KB query → multi-agent → report | Ch 3 §3.2 | W5 |
| `agent_sequence.drawio` (+`.png`) | LangGraph nodes + edges + critic revision conditional | Ch 3 §3.3 + Ch 4 | W5 |
| `er_diagram.drawio` (+`.png`) | GraphRAG entity/relation schema | Ch 4 §4.5 | W9 |
| `deployment.drawio` (+`.png`) | Docker-compose topology + external API deps | Ch 4 §4.10 | W9 |

## Diagram content notes

### `architecture.drawio` (5 horizontal bands, bottom-to-top)
1. **Data Layer** — IBM Telco loader, Maven loader, SEBD enterprise billing loader, anomaly injector, augmentor
2. **Detection Layer** — IsolationForest, rule pre-filter
3. **RAG Layer** — Embedder, chunker, ChromaDB, BM25, hybrid retriever, reranker, GraphRAG (NetworkX)
4. **Agent Layer** — Investigator, Reasoner, Critic, Reporter (with critic revision arrow back to Reasoner); SWARM router on the left; LLM provider abstraction (Groq/Kimi/Gemini/DeepSeek) on the right
5. **UI & Deployment Layer** — Streamlit (5 pages), FastAPI, Docker, MLflow, Langfuse

### `data_flow.drawio` (left-to-right swim lane)
- Lane 1: User uploads CDR CSV
- Lane 2: Anomaly injector + detector flag rows
- Lane 3: KB query built from flagged anomaly
- Lane 4: Multi-agent pipeline runs (with critic loop visible)
- Lane 5: RCA report JSON returned + persisted to MLflow

### `agent_sequence.drawio` (UML sequence)
- Actors: User, Investigator, KB, Reasoner, Critic, Reporter, LLM (Groq)
- Show the critic revision loop as a dashed back-arrow
- Show LLM calls from each agent (token count noted in margin)

### `er_diagram.drawio` (entity-relationship)
- Nodes: Service, Customer, Bill, CDR, SLA, Incident, Cause
- Edges: CAUSES, AFFECTS, BREACHES, INCLUDES, APPLIES_TO
- See `docs/GRAPHRAG_DESIGN.md` for the full taxonomy

### `deployment.drawio` (deployment topology)
- Boxes: Docker host, Streamlit container, FastAPI container, ChromaDB volume, MLflow volume
- External: Groq API, Langfuse SaaS, GitHub (CI)
- Network: nginx reverse proxy in front
