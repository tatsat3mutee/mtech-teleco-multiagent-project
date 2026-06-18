"""
Document chunking for RAG knowledge base.
Recursive text splitting with overlap for optimal retrieval.
"""
from pathlib import Path
from typing import List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import CHUNK_SIZE, CHUNK_OVERLAP


class TextChunker:
    """Recursive text splitter with overlap."""

    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Split text into chunks recursively."""
        chunks = self._recursive_split(text, self.separators)
        # Merge small chunks
        merged = self._merge_chunks(chunks)
        return merged

    def _recursive_split(self, text: str, separators: list) -> List[str]:
        """Recursively split text using separators in order of preference."""
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        sep = separators[0] if separators else ""
        remaining_seps = separators[1:] if len(separators) > 1 else [""]

        if sep == "":
            # Hard split by character count
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
            return chunks

        parts = text.split(sep)
        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(part) > self.chunk_size:
                    # Part is too big — recurse with next separator
                    sub_chunks = self._recursive_split(part, remaining_seps)
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """Merge small chunks and add overlap."""
        if not chunks:
            return []

        merged = []
        for i, chunk in enumerate(chunks):
            # Add overlap from previous chunk
            if i > 0 and self.chunk_overlap > 0:
                prev = chunks[i - 1]
                overlap = prev[-self.chunk_overlap:]
                chunk = overlap + " " + chunk

            if len(chunk) > 0:
                merged.append(chunk.strip())

        return merged

    def chunk_document(self, text: str, metadata: dict = None) -> List[dict]:
        """
        Split document and return chunks with metadata.
        Returns list of {text, metadata} dicts.
        """
        chunks = self.split_text(text)
        result = []
        for i, chunk in enumerate(chunks):
            chunk_meta = {
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            if metadata:
                chunk_meta.update(metadata)
            result.append({"text": chunk, "metadata": chunk_meta})
        return result


def chunk_file(filepath: Path, chunk_size: int = CHUNK_SIZE) -> List[dict]:
    """Read and chunk a text/markdown file."""
    text = filepath.read_text(encoding="utf-8")
    chunker = TextChunker(chunk_size=chunk_size)
    metadata = {
        "source": filepath.name,
        "source_path": str(filepath),
        "doc_type": filepath.suffix.lstrip("."),
    }
    return chunker.chunk_document(text, metadata)
