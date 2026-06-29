from typing import Dict, List, Optional

from app.config.constants import ENDPOINT_BROWSE
from app.config.headers import get_youtube_headers
from app.config.logger import Logger
from app.crawlers.youtube.client import (create_httpx_client, get_context,
                                         get_youtube_api_key, get_youtube_api_url)

from ..playlist.playlist import get_videos_from_playlist

logger = Logger.get(__name__)


def _extract_playlist_ids(data: Dict) -> List[Dict]:
    playlists = []
    tabs = (
        data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("tabs", [])
    )
    for tab in tabs:
        renderer = tab.get("tabRenderer", {})
        content = renderer.get("content", {})
        grid = content.get("richGridRenderer", {})
        sections = grid.get("contents", [])
        for sec in sections:
            shelf = (
                sec.get("richSectionRenderer", {})
                .get("content", {})
                .get("richShelfRenderer", {})
            )
            shelf_title = shelf.get("title", {}).get("simpleText", "")
            for item in shelf.get("contents", []):
                lockup = (
                    item.get("richItemRenderer", {})
                    .get("content", {})
                    .get("lockupViewModel", {})
                )
                pid = lockup.get("contentId", "")
                title = (
                    lockup.get("metadata", {})
                    .get("lockupMetadataViewModel", {})
                    .get("title", {})
                    .get("content", "")
                )
                if pid and pid.startswith("RDCLAK"):  # music radio playlist ID prefix
                    playlists.append(
                        {"playlist_id": pid, "title": title, "shelf": shelf_title}
                    )
    return playlists


async def browse_topic_channel(
    channel_id: str,
    max_videos: int = 20,
    proxy: Optional[str] = None,
) -> Dict:
    api_key = await get_youtube_api_key(proxy=proxy)
    headers = get_youtube_headers()
    url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    context = get_context()
    context["client"]["gl"] = "VN"
    context["client"]["hl"] = "vi"

    payload = {"context": context, "browseId": channel_id}

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    playlists = _extract_playlist_ids(data)
    logger.info("[topic] channel=%s playlists=%d", channel_id, len(playlists))

    if not playlists:
        logger.warning("[topic] no playlists found for channel %s", channel_id)
        return {"channel_id": channel_id, "playlists": [], "videos": []}

    top = playlists[0]
    try:
        videos = await get_videos_from_playlist(top["playlist_id"], proxy=proxy)
        logger.info("[topic] playlist=%s videos=%d", top["playlist_id"], len(videos))
    except Exception as e:
        logger.warning(
            "[topic] failed to fetch playlist %s: %s", top["playlist_id"], e
        )
        videos = []

    return {
        "channel_id": channel_id,
        "playlists": playlists[:5],
        "featured_playlist": top,
        "videos": videos[:max_videos],
    }
