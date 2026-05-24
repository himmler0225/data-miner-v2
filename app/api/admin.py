import asyncio
import httpx
from fastapi import APIRouter, Depends
from app.middleware import verify_api_key
from app.utils import get_youtube_api_key, get_context, create_httpx_client
from app.config import get_youtube_headers, get_youtube_api_url
from app.config.constants import ENDPOINT_SEARCH, SEARCH_FILTER_LOCATION
from app.scheduler.jobs import (
    crawl_trending_videos,
    crawl_shorts_videos,
    crawl_location_videos,
    crawl_popular_keywords,
    cleanup_old_data,
    health_check_job,
    reset_circuit,
    get_failure_counts,
    MAX_CONSECUTIVE_FAILURES,
)
from app.config.urls import proxy_manager
from app.config.logging_config import get_logger

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)

_running_tasks: dict[str, asyncio.Task] = {}

async def _run_job(job_id: str, coro_func):
    try:
        logger.info(f"Job '{job_id}' started")
        result = await coro_func()
        logger.info(f"Job '{job_id}' completed: {result}")
        return result
    except asyncio.CancelledError:
        logger.warning(f"Job '{job_id}' was cancelled")
        raise
    except Exception as e:
        logger.error(f"Job '{job_id}' failed: {e}", exc_info=True)
        raise
    finally:
        _running_tasks.pop(job_id, None)

def _start_job(job_id: str, coro_func) -> dict:
    if job_id in _running_tasks and not _running_tasks[job_id].done():
        return {"status": "already_running", "job": job_id}
    task = asyncio.create_task(_run_job(job_id, coro_func))
    _running_tasks[job_id] = task
    return {"status": "started", "job": job_id}

@router.get("/proxy/debug")
async def proxy_debug():
    import os
    keys_raw = os.getenv("PROXY_KEYS", "")
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
    if not keys:
        return {"error": "PROXY_KEYS trống trong .env", "keys_raw": keys_raw}
    key = keys[0]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://proxyxoay.shop/api/get.php",
                params={"key": key, "nhamang": "Random", "tinhthanh": "0"},
            )
            return {"key": key[:8] + "...", "status_code": resp.status_code, "body": resp.text}
    except Exception as e:
        return {"error": repr(e)}

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
        import json
        return {
            "status_code": resp.status_code,
            "top_keys": list(data.keys()),
            "contents_keys": list(data.get("contents", {}).keys()),
            "raw_preview": json.dumps(data, ensure_ascii=False)[:5000],
        }
    except Exception as e:
        return {"error": repr(e)}

@router.get("/proxy/status")
async def proxy_status():
    return {"proxies": proxy_manager.status()}

@router.get("/proxy/test")
async def test_proxy():
    proxy_url = await proxy_manager.get_proxy()
    if not proxy_url:
        return {"status": "error", "detail": "Không lấy được proxy — kiểm tra PROXY_KEYS trong .env"}
    try:
        async with httpx.AsyncClient(proxies=proxy_url, timeout=10) as client:
            resp = await client.get("http://httpbin.org/ip")
            ip = resp.json().get("origin", "unknown")
        return {"status": "ok", "exit_ip": ip, "proxy": proxy_url}
    except Exception as e:
        return {"status": "error", "proxy": proxy_url, "error": repr(e)}

@router.get("/jobs")
async def list_jobs():
    from app.scheduler.scheduler import get_scheduler
    scheduler = get_scheduler()
    failures = get_failure_counts()
    jobs = []
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        failure_count = failures.get(job.id, 0)
        task = _running_tasks.get(job.id)
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "running": task is not None and not task.done(),
            "failure_count": failure_count,
            "circuit_open": failure_count >= MAX_CONSECUTIVE_FAILURES,
        })
    return {"jobs": jobs}

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

@router.post("/jobs/cleanup")
async def trigger_cleanup():
    return _start_job("cleanup_data", cleanup_old_data)

@router.post("/jobs/health")
async def trigger_health():
    result = await health_check_job()
    return {"status": "done", "result": result}

@router.post("/jobs/{job_id}/reset")
async def reset_job(job_id: str):
    """Cancel job đang chạy + reset circuit breaker."""
    task = _running_tasks.pop(job_id, None)
    cancelled = False
    if task and not task.done():
        task.cancel()
        cancelled = True
        logger.info(f"Job '{job_id}' cancelled via reset endpoint")
    reset_circuit(job_id)
    return {"status": "reset", "job": job_id, "cancelled": cancelled}
