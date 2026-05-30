from functools import wraps
import re
import time
import random
import asyncio
from fastapi import HTTPException
import httpx
import json
from typing import Optional
from .config.urls import YOUTUBE_BASE_URL, get_proxy
from .config.constants import (
    CLIENT_NAME, CLIENT_VERSION, CLIENT_HL, CLIENT_GL, DEFAULT_TIMEOUT
)
from app.config.logging_config import get_logger
from app.exceptions import YouTubeStructureChangedError

_KEY_TTL = 3600  # 1 hour

logger = get_logger(__name__)
_api_key_cache: dict = {"value": "", "expires": 0.0}
_visitor_data_cache: dict = {"value": "", "expires": 0.0}
_client_version_cache: dict = {"value": "", "expires": 0.0}

async def get_youtube_api_key(proxy: str = None) -> str:
    now = time.monotonic()
    if _api_key_cache["value"] and now < _api_key_cache["expires"]:
        return _api_key_cache["value"]

    async with create_httpx_client(proxy=proxy) as client:
        resp = await client.get(YOUTUBE_BASE_URL)
        html = resp.text

        match = re.search(r'"INNERTUBE_API_KEY"\s*:\s*"([^"]+)"', html)
        if not match:
            raise Exception("INNERTUBE_API_KEY not found in YouTube homepage")
        key = match.group(1)

        vd_match = re.search(r'"visitorData"\s*:\s*"([^"]+)"', html)
        if vd_match:
            _visitor_data_cache["value"] = vd_match.group(1)
            _visitor_data_cache["expires"] = now + _KEY_TTL

        cv_match = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', html)
        if cv_match:
            _client_version_cache["value"] = cv_match.group(1)
            _client_version_cache["expires"] = now + _KEY_TTL

        _api_key_cache["value"] = key
        _api_key_cache["expires"] = now + _KEY_TTL
        return key

def get_visitor_data() -> Optional[str]:
    """Return cached visitorData if fresh, else None."""
    if _visitor_data_cache["value"] and time.monotonic() < _visitor_data_cache["expires"]:
        return _visitor_data_cache["value"]
    return None

def get_client_version() -> str:
    """Return dynamic client version from homepage, fallback to constant."""
    if _client_version_cache["value"] and time.monotonic() < _client_version_cache["expires"]:
        return _client_version_cache["value"]
    return CLIENT_VERSION

_TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "Europe/London", "Europe/Paris",
    "Asia/Tokyo", "Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Singapore",
    "Australia/Sydney",
]

def get_context(original_url: Optional[str] = None, user_agent: Optional[str] = None) -> dict:
    """Full InnerTube WEB context. browse endpoints require user + request sections."""
    client: dict = {
        "hl": CLIENT_HL,
        "gl": CLIENT_GL,
        "clientName": CLIENT_NAME,
        "clientVersion": get_client_version(),
        "platform": "DESKTOP",
        "clientFormFactor": "UNKNOWN_FORM_FACTOR",
        "timeZone": random.choice(_TIMEZONES),
        "utcOffsetMinutes": random.choice([-300, -360, -420, 0, 60, 120, 420, 540, 600]),
        "screenWidthPoints": random.choice([1280, 1366, 1440, 1536, 1920, 2560]),
        "screenHeightPoints": random.choice([720, 768, 864, 900, 1080, 1440]),
        "screenPixelDensity": random.choice([1, 2]),
    }

    visitor_data = get_visitor_data()
    if visitor_data:
        client["visitorData"] = visitor_data
    if original_url:
        client["originalUrl"] = original_url
    if user_agent:
        client["userAgent"] = user_agent

    return {
        "client": client,
        "user": {"lockedSafetyMode": False},
        "request": {
            "useSsl": True,
            "internalExperimentFlags": [],
            "consistencyTokenJars": [],
        },
    }

async def jitter_sleep(base: float, spread: float = 0.4) -> None:
    """Sleep base ± spread*base seconds. Prevents fixed-interval fingerprinting."""
    await asyncio.sleep(random.uniform(base * (1 - spread), base * (1 + spread)))

async def resolve_channel_id_from_handle(handle: str) -> str:
    async with create_httpx_client() as client:
        url = f"{YOUTUBE_BASE_URL}/@{handle}"
        resp = await client.get(url)
        html = resp.text
        match = re.search(r'channel_id=([a-zA-Z0-9_-]{24})', html)
        if match:
            return match.group(1)
        match = re.search(r'"browseId":"(UC[^\"]+)"', html)
        if match:
            return match.group(1)
        raise Exception("Channel_id not found")

def save_to_json(data, filename="debug.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_default_proxy():
    return get_proxy()

def get_httpx_proxies(proxy: str = None):
    if proxy is None:
        proxy = get_proxy()
    return proxy or None

def create_httpx_client(proxy: str = None, headers: dict = None, timeout: int = DEFAULT_TIMEOUT):
    proxy_url = get_httpx_proxies(proxy)
    kwargs = {"timeout": timeout}
    if headers:
        kwargs["headers"] = headers
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return httpx.AsyncClient(**kwargs)

def parse_view_count(text) -> int:
    if not text:
        return 0

    first = (
        str(text)
        .replace("\xa0", " ")
        .split()[0]
        .strip()
        .upper()
        .replace(",", "")
    )

    try:
        if "TR" in str(text).upper():
            number = first.replace(".", "").replace(",", ".")
            return int(float(number) * 1_000_000)

        if first.endswith("K"):
            return int(float(first[:-1]) * 1_000)

        if first.endswith("M"):
            return int(float(first[:-1]) * 1_000_000)

        if first.endswith("B"):
            return int(float(first[:-1]) * 1_000_000_000)

        return int(first.replace(".", ""))

    except (ValueError, AttributeError):
        return 0

def retry_on_failure(max_retries=3, delay=1):
    """Retry decorator with linear backoff. Raises immediately on YouTubeStructureChangedError."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except YouTubeStructureChangedError as e:
                    logger.critical(
                        f"Cấu trúc YouTube thay đổi trong {func.__name__}: {e}",
                        extra={"extra_data": {"context": e.context}}
                    )
                    raise HTTPException(status_code=502, detail=f"YouTube structure changed: {e}")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} for {func.__name__} failed, "
                            f"retrying in {wait_time}s: {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(f"All {max_retries} retries exhausted for {func.__name__}", exc_info=True)
                    raise last_exception
        return wrapper
    return decorator
