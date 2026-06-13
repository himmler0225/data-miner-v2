import os
import httpx
from fastapi import APIRouter, Depends
from app.middleware import verify_api_key, sample_client_info, get_pool_size
from app.middleware.client_info import get_all_snapshots
from app.config.urls import proxy_manager, proxy_manager_us
from app.config.logger import Logger
from app.schemas.response import ApiResponse
from app.scheduler.jobs import (
    cleanup_old_data,
    health_check_job,
    reset_circuit,
    get_failure_counts,
    MAX_CONSECUTIVE_FAILURES,
)
from ._tasks import _running_tasks, _start_job

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)

@router.get("/client-pool")
async def client_pool_status():
    """View current client fingerprint pool."""
    return ApiResponse.ok({
        "pool_size": get_pool_size(),
        "sample": sample_client_info(),
    })

@router.get("/client-pool/all")
async def client_pool_all():
    """View entire pool (for debug / DB export)."""
    return ApiResponse.ok({"snapshots": get_all_snapshots()})

@router.get("/proxy/status")
async def proxy_status():
    return ApiResponse.ok({"vn": proxy_manager.status(), "us": proxy_manager_us.status()})

@router.post("/proxy/rotate")
async def proxy_rotate():
    proxy_manager.rotate()
    proxy_manager_us.rotate()
    return ApiResponse.ok({"rotated": True})

@router.get("/proxy/test")
async def test_proxy(pool: str = "vn"):
    mgr = proxy_manager_us if pool == "us" else proxy_manager
    proxy_url = await mgr.get_proxy()
    if not proxy_url:
        return ApiResponse.ok({"status": "error", "detail": f"No proxy in '{pool}' pool"})
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
            resp = await client.get("http://httpbin.org/ip")
            ip = resp.json().get("origin", "unknown")
        return ApiResponse.ok({"status": "ok", "pool": pool, "exit_ip": ip})
    except Exception as e:
        return ApiResponse.ok({"status": "error", "pool": pool, "error": repr(e)})

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
    return ApiResponse.ok({"jobs": jobs})

@router.post("/jobs/cleanup")
async def trigger_cleanup():
    return _start_job("cleanup_data", cleanup_old_data)

@router.post("/jobs/health")
async def trigger_health():
    result = await health_check_job()
    return ApiResponse.ok({"status": "done", "result": result})

@router.post("/jobs/{job_id}/reset")
async def reset_job(job_id: str):
    """Cancel running job and reset circuit breaker."""
    task = _running_tasks.pop(job_id, None)
    cancelled = False
    if task and not task.done():
        task.cancel()
        cancelled = True
    if cancelled:
        logger.info("Job '%s' cancelled via reset endpoint", job_id)
    reset_circuit(job_id)
    return ApiResponse.ok({"status": "reset", "job": job_id, "cancelled": cancelled})
