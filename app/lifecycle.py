"""Application startup and shutdown."""

import asyncio
from dataclasses import dataclass, field

from app.config.logger import Logger
from app.config.settings import API_KEYS, ENABLE_IP_WHITELIST, ENABLE_SCHEDULER, LOG_LEVEL, REQUIRE_SERVICE_AUTH
from app.config.rate_limits import RATE_LIMIT_DEFAULT
from app.middleware.service_tokens import expected_service_token

logger = Logger.get(__name__)


@dataclass
class AppState:
    pool_task: asyncio.Task | None = None
    youtube_warm_task: asyncio.Task | None = None
    scheduler_started: bool = False
    background_tasks: list[asyncio.Task] = field(default_factory=list)


def validate_startup_config() -> None:
    if not API_KEYS:
        raise RuntimeError("API_KEYS must be set before starting data-miner")
    if REQUIRE_SERVICE_AUTH and not expected_service_token("ai-layer"):
        raise RuntimeError("SERVICE_TOKEN_AI_LAYER must be set when REQUIRE_SERVICE_AUTH=true")


async def startup(state: AppState) -> None:
    validate_startup_config()
    logger.info("[startup] data-miner starting")
    logger.info(
        "[startup] log_level=%s whitelist=%s rate_limit=%s",
        LOG_LEVEL,
        ENABLE_IP_WHITELIST,
        RATE_LIMIT_DEFAULT,
    )

    await _start_tiktok_pool(state)
    _start_youtube_warmup(state)
    _start_scheduler(state)


async def shutdown(state: AppState) -> None:
    logger.info("[shutdown] data-miner stopping")

    for task in state.background_tasks:
        task.cancel()
    if state.background_tasks:
        await asyncio.gather(*state.background_tasks, return_exceptions=True)

    if state.scheduler_started:
        from app.scheduler.scheduler import shutdown_scheduler

        shutdown_scheduler()


async def _start_tiktok_pool(state: AppState) -> None:
    try:
        from app.crawlers.tiktok.native import session_pool_refresher, warm_session_pool

        await warm_session_pool()
        state.pool_task = asyncio.create_task(session_pool_refresher(), name="tiktok-pool")
        state.background_tasks.append(state.pool_task)
        logger.info("[startup] tiktok session pool ready")
    except Exception as exc:
        logger.warning("[startup] tiktok session pool failed: %s", exc)


def _start_youtube_warmup(state: AppState) -> None:
    try:
        from app.crawlers.youtube.client import warm_youtube_session

        state.youtube_warm_task = asyncio.create_task(warm_youtube_session(), name="youtube-warmup")
        state.background_tasks.append(state.youtube_warm_task)
        logger.info("[startup] youtube session warmup scheduled")
    except Exception as exc:
        logger.warning("[startup] youtube session warmup failed: %s", exc)


def _start_scheduler(state: AppState) -> None:
    if not ENABLE_SCHEDULER:
        return
    try:
        from app.scheduler.config import configure_jobs
        from app.scheduler.scheduler import start_scheduler

        configure_jobs()
        start_scheduler()
        state.scheduler_started = True
        logger.info("[startup] scheduler started")
    except Exception as exc:
        logger.warning("[startup] scheduler failed: %s", exc)
