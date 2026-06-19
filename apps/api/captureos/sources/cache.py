"""In-process TTL cache + min-interval rate limiter for external source fetches (NFR-7).

These are intentionally simple (single-process). In a multi-instance deployment a shared
cache (Redis) and the source's own quota would back this; the adapter interface is unchanged.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

import anyio

from captureos.config import get_settings


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)


class RateLimiter:
    """Enforces a minimum interval between calls per key (politeness, NFR-7)."""

    def __init__(self, per_minute: int) -> None:
        self._interval = 60.0 / max(1, per_minute)
        self._last: dict[str, float] = {}
        self._lock = anyio.Lock()

    async def acquire(self, key: str = "default") -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last.get(key, 0.0))
            if wait > 0:
                await anyio.sleep(wait)
            self._last[key] = time.monotonic()


@lru_cache
def get_source_cache() -> TTLCache:
    return TTLCache()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().source_fetch_rate_limit_per_min)
