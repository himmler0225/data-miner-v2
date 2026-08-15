import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config.logger import Logger
from app.config.settings import API_KEYS
from app.middleware.config import API_KEY_HEADER

logger = Logger.get(__name__)
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def _valid_keys() -> set[str]:
    env_keys = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
    return env_keys if env_keys else set(API_KEYS)


def get_api_keys() -> set[str]:
    return _valid_keys()


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    valid_keys = _valid_keys()
    if not valid_keys:
        logger.error("API authentication attempted but no API keys configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="errors.api_auth_not_configured",
        )
    if not api_key:
        logger.warning("Request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="errors.missing_api_key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    if api_key not in valid_keys:
        logger.warning("Invalid API key attempt: %s...", api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="errors.invalid_api_key",
        )
    logger.debug("Valid API key used: %s...", api_key[:8])
    return api_key
