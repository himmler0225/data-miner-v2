# HTTP errors are caught and logged but never raised — crawl continues even if ingest fails.
import os
import httpx
from typing import Dict, List, Optional
from app.config.logging_config import get_logger
from app.types import ChannelInfo, SearchVideo, Comment

logger = get_logger(__name__)

INGEST_API_URL = os.getenv("INGEST_API_URL", "http://localhost:3000")
INGEST_SERVICE_KEY = os.getenv("INGEST_SERVICE_KEY", "")

_HEADERS = {
    "X-Service-Key": INGEST_SERVICE_KEY,
    "Content-Type": "application/json",
}


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=INGEST_API_URL, headers=_HEADERS, timeout=30)


def _safe_int(value) -> Optional[int]:
    """Parse int from possibly comma-formatted strings like '1,234,567'."""
    if value is None:
        return None
    cleaned = "".join(c for c in str(value) if c.isdigit())
    return int(cleaned) if cleaned else None


async def ingest_channel(data: ChannelInfo) -> bool:
    payload = {
        "channelId": data.get("channel_id"),
        "channelName": data.get("channel_name"),
        "handle": data.get("handle") or None,
        "avatar": data.get("avatar") or None,
        "banner": data.get("banner") or None,
        "subscriberCount": data.get("subscriber_count") or None,
        "description": data.get("description") or None,
    }
    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/channel", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_channel failed: {e!r}")
            return False


async def ingest_search(
    query: str,
    videos: List[SearchVideo],
    sort: str = "relevance",
) -> bool:
    normalized = []
    for v in videos:
        video_id = v.get("video_id")
        if not video_id:
            continue
        normalized.append({
            "videoId": video_id,
            "title": v.get("title") or None,
            "channelId": v.get("channel_id") or None,
            "channel": v.get("channel") or None,
            "viewCount": v.get("view_count"),  # keep 0, don't coerce to None
            "duration": v.get("duration") or None,
            "publishedTime": v.get("published_time") or None,
            "thumbnails": v.get("thumbnails") or None,
        })
    if not normalized:
        return True
    payload = {"query": query, "sort": sort, "videos": normalized}

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/search", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_search failed (query='{query}'): {e!r}")
            return False


async def ingest_detail(
    video_id: str,
    detail: dict,
) -> bool:
    # detail has two shapes: error=True with reason, or full video fields.
    if detail.get("error"):
        payload = {
            "videoId": video_id,
            "error": True,
            "reason": detail.get("reason"),
        }
    else:
        payload = {
            "videoId": video_id,
            "title": detail.get("title"),
            "author": detail.get("author"),
            "channelId": detail.get("channel_id") or None,
            "views": _safe_int(detail.get("views")),
            "lengthSeconds": _safe_int(detail.get("length_seconds")),
            "isLiveContent": detail.get("is_live_content", False),
            "description": detail.get("description") or None,
            "thumbnails": detail.get("thumbnails") or None,
        }

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/detail", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_detail failed (video_id={video_id}): {e!r}")
            return False


async def ingest_trending(
    videos: List[Dict],
    category: Optional[str] = None,
) -> bool:
    normalized = []
    for v in videos:
        video_id = v.get("video_id")
        if not video_id:
            continue
        normalized.append({
            "videoId": video_id,
            "rank": v.get("rank"),
            "title": v.get("title") or None,
            "channelId": v.get("channel_id") or None,
            "channel": v.get("channel") or None,
            "viewCount": v.get("view_count"),  # keep 0, don't coerce to None
            "duration": v.get("duration") or None,
            "publishedTime": v.get("published_time") or None,
            "thumbnails": v.get("thumbnails") or None,
        })
    if not normalized:
        return True
    payload: Dict = {"videos": normalized}
    if category:
        payload["category"] = category

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/trending", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_trending failed (category={category!r}): {e!r}")
            return False


