import os
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config.logger import Logger

logger = Logger.get(__name__)
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_keys() -> set[str]:
    raw = os.getenv("API_KEYS", "")
    keys = {item.strip() for item in raw.split(",") if item.strip()}
    if not keys:
        logger.warning("No API_KEYS configured in environment variables")
        return set()
    logger.info("Loaded %s API keys from environment", len(keys))
    return keys


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    valid_keys = get_api_keys()
    if not valid_keys:
        logger.error("API authentication attempted but no API keys configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured",
        )
    if not api_key:
        logger.warning("Request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    if api_key not in valid_keys:
        logger.warning("Invalid API key attempt: %s...", api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    logger.debug("Valid API key used: %s...", api_key[:8])
    return api_key


def get_optional_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    if not api_key:
        return None
    valid_keys = get_api_keys()
    if valid_keys and api_key in valid_keys:
        return api_key
    return None
