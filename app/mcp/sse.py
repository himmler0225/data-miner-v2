from fastapi import FastAPI, Request
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import Response

from app.config.logger import Logger
from app.mcp.config import MCP_SSE_PATH

logger = Logger.get(__name__)


def mount_mcp_sse(app: FastAPI, path: str | None = None) -> None:
    """Mount MCP server via SSE when the mcp package is available."""
    mount_path = path or MCP_SSE_PATH
    try:
        from mcp.server.sse import SseServerTransport
        from app.mcp.server import server
    except ImportError as exc:
        logger.warning("[mcp] SSE mount skipped — mcp package not installed: %s", exc)
        return

    transport = SseServerTransport(f"{mount_path}/messages/")

    async def handle_sse(request: Request) -> Response:
        async with transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
        return Response()

    sse_app = Starlette(
        routes=[
            Route(f"{mount_path}/sse", endpoint=handle_sse),
            Mount(f"{mount_path}/messages/", app=transport.handle_post_message),
        ]
    )
    app.mount("/", sse_app)
    logger.info("[mcp] SSE mounted at %s/sse", mount_path)
