import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.i18n import t
from app.i18n.locale import resolve_locale_from_scope
from app.mcp.config import MCP_AUTH_TOKEN


async def _send_json(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class MCPAuthMiddleware:
    """Optional Bearer auth for /mcp/* when MCP_AUTH_TOKEN is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not MCP_AUTH_TOKEN:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode().strip()
        if auth != f"Bearer {MCP_AUTH_TOKEN}":
            locale = resolve_locale_from_scope(scope)
            await _send_json(send, 401, t("errors.invalid_mcp_token", locale))
            return

        await self.app(scope, receive, send)
