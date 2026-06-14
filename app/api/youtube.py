from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response
from app.crawlers.youtube.search import search_youtube
from app.crawlers.youtube.topic import browse_topic_channel
from app.crawlers.youtube.detail import get_video_detail
from app.crawlers.youtube.channel import get_channel_videos
from app.crawlers.youtube.channel_info import get_channel_info
from app.crawlers.youtube.playlist import get_playlist_videos, get_videos_from_playlist
from app.crawlers.youtube.comment import get_video_comments, get_video_comments_batch
from app.crawlers.youtube.transcript import get_transcript, get_transcript_batch
from app.crawlers.youtube.live import get_all_live_videos
from app.crawlers.youtube.shorts import get_shorts_feed
from app.crawlers.youtube.location import get_videos_by_region
from app.utils import resolve_channel_id_from_handle, retry_on_failure
from app.middleware import verify_api_key, limiter
from app.config.logger import Logger
from app.config.urls import proxy_manager, proxy_manager_us
from app.config.settings import PROXY_US
from app.schemas.response import ApiResponse

from dotenv import load_dotenv
load_dotenv()

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)

_CHANNEL_TOPICS = {
    "music": "UC-9-kyTW8ZkZNDHQJ6FgpwQ",
}
_SEARCH_TOPICS = {
    "gaming":  ("gaming highlights",        "view_count"),
    "news":    ("tin tức việt nam hôm nay", "upload_date"),
    "sports":  ("thể thao việt nam",        "view_count"),
    "tech":    ("review công nghệ",         "view_count"),
    "beauty":  ("beauty skincare review",   "view_count"),
    "food":    ("ẩm thực việt nam",         "view_count"),
    "travel":  ("du lịch việt nam",         "view_count"),
}
_ALL_TOPICS = list(_CHANNEL_TOPICS.keys()) + list(_SEARCH_TOPICS.keys())

@router.get("/videos/by-topic", summary="Videos by Topic")
async def videos_by_topic(
    topic: str = Query(..., description=f"Topic: {', '.join(_ALL_TOPICS)}"),
    limit: int = Query(20, ge=1, le=50),
    page: int = Query(1, ge=1),
):
    t = topic.lower()
    if t not in _CHANNEL_TOPICS and t not in _SEARCH_TOPICS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown topic '{topic}'. Available: {', '.join(_ALL_TOPICS)}",
        )

    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        start = (page - 1) * limit
        if t in _CHANNEL_TOPICS:
            result = await browse_topic_channel(_CHANNEL_TOPICS[t], max_videos=start + limit, proxy=proxy)
            videos = result["videos"][start:]
            return {
                "topic": topic, "source": "channel_browse",
                "playlists": result.get("playlists", []),
                "featured": result.get("featured_playlist"),
                "total": len(videos), "videos": videos,
            }
        query, sort = _SEARCH_TOPICS[t]
        results = await search_youtube(query, max_results=start + limit, sort=sort, proxy=proxy)
        return {
            "topic": topic, "source": "search", "query": query,
            "page": page, "total": len(results), "videos": results[start:start + limit],
        }

    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/search", summary="Search Videos")
