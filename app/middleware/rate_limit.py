from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config.logger import Logger
from app.config.settings import RATE_LIMIT_BURST, RATE_LIMIT_DEFAULT, RATE_LIMIT_STORAGE

logger = Logger.get(__name__)


def get_identifier(request: Request) -> str:
    service = request.headers.get("X-Service-Name", "").strip()
    if service:
        return f"service:{service}"
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"key:{api_key[:8]}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=get_identifier,
    default_limits=[RATE_LIMIT_DEFAULT, RATE_LIMIT_BURST],
    storage_uri=RATE_LIMIT_STORAGE,
    headers_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    identifier = get_identifier(request)
    logger.warning(
        "Rate limit exceeded",
        extra={
            "extra_data": {
                "identifier": identifier,
                "path": request.url.path,
                "method": request.method,
                "limit": str(exc.detail),
            }
        },
    )
    return _rate_limit_exceeded_handler(request, exc)
