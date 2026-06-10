from app.config.logger import Logger
from typing import Dict, Optional

import httpx

from app.config.settings import SOCIAVAULT_API_KEY

logger = Logger.get(__name__)

_BASE_URL = "https://api.sociavault.com/v1"
_API_KEY  = SOCIAVAULT_API_KEY

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"X-API-Key": _API_KEY},
        timeout=20,
    )

async def search_keyword(
    query: str,
    cursor: int = 0,
    sort_by: Optional[str] = None,
    date_posted: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict:
    params: Dict = {"query": query, "cursor": cursor}
    if sort_by:     params["sort_by"]     = sort_by
    if date_posted: params["date_posted"] = date_posted
    if region:      params["region"]      = region

    async with _client() as c:
        r = await c.get("/scrape/tiktok/search/keyword", params=params)
        r.raise_for_status()
    logger.info("[sociavault] search query=%r", query)
    return r.json()

async def get_video_info(
    url: str,
    get_transcript: bool = False,
    region: Optional[str] = None,
) -> Dict:
    params: Dict = {"url": url}
    if get_transcript: params["get_transcript"] = "true"
    if region:         params["region"]         = region

    async with _client() as c:
        r = await c.get("/scrape/tiktok/video-info", params=params)
        r.raise_for_status()
    logger.info("[sociavault] video-info url=%s", url[:60])
    return r.json()

async def get_comments(
    url: str,
    cursor: int = 0,
) -> Dict:
    async with _client() as c:
        r = await c.get("/scrape/tiktok/comments", params={"url": url, "cursor": cursor})
        r.raise_for_status()
    logger.info("[sociavault] comments url=%s", url[:60])
    return r.json()

async def get_profile(handle: str) -> Dict:
    async with _client() as c:
        r = await c.get("/scrape/tiktok/profile", params={"handle": handle})
        r.raise_for_status()
    logger.info("[sociavault] profile handle=%s", handle)
    return r.json()
