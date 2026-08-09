from typing import Any

from app.config.logger import Logger
from app.config.proxy import get_proxy
from app.crawlers.youtube.channel.channel import get_channel_videos
from app.crawlers.youtube.channel_info.channel_info import get_channel_info
from app.crawlers.youtube.client import resolve_channel_id_from_handle
from app.crawlers.youtube.comment.comment import get_video_comments, get_video_comments_batch
from app.crawlers.youtube.detail.detail import get_video_detail
from app.crawlers.youtube.live.live import get_all_live_videos
from app.crawlers.youtube.location.location import get_videos_by_region
from app.crawlers.youtube.playlist.playlist import get_playlist_videos, get_videos_from_playlist
from app.crawlers.youtube.search.search import search_youtube
from app.crawlers.youtube.shorts.shorts import get_shorts_feed
from app.crawlers.youtube.config import CHANNEL_TOPICS, SEARCH_TOPICS
from app.crawlers.youtube.transcript.transcript import get_transcript, get_transcript_batch
from app.services.tiktok import search_videos as tiktok_search_videos
from app.services.youtube import get_videos_by_topic
from app.tools.registry import AgentToolSpec, register
from app.tools.schemas import TIKTOK_TOOL_SPECS, YOUTUBE_TOOL_SPECS

logger = Logger.get(__name__)


