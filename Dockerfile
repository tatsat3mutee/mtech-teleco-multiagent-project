FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

# Pre-download embedding model at build time (avoids cold-start delay)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Pre-build ChromaDB knowledge base from corpus (eliminates cold-start rebuild)
# Runs at image build time so the first request is served immediately.
# Fails the build loudly if the corpus is missing — a silent skip would ship
# an image that rebuilds embeddings on every cold start.
RUN python -c "\
from src.rag.knowledge_base import KnowledgeBase; \
kb = KnowledgeBase(); \
kb.build_from_corpus(); \
print('ChromaDB knowledge base built successfully') \
"

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit (CMD, not ENTRYPOINT, so platform start commands — e.g. Railway
# `startCommand` with $PORT, or docker-compose `command: uvicorn api.main:app` —
# can override it without needing --entrypoint gymnastics)
CMD ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
