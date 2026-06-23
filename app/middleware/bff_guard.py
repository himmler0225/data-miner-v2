"""Chặn gọi trực tiếp Tiki/FPT — chỉ BFF (ai-chatbot) có token mới qua."""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.logger import Logger
from app.config.settings import BFF_CLIENT_TOKEN, BFF_GUARD_ENABLED

logger = Logger.get(__name__)

BFF_GUARD_PREFIXES = ("/api/tiki", "/api/fpt-shop")
BFF_HEADER = b"x-rm-bff"


def _is_guarded_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in BFF_GUARD_PREFIXES)


async def _send_404(send: Send) -> None:
    await send({
        "type": "http.response.start",
        "status": 404,
        "headers": [[b"content-length", b"0"], [b"cache-control", b"no-store"]],
    })
    await send({"type": "http.response.body", "body": b"", "more_body": False})


class BffGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not BFF_GUARD_ENABLED or not _is_guarded_path(path):
            await self.app(scope, receive, send)
            return

        if not BFF_CLIENT_TOKEN:
            logger.warning("BFF_GUARD_ENABLED but BFF_CLIENT_TOKEN missing — skipping guard")
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        token = headers.get(BFF_HEADER, b"").decode()
        fetch_mode = headers.get(b"sec-fetch-mode", b"").decode().lower()
        fetch_dest = headers.get(b"sec-fetch-dest", b"").decode().lower()

        if fetch_dest == "document" or fetch_mode == "navigate":
            await _send_404(send)
            return

        if token != BFF_CLIENT_TOKEN:
            logger.warning("Blocked unauthenticated BFF access", extra={
                "extra_data": {"path": path, "method": scope.get("method", "")},
            })
            await _send_404(send)
            return

        await self.app(scope, receive, send)
