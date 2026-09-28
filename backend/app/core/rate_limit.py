"""In-process token-bucket rate limiting (ARCHITECTURE.md §9).

Single backend instance (Railway service runs 1 worker), so an in-memory store is sufficient — no Redis
dependency. A Cloudflare rule on /api/v1/auth/* is the second layer once a domain exists (see A17).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.core.errors import RateLimitedError


class _Bucket:
    __slots__ = ("count", "window_start")

    def __init__(self) -> None:
        self.count = 0
        self.window_start = time.monotonic()


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            if now - bucket.window_start >= window_seconds:
                bucket.window_start = now
                bucket.count = 0
            bucket.count += 1
            if bucket.count > limit:
                raise RateLimitedError()

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


rate_limiter = RateLimiter()

# Login: 5/min per IP+identifier, 20/min per IP (ARCHITECTURE.md §9)
LOGIN_PER_IDENTIFIER = (5, 60.0)
LOGIN_PER_IP = (20, 60.0)
AUTOSAVE_PER_ATTEMPT = (2, 1.0)
