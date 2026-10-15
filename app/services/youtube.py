"""YouTube operations shared by the REST API and the MCP tools.

Every operation here:
- validates its input (InvalidInputError -> 400),
- resolves @handles to channel ids,
- picks a proxy per attempt and retries transient upstream failures,
- maps YouTube's 400/404 to YouTubeNotFoundError (-> 404),
- caches its result briefly,
- returns the response payload.

List operations page with `limit` + an opaque `cursor` and return
`{"items": [...], "next_cursor": str | None, "has_more": bool, **context}`.
Item shapes are defined in app/crawlers/youtube/shared/models.py.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

import httpx

from app.config.proxy import get_proxy
from app.crawlers.retry import retry_async
from app.crawlers.youtube.channel.channel import fetch_channel_videos_page
from app.crawlers.youtube.channel_info.channel_info import get_channel_info
from app.crawlers.youtube.client import resolve_channel_id_from_handle
from app.crawlers.youtube.comment.comment import CommentSort, fetch_comments_page
from app.crawlers.youtube.config import (
    BATCH_CONCURRENCY,
    CACHE_MAX_ENTRIES,
    CACHE_TTL_HANDLE,
    CACHE_TTL_ITEM,
    CACHE_TTL_LIST,
    CACHE_TTL_TRANSCRIPT,
    CHANNEL_TOPICS,
    DEFAULT_PAGE_LIMIT,
    MAX_BATCH_IDS,
    MAX_PAGE_LIMIT,
    SEARCH_FILTER_LIVE,
    SEARCH_TOPICS,
)
from app.crawlers.youtube.detail.detail import get_video_detail
from app.crawlers.youtube.location.location import get_region_context
from app.crawlers.youtube.playlist.playlist import fetch_channel_playlists_page, fetch_playlist_videos_page
from app.crawlers.youtube.search.search import fetch_search_page
from app.crawlers.youtube.search.search_constants import SORT_OPTIONS
from app.crawlers.youtube.shared.paging import Page, collect_page
from app.crawlers.youtube.shorts.shorts import get_shorts_feed
from app.crawlers.youtube.topic.topic import get_topic_playlists
from app.crawlers.youtube.transcript.transcript import get_transcript
from app.exceptions import InvalidInputError, YouTubeNotFoundError
from app.services.cache import TTLCache

T = TypeVar("T")

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{3,100}$")
_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
_COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")
_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z]{2,4})?$")

COMMENT_SORTS = ("top", "newest")
TOPICS = [*CHANNEL_TOPICS, *SEARCH_TOPICS]

_cache = TTLCache(CACHE_MAX_ENTRIES)


# ── validation ────────────────────────────────────────────────────────────────


def _check(value: str, pattern: re.Pattern, kind: str) -> str:
    value = (value or "").strip()
    if not pattern.match(value):
        raise InvalidInputError("errors.invalid_id", kind=kind, value=value)
    return value


def validate_video_id(video_id: str) -> str:
    return _check(video_id, _VIDEO_ID_RE, "video_id")


def validate_playlist_id(playlist_id: str) -> str:
    return _check(playlist_id, _PLAYLIST_ID_RE, "playlist_id")


def _param(name: str, value, allowed: Iterable) -> str:
    if value not in allowed:
        raise InvalidInputError("errors.invalid_param", name=name, value=value)
    return value


def _query(value: str, *, required: bool = True) -> str:
    value = (value or "").strip()
    if required and not value:
        raise InvalidInputError("errors.invalid_param", name="q", value=value)
    return value


def _limit(limit: int | None) -> int:
    return max(1, min(int(limit or DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT))


def parse_video_ids(raw: str | Iterable[str]) -> list[str]:
    """Video ids from a comma-separated string or a list, validated and de-duplicated."""
    parts = raw.split(",") if isinstance(raw, str) else raw
    ids = list(dict.fromkeys(str(p).strip() for p in parts if str(p).strip()))
    if not ids:
        raise InvalidInputError("errors.video_ids_empty")
    if len(ids) > MAX_BATCH_IDS:
        raise InvalidInputError("errors.too_many_video_ids", max=MAX_BATCH_IDS)
    return [validate_video_id(v) for v in ids]


# ── upstream calls ────────────────────────────────────────────────────────────


async def _call(fetch: Callable[[str | None], Awaitable[T]], *, what: str, country: str | None = None) -> T:
    """`fetch(proxy)` with a fresh proxy per attempt and transient-error retries.
    YouTube answers 400/404 for ids that don't exist; those become not-found."""

    async def attempt() -> T:
        proxy = await get_proxy(country) if country else await get_proxy()
        return await fetch(proxy)

    try:
        return await retry_async(attempt)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 404):
            raise YouTubeNotFoundError(f"{what} (YouTube HTTP {exc.response.status_code})") from exc
        raise


PageFn = Callable[[str | None, str | None], Awaitable[tuple[list[dict], str | None]]]


