"""YouTube REST routes: thin wrappers over app.services.youtube.

List routes take `limit` + `cursor` and return
`{"items", "next_cursor", "has_more", ...}`; pass `next_cursor` back as
`cursor` for the next page. Errors: 400 bad input, 404 not found,
502/503 upstream failures (see app/api/errors.py).
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.errors import api_ok
from app.api.rate_limit_config import endpoint_limit
from app.crawlers.youtube.config import DEFAULT_PAGE_LIMIT, MAX_BATCH_IDS, MAX_PAGE_LIMIT
from app.middleware.auth_middleware import verify_api_key
from app.middleware.rate_limit import limiter
from app.services import youtube as yt

router = APIRouter(dependencies=[Depends(verify_api_key)])

Limit = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT, description="Items per page")
Cursor = Query(None, description="`next_cursor` from the previous page")
VideoIds = Query(..., description=f"Comma-separated video ids (max {MAX_BATCH_IDS})")
SearchSort = Literal["relevance", "upload_date", "view_count", "rating"]
CommentSort = Literal["top", "newest"]


# ── videos ────────────────────────────────────────────────────────────────────


@router.get("/videos/search", summary="Search Videos")
@limiter.limit(endpoint_limit("search"))
async def search_videos(
    request: Request,
    response: Response,
    q: str,
    sort: SearchSort = "relevance",
    limit: int = Limit,
    cursor: str | None = Cursor,
):
    return await api_ok(yt.search_videos(q, sort=sort, limit=limit, cursor=cursor))


@router.get("/videos/by-topic", summary="Videos by Topic")
@limiter.limit(endpoint_limit("topic"))
async def videos_by_topic(
    request: Request,
    response: Response,
    topic: str = Query(..., description=f"One of: {', '.join(yt.TOPICS)}"),
    limit: int = Limit,
    cursor: str | None = Cursor,
):
    return await api_ok(yt.topic_videos(topic, limit=limit, cursor=cursor))


@router.get("/videos/live", summary="Live Videos")
@limiter.limit(endpoint_limit("live"))
async def live_videos(
    request: Request, response: Response, q: str = "", limit: int = Limit, cursor: str | None = Cursor
):
    return await api_ok(yt.live_videos(q, limit=limit, cursor=cursor))


@router.get("/videos/location", summary="Videos by Region")
@limiter.limit(endpoint_limit("location"))
async def region_videos(
    request: Request,
    response: Response,
    q: str,
    gl: str = Query(..., description="Country code (VN, US, JP...)"),
    hl: str = Query("vi", description="Language code (vi, en, ja...)"),
    limit: int = Limit,
    cursor: str | None = Cursor,
):
    return await api_ok(yt.region_videos(q, gl=gl, hl=hl, limit=limit, cursor=cursor))


@router.get("/videos/shorts", summary="Shorts Feed")
@limiter.limit(endpoint_limit("shorts"))
async def shorts_feed(request: Request, response: Response, limit: int = Limit):
    return await api_ok(yt.shorts_feed(limit=limit))


@router.get("/videos/comments/batch", summary="Comments for multiple videos")
@limiter.limit(endpoint_limit("comments"))
async def comments_batch(
    request: Request, response: Response, video_ids: str = VideoIds, sort: CommentSort = "top", limit: int = Limit
):
    return await api_ok(yt.comments_batch(video_ids, sort=sort, limit=limit))


@router.get("/videos/transcript/batch", summary="Transcripts for multiple videos")
@limiter.limit(endpoint_limit("transcript"))
async def transcript_batch(request: Request, response: Response, video_ids: str = VideoIds):
    return await api_ok(yt.transcript_batch(video_ids))


@router.get("/videos/{video_id}", summary="Video Detail")
@limiter.limit(endpoint_limit("video_detail"))
async def video_detail(request: Request, response: Response, video_id: str):
    return await api_ok(yt.video_detail(video_id))


@router.get("/videos/{video_id}/comments", summary="Video Comments")
@limiter.limit(endpoint_limit("comments"))
async def video_comments(
    request: Request,
    response: Response,
    video_id: str,
    sort: CommentSort = "top",
    limit: int = Limit,
    cursor: str | None = Cursor,
):
    return await api_ok(yt.video_comments(video_id, sort=sort, limit=limit, cursor=cursor))


@router.get("/videos/{video_id}/transcript", summary="Video Transcript")
@limiter.limit(endpoint_limit("transcript"))
async def video_transcript(request: Request, response: Response, video_id: str):
    return await api_ok(yt.video_transcript(video_id))


# ── channels / playlists ──────────────────────────────────────────────────────
# `channel_id` accepts a channel id (UC...) or an @handle.


@router.get("/channels/{channel_id}", summary="Channel Info")
@limiter.limit(endpoint_limit("channel_info"))
async def channel_info(request: Request, response: Response, channel_id: str):
    return await api_ok(yt.channel_info(channel_id))


@router.get("/channels/{channel_id}/videos", summary="Channel Videos")
@limiter.limit(endpoint_limit("channel_videos"))
async def channel_videos(
    request: Request, response: Response, channel_id: str, limit: int = Limit, cursor: str | None = Cursor
):
    return await api_ok(yt.channel_videos(channel_id, limit=limit, cursor=cursor))


@router.get("/channels/{channel_id}/playlists", summary="Channel Playlists")
@limiter.limit(endpoint_limit("playlist"))
async def channel_playlists(
    request: Request, response: Response, channel_id: str, limit: int = Limit, cursor: str | None = Cursor
):
    return await api_ok(yt.channel_playlists(channel_id, limit=limit, cursor=cursor))


@router.get("/playlists/{playlist_id}/videos", summary="Playlist Videos")
@limiter.limit(endpoint_limit("playlist"))
async def playlist_videos(
    request: Request, response: Response, playlist_id: str, limit: int = Limit, cursor: str | None = Cursor
):
    return await api_ok(yt.playlist_videos(playlist_id, limit=limit, cursor=cursor))
