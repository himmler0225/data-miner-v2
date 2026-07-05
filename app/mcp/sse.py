import asyncio

from anyio import BrokenResourceError
from fastapi import FastAPI, Request
from starlette.requests import ClientDisconnect
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from app.config.logger import Logger
from app.mcp.config import MCP_SSE_PATH

logger = Logger.get(__name__)


class _SSEAlreadySentResponse(Response):
    """connect_sse đã gửi HTTP response — tránh FastAPI gửi lần 2 (gây Exception in ASGI)."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        return


def mount_mcp_sse(app: FastAPI, path: str | None = None) -> None:
    """Register MCP SSE + message routes on the FastAPI app (call after API routers)."""
    mount_path = (path or MCP_SSE_PATH).rstrip("/")
    try:
        from mcp.server.sse import SseServerTransport
        from app.mcp.server import server
    except ImportError as exc:
        logger.warning("[mcp] SSE mount skipped — mcp package not installed: %s", exc)
        return

    messages_path = f"{mount_path}/messages/"
    transport = SseServerTransport(messages_path)

    async def handle_sse(request: Request) -> Response:
        try:
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        except (asyncio.CancelledError, ClientDisconnect, BrokenResourceError):
            logger.debug("[mcp] SSE client disconnected")
        except ExceptionGroup as exc:
            if all(
                isinstance(e, (asyncio.CancelledError, ClientDisconnect, BrokenResourceError))
                for e in exc.exceptions
            ):
                logger.debug("[mcp] SSE client disconnected (task group)")
            else:
                logger.warning("[mcp] SSE session error: %s", exc)
                raise
        return _SSEAlreadySentResponse()

    app.add_api_route(
        f"{mount_path}/sse",
        handle_sse,
        methods=["GET"],
        include_in_schema=False,
    )
    app.mount(f"{mount_path}/messages", transport.handle_post_message)
    logger.info("[mcp] SSE mounted at %s/sse", mount_path)
