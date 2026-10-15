from typing import Any

from app.config.logger import Logger
from app.services import youtube as yt
from app.services.tiktok import search_videos as tiktok_search_videos
from app.tools.registry import AgentToolSpec, register
from app.tools.schemas import TIKTOK_TOOL_SPECS, YOUTUBE_TOOL_SPECS

logger = Logger.get(__name__)


# ── YouTube handlers ──────────────────────────────────────────────────────────
# Thin adapters from tool arguments to app.services.youtube (same code path as
# the REST API). Tool argument names are kept as the agent layer defines them.


async def _youtube_search_handler(inp: dict) -> Any:
    return await yt.search_videos(
        inp["keyword"], sort=inp.get("sort", "relevance"), limit=inp.get("max_results", 5), cursor=inp.get("cursor")
    )


async def _youtube_get_by_topic_handler(inp: dict) -> Any:
    return await yt.topic_videos(inp["topic"], limit=inp.get("max_results"), cursor=inp.get("cursor"))


async def _youtube_get_shorts_handler(inp: dict) -> Any:
    return await yt.shorts_feed(limit=inp.get("max_results"))


async def _youtube_get_live_handler(inp: dict) -> Any:
    return await yt.live_videos(inp.get("query", ""), limit=inp.get("max_results"), cursor=inp.get("cursor"))


async def _youtube_get_by_region_handler(inp: dict) -> Any:
    return await yt.region_videos(
        inp["query"], gl=inp["gl"], hl=inp.get("hl", "vi"), limit=inp.get("max_results"), cursor=inp.get("cursor")
    )


async def _youtube_get_detail_handler(inp: dict) -> Any:
    return await yt.video_detail(inp["video_id"])


async def _youtube_get_comments_handler(inp: dict) -> Any:
    return await yt.video_comments(
        inp["video_id"], sort=inp.get("sort", "top"), limit=inp.get("max_comments"), cursor=inp.get("cursor")
    )


async def _youtube_get_comments_batch_handler(inp: dict) -> Any:
    return await yt.comments_batch(inp["video_ids"], sort=inp.get("sort", "top"), limit=inp.get("max_per_video"))


async def _youtube_get_transcript_handler(inp: dict) -> Any:
    return await yt.video_transcript(inp["video_id"])


async def _youtube_get_transcript_batch_handler(inp: dict) -> Any:
    return await yt.transcript_batch(inp["video_ids"])


async def _youtube_get_channel_info_handler(inp: dict) -> Any:
    return await yt.channel_info(inp["channel_id"])


async def _youtube_get_channel_videos_handler(inp: dict) -> Any:
    return await yt.channel_videos(inp["channel_id"], limit=inp.get("max_results"), cursor=inp.get("cursor"))


async def _youtube_get_channel_playlists_handler(inp: dict) -> Any:
    return await yt.channel_playlists(inp["channel_id"], limit=inp.get("max_results"), cursor=inp.get("cursor"))


async def _youtube_get_playlist_videos_handler(inp: dict) -> Any:
    return await yt.playlist_videos(inp["playlist_id"], limit=inp.get("max_results"), cursor=inp.get("cursor"))


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
