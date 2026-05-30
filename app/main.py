from dotenv import load_dotenv
load_dotenv()  # Phải gọi trước mọi import đọc env

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from app.api.youtube import router as youtube_router
from app.api.tiki import router as tiki_router
from app.api.lazada import router as lazada_router
from app.api.admin import router as admin_router
from app.middleware import (
    LoggingMiddleware,
    IPWhitelistMiddleware,
    ClientInfoMiddleware,
    limiter,
    rate_limit_exceeded_handler,
)
from app.config.logging_config import setup_logging, get_logger
from app.crawlers.youtube.live_ws_client import connect_background, disconnect_from_nestjs

log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level=log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Data Miner API starting up...")
    logger.info(f"Log level: {log_level}")
    logger.info(f"IP whitelist: {os.getenv('ENABLE_IP_WHITELIST', 'false')}")
    logger.info(f"Rate limit: {os.getenv('RATE_LIMIT_DEFAULT', '100/hour')}")
    logger.info("Scheduler disabled — demo mode")
    connect_background()
    logger.info("NestJS WebSocket connection initialized")

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
app.include_router(lazada_router, prefix="/api/lazada", tags=["Lazada"])
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Không cần xác thực — dùng cho load balancer / uptime monitor."""
    return {
        "status": "healthy",
        "service": "data-miner",
        "version": "1.0.0",
    }
