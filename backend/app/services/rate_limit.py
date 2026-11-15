"""Simple in-process sliding-window rate limiter for sensitive auth endpoints.

Limitation: counters live in one process. With several workers or servers,
use a shared store (e.g. Redis) or a reverse-proxy rate limit instead.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings
from app.services.audit import client_ip

_WINDOW_SECONDS = 60
_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def rate_limited(scope: str):
    """FastAPI dependency: at most RATE_LIMIT_AUTH requests per minute per client IP and scope."""

    def dependency(request: Request) -> None:
        key = f"{scope}:{client_ip(request) or 'unknown'}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > _WINDOW_SECONDS:
                q.popleft()
            if len(q) >= settings.rate_limit_auth:
                retry = int(_WINDOW_SECONDS - (now - q[0])) + 1
                raise HTTPException(429, "Too many attempts. Please wait and try again.", headers={"Retry-After": str(retry)})
            q.append(now)

    return dependency
