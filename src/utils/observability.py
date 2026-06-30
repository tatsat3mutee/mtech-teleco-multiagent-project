"""
Observability module — Langfuse integration for LLM tracing and cost tracking.

Auto-configures LiteLLM callbacks when LANGFUSE_PUBLIC_KEY is set.
Provides trace_pipeline() context manager and span() decorator for
per-node observability in the LangGraph pipeline.

Configuration (env vars or config.py):
    LANGFUSE_PUBLIC_KEY: Langfuse project public key
    LANGFUSE_SECRET_KEY: Langfuse project secret key
    LANGFUSE_HOST: https://cloud.langfuse.com (default) or self-hosted URL
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)

_langfuse_client = None
_initialized = False


def _ensure_initialized():
    """Lazy initialization of Langfuse + LiteLLM callback wiring."""
    global _langfuse_client, _initialized
    if _initialized:
        return
    _initialized = True

    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

        if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
            logger.info("Langfuse keys not configured — observability disabled")
            return

        # Wire LiteLLM → Langfuse callback (auto-logs every LLM call)
        import litellm
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        # Initialize Langfuse client for manual traces/spans
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        logger.info("Langfuse observability initialized")

    except ImportError as e:
        logger.debug(f"Langfuse not installed: {e}")
    except Exception as e:
        logger.warning(f"Langfuse initialization failed: {e}")


def get_langfuse() -> Optional[Any]:
    """Return Langfuse client or None if not configured."""
    _ensure_initialized()
    return _langfuse_client


@contextmanager
def trace_pipeline(anomaly_id: str, anomaly_type: str = "unknown"):
    """
    Context manager that creates a Langfuse trace for an RCA pipeline run.

    Usage:
        with trace_pipeline("CUST-001", "zero_billing") as trace:
            # run pipeline nodes
            pass

    Yields the trace object (or a no-op stub if Langfuse unavailable).
    """
    _ensure_initialized()
    client = _langfuse_client

    if client is None:
        # No-op stub
        yield _NoOpTrace()
        return

    trace = client.trace(
        name="rca_pipeline",
        metadata={"anomaly_id": anomaly_id, "anomaly_type": anomaly_type},
        tags=[anomaly_type],
    )
    start = time.time()
    try:
        yield trace
    finally:
        trace.update(
            metadata={
                "anomaly_id": anomaly_id,
                "anomaly_type": anomaly_type,
                "duration_ms": (time.time() - start) * 1000,
            }
        )
        # Flush to ensure trace is sent
        try:
            client.flush()
        except Exception:
            pass


def create_span(trace, name: str, **metadata):
    """
    Create a Langfuse span (child of trace) for a pipeline node.

    Usage:
        span = create_span(trace, "investigator", retrieval_count=5)
        # ... do work ...
        span.end()
    """
    _ensure_initialized()
    if trace is None or isinstance(trace, _NoOpTrace):
        return _NoOpSpan()

    try:
        return trace.span(name=name, metadata=metadata)
    except Exception:
        return _NoOpSpan()


class _NoOpTrace:
    """Stub when Langfuse is not available."""
    id = "no-op"

    def span(self, **kwargs):
        return _NoOpSpan()

    def update(self, **kwargs):
        pass


class _NoOpSpan:
    """Stub span when Langfuse is not available."""
    def end(self, **kwargs):
        pass

    def update(self, **kwargs):
        pass
