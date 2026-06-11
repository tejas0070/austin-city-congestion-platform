from __future__ import annotations

import time
from typing import Any

# NOTE: _store is per-process. In a multi-worker deployment (gunicorn/uvicorn --workers N)
# each worker maintains an independent cache. Use Redis for a shared cache.
_store: dict[str, tuple] = {}


def set_cache(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Store a value under key with an expiry time."""
    expires_at = time.time() + ttl_seconds
    _store[key] = (value, expires_at)


def get_cache(key: str) -> Any | None:
    """Return the cached value for key, or None if absent or expired."""
    entry = _store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _store[key]
        return None
    return value


def clear_cache() -> None:
    """Remove all entries from the cache."""
    _store.clear()
