import json
import os
from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.logger import Logger
from app.config.settings import REQUIRE_SERVICE_AUTH
from app.middleware.service_tokens import validate_service_identity

logger = Logger.get(__name__)

PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


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


class ServiceAuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not REQUIRE_SERVICE_AUTH:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        service_name = headers.get(b"x-service-name", b"").decode().strip() or None
        service_token = headers.get(b"x-service-token", b"").decode().strip() or None

        if not service_name or not service_token:
            await _send_json(send, 403, "Service identity required")
            return

        if not validate_service_identity(service_name, service_token):
            await _send_json(send, 403, "Invalid service token")
            return

        await self.app(scope, receive, send)
