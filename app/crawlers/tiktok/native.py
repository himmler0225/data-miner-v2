import asyncio
import dataclasses
import itertools
import os
import sys
import threading
import time as _time
from typing import Dict, List, Optional

from app.config.constants import (MSTOKEN_TTL, POOL_REFRESH_INTERVAL,
                                  TIKTOK_NATIVE_TIMEOUT, TIKTOK_POOL_SIZE,
                                  TIKTOK_WARM_EXPLORE, TIKTOK_WARM_TIMEOUT,
                                  TIKTOK_WARM_TIMEOUT_2)
from app.config.logger import Logger
from app.config.proxy import TIKTOK_COUNTRY, get_proxy
from app.exceptions import NativeSearchError

logger = Logger.get(__name__)

_TIKTOK_DIR = os.path.dirname(__file__)
if _TIKTOK_DIR not in sys.path:
    sys.path.insert(0, _TIKTOK_DIR)

_NATIVE_TIMEOUT = TIKTOK_NATIVE_TIMEOUT


async def _proxy_dict() -> Optional[Dict]:
    proxy = await get_proxy(TIKTOK_COUNTRY)

    if not proxy:
        logger.warning("🔴 [tiktok] US proxy not configured — TikTok will likely fail")
        return None

    return {"http": proxy, "https": proxy}


_MSTOKEN_TTL = MSTOKEN_TTL


@dataclasses.dataclass
class TikTokIdentity:
    session: object  # requests.Session (carries ttwid)
    proxy: Optional[Dict]  # proxy used for warm + search
    ua: str  # UA consistent across warm + search
    mstoken: Optional[str] = None  # last-minted msToken for THIS session
    mstoken_ts: float = 0.0  # time.monotonic() when it was minted
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)


_POOL_SIZE = TIKTOK_POOL_SIZE
_pool: List[TikTokIdentity] = []
_pool_cycle = None
_pool_lock = threading.Lock()


