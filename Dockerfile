FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps.
# torch is installed FIRST from the CPU-only index: sentence-transformers pulls
# torch, and the default Linux wheel bundles ~6 GB of NVIDIA CUDA libraries that
# are useless on CPU-only hosts (t3.medium has no GPU) and overflow a 30 GB disk
# during image export. CPU wheel keeps the image ~3-4 GB total.
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY config.py .
COPY app.py .
COPY run_pipeline.py .
COPY src/ src/
COPY api/ api/
COPY pages/ pages/
COPY scripts/ scripts/
COPY models/ models/
COPY data/corpus/ data/corpus/
COPY data/eval/ data/eval/
COPY data/demo/ data/demo/
# Demo artifacts: preloaded anomalies for RCA Viewer + real ablation results
# for the Experiment Results page (both tiny, ~1.3 MB total)
COPY data/processed/anomalies_labeled.csv data/processed/anomalies_labeled.csv
COPY results/ablation/ results/ablation/
# Pre-built GraphRAG causal graph (graph-first retrieval for zero_billing/cdr_failure)
COPY data/graph_rag/ data/graph_rag/

# Pre-download embedding model at build time (avoids cold-start delay)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Pre-build ChromaDB knowledge base from corpus (eliminates cold-start rebuild)
# Runs at image build time so the first request is served immediately.
# Fails the build loudly if the corpus is missing or zero chunks were indexed —
# a silent skip would ship an image that rebuilds embeddings on every cold start.
RUN python -c "\
from src.rag.knowledge_base import build_knowledge_base; \
kb = build_knowledge_base(); \
assert kb.count > 0, 'KB build produced 0 chunks'; \
print(f'ChromaDB knowledge base built: {kb.count} chunks') \
"

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit (CMD, not ENTRYPOINT, so platform start commands — e.g.
# docker-compose `command: uvicorn api.main:app` for the API service —
# can override it without needing --entrypoint gymnastics)
CMD ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
