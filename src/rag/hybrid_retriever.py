"""
Hybrid retrieval: BM25 lexical + dense cosine + Reciprocal Rank Fusion (RRF),
plus optional cross-encoder reranker.

Design goals:
  - No new heavy deps. Uses `rank_bm25` (lightweight) + existing
    sentence-transformers embedder + Chroma-persisted corpus.
  - Fully offline-constructable. The BM25 index is rebuilt in-memory from
    the ChromaDB documents on init.
  - Optional reranker. `Reranker` is a thin wrapper around a cross-encoder
    (BAAI/bge-reranker-base by default); skipped automatically if the model
    can't be loaded, with a warning.

Contract:
    from src.rag.hybrid_retriever import HybridRetriever
    hr = HybridRetriever.from_knowledge_base(kb)
    hits = hr.search("duplicate charge after kafka rebalance", k=5, use_reranker=True)
    # -> list of {text, source, bm25_rank, dense_rank, rrf_score, rerank_score}
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import TOP_K

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _reciprocal_rank_fusion(
    rankings: List[List[str]],
    k_const: int = 60,
) -> Dict[str, float]:
    """Standard RRF (Cormack et al., 2009). Returns doc_id -> fused score."""
    scores: Dict[str, float] = {}
    for ranks in rankings:
        for i, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k_const + i + 1)
    return scores


@dataclass
class HybridRetriever:
    """BM25 + dense + RRF over a ChromaDB-backed corpus."""

    documents: List[str]
    metadatas: List[dict]
    ids: List[str]
    embedder: object  # src.rag.embedder.Embedder
    chroma_collection: object  # lazy dense query

    _bm25: Optional[object] = None
    _tokenized_corpus: List[List[str]] = field(default_factory=list)

    def __post_init__(self):
        try:
            from rank_bm25 import BM25Okapi
            self._tokenized_corpus = [_tokenize(d) for d in self.documents]
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        except Exception as e:
            print(f"[hybrid] BM25 init failed: {e} — falling back to dense-only")
            self._bm25 = None

    # ── factory ────────────────────────────────────────────────
    @classmethod
    def from_knowledge_base(cls, kb) -> "HybridRetriever":
        """Pull all docs out of the Chroma collection for BM25 indexing."""
        data = kb.collection.get(include=["documents", "metadatas"])
        return cls(
            documents=data["documents"],
            metadatas=data["metadatas"],
            ids=data["ids"],
            embedder=kb.embedder,
            chroma_collection=kb.collection,
        )

    # ── retrieval ──────────────────────────────────────────────
    def _bm25_top(self, query: str, k: int) -> List[str]:
        if self._bm25 is None or not self.documents:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        order = np.argsort(-scores)[:k]
        return [self.ids[i] for i in order if scores[i] > 0]

    def _dense_top(self, query: str, k: int) -> List[str]:
        try:
            qemb = self.embedder.embed_query(query)
            res = self.chroma_collection.query(
                query_embeddings=[qemb.tolist()],
                n_results=k,
                include=["metadatas"],
            )
            # chroma returns ids in the "ids" key alongside the include list
            return res.get("ids", [[]])[0]
        except Exception as e:
            print(f"[hybrid] dense retrieval failed: {e}")
            return []

    def search(
        self,
        query: str,
        k: int = TOP_K,
        candidate_k: int = 20,
        use_reranker: bool = False,
    ) -> List[dict]:
        """Hybrid search. Returns top-k merged hits."""
        bm25_ids = self._bm25_top(query, candidate_k)
        dense_ids = self._dense_top(query, candidate_k)

        fused = _reciprocal_rank_fusion([bm25_ids, dense_ids])
        ranked = sorted(fused.items(), key=lambda x: -x[1])

        # Build candidate set for rerank
        cand = ranked[: max(k * 3, candidate_k)]
        by_id = {cid: i for i, cid in enumerate(self.ids)}

        hits = []
        for cid, rrf in cand:
            if cid not in by_id:
                continue
            idx = by_id[cid]
            hits.append({
                "id": cid,
                "text": self.documents[idx],
                "metadata": self.metadatas[idx],
                "source": (self.metadatas[idx] or {}).get("source", "unknown"),
                "bm25_rank": bm25_ids.index(cid) if cid in bm25_ids else None,
                "dense_rank": dense_ids.index(cid) if cid in dense_ids else None,
                "rrf_score": rrf,
            })

        if use_reranker and hits:
            try:
                from src.rag.reranker import Reranker
                rr = Reranker.get_default()
                if rr is not None:
                    scored = rr.rerank(query, [h["text"] for h in hits])
                    for h, s in zip(hits, scored):
                        h["rerank_score"] = float(s)
                    hits.sort(key=lambda h: -h.get("rerank_score", h["rrf_score"]))
            except Exception as e:
                print(f"[hybrid] rerank skipped: {e}")

        return hits[:k]
