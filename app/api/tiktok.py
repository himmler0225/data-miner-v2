from fastapi import APIRouter, Depends, Query, Request, Response

import app.crawlers.tiktok.tikhub as tikhub
from app.api.errors import api_ok
from app.api.rate_limit_config import endpoint_limit
from app.crawlers.tiktok.config import DEFAULT_LANGUAGE, DEFAULT_REGION
from app.crawlers.tiktok.native import trending_native
from app.middleware.auth_middleware import verify_api_key
from app.middleware.rate_limit import limiter
from app.services.tiktok import search_videos

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/search", summary="TikTok Search (cache -> native -> TikHub)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_search(
    request: Request,
    response: Response,
    q: str = Query(..., description="Search keyword"),
    count: int = Query(20, ge=1, le=100),
    cursor: int = Query(0, ge=0),
    region: str = Query(DEFAULT_REGION),
    language: str = Query(DEFAULT_LANGUAGE),
    sort_by: str = Query(None, enum=["most-liked", "most-viewed", "most-recent", "most-relevant"]),
):
    return await api_ok(
        search_videos(q, count=count, cursor=cursor, region=region, language=language, sort_by=sort_by)
    )


@router.get("/trending", summary="TikTok Trending (native)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_trending(
    request: Request,
    response: Response,
    count: int = Query(20, ge=1, le=50),
    region: str = Query(DEFAULT_REGION),
    language: str = Query(DEFAULT_LANGUAGE),
):
    return await api_ok(trending_native(count=count, region=region, language=language))


@router.get("/video-info", summary="TikTok Video Info (TikHub)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_video_info(
    request: Request,
    response: Response,
    url: str = Query(..., description="TikTok video URL"),
):
    return await api_ok(tikhub.get_video_info(url=url))


@router.get("/comments", summary="TikTok Comments (TikHub)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_comments(
    request: Request,
    response: Response,
    aweme_id: str = Query(..., description="TikTok video ID (aweme_id)"),
    cursor: int = Query(0, ge=0),
    count: int = Query(20, ge=1, le=50),
):
    async def _():
        raw = await tikhub.get_comments(aweme_id=aweme_id, cursor=cursor, count=count)
        data = raw.get("data") or {}
        return {
            "aweme_id": aweme_id,
            "comments": tikhub.format_comments(raw),
            "has_more": data.get("has_more", False),
            "cursor": data.get("cursor", 0),
        }

    return await api_ok(_())


@router.get("/profiles/{handle}", summary="TikTok Profile (TikHub)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_profile(
    request: Request,
    response: Response,
    handle: str,
):
    return await api_ok(tikhub.get_profile(unique_id=handle))


@router.get("/transcript", summary="TikTok Video Transcript (TikHub)")
@limiter.limit(endpoint_limit("tiktok"))
async def tiktok_transcript(
    request: Request,
    response: Response,
    aweme_id: str = Query(..., description="TikTok video ID"),
):
    async def _():
        raw = await tikhub.get_transcript(aweme_id=aweme_id)
        fmt = tikhub.format_transcript(raw)
        if fmt is None:
            return {"aweme_id": aweme_id, "available": False, "text": None}
        return fmt

    return await api_ok(_())
