from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from app.middleware import verify_api_key, limiter
from app.api.rate_limit_config import get_rate_limit
from app.crawlers.tiktok.native import search_native, trending_native
from app.crawlers.tiktok import tikhub, cache as search_cache
from app.config.logger import Logger
from app.schemas.response import ApiResponse
from app.exceptions import NativeSearchError, TikHubError

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)


@router.get("/search", summary="TikTok Search (cache → native → TikHub)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_search(
    request: Request,
    response: Response,
    q: str = Query(..., description="Từ khóa tìm kiếm"),
    count: int = Query(20, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    region: str = Query("VN"),
    language: str = Query("vi"),
    sort_by: str = Query(None, enum=["most-liked", "most-viewed", "most-recent", "most-relevant"]),
):
    cache_key = (q.lower().strip(), count, cursor, region, sort_by)

    cached = search_cache.get(cache_key)
    if cached is not None:
        logger.info("⚡ [search] cache hit q=%r", q)
        return ApiResponse.ok(cached)

    # 1. Native (free, reverse-engineered)
    try:
        result = await search_native(keyword=q, count=count, cursor=cursor, region=region, language=language)
        if result.get("videos"):
            search_cache.put(cache_key, result)
            return ApiResponse.ok(result)
        logger.warning("🟡 [search] native empty → TikHub fallback")
    except NativeSearchError as e:
        logger.warning("🔴 [search] native pool exhausted → TikHub fallback: %s", e)
    except Exception as e:
        logger.warning("🔴 [search] native failed (%s) → TikHub fallback", e)

    # 2. TikHub fallback (paid, $0.001/call)
    try:
        sort_type = 1 if sort_by == "most-liked" else 0
        raw = await tikhub.search_videos(keyword=q, cursor=cursor, count=count, sort_type=sort_type)
        formatted = tikhub.format_search(raw)
        if formatted.get("videos"):
            search_cache.put(cache_key, formatted)
        return ApiResponse.ok(formatted)
    except TikHubError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending", summary="TikTok Trending (native)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_trending(
    request: Request,
    response: Response,
    count: int = Query(20, ge=1, le=50),
    region: str = Query("VN"),
    language: str = Query("vi"),
):
    try:
        return ApiResponse.ok(await trending_native(count=count, region=region, language=language))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video-info", summary="TikTok Video Info (TikHub)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_video_info(
    request: Request,
    response: Response,
    url: str = Query(..., description="TikTok video URL"),
):
    try:
        raw = await tikhub.get_video_info(url=url)
        return ApiResponse.ok(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comments", summary="TikTok Comments (TikHub)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_comments(
    request: Request,
    response: Response,
    aweme_id: str = Query(..., description="TikTok video ID (aweme_id)"),
    cursor: int = Query(0, ge=0),
    count: int = Query(20, ge=1, le=50),
):
    try:
        raw = await tikhub.get_comments(aweme_id=aweme_id, cursor=cursor, count=count)
        return ApiResponse.ok({
            "aweme_id": aweme_id,
            "comments": tikhub.format_comments(raw),
            "has_more": (raw.get("data") or {}).get("has_more", False),
            "cursor":   (raw.get("data") or {}).get("cursor", 0),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles/{handle}", summary="TikTok Profile (TikHub)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_profile(
    request: Request,
    response: Response,
    handle: str,
):
    try:
        return ApiResponse.ok(await tikhub.get_profile(unique_id=handle))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcript", summary="TikTok Video Transcript (TikHub)")
@limiter.limit(get_rate_limit("tiktok"))
async def tiktok_transcript(
    request: Request,
    response: Response,
    aweme_id: str = Query(..., description="TikTok video ID"),
):
    try:
        raw = await tikhub.get_transcript(aweme_id=aweme_id)
        fmt = tikhub.format_transcript(raw)
        if fmt is None:
            return ApiResponse.ok({"aweme_id": aweme_id, "available": False, "text": None})
        return ApiResponse.ok(fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
