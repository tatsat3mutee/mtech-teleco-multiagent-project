"""
ChromaDB Knowledge Base management.
Handles document indexing, storage, and retrieval.
"""
import chromadb
import logging
from pathlib import Path
from typing import List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION_NAME, CORPUS_DIR, RCA_PLAYBOOKS_DIR, TOP_K
from src.rag.chunker import TextChunker, chunk_file
from src.rag.embedder import get_embedding_model

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """ChromaDB-backed knowledge base for telecom billing RCA."""

    def __init__(self, persist_dir: Path = CHROMA_PERSIST_DIR,
                 collection_name: str = CHROMA_COLLECTION_NAME):
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = get_embedding_model()

    @property
    def count(self) -> int:
        """Number of documents in the collection."""
        return self.collection.count()

    def index_documents(self, docs_dir: Path = None, glob_pattern: str = "*.md"):
        """Index all documents from a directory into ChromaDB."""
        if docs_dir is None:
            docs_dir = RCA_PLAYBOOKS_DIR

        files = list(docs_dir.glob(glob_pattern))
        if not files:
            print(f"No files matching {glob_pattern} found in {docs_dir}")
            return

        all_chunks = []
        for filepath in files:
            chunks = chunk_file(filepath)
            all_chunks.extend(chunks)

        if not all_chunks:
            print("No chunks generated from documents.")
            return

        # Deduplicate chunks by text content (avoid indexing identical text twice)
        seen_texts = set()
        unique_chunks = []
        for chunk in all_chunks:
            text_key = chunk["text"].strip()
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_chunks.append(chunk)
        if len(unique_chunks) < len(all_chunks):
            logger.info(f"Deduplicated {len(all_chunks) - len(unique_chunks)} duplicate chunks")
        all_chunks = unique_chunks

        # Embed all chunks
        texts = [c["text"] for c in all_chunks]
        embeddings = self.embedder.embed_texts(texts)

        # Prepare for ChromaDB
        ids = [f"doc_{i}" for i in range(len(all_chunks))]
        metadatas = [c["metadata"] for c in all_chunks]

        # Upsert in batches (ChromaDB limit)
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end].tolist(),
                documents=texts[i:end],
                metadatas=metadatas[i:end],
            )

        print(f"Indexed {len(all_chunks)} chunks from {len(files)} documents.")

    def query(self, query_text: str, n_results: int = TOP_K) -> dict:
        """Query the knowledge base and return relevant documents."""
        query_embedding = self.embedder.embed_query(query_text)

        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
        }

    def search(self, query_text: str, n_results: int = TOP_K) -> List[dict]:
        """Search and return structured results. Returns [] on error."""
        try:
            raw = self.query(query_text, n_results)

            results = []
            for doc, meta, dist in zip(raw["documents"], raw["metadatas"], raw["distances"]):
                results.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "relevance_score": 1 - dist,  # Convert distance to similarity
                    "metadata": meta,
                })

            return results
        except Exception as exc:
            logger.error(f"KnowledgeBase.search() failed: {exc}", exc_info=True)
            return []

    def reset(self):
        """Clear all documents from the collection."""
        self.client.delete_collection(CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        print("Knowledge base reset.")

    def get_all_sources(self) -> List[str]:
        """Get all unique source documents in the knowledge base."""
        all_data = self.collection.get(include=["metadatas"])
        sources = set()
        for meta in all_data["metadatas"]:
            if meta and "source" in meta:
                sources.add(meta["source"])
        return sorted(sources)


def build_knowledge_base(force_rebuild: bool = False) -> KnowledgeBase:
    """Build or load the knowledge base."""
    kb = KnowledgeBase()

    if kb.count > 0 and not force_rebuild:
        print(f"Knowledge base already has {kb.count} documents. Use force_rebuild=True to rebuild.")
        return kb

    if force_rebuild:
        kb.reset()

    # Index RCA playbooks
    print("Indexing RCA playbooks...")
    kb.index_documents(RCA_PLAYBOOKS_DIR, "*.md")

    # Index any other corpus documents
    corpus_dirs = [d for d in CORPUS_DIR.iterdir() if d.is_dir() and d != RCA_PLAYBOOKS_DIR]
    for d in corpus_dirs:
        print(f"Indexing documents from {d.name}...")
        kb.index_documents(d, "*.md")
        kb.index_documents(d, "*.txt")

    print(f"\nTotal documents in knowledge base: {kb.count}")

    # Invalidate cached RCA results since KB content changed
    try:
        from src.utils.cache import invalidate_rca_cache
        invalidate_rca_cache()
        logger.info("RCA cache invalidated after KB rebuild")
    except Exception as exc:
        logger.warning(f"Could not invalidate RCA cache: {exc}")

    return kb


if __name__ == "__main__":
    kb = build_knowledge_base(force_rebuild=True)
    # Test query
    results = kb.search("zero billing anomaly root cause")
    for r in results:
        print(f"\n[{r['relevance_score']:.3f}] {r['source']}")
        print(f"  {r['text'][:200]}...")
