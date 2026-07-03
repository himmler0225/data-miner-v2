import warnings

warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.admin import router as admin_router
from app.api.movies import router as movies_router
from app.api.tiktok import router as tiktok_router
from app.api.youtube import router as youtube_router
from app.config.logger import Logger
from app.config.settings import CORS_ORIGINS, LOG_LEVEL
from app.lifecycle import AppState, shutdown, startup
from app.mcp.config import MCP_ENABLED
from app.mcp.sse import mount_mcp_sse
from app.middleware.client_info import ClientInfoMiddleware
from app.middleware.ip_whitelist import IPWhitelistMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.service_auth import ServiceAuthMiddleware
from app.schemas.response import ApiResponse

Logger.setup(level=LOG_LEVEL)
logger = Logger.get(__name__)
_app_state = AppState()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Logger.sync_uvicorn(LOG_LEVEL)
    from app.config.remote import load_and_apply

    await load_and_apply()
    await startup(_app_state)
    yield
    await shutdown(_app_state)


app = FastAPI(
    title="Data Miner API",
    description="",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
if MCP_ENABLED:
    mount_mcp_sse(app)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=ApiResponse.fail(str(exc.detail)).model_dump())


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
    return response


app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)
app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(ServiceAuthMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ClientInfoMiddleware)
app.include_router(youtube_router, prefix="/api", tags=["YouTube"])
app.include_router(tiktok_router, prefix="/api/tiktok", tags=["TikTok"])
app.include_router(movies_router, prefix="/api/movies", tags=["Movies"])
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return ApiResponse.ok({"service": "data-miner", "version": "1.0.0"})
