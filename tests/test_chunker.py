"""Tests for src.rag.chunker — offline, no embeddings."""
import pytest

from src.rag.chunker import TextChunker


class TestTextChunker:
    def test_short_text_single_chunk(self):
        c = TextChunker(chunk_size=500, chunk_overlap=50)
        out = c.split_text("short body of text")
        assert len(out) == 1
        assert "short body" in out[0]

    def test_empty_text_yields_no_chunks(self):
        c = TextChunker(chunk_size=500, chunk_overlap=50)
        assert c.split_text("") == []
        assert c.split_text("   ") == []

    def test_long_text_is_split(self):
        c = TextChunker(chunk_size=100, chunk_overlap=10)
        text = ("Paragraph one. " * 20) + "\n\n" + ("Paragraph two. " * 20)
        out = c.split_text(text)
        assert len(out) > 1
        # no chunk should grossly exceed chunk_size + overlap slack
        for chunk in out:
            assert len(chunk) <= 100 + 50  # overlap slack

    def test_chunk_document_attaches_metadata(self):
        c = TextChunker(chunk_size=80, chunk_overlap=0)
        chunks = c.chunk_document("a" * 200, metadata={"source": "x.md"})
        assert len(chunks) >= 2
        assert all(ch["metadata"]["source"] == "x.md" for ch in chunks)
        assert all("chunk_index" in ch["metadata"] for ch in chunks)
        assert chunks[0]["metadata"]["total_chunks"] == len(chunks)

    def test_metadata_optional(self):
        c = TextChunker(chunk_size=80, chunk_overlap=0)
        chunks = c.chunk_document("hello world")
        assert chunks[0]["metadata"]["chunk_index"] == 0
