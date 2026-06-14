"""One-shot builder: extract entities+relations from RCA playbooks → NetworkX graph.

Usage:
    python scripts/build_graph_rag.py          # LLM extraction (needs GROQ_API_KEY or OPENROUTER_API_KEY)
    python scripts/build_graph_rag.py --offline  # heuristic only, no network
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from src.rag.graph_rag import GraphRAGBuilder, GRAPHRAG_DIR


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true", help="use heuristic extractor only")
    args = p.parse_args()

    b = GraphRAGBuilder(use_llm=not args.offline)
    b.build_from_playbooks()
    b.save(GRAPHRAG_DIR)
    print(f"Graph saved -> {GRAPHRAG_DIR}")
    print(f"Nodes: {b.graph.number_of_nodes()}  Edges: {b.graph.number_of_edges()}")
    # Summary by type
    types = {}
    for _, data in b.graph.nodes(data=True):
        types[data.get("type", "?")] = types.get(data.get("type", "?"), 0) + 1
    print(f"Node types: {types}")


if __name__ == "__main__":
    main()
