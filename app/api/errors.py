"""Unified API error mapping and response helper."""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import HTTPException

from app.crawlers.movies import client as movie_client
from app.exceptions import CrawlNetworkError, CrawlTimeoutError, TikHubError, YouTubeStructureChangedError
from app.schemas.response import ApiResponse

T = TypeVar("T")


def to_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, movie_client.MovieValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, (movie_client.MovieUpstreamError, TikHubError, YouTubeStructureChangedError)):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, (CrawlNetworkError, CrawlTimeoutError)):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


async def api_ok(coro: Awaitable[T]) -> Any:
    """Run coroutine and wrap result in ApiResponse.ok; map domain errors to HTTPException."""
    try:
        return ApiResponse.ok(await coro)
    except Exception as exc:
        raise to_http_exception(exc) from exc


async def run_handler(handler: Callable[[], Awaitable[T]]) -> Any:
  """Alias for route handlers that use inner `async def _()` pattern."""
  return await api_ok(handler())
