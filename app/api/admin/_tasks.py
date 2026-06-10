from __future__ import annotations
import asyncio
from app.config.logger import Logger
from app.schemas.response import ApiResponse

logger = Logger.get(__name__)

_running_tasks: dict[str, asyncio.Task] = {}

async def _run_job(job_id: str, coro_func):
    try:
        logger.info("Job '%s' started", job_id)
        result = await coro_func()
        logger.info("Job '%s' completed: %s", job_id, result)
        return result
    except asyncio.CancelledError:
        logger.warning("Job '%s' cancelled", job_id)
        raise
    except Exception as e:
        logger.error(f"Job '{job_id}' failed: {e}", exc_info=True)
        raise
    finally:
        _running_tasks.pop(job_id, None)

def _start_job(job_id: str, coro_func) -> dict:
    if job_id in _running_tasks and not _running_tasks[job_id].done():
        return ApiResponse.ok({"status": "already_running", "job": job_id})
    task = asyncio.create_task(_run_job(job_id, coro_func))
    _running_tasks[job_id] = task
    return ApiResponse.ok({"status": "started", "job": job_id})
