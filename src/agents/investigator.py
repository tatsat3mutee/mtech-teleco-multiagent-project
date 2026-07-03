"""
Investigator Agent — retrieves relevant documents from the RAG knowledge base.

Retrieval strategy is chosen by the SWARM router (swarm_router.py):
  graph_first  → GraphRAG entity-relation graph traversal (zero_billing, cdr_failure)
  vector_first → ChromaDB dense + BM25 hybrid retrieval (all other types)

GraphRAG also activates when USE_GRAPH_RAG=1 environment variable is set.
Requires: data/graph_rag/kb_graph.pkl — build with: python scripts/build_graph_rag.py --offline
"""
import os
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.agents.state import AgentState
from src.agents.prompts import INVESTIGATOR_SYSTEM_PROMPT, INVESTIGATOR_PROMPT
from src.agents.llm_utils import call_llm
from src.agents.swarm_router import get_retrieval_strategy, get_routing_explanation
from src.rag.knowledge_base import KnowledgeBase
from config import TOP_K


def investigator_node(state: AgentState) -> AgentState:
    """
    Investigator Agent node for LangGraph.
    Receives anomaly context → SWARM routing decision → retrieves top-k docs.
    """
    anomaly = state.get("anomaly_data", {})
    anomaly_type = anomaly.get("anomaly_type", "billing anomaly")

    # SWARM routing — determines retrieval path before any LLM call
    strategy = get_retrieval_strategy(anomaly_type)
    explanation = get_routing_explanation(anomaly_type)
    state["retrieval_strategy"] = strategy
    state["routing_explanation"] = explanation

    # Format the investigator prompt
    prompt = INVESTIGATOR_PROMPT.format(
        account_id=anomaly.get("account_id", "UNKNOWN"),
        anomaly_type=anomaly_type,
        confidence=anomaly.get("confidence", 0.0),
        monthly_charges=anomaly.get("monthly_charges", 0.0),
        total_charges=anomaly.get("total_charges", 0.0),
        tenure=anomaly.get("tenure", 0),
        features=anomaly.get("features", {}),
    )

    # Try to get a refined query from the LLM
    llm_query = call_llm(
        INVESTIGATOR_SYSTEM_PROMPT, prompt,
        trace_name="investigator",
        session_id=anomaly.get("account_id"),
    )

    # Build search query — use LLM query if available, otherwise fallback
    if llm_query:
        search_query = llm_query.strip()
    else:
        query_map = {
            "zero_billing": "zero billing active customer rating engine configuration billing pipeline failure",
            "duplicate_charge": "duplicate charge billing deduplication failure retry logic idempotency",
            "usage_spike": "usage spike Fiber optic internet service charges rate card roaming overage",
            "cdr_failure": "billing record failure NULL charges streaming service bundle rating pipeline",
            "sla_breach": "SLA breach annual contract monthly charges P95 cap rate plan configuration",
        }
        search_query = query_map.get(anomaly_type,
                                      f"{anomaly_type} billing anomaly root cause analysis telecom")

    # ── GraphRAG retrieval (graph_first strategy OR USE_GRAPH_RAG=1 env override) ──
    use_graph = (
        strategy == "graph_first" or
        os.environ.get("USE_GRAPH_RAG", "").lower() in ("1", "true")
    )
    if use_graph:
        try:
            from src.rag.graph_rag import GraphRAGRetriever, GRAPHRAG_DIR, GRAPH_PATH
            if GRAPH_PATH.exists():
                gr = GraphRAGRetriever.load(GRAPHRAG_DIR)
                graph_results = gr.retrieve(search_query, k=TOP_K)
                if graph_results:
                    retrieved_docs = [
                        {
                            "text": r["text"],
                            "source": r["source"],
                            # graph_score is a node+edge support count (typically 0–10+);
                            # normalise to [0, 1] for compatibility with the rest of the pipeline.
                            "relevance_score": min(r.get("graph_score", 1.0) / 10.0, 1.0),
                            "metadata": {
                                "source": r["source"],
                                "chunk_id": r.get("chunk_id", ""),
                                "retrieval_mode": "graph_rag",
                            },
                        }
                        for r in graph_results
                    ]
                    state["retrieval_query"] = search_query
                    state["retrieved_docs"] = retrieved_docs
                    state["retrieval_count"] = len(retrieved_docs)
                    state["pipeline_status"] = "investigated"
                    return state
                print("[GraphRAG] zero results — falling back to vector retrieval")
            else:
                print("[GraphRAG] graph not built — falling back to vector retrieval")
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(
                "GraphRAG retrieval failed — falling back to vector retrieval",
                exc_info=_e,
            )
            print(f"[GraphRAG] error ({_e}) — falling back to vector retrieval")
    # ── Default: ChromaDB dense retrieval ──────────────────────────────────────
    # Query knowledge base
    kb = KnowledgeBase()
    results = kb.search(search_query, n_results=TOP_K)

    retrieved_docs = []
    for r in results:
        retrieved_docs.append({
            "text": r["text"],
            "source": r["source"],
            "relevance_score": r["relevance_score"],
            "metadata": r["metadata"],
        })

    state["retrieval_query"] = search_query
    state["retrieved_docs"] = retrieved_docs
    state["retrieval_count"] = len(retrieved_docs)
    state["pipeline_status"] = "investigated"

    return state
