"""
PL Capital Simple TTL Cache.

A dict-based TTL cache for expensive analytical results.
Uses time.monotonic() for expiry checks (not wall clock, monotonic is safer).

Interface
---------
get_cached_result(key)          -> value or None
set_cached_result(key, value, ttl_seconds=300)
clear_cache()
cache_stats()                   -> dict with hit/miss/size counts
"""

import time
from typing import Any, Optional

# Internal store: {key: (value, expiry_monotonic)}
_cache: dict = {}
_hits: int = 0
_misses: int = 0


def get_cached_result(key: str) -> Optional[Any]:
    """Return cached value if present and not expired, else None."""
    global _hits, _misses
    entry = _cache.get(key)
    if entry is None:
        _misses += 1
        return None
    value, expiry = entry
    if time.monotonic() > expiry:
        del _cache[key]
        _misses += 1
        return None
    _hits += 1
    return value


def set_cached_result(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Store value with a TTL. ttl_seconds=0 means never cache."""
    if ttl_seconds <= 0:
        return
    expiry = time.monotonic() + ttl_seconds
    _cache[key] = (value, expiry)


def clear_cache() -> None:
    """Evict all entries."""
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0


def cache_stats() -> dict:
    """Return hit/miss/size statistics."""
    now = time.monotonic()
    active = sum(1 for _, (_, exp) in _cache.items() if exp > now)
    expired = len(_cache) - active
    return {
        "hits": _hits,
        "misses": _misses,
        "total_entries": len(_cache),
        "active_entries": active,
        "expired_entries": expired,
        "hit_rate": round(_hits / (_hits + _misses), 4) if (_hits + _misses) > 0 else 0.0,
    }
