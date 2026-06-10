"""
Async wrappers around the sync services/ crawlers.
Adds tiktok/ to sys.path so services/ can resolve lib/signatures imports.

Token warming: module-level cache so each search reuses the token
instead of re-fetching TikTok homepage on every call.
"""
import asyncio
from app.config.logger import Logger
import os
import random
import sys
import time as _time
from typing import Dict, List, Optional

logger = Logger.get(__name__)

_TIKTOK_DIR = os.path.dirname(__file__)
if _TIKTOK_DIR not in sys.path:
    sys.path.insert(0, _TIKTOK_DIR)

# ── Token cache ───────────────────────────────────────────────────────────────

_token_cache: Dict = {"value": None, "expires": 0.0}
_TOKEN_TTL   = 55.0   # TikTok sessions ~1 min, refresh 5s sớm
_warm_lock   = asyncio.Lock()


def _cached_token() -> Optional[str]:
    if _token_cache["value"] and _time.time() < _token_cache["expires"]:
        return _token_cache["value"]
    return None


async def warm_token() -> Optional[str]:
    """Fetch a real msToken from TikTok homepage and cache it. Call on startup."""
    async with _warm_lock:
        if _cached_token():
            return _cached_token()
        try:
            from services import TikTokBaseService
            svc = TikTokBaseService(proxies=_pick_proxy())
            token = await asyncio.to_thread(svc.get_fresh_mstoken)
            if token:
                _token_cache["value"]   = token
                _token_cache["expires"] = _time.time() + _TOKEN_TTL
                logger.info("[native] msToken warmed: %s...", token[:20])
                return token
        except Exception as e:
            logger.warning("[native] token warm failed: %s", e)
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_video(item: Dict) -> Dict:
    video  = item.get("item", item)
    author = video.get("author", {})
    stats  = video.get("stats", {})
    music  = video.get("music", {})
    vid    = video.get("video", {})
    tags   = [t["hashtagName"] for t in video.get("textExtra", []) if t.get("hashtagName")]

    return {
        "video_id":    video.get("id"),
        "desc":        video.get("desc", ""),
        "create_time": video.get("createTime"),
        "url":         f"https://www.tiktok.com/@{author.get('uniqueId', '_')}/video/{video.get('id')}",
        "cover":       vid.get("cover"),
        "duration":    vid.get("duration"),
        "author": {
            "id":        author.get("id"),
            "sec_uid":   author.get("secUid"),
            "unique_id": author.get("uniqueId"),
            "nickname":  author.get("nickname"),
            "avatar":    author.get("avatarThumb"),
        },
        "stats": {
            "play":    stats.get("playCount"),
            "like":    stats.get("diggCount"),
            "comment": stats.get("commentCount"),
            "share":   stats.get("shareCount"),
            "collect": stats.get("collectCount"),
        },
        "music": {
            "title":  music.get("title"),
            "author": music.get("authorName"),
        },
        "tags": tags,
    }


def _extract_sociavault_video(aweme: Dict) -> Dict:
    author = aweme.get("author") or {}
    stats  = aweme.get("statistics") or {}
    music  = aweme.get("music") or {}
    vid    = aweme.get("video") or {}

    def _first_url(obj) -> Optional[str]:
        urls = (obj or {}).get("url_list") or {}
        if isinstance(urls, list): return urls[0] if urls else None
        if isinstance(urls, dict): return urls.get(0) or urls.get("0")
        return None

    avatar = _first_url(author.get("avatar_168x168") or author.get("avatar_thumb"))
    cover  = _first_url(vid.get("cover") or vid.get("origin_cover"))
    tags   = [t["hashtag_name"] for t in aweme.get("text_extra", [])
              if isinstance(t, dict) and t.get("hashtag_name")]
    uid    = author.get("unique_id") or author.get("uniqueId") or "_"

    return {
        "video_id":    aweme.get("aweme_id"),
        "desc":        aweme.get("desc", ""),
        "create_time": aweme.get("create_time"),
        "url":         f"https://www.tiktok.com/@{uid}/video/{aweme.get('aweme_id')}",
        "cover":       cover or None,
        "duration":    vid.get("duration"),
        "author": {
            "id":        author.get("uid"),
            "sec_uid":   author.get("sec_uid"),
            "unique_id": uid,
            "nickname":  author.get("nickname"),
            "avatar":    avatar or None,
        },
        "stats": {
            "play":    stats.get("play_count"),
            "like":    stats.get("digg_count"),
            "comment": stats.get("comment_count"),
            "share":   stats.get("share_count"),
            "collect": stats.get("collect_count"),
        },
        "music": {
            "title":  music.get("title"),
            "author": music.get("author"),
        },
        "tags": tags,
    }


def _format_sociavault_search(raw: Dict) -> Dict:
    inner   = raw.get("data") or {}
    items   = inner.get("search_item_list") or {}
    videos  = [
        _extract_sociavault_video(v["aweme_info"])
        for v in items.values()
        if isinstance(v, dict) and v.get("aweme_info")
    ]
    return {
        "success":  raw.get("success", False),
        "count":    len(videos),
        "has_more": bool(inner.get("has_more")),
        "cursor":   inner.get("cursor", 0),
        "videos":   videos,
        "source":   "sociavault",
    }


def _pick_proxy(pool: Optional[List[str]] = None) -> Optional[Dict]:
    from app.config.urls import PROXY_LIST
    proxies = pool or PROXY_LIST
    if not proxies:
        return None
    url = random.choice(proxies)
    return {"http": url, "https": url}


def _inject_token(service) -> bool:
    """
    Monkey-patch service to use cached token.
    Returns True if cache was available (can also skip sleep).
    """
    token = _cached_token()
    if not token:
        return False
    service.get_fresh_mstoken = lambda: token
    # Skip the artificial 1.5s delay since we already have the token
    original = service._make_request
    def _fast_make_request(endpoint, params, use_fresh_token=True,
                           delay_before_request=1.5, **kw):
        return original(endpoint, params, use_fresh_token=use_fresh_token,
                        delay_before_request=0, **kw)
    service._make_request = _fast_make_request
    return True


# ── Public functions ──────────────────────────────────────────────────────────

async def search_native(
    keyword: str,
    count: int = 20,
    cursor: int = 0,
    region: str = "VN",
    language: str = "vi",
) -> Dict:
    from services import SearchService
    service = SearchService(region=region, language=language, proxies=_pick_proxy())

    from_cache = _inject_token(service)
    if from_cache:
        logger.debug("[native/search] using cached token (no homepage request)")

    result = await asyncio.to_thread(
        service.search,
        keyword=keyword, count=count, cursor=cursor, use_fresh_token=True,
    )

    # If search succeeded, refresh token cache for next call
    if result.get("success") and result.get("data") and not from_cache:
        if service._session_mstoken:
            _token_cache["value"]   = service._session_mstoken
            _token_cache["expires"] = _time.time() + _TOKEN_TTL
            logger.info("[native] token cached from live request: %s...", service._session_mstoken[:20])

    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"]  = len(result["videos"])
    logger.info("[native/search] keyword=%r cached=%s count=%d", keyword, from_cache, result["count"])
    return result


async def trending_native(
    count: int = 20,
    region: str = "VN",
    language: str = "vi",
) -> Dict:
    from services import TrendingService
    service = TrendingService(region=region, language=language, proxies=_pick_proxy())
    result = await asyncio.to_thread(service.get_trending, count=count)

    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"]  = len(result["videos"])
    logger.info("[native/trending] region=%s success=%s count=%d", region, result.get("success"), result["count"])
    return result