async def ingest_shorts(videos: List[Dict]) -> bool:
    normalized = []
    for v in videos:
        video_id = v.get("video_id")
        if not video_id:
            continue
        raw_dur = v.get("duration")
        try:
            duration = int(raw_dur) if raw_dur is not None and raw_dur != "" else None
        except (ValueError, TypeError):
            duration = None
        normalized.append({
            "videoId": video_id,
            "title": v.get("title") or None,
            "url": v.get("url") or f"https://www.youtube.com/shorts/{video_id}",
            "channelId": v.get("channel_id") or None,
            "channelName": v.get("channel_name") or None,
            "viewCount": v.get("view_count"),  # keep 0, don't coerce to None
            "duration": duration,
            "thumbnails": v.get("thumbnails") or None,
        })

    if not normalized:
        return True

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/shorts", json={"videos": normalized})
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_shorts failed: {e!r}")
            return False


async def ingest_channel_videos(
    channel_id: str,
    videos: List[Dict],
    channel_name: Optional[str] = None,
) -> bool:
    normalized = []
    for v in videos:
        # channel.py returns "videoId" (camelCase); normalise to snake_case
        video_id = v.get("videoId") or v.get("video_id")
        if not video_id:
            continue
        thumbnails = v.get("thumbnail") or v.get("thumbnails") or None
        if isinstance(thumbnails, dict):
            thumbnails = [thumbnails]
        normalized.append({
            "videoId": video_id,
            "title": v.get("title") or None,
            "viewCount": _safe_int(v.get("views") if v.get("views") is not None else v.get("view_count")),
            "duration": v.get("duration") or None,
            "publishedTime": v.get("public") or v.get("published_time") or None,
            "thumbnails": thumbnails,
        })

    if not normalized:
        return True

    payload: Dict = {"channelId": channel_id, "videos": normalized}
    if channel_name:
        payload["channelName"] = channel_name

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/channel-videos", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_channel_videos failed (channel_id={channel_id}): {e!r}")
            return False


async def ingest_playlists(
    channel_id: str,
    playlists: List[Dict],
) -> bool:
    normalized = []
    for p in playlists:
        playlist_id = p.get("playlistId") or p.get("playlist_id")
        if not playlist_id:
            continue
        normalized.append({
            "playlistId": playlist_id,
            "title": p.get("title") or "",
            "thumbnail": p.get("thumbnail") or None,
            "videoCount": _safe_int(p.get("videoCount") or p.get("video_count")),
        })

    if not normalized:
        return True

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/playlists", json={
                "channelId": channel_id,
                "playlists": normalized,
            })
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_playlists failed (channel_id={channel_id}): {e!r}")
            return False


async def ingest_playlist_items(
    playlist_id: str,
    videos: List[Dict],
) -> bool:
    normalized = []
    for i, v in enumerate(videos):
        video_id = v.get("video_id") or v.get("videoId")
        if not video_id:
            continue
        normalized.append({
            "videoId": video_id,
            "title": v.get("title") or "",
            "position": i,
            "durationText": v.get("duration") or v.get("duration_text"),
            "publishedTimeText": v.get("published_time") or v.get("published_time_text"),
            "thumbnail": v.get("thumbnail"),
        })

    if not normalized:
        return True

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/playlist-items", json={
                "playlistId": playlist_id,
                "videos": normalized,
            })
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_playlist_items failed (playlist_id={playlist_id}): {e!r}")
            return False


async def ingest_comments(
    video_id: str,
    comments: List[Comment],
) -> bool:
    normalized = []
    for c in comments:
        replies = [
            {
                "commentId": r.get("comment_id"),
                "author": r.get("author"),
                "avatar": r.get("avatar") or None,
                "content": r.get("content"),
                "likes": r.get("likes"),
                "publishedTime": r.get("published_time") or None,
            }
            for r in (c.get("replies") or [])
        ]
        normalized.append({
            "commentId": c.get("comment_id"),
            "author": c.get("author"),
            "avatar": c.get("avatar") or None,
            "content": c.get("content"),
            "likes": c.get("likes"),
            "repliesCount": c.get("replies_count"),
            "publishedTime": c.get("published_time") or None,
            "replies": replies,
        })

    payload = {"videoId": video_id, "comments": normalized}

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/comments", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(
                f"ingest_comments failed (video_id={video_id}, "
                f"count={len(comments)}): {e!r}"
            )
            return False