def _warm_one_identity(proxy: Optional[Dict]) -> Optional[TikTokIdentity]:
    """Warm a session THROUGH `proxy` so ttwid + IP + UA are bound together.
    Uses curl_cffi to impersonate Chrome TLS fingerprint and bypass TikTok WAF."""
    from curl_cffi import requests as cffi_requests
    from services import TikTokBaseService

    proxy_url = proxy.get("https") or proxy.get("http") if proxy else None
    ua = TikTokBaseService.MAC_SEARCH_UA

    proxy_url = (proxy or {}).get("https") or (proxy or {}).get("http")
    logger.info(
        "🔵 [pool] warming session proxy=%s", proxy_url[:30] if proxy_url else "DIRECT⚠️"
    )
    if not proxy_url:
        logger.warning(
            "🔴 [pool] no proxy available — ttwid will bind to server IP, search will likely fail"
        )

    try:
        s = cffi_requests.Session(impersonate="chrome120", proxies=proxy)
        s.headers.update(
            {
                "User-Agent": ua,
                "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            }
        )
        s.get(
            TikTokBaseService.BASE_URL,
            timeout=TIKTOK_WARM_TIMEOUT,
            allow_redirects=True,
        )
        s.get(
            f"{TikTokBaseService.BASE_URL}/explore",
            timeout=TIKTOK_WARM_EXPLORE,
            allow_redirects=True,
        )
    except Exception as e:
        err_str = str(e)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower():
            logger.warning("🟡 [pool] warm timeout proxy=%s — retrying once", proxy_url)
            try:
                s2 = cffi_requests.Session(impersonate="chrome120", proxies=proxy)
                s2.headers.update(
                    {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
                )
                s2.get(
                    TikTokBaseService.BASE_URL,
                    timeout=TIKTOK_WARM_TIMEOUT_2,
                    allow_redirects=True,
                )
                s = s2
            except Exception as e2:
                logger.warning(
                    "🔴 [pool] warm retry also failed proxy=%s err=%s", proxy_url, e2
                )
                return None
        else:
            logger.warning("🔴 [pool] warm failed proxy=%s err=%s", proxy_url, e)
            return None

    cookie_names = (
        set(s.cookies.keys())
        if hasattr(s.cookies, "keys")
        else {c.name for c in s.cookies}
    )
    if "ttwid" not in cookie_names:
        logger.warning("🔴 [pool] session warmed without ttwid — discarding")
        return None

    cookies = cookie_names
    logger.info("🔵 [pool] identity ready cookies=%s", sorted(cookies))
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
    logger.info("🔵 [pool] warmed %d/%d identities", len(good), size)
    return len(good)


def _next_identity() -> Optional[TikTokIdentity]:
    with _pool_lock:
        if not _pool_cycle:
            return None
        return next(_pool_cycle)


async def session_pool_refresher(interval: float = POOL_REFRESH_INTERVAL) -> None:
    """Refresh every 10 min to stay within the sticky-proxy window (15 min)."""
    while True:
        await asyncio.sleep(interval)
        try:
            await warm_session_pool()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("🔴 [pool] refresh error: %s", e)


def _extract_video(item: Dict) -> Dict:
    video = item.get("item", item)
    author = video.get("author", {})
    stats = video.get("stats", {})
    music = video.get("music", {})
    vid = video.get("video", {})
    tags = [
        t["hashtagName"] for t in video.get("textExtra", []) if t.get("hashtagName")
    ]

    return {
        "video_id": video.get("id"),
        "desc": video.get("desc", ""),
        "create_time": video.get("createTime"),
        "url": f"https://www.tiktok.com/@{author.get('uniqueId', '_')}/video/{video.get('id')}",
        "cover": vid.get("cover"),
        "duration": vid.get("duration"),
        "author": {
            "id": author.get("id"),
            "sec_uid": author.get("secUid"),
            "unique_id": author.get("uniqueId"),
            "nickname": author.get("nickname"),
            "avatar": author.get("avatarThumb"),
        },
        "stats": {
            "play": stats.get("playCount"),
            "like": stats.get("diggCount"),
            "comment": stats.get("commentCount"),
            "share": stats.get("shareCount"),
            "collect": stats.get("collectCount"),
        },
        "music": {
            "title": music.get("title"),
            "author": music.get("authorName"),
        },
        "tags": tags,
    }


def _search_with_identity(
    ident: TikTokIdentity, keyword, count, cursor, region, language
) -> Dict:
    """Runs in a thread. US proxy session already has ttwid — go straight to the
    search API without visiting the search page first (confirmed unnecessary).
    requests.Session isn't thread-safe → hold the lock."""
    from services import SearchService

    with ident.lock:
        service = SearchService(
            region=region, language=language, proxies=ident.proxy, session=ident.session
        )
        now = _time.monotonic()
        if ident.mstoken and (now - ident.mstoken_ts) < _MSTOKEN_TTL:
            token = ident.mstoken
            service.get_fresh_mstoken = lambda: token
        else:
            ident.mstoken = None  # force fresh mint
            ident.mstoken_ts = 0.0

        # Patch out the 1.5s artificial pre-request sleep.
        original = service._make_request

        def _no_delay(
            endpoint, params, use_fresh_token=True, delay_before_request=1.5, **kw
        ):  # noqa: ignored
            return original(
                endpoint,
                params,
                use_fresh_token=use_fresh_token,
                delay_before_request=0,
                **kw,
            )

        service._make_request = _no_delay

        result = service.search(
            keyword=keyword, count=count, cursor=cursor, use_fresh_token=True
        )

        # Store the freshly minted token for next call.
        if service._session_mstoken:
            ident.mstoken = service._session_mstoken
            ident.mstoken_ts = _time.monotonic()

        return result


def _finalize(result: Dict, keyword: str, t0: float, tag: str) -> Dict:
    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"] = len(result["videos"])
    logger.info(
        "🟢 [native] keyword=%r took=%.2fs count=%d success=%s via=%s",
        keyword,
        _time.perf_counter() - t0,
        result["count"],
        result.get("success"),
        tag,
    )
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
        proxy = await _proxy_dict()
        ident = await asyncio.to_thread(_warm_one_identity, proxy)
        if ident is None:
            raise NativeSearchError("pool exhausted and on-demand warm failed")

    result = await asyncio.wait_for(
        asyncio.to_thread(
            _search_with_identity, ident, keyword, count, cursor, region, language
        ),
        timeout=_NATIVE_TIMEOUT,
    )

    logger.info(
        "🔵 [native] raw result success=%s data_len=%d",
        result.get("success"),
        len(result.get("data") or []),
    )

    if not result.get("data"):
        ident.mstoken = None
        ident2 = _next_identity()
        if ident2 is not None and ident2 is not ident:
            logger.info(
                "🟡 [native] empty → rotating identity & retry identity & retry"
            )
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _search_with_identity,
                    ident2,
                    keyword,
                    count,
                    cursor,
                    region,
                    language,
                ),
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

    service = TrendingService(
        region=region, language=language, proxies=await _proxy_dict()
    )
    result = await asyncio.wait_for(
        asyncio.to_thread(service.get_trending, count=count),
        timeout=_NATIVE_TIMEOUT,
    )

    raw = result.pop("data", []) or []
    result["videos"] = [_extract_video(i) for i in raw]
    result["count"] = len(result["videos"])
    logger.info(
        "🟢 [trending] region=%s success=%s count=%d",
        region,
        result.get("success"),
        result["count"],
    )
    return result
