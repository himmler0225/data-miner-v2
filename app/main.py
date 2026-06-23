from dotenv import load_dotenv
load_dotenv()

import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api.youtube import router as youtube_router
from app.api.tiki import router as tiki_router
from app.api.tiktok import router as tiktok_router
from app.api.fpt_shop import router as fpt_router
from app.api.admin import router as admin_router
from app.middleware import (
    LoggingMiddleware,
    IPWhitelistMiddleware,
    BffGuardMiddleware,
    ClientInfoMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from app.config.settings import LOG_LEVEL, ENABLE_IP_WHITELIST, RATE_LIMIT_DEFAULT, CORS_ORIGINS
from app.config.logger import Logger
from app.schemas.response import ApiResponse
Logger.setup(level=LOG_LEVEL)

logger = Logger.get(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config.remote import load_and_apply
    await load_and_apply()
    logger.info("[startup] data-miner starting")
    logger.info("[startup] log_level=%s whitelist=%s rate_limit=%s", LOG_LEVEL, ENABLE_IP_WHITELIST, RATE_LIMIT_DEFAULT)

    pool_task = None
    try:
        from app.crawlers.tiktok.native import warm_session_pool, session_pool_refresher
        await warm_session_pool()
        pool_task = asyncio.create_task(session_pool_refresher())
        logger.info("[startup] tiktok session pool ready")
    except Exception as exc:
        logger.warning("[startup] tiktok session pool failed: %s", exc)

    try:
        from app.utils import warm_youtube_session
        asyncio.create_task(warm_youtube_session())
        logger.info("[startup] youtube session warmup scheduled")
    except Exception as exc:
        logger.warning("[startup] youtube session warmup failed: %s", exc)

    yield

    logger.info("[shutdown] data-miner stopping")
    if pool_task:
        pool_task.cancel()

app = FastAPI(
    title="Data Miner API",
    description="",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.fail(str(exc.detail)).model_dump(),
    )

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(BffGuardMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ClientInfoMiddleware)
app.include_router(youtube_router, prefix="/api", tags=["YouTube"])
app.include_router(tiki_router, prefix="/api/tiki", tags=["Tiki"])
app.include_router(fpt_router, prefix="/api/fpt-shop", tags=["FPT Shop"])
app.include_router(tiktok_router, prefix="/api/tiktok", tags=["TikTok"])
app.include_router(admin_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return ApiResponse.ok({"service": "data-miner", "version": "1.0.0"})
