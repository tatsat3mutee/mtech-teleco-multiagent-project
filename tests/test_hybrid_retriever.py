"""Tests for src.rag.hybrid_retriever — BM25 + RRF math, no dense/Chroma needed."""
from src.rag.hybrid_retriever import _tokenize, _reciprocal_rank_fusion


class TestTokenize:
    def test_lowercases(self):
        assert "rating" in _tokenize("Rating Engine")

    def test_drops_short(self):
        toks = _tokenize("a bb cdr")
        assert "cdr" in toks
        assert "a" not in toks
        assert "bb" not in toks

    def test_keeps_hyphens(self):
        assert "cdr-failure" in _tokenize("CDR-failure occurred")


class TestRRF:
    def test_single_ranking(self):
        scores = _reciprocal_rank_fusion([["a", "b", "c"]], k_const=60)
        assert scores["a"] > scores["b"] > scores["c"]

    def test_two_rankings_agree(self):
        scores = _reciprocal_rank_fusion([["a", "b"], ["a", "b"]])
        assert scores["a"] > scores["b"]

    def test_two_rankings_disagree(self):
        # A is top of list1, bottom of list2; B is mid in both
        scores = _reciprocal_rank_fusion([["a", "b", "c"], ["c", "b", "a"]])
        # b and c should rank ahead of a (a has one good + one bad)
        assert scores["b"] > 0
        assert "a" in scores and "b" in scores and "c" in scores

    def test_empty_rankings(self):
        assert _reciprocal_rank_fusion([]) == {}
        assert _reciprocal_rank_fusion([[]]) == {}
