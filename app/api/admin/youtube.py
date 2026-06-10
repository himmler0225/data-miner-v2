import json
from fastapi import APIRouter, Depends
from app.middleware import verify_api_key
from app.utils import get_youtube_api_key, get_context, create_httpx_client
from app.config import get_youtube_headers, get_youtube_api_url
from app.config.constants import ENDPOINT_SEARCH, SEARCH_FILTER_LOCATION
from app.config.urls import proxy_manager
from app.config.logger import Logger
from app.schemas.response import ApiResponse
from app.scheduler.jobs import (
    crawl_trending_videos,
    crawl_shorts_videos,
    crawl_location_videos,
    crawl_popular_keywords,
)
from ._tasks import _start_job

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)

@router.get("/debug/location")
async def debug_location(lat: float = 10.8231, lng: float = 106.6297):
    proxy = await proxy_manager.get_proxy()
    try:
        api_key = await get_youtube_api_key(proxy=proxy)
        search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
        headers = get_youtube_headers()
        payload = {
            "context": get_context(),
            "query": "*",
            "params": SEARCH_FILTER_LOCATION,
            "location": f"{lat},{lng}",
            "locationRadius": "50km",
        }
        async with create_httpx_client(proxy=proxy, headers=headers) as client:
            resp = await client.post(search_url, json=payload)
            data = resp.json()
        return ApiResponse.ok({
            "status_code": resp.status_code,
            "top_keys": list(data.keys()),
            "contents_keys": list(data.get("contents", {}).keys()),
            "raw_preview": json.dumps(data, ensure_ascii=False)[:5000],
        })
    except Exception as e:
        return ApiResponse.ok({"error": repr(e)})

@router.post("/jobs/trending")
async def trigger_trending():
    return _start_job("crawl_trending", crawl_trending_videos)

@router.post("/jobs/shorts")
async def trigger_shorts():
    return _start_job("crawl_shorts", crawl_shorts_videos)

@router.post("/jobs/location")
async def trigger_location():
    return _start_job("crawl_location", crawl_location_videos)

@router.post("/jobs/keywords")
async def trigger_keywords():
    return _start_job("crawl_keywords", crawl_popular_keywords)
