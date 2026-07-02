from __future__ import annotations

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Fixed-window per-IP limiter. Like utils/cache.py this state is per-process, so
# on a multi-worker deployment each worker enforces its own window — fine for a
# free-tier single-instance API whose real goal is blunting scrapers/abuse.
# For a shared limit across workers/instances, back this with Redis.
_DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT_REQUESTS", "120"))
_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Only trust X-Forwarded-For when explicitly behind a known proxy; otherwise a
# client could spoof the header to evade the limit.
_TRUST_PROXY = os.environ.get("TRUST_PROXY", "false").lower() == "true"

# ip -> (window_start_epoch, request_count)
_hits: dict[str, tuple[float, int]] = {}

# Housekeeping is time-gated (at most once per window) rather than size-gated, so
# a saturated dict can't trigger a full O(n) scan on every request.
_last_prune: float = 0.0


def _client_ip(request: Request) -> str:
    if _TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_allowed(ip: str, now: float) -> tuple[bool, int]:
    """Return (allowed, seconds_until_reset) and record the hit when allowed."""
    window_start, count = _hits.get(ip, (now, 0))
    if now - window_start >= _WINDOW_SECONDS:
        window_start, count = now, 0

    if count >= _DEFAULT_LIMIT:
        return False, int(_WINDOW_SECONDS - (now - window_start)) + 1

    _hits[ip] = (window_start, count + 1)
    return True, 0


def _prune(now: float) -> None:
    """Drop expired windows so the dict can't grow unbounded over time."""
    expired = [ip for ip, (start, _) in _hits.items() if now - start >= _WINDOW_SECONDS]
    for ip in expired:
        del _hits[ip]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject a client that exceeds the per-IP request budget with HTTP 429."""

    async def dispatch(self, request: Request, call_next) -> Response:
        now = time.time()
        global _last_prune
        if now - _last_prune >= _WINDOW_SECONDS:
            _prune(now)
            _last_prune = now

        ip = _client_ip(request)
        allowed, retry_after = _is_allowed(ip, now)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