async def _list(
    cache_key: tuple,
    fetch_page: PageFn,
    *,
    what: str,
    limit: int | None,
    cursor: str | None,
    item_key: str,
    country: str | None = None,
) -> dict:
    """One page of a list operation. `fetch_page(token, proxy)` returns one YouTube page."""
    limit = _limit(limit)

    async def build() -> dict:
        page = await collect_page(
            lambda token: _call(lambda proxy: fetch_page(token, proxy), what=what, country=country),
            limit,
            cursor or None,
            key=lambda item: item[item_key],
        )
        return page.as_dict()

    return await _cache.get_or_fetch((*cache_key, limit, cursor or None), CACHE_TTL_LIST, build)


async def resolve_channel(channel: str) -> str:
    """Channel id for a channel id (UC...) or an @handle."""
    channel = (channel or "").strip()
    if _CHANNEL_ID_RE.match(channel):
        return channel
    if not _HANDLE_RE.match(channel):
        raise InvalidInputError("errors.invalid_id", kind="channel_id", value=channel)
    return await _cache.get_or_fetch(
        ("handle", channel.lower()),
        CACHE_TTL_HANDLE,
        lambda: _call(lambda proxy: resolve_channel_id_from_handle(channel, proxy=proxy), what=f"channel {channel}"),
    )


# ── videos ────────────────────────────────────────────────────────────────────


async def search_videos(q: str, *, sort: str = "relevance", limit: int | None = None, cursor: str | None = None):
    q = _query(q)
    sort = _param("sort", sort, SORT_OPTIONS)
    page = await _list(
        ("search", q, sort),
        lambda token, proxy: fetch_search_page(q, params=SORT_OPTIONS[sort], token=token, proxy=proxy),
        what=f"search {q!r}",
        limit=limit,
        cursor=cursor,
        item_key="video_id",
    )
    return {"query": q, "sort": sort, **page}


async def live_videos(q: str = "", *, limit: int | None = None, cursor: str | None = None) -> dict:
    q = _query(q, required=False)
    page = await _list(
        ("live", q),
        lambda token, proxy: fetch_search_page(q, params=SEARCH_FILTER_LIVE, token=token, proxy=proxy),
        what=f"live search {q!r}",
        limit=limit,
        cursor=cursor,
        item_key="video_id",
    )
    return {"query": q, **page}


async def region_videos(
    q: str, *, gl: str, hl: str = "vi", limit: int | None = None, cursor: str | None = None
) -> dict:
    """Search as a viewer in country `gl` (language `hl`), through a proxy in that
    region when one is configured (US, otherwise VN)."""
    q = _query(q)
    gl = _check(gl, _COUNTRY_RE, "gl").upper()
    hl = _check(hl, _LANGUAGE_RE, "hl")
    page = await _list(
        ("region", q, gl, hl),
        lambda token, proxy: fetch_search_page(q, context=get_region_context(gl, hl), token=token, proxy=proxy),
        what=f"region search {q!r}",
        limit=limit,
        cursor=cursor,
        item_key="video_id",
        country="US" if gl == "US" else "VN",
    )
    return {"query": q, "gl": gl, "hl": hl, **page}


async def topic_videos(topic: str, *, limit: int | None = None, cursor: str | None = None) -> dict:
    """Videos for a topic: channel topics play the channel's featured playlist,
    search topics run a preset search."""
    topic = _param("topic", (topic or "").lower(), TOPICS)
    if topic in SEARCH_TOPICS:
        query, sort = SEARCH_TOPICS[topic]
        page = await search_videos(query, sort=sort, limit=limit, cursor=cursor)
        return {"topic": topic, "source": "search", **page}

    channel_id = CHANNEL_TOPICS[topic]
    playlists = await _cache.get_or_fetch(
        ("topic_playlists", channel_id),
        CACHE_TTL_LIST,
        lambda: _call(lambda proxy: get_topic_playlists(channel_id, proxy=proxy), what=f"topic {topic}"),
    )
    if not playlists:
        return {"topic": topic, "source": "channel", "featured_playlist": None, **Page([], None).as_dict()}
    featured = playlists[0]
    page = await playlist_videos(featured["playlist_id"], limit=limit, cursor=cursor)
    return {"topic": topic, "source": "channel", "featured_playlist": featured, **page}


async def shorts_feed(*, limit: int | None = None) -> dict:
    """Trending Shorts. The feed is randomized server-side, so there's no cursor."""
    limit = _limit(limit)

    async def build() -> dict:
        items = await _call(lambda proxy: get_shorts_feed(proxy=proxy, max_results=limit), what="shorts feed")
        return {"items": items, "next_cursor": None, "has_more": False}

    return await _cache.get_or_fetch(("shorts", limit), CACHE_TTL_LIST, build)


