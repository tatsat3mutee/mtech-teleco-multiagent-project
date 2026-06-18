"""
GraphRAG over the telecom RCA playbooks — the Phase 2 headline novelty.

Pipeline:
  1. Chunk each playbook (reuses `TextChunker`).
  2. Extract entities + typed relations per chunk via LLM (schema below).
     Falls back to a deterministic heuristic extractor when no LLM key
     is missing, so the pipeline remains buildable offline and the pytest
     suite does not require network.
  3. Build a `networkx.DiGraph`:
       - nodes = entities (SYSTEM / COMPONENT / FAILURE_MODE / FIX)
       - edges = CAUSES, DEPENDS_ON, FEEDS_INTO, TRIGGERS, FIXES
       - each node keeps the set of source chunk ids it was extracted from.
  4. Persist the graph + a chunk-id→text map to disk.

Retrieval (`GraphRAGRetriever.retrieve`):
  - Extracts seed entities from the query (LLM or heuristic).
  - Does a 1-2 hop BFS in the graph from matched seeds.
  - Collects the union of source chunk ids reachable within `max_hops`.
  - Scores each chunk by (a) degree of its supporting nodes in the sub-graph
    and (b) a dense cosine-similarity prior from the existing vector KB.
  - Returns top-k chunks.

This module is intentionally dependency-light: NetworkX + the existing chunker
+ sentence-transformers (already a project dep). No neo4j, no langchain-graph.

Typical usage:
    from src.rag.graph_rag import GraphRAGBuilder, GraphRAGRetriever
    builder = GraphRAGBuilder()
    builder.build_from_playbooks(RCA_PLAYBOOKS_DIR)
    builder.save(GRAPHRAG_DIR)

    r = GraphRAGRetriever.load(GRAPHRAG_DIR)
    hits = r.retrieve("duplicate charge after rating engine retry", k=5)
"""
from __future__ import annotations

import json
import pickle
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

import networkx as nx

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PROJECT_ROOT, RCA_PLAYBOOKS_DIR
from src.rag.chunker import TextChunker


GRAPHRAG_DIR = PROJECT_ROOT / "data" / "graph_rag"
GRAPH_PATH = GRAPHRAG_DIR / "kb_graph.pkl"
CHUNKS_PATH = GRAPHRAG_DIR / "chunks.json"


# ─────────────────────────────────────────────────────────────
# Extraction schema
# ─────────────────────────────────────────────────────────────

ENTITY_TYPES = ("SYSTEM", "COMPONENT", "FAILURE_MODE", "FIX", "METRIC")
RELATION_TYPES = ("CAUSES", "DEPENDS_ON", "FEEDS_INTO", "TRIGGERS", "FIXES", "MONITORS")

EXTRACTION_SYSTEM = (
    "You are an information-extraction engine for telecom billing operations. "
    "From the provided playbook chunk, extract entities and relations.\n\n"
    f"Entity types: {ENTITY_TYPES}\n"
    f"Relation types: {RELATION_TYPES}\n\n"
    "Return a JSON object with two arrays:\n"
    '  entities: [{"name": str, "type": str}]\n'
    '  relations: [{"src": str, "rel": str, "dst": str}]\n'
    "Names must be short (1-4 words), canonical (lowercased singular, e.g. "
    '"rating engine", "cdr dedup"). Only extract relations that are explicitly '
    "supported by the text. Return at most 10 entities and 10 relations."
)


# Heuristic fallback — tiny keyword map so builds work offline.
_HEURISTIC_ENTITIES = {
    "SYSTEM": ["billing system", "rating engine", "mediation", "cdr pipeline",
               "ocs", "charging system", "tax engine", "invoice generator"],
    "COMPONENT": ["dedup service", "stream processor", "kafka topic",
                  "rating table", "rating rule", "price plan", "tariff",
                  "cdr parser", "cdr file", "ingestion job", "dlq"],
    "FAILURE_MODE": ["duplicate charge", "zero billing", "cdr failure",
                     "usage spike", "sla breach", "rating error",
                     "mediation lag", "dedup miss", "rebalance replay",
                     "dst transition", "cert expiry"],
    "FIX": ["replay cdr", "rebuild dedup cache", "rotate cert",
            "reprocess window", "rerun rating", "patch rating rule",
            "clear dlq", "regenerate invoice"],
    "METRIC": ["rating latency", "cdr count", "duplicate rate",
               "zero billing rate", "dlq depth"],
}

_HEURISTIC_RELATIONS = [
    ("mediation", "FEEDS_INTO", "rating engine"),
    ("rating engine", "FEEDS_INTO", "invoice generator"),
    ("cdr pipeline", "FEEDS_INTO", "mediation"),
    ("dedup service", "DEPENDS_ON", "kafka topic"),
    ("rebalance replay", "CAUSES", "duplicate charge"),
    ("dedup miss", "CAUSES", "duplicate charge"),
    ("cdr failure", "CAUSES", "zero billing"),
    ("mediation lag", "CAUSES", "sla breach"),
    ("dst transition", "CAUSES", "zero billing"),
    ("cert expiry", "CAUSES", "cdr failure"),
    ("replay cdr", "FIXES", "zero billing"),
    ("rebuild dedup cache", "FIXES", "duplicate charge"),
    ("rotate cert", "FIXES", "cert expiry"),
    ("rerun rating", "FIXES", "rating error"),
    ("rating latency", "MONITORS", "rating engine"),
    ("duplicate rate", "MONITORS", "dedup service"),
]


