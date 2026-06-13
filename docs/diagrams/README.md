# Diagrams

The system diagrams are maintained as Mermaid sources (`.md`) and render directly on
GitHub and in most Markdown viewers. For the dissertation, each can be exported to an
image from a Mermaid-capable viewer.

## Exporting for Word / PowerPoint

Mermaid does not render natively in Word or PowerPoint, so export each diagram to an
image (PNG or SVG) and embed the image. Any of these works:

- **mermaid.live** — paste the code block, then **Actions → PNG / SVG**.
- **VS Code** — a Mermaid preview extension (e.g. Markdown Preview Mermaid Support),
  then screenshot or export.
- **CLI** — `mmdc -i architecture.md -o architecture.png` (mermaid-cli).

Use SVG for the dissertation where possible (sharp at any zoom); PNG is fine for
slides.

## Diagram inventory

| File | Shows | Dissertation location |
|---|---|---|
| `architecture.md` | 5-layer stack: Data → Detection → RAG → Agents → UI+Deploy | Ch 3 §3.1 |
| `data_flow.md` | CDR → injection → detection → KB query → multi-agent → report | Ch 3 §3.2 |
| `agent_sequence.md` | LangGraph nodes + edges + critic revision conditional | Ch 3 §3.3 + Ch 4 |
| `er_diagram.md` | GraphRAG entity/relation schema | Ch 4 §4.5 |
| `deployment.md` | Docker-compose topology + external API deps | Ch 4 §4.10 |

## Diagram content notes

### `architecture.md` (5 horizontal bands, bottom-to-top)
1. **Data Layer** — IBM Telco loader, Maven loader, SEBD enterprise billing loader, anomaly injector, augmentor
2. **Detection Layer** — IsolationForest, rule pre-filter
3. **RAG Layer** — Embedder, chunker, ChromaDB, BM25, hybrid retriever, reranker, GraphRAG (NetworkX)
4. **Agent Layer** — Investigator, Reasoner, Critic, Reporter (with critic revision arrow back to Reasoner); SWARM router on the left; LLM provider abstraction (Groq/OpenRouter) on the right
5. **UI & Deployment Layer** — Streamlit (5 pages), FastAPI, Docker, MLflow, Langfuse

### `data_flow.md` (left-to-right swim lane)
- Lane 1: User uploads CDR CSV
- Lane 2: Anomaly injector + detector flag rows
- Lane 3: KB query built from flagged anomaly
- Lane 4: Multi-agent pipeline runs (with critic loop visible)
- Lane 5: RCA report JSON returned + persisted to MLflow

### `agent_sequence.md` (UML sequence)
- Actors: User, Investigator, KB, Reasoner, Critic, Reporter, LLM (Groq)
- Show the critic revision loop as a dashed back-arrow
- Show LLM calls from each agent (token count noted in margin)

### `er_diagram.md` (entity-relationship)
- Nodes: Service, Customer, Bill, CDR, SLA, Incident, Cause
- Edges: CAUSES, AFFECTS, BREACHES, INCLUDES, APPLIES_TO
- See `docs/GRAPHRAG_DESIGN.md` for the full taxonomy

### `deployment.md` (deployment topology)
- Boxes: Docker host, Streamlit container, FastAPI container, ChromaDB volume, MLflow volume
- External: Groq API, Langfuse SaaS, GitHub (CI)
- Network: nginx reverse proxy in front
