"""
Retry decorator with exponential backoff using tenacity.
Configured to retry network/temporary errors, not permanent failures.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Exceptions that are retryable (temporary/network errors)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Exceptions that are NOT retryable — fail immediately
NON_RETRYABLE_EXCEPTIONS = (
    ValueError,
    PermissionError,
)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    exceptions: tuple = RETRYABLE_EXCEPTIONS,
) -> Any:
    """
    Decorator factory: retry on specified exceptions with exponential backoff.

    Do NOT retry:
    - 404 Not Found
    - Invalid domains
    - Malformed URLs
    - ValueError / PermissionError

    Usage:
        @with_retry(max_attempts=3)
        async def fetch_page(url):
            ...
    """
    return retry(
        retry=retry_if_exception_type(exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        reraise=True,
    )


async def retry_async(
    fn: Callable,
    *args: Any,
    max_attempts: int = 3,
    exceptions: tuple = RETRYABLE_EXCEPTIONS,
    **kwargs: Any,
) -> Any:
    """
    Functional retry helper for async callables.
    Returns the result or raises after exhausting retries.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except NON_RETRYABLE_EXCEPTIONS:
            raise
        except exceptions as exc:
            last_exc = exc
            logger.debug(
                "Retry attempt",
                extra={"attempt": attempt, "max": max_attempts, "error": str(exc)},
            )
            if attempt == max_attempts:
                raise
            import asyncio
            await asyncio.sleep(min(2 ** attempt, 30))
    raise last_exc  # type: ignore[misc]