def _parse_video_ids(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [v.strip() for v in raw.split(",") if v.strip()]
    return [str(v).strip() for v in raw if str(v).strip()]


# ── YouTube handlers ──────────────────────────────────────────────────────────


async def _youtube_search_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    results = await search_youtube(
        inp["keyword"],
        max_results=inp.get("max_results", 5),
        sort=inp.get("sort", "relevance"),
        proxy=proxy,
    )
    return {"results": results}


async def _youtube_get_by_topic_handler(inp: dict) -> Any:
    topic = inp["topic"].lower()
    if topic not in CHANNEL_TOPICS and topic not in SEARCH_TOPICS:
        raise ValueError(f"Unknown topic '{topic}'")
    return await get_videos_by_topic(topic, limit=inp.get("max_results", 20))


async def _youtube_get_shorts_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    limit = inp.get("max_results", 20)
    videos = await get_shorts_feed(proxy=proxy, max_results=limit)
    return {"total": len(videos), "videos": videos}


async def _youtube_get_live_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    limit = inp.get("max_results", 20)
    videos = await get_all_live_videos(q=inp.get("query", ""), proxy=proxy, max_results=limit)
    return {"total": len(videos), "videos": videos}


async def _youtube_get_by_region_handler(inp: dict) -> Any:
    gl = inp["gl"]
    country = "US" if gl.upper() == "US" else "VN"
    proxy = await get_proxy(country)
    videos = await get_videos_by_region(
        gl=gl,
        hl=inp.get("hl", "vi"),
        query=inp["query"],
        proxy=proxy,
        max_results=inp.get("max_results", 20),
    )
    return {"gl": gl, "query": inp["query"], "total": len(videos), "videos": videos}


async def _youtube_get_detail_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    detail = await get_video_detail(inp["video_id"], proxy=proxy)
    return {"detail": detail}


async def _youtube_get_comments_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    sort = inp.get("sort", "top")
    if sort not in ("top", "newest"):
        sort = "top"
    comments = await get_video_comments(
        inp["video_id"],
        proxy=proxy,
        max_comments=inp.get("max_comments", 20),
        sort=sort,
    )
    return {"video_id": inp["video_id"], "total": len(comments), "comments": comments}


async def _youtube_get_comments_batch_handler(inp: dict) -> Any:
    ids = _parse_video_ids(inp.get("video_ids", []))[:8]
    sort = inp.get("sort", "top")
    if sort not in ("top", "newest"):
        sort = "top"
    proxy = await get_proxy()
    return await get_video_comments_batch(
        ids,
        proxy=proxy,
        max_per_video=inp.get("max_per_video", 20),
        sort=sort,
    )


async def _youtube_get_transcript_handler(inp: dict) -> Any:
    result = await get_transcript(inp["video_id"])
    if result is None:
        return {"video_id": inp["video_id"], "available": False, "text": None}
    return {**result, "available": True}


async def _youtube_get_transcript_batch_handler(inp: dict) -> Any:
    ids = _parse_video_ids(inp.get("video_ids", []))[:8]
    results = await get_transcript_batch(ids)
    return {
        "requested": len(ids),
        "available": sum(1 for v in results.values() if v),
        "results": results,
    }


async def _youtube_get_channel_info_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    info = await get_channel_info(inp["channel_id"], proxy=proxy)
    return {"info": info}


async def _youtube_get_channel_videos_handler(inp: dict) -> Any:
    channel_id = inp["channel_id"]
    resolved = (
        await resolve_channel_id_from_handle(channel_id.lstrip("@"))
        if channel_id.startswith("@")
        else channel_id
    )
    proxy = await get_proxy()
    videos = await get_channel_videos(channel_id=resolved, max_results=inp.get("max_results", 30), proxy=proxy)
    return {"channel_id": resolved, "total": len(videos), "videos": videos}


async def _youtube_get_channel_playlists_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    playlists = await get_playlist_videos(inp["channel_id"], proxy=proxy)
    return {"channel_id": inp["channel_id"], "total": len(playlists), "playlists": playlists}


async def _youtube_get_playlist_videos_handler(inp: dict) -> Any:
    proxy = await get_proxy()
    videos = await get_videos_from_playlist(inp["playlist_id"], proxy=proxy)
    limit = inp.get("max_results", 30)
    return {"playlist_id": inp["playlist_id"], "total": len(videos), "videos": videos[:limit]}


# ── TikTok handlers ───────────────────────────────────────────────────────────


async def _tiktok_search_handler(inp: dict) -> Any:
    return await tiktok_search_videos(
        inp["keyword"],
        cursor=inp.get("cursor", 0),
        region=inp.get("region") or "VN",
        sort_by=inp.get("sort_by"),
    )


async def _tiktok_video_info_handler(inp: dict) -> Any:
    import app.crawlers.tiktok.tikhub as tikhub

    return await tikhub.get_video_info(url=inp["url"])


async def _tiktok_comments_handler(inp: dict) -> Any:
    import app.crawlers.tiktok.tikhub as tikhub

    raw = await tikhub.get_comments(
        aweme_id=inp["aweme_id"],
        cursor=inp.get("cursor", 0),
        count=inp.get("count", 20),
    )
    data = raw.get("data") or {}
    return {
        "aweme_id": inp["aweme_id"],
        "comments": tikhub.format_comments(raw),
        "has_more": data.get("has_more", False),
        "cursor": data.get("cursor", 0),
    }


async def _tiktok_profile_handler(inp: dict) -> Any:
    import app.crawlers.tiktok.tikhub as tikhub

    return await tikhub.get_profile(unique_id=inp["handle"])


async def _tiktok_transcript_handler(inp: dict) -> Any:
    import app.crawlers.tiktok.tikhub as tikhub

    raw = await tikhub.get_transcript(aweme_id=inp["aweme_id"])
    fmt = tikhub.format_transcript(raw)
    if fmt is None:
        return {"aweme_id": inp["aweme_id"], "available": False, "text": None}
    return fmt


# ── Handler map + registration ────────────────────────────────────────────────

_HANDLERS: dict[str, Any] = {
    "youtube_search": _youtube_search_handler,
    "youtube_get_by_topic": _youtube_get_by_topic_handler,
    "youtube_get_shorts": _youtube_get_shorts_handler,
    "youtube_get_live": _youtube_get_live_handler,
    "youtube_get_by_region": _youtube_get_by_region_handler,
    "youtube_get_detail": _youtube_get_detail_handler,
    "youtube_get_comments": _youtube_get_comments_handler,
    "youtube_get_comments_batch": _youtube_get_comments_batch_handler,
    "youtube_get_transcript": _youtube_get_transcript_handler,
    "youtube_get_transcript_batch": _youtube_get_transcript_batch_handler,
    "youtube_get_channel_info": _youtube_get_channel_info_handler,
    "youtube_get_channel_videos": _youtube_get_channel_videos_handler,
    "youtube_get_channel_playlists": _youtube_get_channel_playlists_handler,
    "youtube_get_playlist_videos": _youtube_get_playlist_videos_handler,
    "tiktok_search": _tiktok_search_handler,
    "tiktok_video_info": _tiktok_video_info_handler,
    "tiktok_comments": _tiktok_comments_handler,
    "tiktok_profile": _tiktok_profile_handler,
    "tiktok_transcript": _tiktok_transcript_handler,
}

_PLATFORM_PREFIX = {
    "youtube_": "youtube",
    "tiktok_": "tiktok",
}


def _platform_for(name: str) -> str:
    for prefix, platform in _PLATFORM_PREFIX.items():
        if name.startswith(prefix):
            return platform
    raise ValueError(f"Cannot infer platform for tool: {name}")


def _register_all() -> None:
    for spec in (*YOUTUBE_TOOL_SPECS, *TIKTOK_TOOL_SPECS):
        name = spec["name"]
        handler = _HANDLERS.get(name)
        if handler is None:
            raise RuntimeError(f"Missing handler for tool: {name}")
        register(
            AgentToolSpec(
                name=name,
                description=spec["description"],
                platform=_platform_for(name),  # type: ignore[arg-type]
                parameters=spec["parameters"],
                handler=handler,
            )
        )


_register_all()
