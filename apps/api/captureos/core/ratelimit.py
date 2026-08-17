"""In-memory fixed-window rate limiter guarding /auth/login and /auth/register.

Per-process state: resets on restart and does not coordinate across multiple worker
processes/instances. That's an accepted tradeoff for the local-first default (matches
WORKFLOW_INLINE_WORKER's single-process posture) — a multi-instance production
deployment would need a shared store (e.g. Redis) behind this same interface. Kept as
a small standalone module rather than a full provider since auth is the only consumer.
"""

from __future__ import annotations

import time

from captureos.config import get_settings
from captureos.core.errors import RateLimitedError

_attempts: dict[str, list[float]] = {}


def check_rate_limit(key: str) -> None:
    """Raise RateLimitedError if ``key`` has exceeded the configured attempt budget
    within the current window; otherwise records this attempt against it."""
    settings = get_settings()
    limit = settings.auth_rate_limit_attempts
    window = settings.auth_rate_limit_window_seconds
    now = time.monotonic()

    recent = [t for t in _attempts.get(key, []) if now - t < window]
    if len(recent) >= limit:
        raise RateLimitedError(
            f"Too many attempts. Try again in under {window} seconds.",
            details={"retry_after_seconds": window},
        )
    recent.append(now)
    _attempts[key] = recent


def reset_rate_limits() -> None:
    """Clear all tracked attempts (test isolation)."""
    _attempts.clear()
