import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple

import httpx

from app.config.logger import Logger

from .client_constants import (BASE_UA, DEFAULT_DELIVERY_ZONE, GUEST_TOKEN_URL,
                               SEC_CH_UA)

logger = Logger.get(__name__)


def generate_trackity_id() -> str:
    return str(uuid.uuid4())


async def fetch_guest_token(proxy: Optional[str] = None) -> str:
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(timeout=10, transport=transport) as client:
        resp = await client.post(
            GUEST_TOKEN_URL,
            headers={"user-agent": BASE_UA},
            json={"grant_type": "guest"},
        )
        resp.raise_for_status()
        data = resp.json()

    token = data.get("access_token") or data.get("guest_token")
    if not token:
        raise RuntimeError(f"Failed to get guest token from Tiki: {data}")

    logger.info("🔵 [tiki] guest token acquired: %s...", token[:8])
    return token


async def create_tiki_session(proxy: Optional[str] = None) -> Tuple[str, str]:
    """Create a new (trackity_id, guest_token) pair for a crawl session."""
    trackity_id = generate_trackity_id()
    guest_token = await fetch_guest_token(proxy=proxy)
    return trackity_id, guest_token


def build_cookies(trackity_id: str, guest_token: str) -> Dict:
    return {
        "_trackity": trackity_id,
        "TOKENS": (
            f'{{"access_token":"{guest_token}",' f'"guest_token":"{guest_token}"}}'
        ),
        "delivery_zone": DEFAULT_DELIVERY_ZONE,
    }


def build_headers(
    guest_token: str,
    extra: Optional[Dict] = None,
    ua: Optional[str] = None,
    lang: str = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
) -> Dict:
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": lang,
        "priority": "u=1, i",
        "referer": "https://tiki.vn/",
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "user-agent": ua or BASE_UA,
        "x-guest-token": guest_token,
    }
    if extra:
        headers.update(extra)
    return headers


@asynccontextmanager
async def create_tiki_client(
    headers: Dict,
    cookies: Dict,
    proxy: Optional[str] = None,
):
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(
        cookies=cookies,
        headers=headers,
        timeout=15,
        transport=transport,
    ) as client:
        yield client
