import os
import httpx
from fastapi import APIRouter, Depends
from app.middleware import verify_api_key, sample_client_info, get_pool_size
from app.middleware.client_info import get_all_snapshots
from app.config.urls import proxy_manager
from app.config.logging_config import get_logger
from app.scheduler.jobs import (
    cleanup_old_data,
    health_check_job,
    reset_circuit,
    get_failure_counts,
    MAX_CONSECUTIVE_FAILURES,
)
from ._tasks import _running_tasks, _start_job

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)


@router.get("/client-pool")
async def client_pool_status():
    """Xem pool client fingerprint đang có."""
    return {
        "pool_size": get_pool_size(),
        "sample": sample_client_info(),
    }


@router.get("/client-pool/all")
async def client_pool_all():
    """Xem toàn bộ pool (dùng để debug / export ra DB)."""
    return {"snapshots": get_all_snapshots()}


@router.get("/proxy/debug")
async def proxy_debug():
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


@router.get("/proxy/status")
async def proxy_status():
    return {"proxies": proxy_manager.status()}


@router.get("/proxy/test")
async def test_proxy():
    proxy_url = await proxy_manager.get_proxy()
    if not proxy_url:
        return {"status": "error", "detail": "Không lấy được proxy — kiểm tra PROXY_KEYS trong .env"}
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
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
    if cancelled:
        logger.info(f"Job '{job_id}' cancelled via reset endpoint")
    reset_circuit(job_id)
    return {"status": "reset", "job": job_id, "cancelled": cancelled}