async def video_detail(video_id: str) -> dict:
    video_id = validate_video_id(video_id)
    return await _cache.get_or_fetch(
        ("detail", video_id),
        CACHE_TTL_ITEM,
        lambda: _call(lambda proxy: get_video_detail(video_id, proxy=proxy), what=f"video {video_id}"),
    )


# ── comments / transcripts ────────────────────────────────────────────────────


async def video_comments(
    video_id: str, *, sort: CommentSort = "top", limit: int | None = None, cursor: str | None = None
) -> dict:
    video_id = validate_video_id(video_id)
    sort = _param("sort", sort, COMMENT_SORTS)
    page = await _list(
        ("comments", video_id, sort),
        lambda token, proxy: fetch_comments_page(video_id, sort, token=token, proxy=proxy),
        what=f"video {video_id}",
        limit=limit,
        cursor=cursor,
        item_key="comment_id",
    )
    return {"video_id": video_id, "sort": sort, **page}


async def video_transcript(video_id: str) -> dict:
    video_id = validate_video_id(video_id)
    return await _cache.get_or_fetch(
        ("transcript", video_id),
        CACHE_TTL_TRANSCRIPT,
        lambda: _call(lambda proxy: get_transcript(video_id, proxy=proxy), what=f"video {video_id}"),
    )


async def _batch(video_ids: list[str], run: Callable[[str], Awaitable[dict]]) -> list[dict]:
    """`run(video_id)` for each id (bounded concurrency), keeping input order.
    A failing video becomes an item with available=False instead of failing the batch."""
    sem = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def one(video_id: str) -> dict:
        async with sem:
            try:
                return await run(video_id)
            except YouTubeNotFoundError as exc:
                return {"video_id": video_id, "available": False, "reason": "not_found", "error": str(exc)}
            except Exception as exc:
                return {"video_id": video_id, "available": False, "reason": "error", "error": str(exc)}

    return await asyncio.gather(*(one(v) for v in video_ids))


async def comments_batch(video_ids: str | Iterable[str], *, sort: CommentSort = "top", limit: int | None = None):
    """First `limit` comments of several videos. Videos with comments disabled or
    failing are reported per item (available=False + reason) rather than failing the call."""
    ids = parse_video_ids(video_ids)
    sort = _param("sort", sort, COMMENT_SORTS)

    async def run(video_id: str) -> dict:
        page = await video_comments(video_id, sort=sort, limit=limit)
        if not page["items"]:
            return {"video_id": video_id, "available": False, "reason": "disabled_or_empty", "comments": []}
        return {"video_id": video_id, "available": True, "reason": None, "comments": page["items"]}

    items = [{"comments": [], **item} for item in await _batch(ids, run)]
    return {
        "requested": len(ids),
        "succeeded": sum(1 for item in items if item["available"]),
        "total_comments": sum(len(item["comments"]) for item in items),
        "items": items,
    }


async def transcript_batch(video_ids: str | Iterable[str]) -> dict:
    ids = parse_video_ids(video_ids)
    items = await _batch(ids, video_transcript)
    return {
        "requested": len(ids),
        "succeeded": sum(1 for item in items if item["available"]),
        "items": items,
    }


# ── channels / playlists ──────────────────────────────────────────────────────


async def channel_info(channel: str) -> dict:
    channel_id = await resolve_channel(channel)
    return await _cache.get_or_fetch(
        ("channel", channel_id),
        CACHE_TTL_ITEM,
        lambda: _call(lambda proxy: get_channel_info(channel_id, proxy=proxy), what=f"channel {channel_id}"),
    )


async def channel_videos(channel: str, *, limit: int | None = None, cursor: str | None = None) -> dict:
    channel_id = await resolve_channel(channel)
    page = await _list(
        ("channel_videos", channel_id),
        lambda token, proxy: fetch_channel_videos_page(channel_id, token=token, proxy=proxy),
        what=f"channel {channel_id}",
        limit=limit,
        cursor=cursor,
        item_key="video_id",
    )
    return {"channel_id": channel_id, **page}


async def channel_playlists(channel: str, *, limit: int | None = None, cursor: str | None = None) -> dict:
    channel_id = await resolve_channel(channel)
    page = await _list(
        ("channel_playlists", channel_id),
        lambda token, proxy: fetch_channel_playlists_page(channel_id, token=token, proxy=proxy),
        what=f"channel {channel_id}",
        limit=limit,
        cursor=cursor,
        item_key="playlist_id",
    )
    return {"channel_id": channel_id, **page}


async def playlist_videos(playlist_id: str, *, limit: int | None = None, cursor: str | None = None) -> dict:
    playlist_id = validate_playlist_id(playlist_id)
    page = await _list(
        ("playlist_videos", playlist_id),
        lambda token, proxy: fetch_playlist_videos_page(playlist_id, token=token, proxy=proxy),
        what=f"playlist {playlist_id}",
        limit=limit,
        cursor=cursor,
        item_key="video_id",
    )
    return {"playlist_id": playlist_id, **page}
