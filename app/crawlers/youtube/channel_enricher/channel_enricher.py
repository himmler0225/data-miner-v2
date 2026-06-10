import asyncio
from typing import Optional, Set

from ..channel_info.channel_info import get_channel_info
from ..channel.channel import get_channel_videos
from ..playlist.playlist import get_playlist_videos, get_videos_from_playlist
from app.ingest import youtube as ingest_client
from app.config.logger import Logger
from .channel_enricher_constants import _CHANNEL_CONCURRENCY, _PLAYLIST_ITEM_CONCURRENCY

logger = Logger.get(__name__)

async def _enrich_one(channel_id: str, proxy: Optional[str] = None) -> None:
    async def _info() -> None:
        try:
            data = await get_channel_info(channel_id, proxy=proxy)
            if data.get("channel_id"):
                await ingest_client.ingest_channel(data)
        except Exception as e:
            logger.warning("[enricher] info %s: %s", channel_id, e)

    async def _videos() -> None:
        try:
            videos = await get_channel_videos(channel_id, proxy=proxy, max_results=30)
            if videos:
                await ingest_client.ingest_channel_videos(channel_id=channel_id, videos=videos)
        except Exception as e:
            logger.warning("[enricher] videos %s: %s", channel_id, e)

    async def _playlists() -> None:
        try:
            playlists = await get_playlist_videos(channel_id, proxy=proxy)
            if not playlists:
                return
            sem = asyncio.Semaphore(_PLAYLIST_ITEM_CONCURRENCY)

            async def _fetch_and_ingest(playlist_id: str) -> None:
                async with sem:
                    try:
                        items = await get_videos_from_playlist(playlist_id, proxy=proxy)
                        if not items:
                            return
                        playlist_meta = next(
                            (p for p in playlists if p.get("playlistId") == playlist_id), {}
                        )
                        await ingest_client.ingest_playlists(channel_id=channel_id, playlists=[playlist_meta])
                        await ingest_client.ingest_playlist_items(playlist_id=playlist_id, videos=items)
                    except Exception as e:
                        logger.warning("[enricher] playlist_items %s: %s", playlist_id, e)

            tasks = [_fetch_and_ingest(p["playlistId"]) for p in playlists if p.get("playlistId")]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning("[enricher] playlists %s: %s", channel_id, e)

    logger.info("[enricher] start %s", channel_id)
    await asyncio.gather(_info(), _videos(), _playlists())
    logger.info("[enricher] done  %s", channel_id)

async def enrich_channels_batch(
    channel_ids: Set[str],
    proxy: Optional[str] = None,
    concurrency: int = _CHANNEL_CONCURRENCY,
) -> None:
    if not channel_ids:
        return
    sem = asyncio.Semaphore(concurrency)

    async def _guarded(cid: str) -> None:
        async with sem:
            await _enrich_one(cid, proxy=proxy)

    await asyncio.gather(*[_guarded(cid) for cid in channel_ids], return_exceptions=True)
    logger.info("[enricher] batch complete — %s channels", len(channel_ids))
