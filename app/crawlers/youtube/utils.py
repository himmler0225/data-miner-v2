import asyncio
from functools import wraps

import httpx
from fastapi import HTTPException

from app.config.logger import Logger
from app.config.proxy import registry
from app.exceptions import YouTubeStructureChangedError

logger = Logger.get(__name__)


def parse_view_count(text) -> int:
    if not text:
        return 0

    first = str(text).replace("\xa0", " ").split()[0].strip().upper().replace(",", "")

    try:
        if "TR" in str(text).upper():
            number = first.replace(".", "").replace(",", ".")
            return int(float(number) * 1_000_000)

        if first.endswith("K"):
            return int(float(first[:-1]) * 1_000)

        if first.endswith("M"):
            return int(float(first[:-1]) * 1_000_000)

        if first.endswith("B"):
            return int(float(first[:-1]) * 1_000_000_000)

        return int(first.replace(".", ""))

    except (ValueError, AttributeError):
        return 0


def retry_on_failure(max_retries=3, delay=1):
    """Retry decorator with linear backoff. Raises immediately on YouTubeStructureChangedError."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except YouTubeStructureChangedError as e:
                    logger.critical(
                        f"YouTube structure changed in {func.__name__}: {e}",
                        extra={"extra_data": {"context": e.context}},
                    )
                    raise HTTPException(
                        status_code=502, detail=f"YouTube structure changed: {e}"
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if (
                        isinstance(e, httpx.HTTPStatusError)
                        and 400 <= e.response.status_code < 500
                    ):
                        raise
                    last_exception = e
                    if isinstance(
                        e,
                        (
                            httpx.ProxyError,
                            httpx.ConnectError,
                            httpx.RemoteProtocolError,
                        ),
                    ):
                        registry.rotate()
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            "Attempt %d/%d for %s failed, retrying in %ds: %s",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            wait_time,
                            e,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(
                        " All %d retries exhausted for %s",
                        max_retries,
                        func.__name__,
                        exc_info=True,
                    )
                    raise last_exception

        return wrapper

    return decorator
