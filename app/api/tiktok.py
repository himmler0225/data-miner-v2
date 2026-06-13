from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from app.middleware import verify_api_key, limiter
from app.crawlers.tiktok.native import search_native, trending_native
from app.crawlers.tiktok.sociavault import get_video_info, get_comments, get_profile
from app.config.logger import Logger
from app.schemas.response import ApiResponse
from app.crawlers.tiktok import cache as search_cache

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)

@router.get("/search", summary="TikTok Search (cache → native)")
@limiter.limit("15/minute")
async def tiktok_search(
    request: Request,
    response: Response,
    q: str = Query(..., description="Từ khóa tìm kiếm"),
    count: int = Query(20, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    region: str = Query("VN"),
    language: str = Query("vi"),
):
    cache_key = (q.lower().strip(), count, cursor, region)

    # Cache — repeated keywords return instantly.
    cached = search_cache.get(cache_key)
    if cached is not None:
        logger.info("[search] cache hit q=%r", q)
        return ApiResponse.ok(cached)

    try:
        result = await search_native(keyword=q, count=count, cursor=cursor, region=region, language=language)
    except Exception as e:
        logger.warning("[search] native failed: %s", e)
        result = {"success": False, "count": 0, "videos": []}

    if result.get("videos"):
        search_cache.put(cache_key, result)
    return ApiResponse.ok(result)

@router.get("/trending", summary="TikTok Trending (native)")
@limiter.limit("15/minute")
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

@router.get("/video-info", summary="TikTok Video Info (SociaVault)")
@limiter.limit("15/minute")
async def tiktok_video_info(
    request: Request,
    response: Response,
    url: str = Query(..., description="TikTok video URL"),
    get_transcript: bool = Query(False),
    region: str = Query(None),
):
    try:
        return ApiResponse.ok(await get_video_info(url=url, get_transcript=get_transcript, region=region))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comments", summary="TikTok Comments (SociaVault)")
@limiter.limit("15/minute")
async def tiktok_comments(
    request: Request,
    response: Response,
    url: str = Query(..., description="TikTok video URL"),
    cursor: int = Query(0, ge=0),
):
    try:
        return ApiResponse.ok(await get_comments(url=url, cursor=cursor))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profiles/{handle}", summary="TikTok Profile (SociaVault)")
@limiter.limit("15/minute")
async def tiktok_profile(
    request: Request,
    response: Response,
    handle: str,
):
    try:
        return ApiResponse.ok(await get_profile(handle=handle))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
