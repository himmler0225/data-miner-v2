import asyncio
import dataclasses
import itertools
import threading
from app.config.logger import Logger
import os
import sys
import time as _time
from typing import Dict, List, Optional

logger = Logger.get(__name__)

_TIKTOK_DIR = os.path.dirname(__file__)
if _TIKTOK_DIR not in sys.path:
    sys.path.insert(0, _TIKTOK_DIR)

_NATIVE_TIMEOUT = 25.0  # hard cap so a stuck request falls back to SociaVault

async def _proxy_dict() -> Optional[Dict]:
    """Sticky proxy (same exit IP for ~15 min)."""
    from app.config.urls import proxy_manager
    url = await proxy_manager.get_proxy()
    return {"http": url, "https": url} if url else None


# ── Identity pool ─────────────────────────────────────────────────────────────
# TikTok validates (ttwid + msToken + IP + UA) as ONE consistent profile. They
# must be minted AND used together. Each identity binds a warmed session (ttwid),
# the proxy it was warmed through, and an msToken refreshed on that same session.

@dataclasses.dataclass
class TikTokIdentity:
    session: object                      # requests.Session (carries ttwid)
    proxy:   Optional[Dict]              # the proxy ttwid was minted through
    ua:      str                         # UA used for warm + must match search
    lock:    threading.Lock = dataclasses.field(default_factory=threading.Lock)

_POOL_SIZE  = 3
_pool: List[TikTokIdentity] = []
_pool_cycle = None
_pool_lock  = threading.Lock()


def _warm_one_identity(proxy: Optional[Dict]) -> Optional[TikTokIdentity]:
    """Warm a session THROUGH `proxy` so ttwid + IP + UA are bound together.
    msToken is NOT managed here — SearchService mints it on this trusted session."""
    import requests
    from services import TikTokBaseService
    s = requests.Session()
    if proxy:
        s.proxies.update(proxy)
    ua = TikTokBaseService.MOBILE_UA
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    try:
        s.get(TikTokBaseService.BASE_URL, headers=headers, timeout=10, allow_redirects=True)
        s.get(f"{TikTokBaseService.BASE_URL}/explore", headers=headers, timeout=10, allow_redirects=True)
    except Exception as e:
        logger.warning("[native/pool] warm failed: %s", e)
        return None
    if not any(c.name == "ttwid" for c in s.cookies):
        logger.warning("[native/pool] session warmed without ttwid — discarding")
        return None
    return TikTokIdentity(session=s, proxy=proxy, ua=ua)


async def warm_session_pool(size: int = _POOL_SIZE) -> int:
    """Build the identity pool — each warmed through its own sticky proxy."""
    global _pool, _pool_cycle
    proxies = [await _proxy_dict() for _ in range(size)]
    idents = await asyncio.gather(
        *[asyncio.to_thread(_warm_one_identity, p) for p in proxies]
    )
    good = [i for i in idents if i is not None]
    with _pool_lock:
        _pool = good
        _pool_cycle = itertools.cycle(good) if good else None
    logger.info("[native/pool] warmed %d/%d identities", len(good), size)
    return len(good)


def _next_identity() -> Optional[TikTokIdentity]:
    with _pool_lock:
        if not _pool_cycle:
            return None
        return next(_pool_cycle)


async def session_pool_refresher(interval: float = 600.0) -> None:
    """Refresh every 10 min to stay within the sticky-proxy window (15 min)."""
    while True:
        await asyncio.sleep(interval)
        try:
            await warm_session_pool()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[native/pool] refresh error: %s", e)

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


def _search_with_identity(ident: TikTokIdentity, keyword, count, cursor, region, language) -> Dict:
    """Runs in a thread. Reuses the identity's trusted session (ttwid) + proxy + UA,
    but lets SearchService mint msToken itself — the trusted session mints a valid
    token fast. Do NOT manage msToken manually (the homepage cookie isn't the token
    the search API needs). requests.Session isn't thread-safe → hold the lock."""
    from services import SearchService
    with ident.lock:
        service = SearchService(region=region, language=language,
                                proxies=ident.proxy, session=ident.session)
        return service.search(keyword=keyword, count=count, cursor=cursor, use_fresh_token=True)


def _finalize(result: Dict, keyword: str, t0: float, tag: str) -> Dict:
    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"]  = len(result["videos"])
    logger.info("[native/search] keyword=%r took=%.2fs count=%d success=%s via=%s",
                keyword, _time.perf_counter() - t0, result["count"], result.get("success"), tag)
    return result


async def search_native(
    keyword: str,
    count: int = 20,
    cursor: int = 0,
    region: str = "VN",
    language: str = "vi",
) -> Dict:
    t0 = _time.perf_counter()
    ident = _next_identity()

    if ident is None:
        # Pool empty (warm failed) → one-off identity bound to a fresh proxy.
        proxy = await _proxy_dict()
        ident = await asyncio.to_thread(_warm_one_identity, proxy)
        if ident is None:
            return {"success": False, "videos": [], "count": 0}

    result = await asyncio.wait_for(
        asyncio.to_thread(_search_with_identity, ident, keyword, count, cursor, region, language),
        timeout=_NATIVE_TIMEOUT,
    )

    # Empty → this identity's token/IP profile is stale; rotate to another once.
    if not result.get("data"):
        ident.mstoken = None
        ident2 = _next_identity()
        if ident2 is not None and ident2 is not ident:
            logger.info("[native/search] empty → rotating identity & retry")
            result = await asyncio.wait_for(
                asyncio.to_thread(_search_with_identity, ident2, keyword, count, cursor, region, language),
                timeout=_NATIVE_TIMEOUT,
            )
            return _finalize(result, keyword, t0, "retry")

    return _finalize(result, keyword, t0, "pool")

async def trending_native(
    count: int = 20,
    region: str = "VN",
    language: str = "vi",
) -> Dict:
    from services import TrendingService
    service = TrendingService(region=region, language=language, proxies=await _proxy_dict())
    result = await asyncio.wait_for(
        asyncio.to_thread(service.get_trending, count=count),
        timeout=_NATIVE_TIMEOUT,
    )

    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"]  = len(result["videos"])
    logger.info("[native/trending] region=%s success=%s count=%d", region, result.get("success"), result["count"])
    return result
