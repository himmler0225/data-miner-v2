"""Unified API error mapping and response helper."""

from collections.abc import Awaitable
from typing import Any, TypeVar

import httpx
from fastapi import HTTPException

from app.config.logger import Logger
from app.exceptions import (
    CrawlNetworkError,
    InvalidInputError,
    TikHubError,
    YouTubeNotFoundError,
    YouTubeStructureChangedError,
)
from app.i18n import get_locale
from app.i18n.messages import t
from app.schemas.response import ApiResponse

logger = Logger.get(__name__)

T = TypeVar("T")


def to_http_exception(exc: Exception) -> HTTPException:
    """Map a domain/upstream error to the HTTP error the client sees:
    400 bad input, 404 not found, 502 upstream broke, 503 upstream throttling."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, InvalidInputError):
        return HTTPException(status_code=400, detail=t(exc.key, get_locale(), **exc.params))
    if isinstance(exc, YouTubeNotFoundError):
        return HTTPException(status_code=404, detail=t("errors.not_found", get_locale(), detail=str(exc)))
    if isinstance(exc, YouTubeStructureChangedError):
        logger.critical("YouTube structure changed: %s", exc, extra={"extra_data": {"context": exc.context}})
        return HTTPException(
            status_code=502, detail=t("errors.youtube_structure_changed", get_locale(), detail=str(exc))
        )
    if isinstance(exc, TikHubError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return HTTPException(status_code=503, detail="errors.upstream_rate_limited")
    if isinstance(exc, (CrawlNetworkError, httpx.HTTPStatusError, httpx.TransportError)):
        logger.warning("Upstream error: %r", exc)
        return HTTPException(status_code=502, detail="errors.upstream")
    logger.exception("Unhandled error", exc_info=exc)
    return HTTPException(status_code=500, detail="errors.generic")


async def api_ok(coro: Awaitable[T]) -> Any:
    """Run coroutine and wrap result in ApiResponse.ok; map domain errors to HTTPException."""
    try:
        return ApiResponse.ok(await coro)
    except Exception as exc:
        raise to_http_exception(exc) from exc
