import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends, Request, Response
from app.services.search import search_youtube
from app.services.trending import get_trending_videos
from app.services.detail import get_video_detail
from app.services.channel import get_channel_videos
from app.services.channel_info import get_channel_info
from app.services.playlist import get_playlist_videos, get_videos_from_playlist
from app.services.comment import get_video_comments
from app.services.live import get_all_live_videos
from app.services.shorts import get_shorts_feed
from app.services.location import get_videos_by_region
from app.utils import resolve_channel_id_from_handle
from app.middleware import verify_api_key, limiter
from app.config.logging_config import get_logger
from app.config.urls import proxy_manager

from dotenv import load_dotenv
from functools import wraps
from app.exceptions import YouTubeStructureChangedError

load_dotenv()
router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)

def retry_on_failure(max_retries=3, delay=1):
    """Retry decorator with linear backoff. Raises immediately on YouTubeStructureChangedError."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except YouTubeStructureChangedError as e:
                    logger.critical(
                        f"YouTube structure changed in {func.__name__}: {e}",
                        extra={"extra_data": {"context": e.context}}
                    )
                    raise HTTPException(status_code=502, detail=f"YouTube structure changed: {e}")
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}. "
                            f"Retrying in {wait_time}s... Error: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(f"All {max_retries} attempts failed for {func.__name__}", exc_info=True)
                    raise last_exception
        return wrapper
    return decorator

@router.get("/videos/trending", summary="Trending Videos")
async def trending_videos(
    limit: int = Query(50, ge=1, le=200),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        videos = await get_trending_videos(proxy=proxy, max_results=limit, skip_live=True)
        return {"total": len(videos), "videos": videos}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/videos/search", summary="Search Videos")
@limiter.limit("30/minute")
async def search_videos(
    request: Request,
    response: Response,
    q: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
    sort: str = Query("relevance", enum=["relevance", "upload_date", "view_count", "rating"]),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        results = await search_youtube(q, max_results=start + limit, sort=sort, proxy=proxy)
        return {"query": q, "page": page, "limit": limit, "total": len(results), "results": results[start:start + limit]}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/shorts", summary="Get Videos Shorts")
async def get_videos_shorts(
    limit: int = Query(30, ge=1, le=50),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        videos = await get_shorts_feed(proxy=proxy, max_results=limit)
        return {"total": len(videos), "videos": videos}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/live", summary="Get Videos Live")
async def get_videos_live(
    q: str = Query("", description="Search keyword (optional — omit for general live feed)"),
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
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/location", summary="Get Videos By Region")
async def get_videos_location(
    gl: str = Query(..., description="Country code (e.g. VN, JP, US)"),
    hl: str = Query("en", description="Language code (e.g. vi, ja, en)"),
    query: str = Query(..., description="Search query in local language"),
    max_results: int = Query(50, ge=1, le=100),
):
    try:
        proxy = await proxy_manager.get_proxy()
        videos = await get_videos_by_region(
            gl=gl, hl=hl, query=query, proxy=proxy, max_results=max_results,
        )
        return {"gl": gl, "query": query, "total": len(videos), "videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/{video_id}", summary="Video Detail")
async def video_detail(video_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        detail = await get_video_detail(video_id, proxy=proxy)
        return {"detail": detail}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/{video_id}/comments", summary="Get Comments")
async def get_comments(
    video_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        comments = await get_video_comments(video_id, proxy=proxy, max_comments=start + limit)
        return {"video_id": video_id, "total": len(comments), "comments": comments}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel/{channel_id}", summary="Channel Info")
async def channel_info(channel_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        info = await get_channel_info(channel_id, proxy=proxy)
        return {"info": info}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel/{channel_id}/videos", summary="Channel Videos")
async def channel_videos(
    channel_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        if channel_id.startswith("@"):
            resolved = await resolve_channel_id_from_handle(channel_id.lstrip("@"))
        else:
            resolved = channel_id
        start = (page - 1) * limit
        proxy = await proxy_manager.get_proxy()
        videos = await get_channel_videos(channel_id=resolved, max_results=start + limit, proxy=proxy)
        return {"channel_id": resolved, "total": len(videos), "videos": videos}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel/{channel_id}/playlists", summary="Channel Playlists")
async def channel_playlists(channel_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        playlists = await get_playlist_videos(channel_id, proxy=proxy)
        return {"channel_id": channel_id, "total": len(playlists), "playlists": playlists}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/playlist/{playlist_id}/videos", summary="Playlist Videos")
async def playlist_videos(playlist_id: str):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        videos = await get_videos_from_playlist(playlist_id, proxy=proxy)
        return {"playlist_id": playlist_id, "total": len(videos), "videos": videos}
    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))