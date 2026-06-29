from dotenv import load_dotenv
load_dotenv()
import warnings
warnings.filterwarnings('ignore', category=Warning, module='urllib3')
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api.admin import router as admin_router
from app.api.fpt_shop import router as fpt_router
from app.api.tiki import router as tiki_router
from app.api.tiktok import router as tiktok_router
from app.api.youtube import router as youtube_router
from app.config.logger import Logger
from app.config.settings import CORS_ORIGINS, ENABLE_IP_WHITELIST, LOG_LEVEL, RATE_LIMIT_DEFAULT
from app.middleware.bff_guard import BffGuardMiddleware
from app.middleware.client_info import ClientInfoMiddleware
from app.middleware.ip_whitelist import IPWhitelistMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.service_auth import ServiceAuthMiddleware
from app.schemas.response import ApiResponse
Logger.setup(level=LOG_LEVEL)
logger = Logger.get(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Logger.sync_uvicorn(LOG_LEVEL)
    from app.config.remote import load_and_apply
    from app.config.settings import API_KEYS, REQUIRE_SERVICE_AUTH
    import os

    await load_and_apply()
    if not API_KEYS:
        raise RuntimeError("API_KEYS must be set before starting data-miner")
    if REQUIRE_SERVICE_AUTH and not os.getenv("SERVICE_TOKEN_AI_LAYER"):
        raise RuntimeError("SERVICE_TOKEN_AI_LAYER must be set when REQUIRE_SERVICE_AUTH=true")
    logger.info('[startup] data-miner starting')
    logger.info('[startup] log_level=%s whitelist=%s rate_limit=%s', LOG_LEVEL, ENABLE_IP_WHITELIST, RATE_LIMIT_DEFAULT)
    pool_task = None
    scheduler_started = False
    try:
        from app.crawlers.tiktok.native import session_pool_refresher, warm_session_pool
        await warm_session_pool()
        pool_task = asyncio.create_task(session_pool_refresher())
        logger.info('[startup] tiktok session pool ready')
    except Exception as exc:
        logger.warning('[startup] tiktok session pool failed: %s', exc)
    try:
        from app.crawlers.youtube.client import warm_youtube_session
        asyncio.create_task(warm_youtube_session())
        logger.info('[startup] youtube session warmup scheduled')
    except Exception as exc:
        logger.warning('[startup] youtube session warmup failed: %s', exc)
    try:
        from app.config.settings import ENABLE_SCHEDULER
        if ENABLE_SCHEDULER:
            from app.scheduler.config import configure_jobs
            from app.scheduler.scheduler import start_scheduler
            configure_jobs()
            start_scheduler()
            scheduler_started = True
            logger.info('[startup] scheduler started')
    except Exception as exc:
        logger.warning('[startup] scheduler failed: %s', exc)
    yield
    logger.info('[shutdown] data-miner stopping')
    if scheduler_started:
        from app.scheduler.scheduler import shutdown_scheduler
        shutdown_scheduler()
    if pool_task:
        pool_task.cancel()
app = FastAPI(title='Data Miner API', description='', version='1.0.0', swagger_ui_parameters={'persistAuthorization': True}, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=ApiResponse.fail(str(exc.detail)).model_dump())

@app.middleware('http')
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Process-Time-Ms'] = str(round((time.perf_counter() - start) * 1000, 2))
    return response
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.add_middleware(IPWhitelistMiddleware)
app.add_middleware(ServiceAuthMiddleware)
app.add_middleware(BffGuardMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ClientInfoMiddleware)
app.include_router(youtube_router, prefix='/api', tags=['YouTube'])
app.include_router(tiki_router, prefix='/api/tiki', tags=['Tiki'])
app.include_router(fpt_router, prefix='/api/fpt-shop', tags=['FPT Shop'])
app.include_router(tiktok_router, prefix='/api/tiktok', tags=['TikTok'])
app.include_router(admin_router)

@app.get('/health', tags=['Health'])
async def health_check():
    return ApiResponse.ok({'service': 'data-miner', 'version': '1.0.0'})
