import asyncio
import socketio
from app.config.logger import Logger
from ....config.settings import NESTJS_WS_URL, CRAWLER_WS_KEY

logger = Logger.get(__name__)

_NESTJS_WS_URL  = NESTJS_WS_URL
_CRAWLER_WS_KEY = CRAWLER_WS_KEY

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