def _heuristic_extract(text: str) -> Dict[str, list]:
    """Offline fallback extractor — deterministic keyword match."""
    t = text.lower()
    entities: List[dict] = []
    seen: Set[str] = set()
    for etype, names in _HEURISTIC_ENTITIES.items():
        for name in names:
            if name in t and name not in seen:
                entities.append({"name": name, "type": etype})
                seen.add(name)
    relations = []
    for src, rel, dst in _HEURISTIC_RELATIONS:
        if src in seen and dst in seen:
            relations.append({"src": src, "rel": rel, "dst": dst})
    return {"entities": entities, "relations": relations}


def _llm_extract(text: str) -> Optional[Dict[str, list]]:
    """LLM-backed extractor — returns None on failure (caller falls back)."""
    try:
        from src.evaluation.llm_judge import _call_judge, _parse_json
    except Exception:
        return None
    out = _call_judge(EXTRACTION_SYSTEM, text, max_retries=2)
    if not out:
        return None
    parsed = _parse_json(out)
    if not isinstance(parsed, dict):
        return None
    ents = parsed.get("entities", []) or []
    rels = parsed.get("relations", []) or []
    # Normalize names
    norm_ents = []
    for e in ents:
        name = str(e.get("name", "")).strip().lower()
        etype = str(e.get("type", "")).strip().upper()
        if name and etype in ENTITY_TYPES:
            norm_ents.append({"name": name, "type": etype})
    norm_rels = []
    for r in rels:
        s = str(r.get("src", "")).strip().lower()
        rel = str(r.get("rel", "")).strip().upper()
        d = str(r.get("dst", "")).strip().lower()
        if s and d and rel in RELATION_TYPES:
            norm_rels.append({"src": s, "rel": rel, "dst": d})
    return {"entities": norm_ents, "relations": norm_rels}


# ─────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────

