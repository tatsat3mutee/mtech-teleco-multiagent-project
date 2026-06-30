"""
Lightweight tracing for the RCA pipeline.

Writes one JSONL line per traced event to `PROJECT_ROOT/traces/trace-<pid>-<ts>.jsonl`.
Zero external deps; no network. Designed to be compatible with downstream
conversion to LangSmith / Phoenix if needed, but safe to leave always-on.

Usage:
    from src.utils.tracing import Tracer, trace_span

    Tracer.set_enabled(True)
    with trace_span("retrieval", query="..."):
        docs = kb.search(...)
    Tracer.log_event("llm_call", model="gpt-4o-mini", tokens_in=120, tokens_out=45, latency_ms=800)

Events are best-effort: any I/O error is swallowed (tracing must never break the pipeline).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PROJECT_ROOT

TRACE_DIR = PROJECT_ROOT / "traces"


class Tracer:
    """Process-global JSONL tracer."""

    _enabled: bool = False
    _fp = None
    _lock = threading.Lock()
    _path: Optional[Path] = None

    @classmethod
    def set_enabled(cls, enabled: bool, path: Optional[Path] = None) -> None:
        with cls._lock:
            cls._enabled = enabled
            if cls._fp is not None:
                try:
                    cls._fp.close()
                except Exception:
                    pass
                cls._fp = None
            if enabled:
                TRACE_DIR.mkdir(parents=True, exist_ok=True)
                if path is None:
                    path = TRACE_DIR / f"trace-{os.getpid()}-{int(time.time())}.jsonl"
                cls._path = Path(path)
                try:
                    cls._fp = open(cls._path, "a", encoding="utf-8", buffering=1)
                except Exception as e:
                    print(f"[tracer] open failed: {e}")
                    cls._enabled = False

    @classmethod
    def current_path(cls) -> Optional[Path]:
        return cls._path

    @classmethod
    def log_event(cls, kind: str, **fields: Any) -> None:
        if not cls._enabled or cls._fp is None:
            return
        payload: Dict[str, Any] = {
            "ts": time.time(),
            "kind": kind,
            "pid": os.getpid(),
        }
        payload.update(fields)
        try:
            with cls._lock:
                cls._fp.write(json.dumps(payload, default=str) + "\n")
        except Exception:
            # tracing MUST NOT break the pipeline
            pass


@contextmanager
def trace_span(name: str, **fields: Any):
    """Context manager that emits start+end events with elapsed ms."""
    t0 = time.monotonic()
    Tracer.log_event("span_start", name=name, **fields)
    err: Optional[str] = None
    try:
        yield
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        raise
    finally:
        dt_ms = (time.monotonic() - t0) * 1000.0
        Tracer.log_event(
            "span_end",
            name=name,
            elapsed_ms=round(dt_ms, 2),
            error=err,
            **fields,
        )


def summarize_trace(path: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregate a JSONL trace: counts per kind, total/mean latency per span."""
    p = path or Tracer.current_path()
    if not p or not p.exists():
        return {}
    counts: Dict[str, int] = {}
    span_ms: Dict[str, list] = {}
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            counts[ev.get("kind", "?")] = counts.get(ev.get("kind", "?"), 0) + 1
            if ev.get("kind") == "span_end" and "elapsed_ms" in ev:
                span_ms.setdefault(ev.get("name", "?"), []).append(ev["elapsed_ms"])
    summary = {"event_counts": counts, "spans": {}}
    for name, xs in span_ms.items():
        summary["spans"][name] = {
            "n": len(xs),
            "total_ms": round(sum(xs), 2),
            "mean_ms": round(sum(xs) / len(xs), 2) if xs else 0.0,
            "max_ms": round(max(xs), 2) if xs else 0.0,
        }
    return summary
