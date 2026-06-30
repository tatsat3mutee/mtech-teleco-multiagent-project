"""
Redis-backed RCA result cache.

SHA-256 of the anomaly dict is used as cache key so identical anomaly
inputs always return the same cached result within the TTL window.

Gracefully degrades to a no-op if Redis is unavailable — the pipeline
runs normally without caching. No exceptions propagate to callers.

Configuration:
    REDIS_URL env var: redis://localhost:6379 (default)
    CACHE_TTL_SECONDS: seconds before cached result expires (default: 3600)
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Any, Dict, Optional

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))

# Lazy singleton — only initialised on first cache access
_client = None
_available: Optional[bool] = None
_lock = threading.Lock()


def _get_client():
    global _client, _available
    # Fast path: already resolved
    if _available is not None:
        return _client if _available else None
    # Slow path: first access — acquire lock to prevent double-init
    with _lock:
        # Re-check after acquiring lock (another thread may have initialized)
        if _available is not None:
            return _client if _available else None
        try:
            import redis
            client = redis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            _client = client
            _available = True
            return _client
        except Exception:
            _available = False
            return None


def _cache_key(anomaly: Dict[str, Any]) -> str:
    """Stable SHA-256 key from anomaly dict — order-independent."""
    canonical = json.dumps(anomaly, sort_keys=True, default=str)
    return "rca:" + hashlib.sha256(canonical.encode()).hexdigest()


def get_cached_rca(anomaly: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return cached RCA result for this anomaly, or None if cache miss / unavailable."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(anomaly))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def set_cached_rca(anomaly: Dict[str, Any], result: Dict[str, Any], ttl: int = _TTL) -> bool:
    """Cache the RCA result. Returns True if successfully cached, False otherwise."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.setex(_cache_key(anomaly), ttl, json.dumps(result, default=str))
        return True
    except Exception:
        return False


def invalidate_rca_cache() -> bool:
    """Flush all RCA cache entries (rca:* keys). Call after KB rebuild."""
    client = _get_client()
    if client is None:
        return False
    try:
        keys = client.keys("rca:*")
        if keys:
            client.delete(*keys)
        return True
    except Exception:
        return False


def cache_available() -> bool:
    """True if Redis is reachable and the cache is active."""
    return _get_client() is not None
