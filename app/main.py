from dotenv import load_dotenv
load_dotenv()  # Must be called before any import that reads env vars

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
from app.api.youtube import router as youtube_router
from app.api.tiki import router as tiki_router
from app.api.tiktok import router as tiktok_router
from app.api.admin import router as admin_router
from app.middleware import (
    LoggingMiddleware,
    IPWhitelistMiddleware,
    ClientInfoMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from app.config.settings import LOG_LEVEL, ENABLE_IP_WHITELIST, RATE_LIMIT_DEFAULT
from app.config.logger import Logger
from app.schemas.response import ApiResponse
Logger.setup(level=LOG_LEVEL)

from app.crawlers.youtube.live_ws_client import connect_background, disconnect_from_nestjs

logger = Logger.get(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Data Miner API starting up...")
    logger.info("Log level: %s", LOG_LEVEL)
    logger.info("IP whitelist: %s", ENABLE_IP_WHITELIST)
    logger.info("Rate limit: %s", RATE_LIMIT_DEFAULT)
    logger.info("Scheduler disabled — demo mode")
    connect_background()
    logger.info("NestJS WebSocket connection initialized")

    # Pre-warm TikTok msToken so first search is fast
    try:
        from app.crawlers.tiktok.native import warm_token
        asyncio.create_task(warm_token())
        logger.info("TikTok token warm-up started in background")
    except Exception as e:
        logger.warning("TikTok token warm-up failed to start: %s", e)

    yield

    logger.info("Data Miner API shutting down...")
    await disconnect_from_nestjs()
    logger.info("NestJS WebSocket disconnected")


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

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ClientInfoMiddleware)
app.include_router(youtube_router, prefix="/api", tags=["YouTube"])
app.include_router(tiki_router, prefix="/api/tiki", tags=["Tiki"])
app.include_router(tiktok_router, prefix="/api/tiktok", tags=["TikTok"])
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return ApiResponse.ok({"service": "data-miner", "version": "1.0.0"})
