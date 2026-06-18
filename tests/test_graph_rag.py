"""Tests for src.rag.graph_rag — offline heuristic build + retrieval."""
import pytest

from src.rag.graph_rag import (
    GraphRAGBuilder,
    GraphRAGRetriever,
    _heuristic_extract,
    _tokenize,
    ENTITY_TYPES,
    RELATION_TYPES,
)


class TestHeuristicExtract:
    def test_extracts_known_entities(self):
        out = _heuristic_extract(
            "the mediation pipeline feeds the rating engine; duplicate charge was triggered by rebalance replay."
        )
        names = {e["name"] for e in out["entities"]}
        assert "mediation" in names
        assert "rating engine" in names
        assert "duplicate charge" in names

    def test_all_entity_types_valid(self):
        out = _heuristic_extract("rating engine failed; replay cdr; rating latency high; kafka topic lagging")
        for e in out["entities"]:
            assert e["type"] in ENTITY_TYPES

    def test_relations_only_between_found_entities(self):
        out = _heuristic_extract("mediation feeds rating engine")
        for r in out["relations"]:
            assert r["rel"] in RELATION_TYPES
            names = {e["name"] for e in out["entities"]}
            assert r["src"] in names and r["dst"] in names

    def test_empty_text_no_entities(self):
        out = _heuristic_extract("")
        assert out["entities"] == []
        assert out["relations"] == []


class TestBuilder:
    def test_builds_graph_offline(self, tmp_path):
        # create two fake playbook files
        p1 = tmp_path / "cdr.md"
        p1.write_text("cdr pipeline feeds mediation. mediation feeds rating engine.", encoding="utf-8")
        p2 = tmp_path / "dup.md"
        p2.write_text("dedup service depends on kafka topic. duplicate charge was caused by rebalance replay.", encoding="utf-8")
        b = GraphRAGBuilder(use_llm=False)
        b.build_from_playbooks(playbooks_dir=tmp_path)
        assert b.graph.number_of_nodes() >= 4
        assert b.graph.number_of_edges() >= 1
        assert len(b.chunks) >= 2

    def test_save_and_load_roundtrip(self, tmp_path):
        p = tmp_path / "x.md"
        p.write_text("cdr pipeline feeds mediation. duplicate charge.", encoding="utf-8")
        b = GraphRAGBuilder(use_llm=False)
        b.build_from_playbooks(playbooks_dir=tmp_path)
        out = tmp_path / "graph_out"
        b.save(out_dir=out)
        r = GraphRAGRetriever.load(in_dir=out)
        assert r.graph.number_of_nodes() == b.graph.number_of_nodes()


class TestRetrieval:
    @pytest.fixture
    def retriever(self, tmp_path):
        p = tmp_path / "pb.md"
        p.write_text(
            "Duplicate charge is often caused by rebalance replay in kafka topic.\n\n"
            "Rebuild dedup cache to fix duplicate charge.\n\n"
            "Mediation feeds rating engine. Zero billing happens when cdr failure occurs.",
            encoding="utf-8",
        )
        b = GraphRAGBuilder(use_llm=False, chunk_size=80, chunk_overlap=0)
        b.build_from_playbooks(playbooks_dir=tmp_path)
        out = tmp_path / "g"
        b.save(out_dir=out)
        return GraphRAGRetriever.load(in_dir=out)

    def test_retrieves_nonempty_on_known_query(self, retriever):
        hits = retriever.retrieve("duplicate charge kafka", k=3)
        assert len(hits) >= 1
        assert all("chunk_id" in h and "graph_score" in h for h in hits)

    def test_empty_query_returns_empty(self, retriever):
        hits = retriever.retrieve("unrelated xyzzy blorp", k=3)
        assert hits == []

    def test_k_hops_expands_neighborhood(self, retriever):
        # 2-hop retrieval should return >= results than 0-hop (seeds only)
        h2 = retriever.retrieve("duplicate charge", k=5, max_hops=2)
        h0 = retriever.retrieve("duplicate charge", k=5, max_hops=0)
        assert len(h2) >= len(h0)


class TestTokenize:
    def test_lowercases_and_keeps_words(self):
        assert _tokenize("Rating Engine Failed!") == {"rating", "engine", "failed"}

    def test_drops_short_tokens(self):
        assert "a" not in _tokenize("a big rating")
        assert "rating" in _tokenize("a big rating")