@limiter.limit("30/minute")
async def search_videos(
    request: Request,
    response: Response,
    q: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
    sort: str = Query("relevance", enum=["relevance", "upload_date", "view_count", "rating"]),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        # Always fetch exactly `limit` results for page 1.
        # For deeper pages we must over-fetch (YouTube has no offset API),
        # but cap at 50 to avoid runaway requests.
        fetch_n = min(page * limit, 50)
        results = await search_youtube(q, max_results=fetch_n, sort=sort, proxy=proxy)
        start   = (page - 1) * limit
        return {"query": q, "page": page, "limit": limit, "total": len(results), "results": results[start:start + limit]}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/shorts", summary="Shorts Feed")
async def get_videos_shorts(limit: int = Query(30, ge=1, le=50)):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        videos = await get_shorts_feed(proxy=proxy, max_results=limit)
        return {"total": len(videos), "videos": videos}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/live", summary="Live Videos")
async def get_videos_live(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        videos = await get_all_live_videos(q=q, proxy=proxy, max_results=start + limit)
        return {"total": len(videos), "videos": videos}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/location", summary="Videos by Region")
async def get_videos_location(
    gl: str = Query(...),
    hl: str = Query("vi"),
    query: str = Query(...),
    max_results: int = Query(50, ge=1, le=100),
):
    try:
        # US-geo queries go through the US proxy; everything else via VN.
        mgr = proxy_manager_us if gl.upper() == "US" and PROXY_US else proxy_manager
        proxy = await mgr.get_proxy()
        videos = await get_videos_by_region(gl=gl, hl=hl, query=query, proxy=proxy, max_results=max_results)
        return ApiResponse.ok({"gl": gl, "query": query, "total": len(videos), "videos": videos})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}", summary="Video Detail")
async def video_detail(video_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        detail = await get_video_detail(video_id, proxy=proxy)
        return {"detail": detail}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}/comments", summary="Video Comments")
async def get_comments(
    video_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("top", enum=["top", "newest"]),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        comments = await get_video_comments(video_id, proxy=proxy, max_comments=start + limit, sort=sort)
        return {"video_id": video_id, "total": len(comments), "comments": comments[start:]}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/comments/batch", summary="Comments for multiple videos (parallel)")
async def get_comments_batch(
    video_ids: str = Query(..., description="Comma-separated video_ids (pick top N by view)"),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("top", enum=["top", "newest"]),
):
    ids = [v.strip() for v in video_ids.split(",") if v.strip()][:8]
    if not ids:
        raise HTTPException(status_code=400, detail="video_ids is empty")
    try:
        proxy = await proxy_manager.get_proxy()
        result = await get_video_comments_batch(ids, proxy=proxy, max_per_video=limit, sort=sort)
        return ApiResponse.ok(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/channels/{channel_id}", summary="Channel Info")
async def channel_info(channel_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        info = await get_channel_info(channel_id, proxy=proxy)
        return {"info": info}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/channels/{channel_id}/videos", summary="Channel Videos")
async def channel_videos(
    channel_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        resolved = await resolve_channel_id_from_handle(channel_id.lstrip("@")) if channel_id.startswith("@") else channel_id
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        videos = await get_channel_videos(channel_id=resolved, max_results=start + limit, proxy=proxy)
        return {"channel_id": resolved, "total": len(videos), "videos": videos}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/channels/{channel_id}/playlists", summary="Channel Playlists")
async def channel_playlists(channel_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        playlists = await get_playlist_videos(channel_id, proxy=proxy)
        return {"channel_id": channel_id, "total": len(playlists), "playlists": playlists}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlists/{playlist_id}/videos", summary="Playlist Videos")
async def playlist_videos(playlist_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        videos = await get_videos_from_playlist(playlist_id, proxy=proxy)
        return {"playlist_id": playlist_id, "total": len(videos), "videos": videos}
    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{video_id}/transcript", summary="Video Transcript")
async def video_transcript(video_id: str):
    try:
        result = await get_transcript(video_id)
        if result is None:
            return ApiResponse.ok({"video_id": video_id, "available": False, "text": None})
        return ApiResponse.ok({**result, "available": True})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/transcript/batch", summary="Transcripts for multiple videos")
async def transcript_batch(
    video_ids: str = Query(..., description="Comma-separated video_ids (max 8)"),
):
    ids = [v.strip() for v in video_ids.split(",") if v.strip()][:8]
    if not ids:
        raise HTTPException(status_code=400, detail="video_ids is empty")
    try:
        results = await get_transcript_batch(ids)
        return ApiResponse.ok({
            "requested": len(ids),
            "available": sum(1 for v in results.values() if v),
            "results":   results,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
