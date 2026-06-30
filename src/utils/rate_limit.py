"""
Thread-safe token-bucket rate limiter for LLM API calls.

OpenAI tier-1 gpt-4o-mini ≈ 500 RPM. Default here is 450 RPM (conservative
headroom). Use a module-level singleton so every agent / ablation config
shares the same budget. Override via LLM_RATE_PER_MIN env var.

Usage:
    from src.utils.rate_limit import get_limiter
    limiter = get_limiter()
    limiter.acquire()   # blocks if needed
    response = llm.invoke(...)
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    rate_per_minute: float
    capacity: float
    _tokens: float = 0.0
    _last: float = 0.0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self):
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    @property
    def _rate_per_second(self) -> float:
        return self.rate_per_minute / 60.0

    def acquire(self, tokens: float = 1.0, max_wait: float = 120.0) -> float:
        """Block until `tokens` are available. Returns seconds actually waited."""
        total_wait = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self.capacity, self._tokens + elapsed * self._rate_per_second)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return total_wait
                deficit = tokens - self._tokens
                sleep_for = deficit / self._rate_per_second
            sleep_for = min(sleep_for, max_wait - total_wait)
            if sleep_for <= 0:
                return total_wait
            time.sleep(sleep_for)
            total_wait += sleep_for


_LIMITER: TokenBucket | None = None
_LIMITER_LOCK = threading.Lock()


def get_limiter() -> TokenBucket:
    """Return the process-wide singleton limiter.

    Configurable via env vars:
      LLM_RATE_PER_MIN (default 450 — OpenAI tier-1 gpt-4o-mini headroom)
      LLM_BUCKET_CAPACITY (default 20)
    """
    global _LIMITER
    with _LIMITER_LOCK:
        if _LIMITER is None:
            rpm = float(os.environ.get("LLM_RATE_PER_MIN", "450"))
            cap = float(os.environ.get("LLM_BUCKET_CAPACITY", "20"))
            _LIMITER = TokenBucket(rate_per_minute=rpm, capacity=cap)
    return _LIMITER
