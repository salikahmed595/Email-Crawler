"""
Token-bucket rate limiter for per-domain request throttling.
Fully async, no blocking.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Token bucket state for a single domain."""

    tokens: float
    last_refill: float = field(default_factory=time.monotonic)
    capacity: float = 5.0
    refill_rate: float = 1.0  # tokens per second


class RateLimiter:
    """
    Per-domain token bucket rate limiter.
    Prevents hammering individual sites.

    Usage:
        limiter = RateLimiter(rate=2.0)  # 2 requests/sec per domain
        await limiter.acquire("example.com")
    """

    def __init__(self, rate: float = 2.0, capacity: float | None = None) -> None:
        self._rate = rate
        self._capacity = capacity or max(rate, 1.0)
        self._buckets: dict[str, _Bucket] = defaultdict(
            lambda: _Bucket(tokens=self._capacity, capacity=self._capacity, refill_rate=self._rate)
        )
        self._lock = asyncio.Lock()

    async def acquire(self, key: str) -> None:
        """
        Wait until a token is available for the given key (domain).
        Blocks asynchronously — never busy-waits.
        """
        while True:
            async with self._lock:
                bucket = self._buckets[key]
                now = time.monotonic()
                elapsed = now - bucket.last_refill
                bucket.tokens = min(
                    bucket.capacity,
                    bucket.tokens + elapsed * bucket.refill_rate,
                )
                bucket.last_refill = now

                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    return

                wait_time = (1.0 - bucket.tokens) / bucket.refill_rate

            await asyncio.sleep(wait_time)

    def reset(self, key: str) -> None:
        """Reset the bucket for a domain (e.g. after a crawl completes)."""
        if key in self._buckets:
            del self._buckets[key]


# Global rate limiter instance — shared across all workers in a process
_global_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter singleton."""
    global _global_limiter
    if _global_limiter is None:
        from app.config import get_settings
        settings = get_settings()
        _global_limiter = RateLimiter(rate=settings.request_rate_per_second)
    return _global_limiter
