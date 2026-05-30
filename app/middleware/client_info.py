import random
import time
from collections import deque
from typing import Optional
from typing_extensions import TypedDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Các path không cần capture (health check, docs, admin debug)
_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

# UA của programmatic clients — không dùng được để fake browser fingerprint
_BOT_UA_FRAGMENTS = ("python", "httpx", "aiohttp", "curl", "wget", "go-http", "java", "libwww")


class ClientSnapshot(TypedDict):
    ip: str
    user_agent: str
    accept_language: str
    accept_encoding: str
    ts: float  # unix timestamp — dùng cho TTL / DB sync sau này


# Pool in-memory, tối đa 500 snapshot gần nhất.
# Sau này có thể swap thành Redis SET hoặc DB table mà không thay đổi interface.
_pool: deque[ClientSnapshot] = deque(maxlen=500)


def get_pool_size() -> int:
    return len(_pool)


def sample_client_info() -> Optional[ClientSnapshot]:
    """Lấy ngẫu nhiên 1 snapshot từ pool, trả None nếu pool rỗng."""
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
    Capture IP + browser fingerprint từ mỗi request vào pool in-memory.

    Dữ liệu này được dùng để randomize User-Agent / Accept-Language
    khi gọi YouTube InnerTube API, làm cho request trông giống browser thật.
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
