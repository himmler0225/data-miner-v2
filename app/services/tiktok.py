"""Shared business logic for TikTok — used by REST API and MCP tools."""

import app.crawlers.tiktok.cache as search_cache
import app.crawlers.tiktok.tikhub as tikhub
from app.config.logger import Logger
from app.crawlers.tiktok.config import DEFAULT_LANGUAGE, DEFAULT_REGION, DEFAULT_SEARCH_COUNT
from app.crawlers.tiktok.native import search_native
from app.exceptions import NativeSearchError, TikHubError

logger = Logger.get(__name__)


async def search_videos(
    keyword: str,
    *,
    count: int = DEFAULT_SEARCH_COUNT,
    cursor: int = 0,
    region: str = DEFAULT_REGION,
    language: str = DEFAULT_LANGUAGE,
    sort_by: str | None = None,
) -> dict:
    cache_key = (keyword.lower().strip(), count, cursor, region, sort_by)
    cached = search_cache.get(cache_key)
    if cached is not None:
        logger.info("[tiktok_search] cache hit q=%r", keyword)
        return cached

    try:
        result = await search_native(keyword=keyword, count=count, cursor=cursor, region=region, language=language)
        if result.get("videos"):
            search_cache.put(cache_key, result)
            return result
        logger.warning("[tiktok_search] native empty -> TikHub fallback")
    except NativeSearchError as exc:
        logger.warning("[tiktok_search] native pool exhausted -> TikHub fallback: %s", exc)
    except Exception as exc:
        logger.warning("[tiktok_search] native failed (%s) -> TikHub fallback", exc)

    sort_type = 1 if sort_by == "most-liked" else 0
    try:
        raw = await tikhub.search_videos(keyword=keyword, cursor=cursor, count=count, sort_type=sort_type)
    except TikHubError:
        raise
    except Exception as exc:
        raise TikHubError(str(exc)) from exc

    formatted = tikhub.format_search(raw)
    if formatted.get("videos"):
        search_cache.put(cache_key, formatted)
    return formatted
