from __future__ import annotations
import random
import time
from collections import deque
from typing import Optional
from typing_extensions import TypedDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Paths to skip capturing (health check, docs, admin debug)
_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

# UA fragments that identify programmatic clients — cannot fake a real browser fingerprint
_BOT_UA_FRAGMENTS = ("python", "httpx", "aiohttp", "curl", "wget", "go-http", "java", "libwww")


class ClientSnapshot(TypedDict):
    ip: str
    user_agent: str
    accept_language: str
    accept_encoding: str
    ts: float  # unix timestamp — used for TTL / DB sync


# In-memory pool, capped at 500 most recent snapshots.
# Can be swapped for Redis SET or a DB table without changing the interface.
_pool: deque[ClientSnapshot] = deque(maxlen=500)


def get_pool_size() -> int:
    return len(_pool)


def sample_client_info() -> Optional[ClientSnapshot]:
    """Return a random snapshot from the pool, or None if empty."""
    if not _pool:
        return None
    return random.choice(list(_pool))


def get_all_snapshots() -> list[ClientSnapshot]:
    return list(_pool)


def _extract_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip
    return request.client.host if request.client else ""


def _is_browser_ua(ua: str) -> bool:
    if not ua:
        return False
    ua_lower = ua.lower()
    return not any(frag in ua_lower for frag in _BOT_UA_FRAGMENTS)


class ClientInfoMiddleware(BaseHTTPMiddleware):
    """
    Capture IP + browser fingerprint from each request into an in-memory pool.

    Used to randomize User-Agent / Accept-Language when calling the YouTube
    InnerTube API, making requests look like real browser traffic.
    """

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        path = request.url.path

        if path not in _SKIP_PATHS:
            ua = request.headers.get("User-Agent", "")
            if _is_browser_ua(ua):
                snapshot: ClientSnapshot = {
                    "ip": _extract_ip(request),
                    "user_agent": ua,
                    "accept_language": request.headers.get("Accept-Language", ""),
                    "accept_encoding": request.headers.get("Accept-Encoding", ""),
                    "ts": time.time(),
                }
                _pool.append(snapshot)
                request.state.client_info = snapshot

        return await call_next(request)
