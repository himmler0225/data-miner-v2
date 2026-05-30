import os
import asyncio
import socketio
from ....config.logging_config import get_logger

logger = get_logger(__name__)

_NESTJS_WS_URL = os.getenv("NESTJS_WS_URL", "http://localhost:3000")
_CRAWLER_WS_KEY = os.getenv("CRAWLER_WS_KEY", "")

sio = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=0,
    reconnection_delay=5,
    reconnection_delay_max=30,
    logger=False,
)


@sio.event(namespace="/crawler")
async def connect():
    logger.info(f"[live_ws] Connected to NestJS at {_NESTJS_WS_URL}/crawler")


@sio.event(namespace="/crawler")
async def disconnect():
    logger.warning("[live_ws] Disconnected from NestJS")


@sio.event(namespace="/crawler")
async def connect_error(data):
    logger.error(f"[live_ws] Connection error: {data}")


async def connect_to_nestjs():
    try:
        await sio.connect(
            _NESTJS_WS_URL,
            namespaces=["/crawler"],
            auth={"token": _CRAWLER_WS_KEY},
            transports=["websocket"],
            wait_timeout=10,
        )
    except Exception as e:
        logger.error(f"[live_ws] Failed to connect: {e}")


async def push_live_videos(videos: list) -> None:
    if not sio.connected:
        logger.warning("[live_ws] Not connected, skipping live push")
        return
    await sio.emit("crawler:live:push", {"videos": videos}, namespace="/crawler")
    logger.info(f"[live_ws] Pushed {len(videos)} live videos to NestJS")


async def disconnect_from_nestjs() -> None:
    if sio.connected:
        await sio.disconnect()


def connect_background() -> None:
    """Fire-and-forget connection from sync context (e.g. startup event)."""
    asyncio.create_task(connect_to_nestjs())
