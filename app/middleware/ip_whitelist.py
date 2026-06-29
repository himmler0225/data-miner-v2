import json
from typing import Optional, Set

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.logger import Logger
from app.config.settings import APP_ENV, ENABLE_IP_WHITELIST
from app.config.settings import WHITELISTED_IPS as _IPS_LIST
from app.middleware.service_tokens import validate_service_identity

logger = Logger.get(__name__)


def _build_ip_set() -> Set[str]:
    ips = set(_IPS_LIST)
    if not ips:
        logger.warning("No IP whitelist configured - all IPs will be allowed")
        return set()
    if APP_ENV == "development":
        ips.update({"127.0.0.1", "::1", "localhost"})
    logger.info("Loaded %s whitelisted IPs", len(ips))
    return ips


WHITELISTED_IPS = _build_ip_set()
WHITELIST_ENABLED = ENABLE_IP_WHITELIST


def is_ip_whitelisted(ip: str) -> bool:
    if not WHITELISTED_IPS:
        return True
    return ip in WHITELISTED_IPS


def _get_client_ip_from_scope(scope: Scope, headers: dict) -> str:
    forwarded_for = headers.get(b"x-forwarded-for", b"").decode()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = headers.get(b"x-real-ip", b"").decode()
    if real_ip:
        return real_ip.strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


async def _send_403(send: Send) -> None:
    body = json.dumps(
        {"detail": "Access denied: IP address or service not whitelisted"}
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(body)).encode()],
            ],
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class IPWhitelistMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not WHITELIST_ENABLED:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        client_ip = _get_client_ip_from_scope(scope, headers)
        service_name = headers.get(b"x-service-name", b"").decode() or None
        service_token = headers.get(b"x-service-token", b"").decode() or None
        if validate_service_identity(service_name, service_token):
            logger.debug("Request from whitelisted service: %s", service_name)
            await self.app(scope, receive, send)
            return
        if is_ip_whitelisted(client_ip):
            logger.debug("Request from whitelisted IP: %s", client_ip)
            await self.app(scope, receive, send)
            return
        logger.warning(
            "Blocked request from non-whitelisted source",
            extra={
                "extra_data": {
                    "ip": client_ip,
                    "service": service_name,
                    "path": path,
                    "method": scope.get("method", ""),
                }
            },
        )
        await _send_403(send)
