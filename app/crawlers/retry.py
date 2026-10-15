"""Retry for crawler calls: retries transient upstream failures only."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

import httpx

from app.config.logger import Logger
from app.config.proxy import registry
from app.exceptions import CrawlNetworkError

logger = Logger.get(__name__)

T = TypeVar("T")

# Upstream statuses worth another attempt (through a fresh proxy for 429).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def is_transient(exc: BaseException) -> bool:
    """Network/proxy failures, blocked requests and 429/5xx responses. Everything
    else (4xx, parse errors, YouTubeStructureChangedError, ...) fails the same
    way on every attempt."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, CrawlNetworkError))


def _needs_new_proxy(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return isinstance(exc, (httpx.ProxyError, httpx.ConnectError, httpx.RemoteProtocolError, CrawlNetworkError))


async def retry_async(fn: Callable[[], Awaitable[T]], *, attempts: int = 3, delay: float = 1.0) -> T:
    """Await `fn()` up to `attempts` times with linear backoff, retrying only
    transient failures. `fn` should pick its proxy itself, so a retry after a
    rotation actually goes through a different one."""
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            if _needs_new_proxy(exc):
                registry.rotate()
            wait = delay * attempt
            logger.warning("Attempt %d/%d failed, retrying in %.1fs: %r", attempt, attempts, wait, exc)
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator form of `retry_async` for zero-argument coroutine functions."""

    def decorator(func: Callable[[], Awaitable[T]]) -> Callable[[], Awaitable[T]]:
        @wraps(func)
        async def wrapper() -> T:
            return await retry_async(func, attempts=max_retries, delay=delay)

        return wrapper

    return decorator