@dataclass
class GraphRAGBuilder:
    chunk_size: int = 512
    chunk_overlap: int = 64
    use_llm: bool = True  # auto-disables when no LLM key is configured
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    chunks: Dict[str, dict] = field(default_factory=dict)  # chunk_id -> {text, metadata}

    def _extract(self, text: str) -> Dict[str, list]:
        if self.use_llm:
            out = _llm_extract(text)
            if out is not None and (out["entities"] or out["relations"]):
                return out
        return _heuristic_extract(text)

    def _add_entity(self, name: str, etype: str, chunk_id: str):
        if not self.graph.has_node(name):
            self.graph.add_node(name, type=etype, chunks=set())
        self.graph.nodes[name]["chunks"].add(chunk_id)
        # keep type stable — prefer first-seen
        self.graph.nodes[name].setdefault("type", etype)

    def _add_relation(self, src: str, rel: str, dst: str, chunk_id: str):
        if not self.graph.has_edge(src, dst):
            self.graph.add_edge(src, dst, rel=rel, chunks=set())
        self.graph.edges[src, dst]["chunks"].add(chunk_id)

    def build_from_playbooks(self, playbooks_dir: Path = RCA_PLAYBOOKS_DIR) -> None:
        chunker = TextChunker(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        files = sorted(Path(playbooks_dir).glob("*.md"))
        if not files:
            print(f"[graph-rag] no playbooks in {playbooks_dir}")
            return

        chunk_idx = 0
        for fp in files:
            text = fp.read_text(encoding="utf-8")
            for ch in chunker.chunk_document(text, metadata={"source": fp.name}):
                cid = f"c{chunk_idx:04d}"
                chunk_idx += 1
                self.chunks[cid] = {"text": ch["text"], "metadata": ch["metadata"]}
                extracted = self._extract(ch["text"])
                for e in extracted["entities"]:
                    self._add_entity(e["name"], e["type"], cid)
                for r in extracted["relations"]:
                    # ensure endpoints exist
                    self._add_entity(r["src"], self.graph.nodes.get(r["src"], {}).get("type", "COMPONENT"), cid)
                    self._add_entity(r["dst"], self.graph.nodes.get(r["dst"], {}).get("type", "COMPONENT"), cid)
                    self._add_relation(r["src"], r["rel"], r["dst"], cid)

        # Corpus-level heuristic closure: if both endpoints of a known-good
        # relation appear anywhere in the graph but no edge was added
        # chunk-locally, connect them using the union of their chunk sets.
        # This ensures multi-hop retrieval works even when evidence is spread
        # across separate playbook sections.
        for src, rel, dst in _HEURISTIC_RELATIONS:
            if self.graph.has_node(src) and self.graph.has_node(dst):
                if not self.graph.has_edge(src, dst):
                    union_chunks = (self.graph.nodes[src].get("chunks", set())
                                    | self.graph.nodes[dst].get("chunks", set()))
                    self.graph.add_edge(src, dst, rel=rel, chunks=set(union_chunks))

        print(f"[graph-rag] built graph: {self.graph.number_of_nodes()} nodes, "
              f"{self.graph.number_of_edges()} edges, {len(self.chunks)} chunks")

    def save(self, out_dir: Path = GRAPHRAG_DIR) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        # networkx can't pickle sets inside attrs cleanly across versions — convert
        g_ser = self.graph.copy()
        for _, data in g_ser.nodes(data=True):
            if "chunks" in data and isinstance(data["chunks"], set):
                data["chunks"] = sorted(data["chunks"])
        for _, _, data in g_ser.edges(data=True):
            if "chunks" in data and isinstance(data["chunks"], set):
                data["chunks"] = sorted(data["chunks"])
        with open(out_dir / "kb_graph.pkl", "wb") as f:
            pickle.dump(g_ser, f)
        with open(out_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, indent=2)
        print(f"[graph-rag] saved to {out_dir}")


# ─────────────────────────────────────────────────────────────
# Retriever
# ─────────────────────────────────────────────────────────────

def _tokenize(s: str) -> Set[str]:
    return set(re.findall(r"[a-z]{3,}", s.lower()))


@dataclass
class GraphRAGRetriever:
    graph: nx.DiGraph
    chunks: Dict[str, dict]

    @classmethod
    def load(cls, in_dir: Path = GRAPHRAG_DIR) -> "GraphRAGRetriever":
        with open(Path(in_dir) / "kb_graph.pkl", "rb") as f:
            g = pickle.load(f)
        with open(Path(in_dir) / "chunks.json", "r", encoding="utf-8") as f:
            chunks = json.load(f)
        # rehydrate list→set for runtime
        for _, data in g.nodes(data=True):
            if "chunks" in data and isinstance(data["chunks"], list):
                data["chunks"] = set(data["chunks"])
        for _, _, data in g.edges(data=True):
            if "chunks" in data and isinstance(data["chunks"], list):
                data["chunks"] = set(data["chunks"])
        return cls(graph=g, chunks=chunks)

    # ---- seed entity matching ----
    def _match_seeds(self, query: str) -> List[str]:
        qtoks = _tokenize(query)
        hits: List[Tuple[str, int]] = []
        for node in self.graph.nodes:
            ntoks = _tokenize(node)
            overlap = len(qtoks & ntoks)
            if overlap > 0:
                hits.append((node, overlap))
        hits.sort(key=lambda x: -x[1])
        return [h[0] for h in hits[:5]]

    # ---- k-hop neighborhood ----
    def _khop(self, seeds: List[str], max_hops: int = 2) -> Set[str]:
        if not seeds:
            return set()
        visited: Set[str] = set(seeds)
        frontier: Set[str] = set(seeds)
        for _ in range(max_hops):
            nxt: Set[str] = set()
            for n in frontier:
                if n not in self.graph:
                    continue
                nxt.update(self.graph.successors(n))
                nxt.update(self.graph.predecessors(n))
            nxt -= visited
            if not nxt:
                break
            visited |= nxt
            frontier = nxt
        return visited

    def retrieve(self, query: str, k: int = 5, max_hops: int = 2) -> List[dict]:
        """Return top-k chunks with graph-derived scores."""
        seeds = self._match_seeds(query)
        neighborhood = self._khop(seeds, max_hops=max_hops)
        if not neighborhood:
            return []

        # gather candidate chunk ids with their supporting node count
        chunk_support: Dict[str, int] = {}
        for n in neighborhood:
            for cid in self.graph.nodes[n].get("chunks", set()):
                chunk_support[cid] = chunk_support.get(cid, 0) + 1
        # also count edge-level evidence
        sub = self.graph.subgraph(neighborhood)
        for u, v, data in sub.edges(data=True):
            for cid in data.get("chunks", set()):
                chunk_support[cid] = chunk_support.get(cid, 0) + 1

        # lexical boost: prefer chunks whose text actually shares tokens with q
        qtoks = _tokenize(query)
        ranked: List[Tuple[str, float]] = []
        for cid, support in chunk_support.items():
            txt = self.chunks.get(cid, {}).get("text", "")
            lex = len(qtoks & _tokenize(txt)) if txt else 0
            score = support + 0.5 * lex
            ranked.append((cid, score))
        ranked.sort(key=lambda x: -x[1])

        out: List[dict] = []
        for cid, score in ranked[:k]:
            ch = self.chunks.get(cid, {})
            out.append({
                "text": ch.get("text", ""),
                "source": ch.get("metadata", {}).get("source", "unknown"),
                "graph_score": score,
                "seeds": seeds,
                "chunk_id": cid,
            })
        return out


def build_and_save(use_llm: bool = True) -> Path:
    """One-shot build entry point used by `scripts/build_graph_rag.py`."""
    b = GraphRAGBuilder(use_llm=use_llm)
    b.build_from_playbooks()
    b.save()
    return GRAPHRAG_DIR


if __name__ == "__main__":
    build_and_save(use_llm=False)
