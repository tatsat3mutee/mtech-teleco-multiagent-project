"""
Cross-encoder reranker wrapper.

Uses `sentence-transformers` CrossEncoder if available. The default model is
`cross-encoder/ms-marco-MiniLM-L-6-v2` (~90MB, CPU-friendly). If the model
can't be loaded (no network on first call, or the package is missing), the
reranker returns `None` from `get_default()` so the caller falls back to the
RRF-only ranking.

Contract:
    from src.rag.reranker import Reranker
    rr = Reranker.get_default()
    if rr is not None:
        scores = rr.rerank(query, list_of_doc_texts)  # returns list[float]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class Reranker:
    model: object  # CrossEncoder

    def rerank(self, query: str, docs: List[str]) -> List[float]:
        if not docs:
            return []
        pairs = [(query, d) for d in docs]
        scores = self.model.predict(pairs)
        return [float(s) for s in scores]

    # ── factory ─────────────────────────────────────────────
    _singleton: "Optional[Reranker]" = None
    _tried: bool = False

    @classmethod
    def get_default(cls) -> Optional["Reranker"]:
        if cls._singleton is not None:
            return cls._singleton
        if cls._tried:
            return None
        cls._tried = True
        try:
            from sentence_transformers import CrossEncoder
            model = CrossEncoder(_DEFAULT_MODEL, max_length=256)
            cls._singleton = cls(model=model)
            return cls._singleton
        except Exception as e:
            print(f"[reranker] disabled — could not load {_DEFAULT_MODEL}: {e}")
            return None
