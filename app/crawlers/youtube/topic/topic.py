from app.config.constants import ENDPOINT_BROWSE
from app.config.headers import get_youtube_headers
from app.config.logger import Logger
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ..shared.models import make_playlist
from ..shared.parsers import get_browse_tabs

logger = Logger.get(__name__)

# Auto-generated music "radio" playlists on topic channels.
_RADIO_PLAYLIST_PREFIX = "RDCLAK"


def extract_topic_playlists(data: dict) -> list[dict]:
    """Radio playlists on a topic channel's Home shelves, in page order."""
    playlists = []
    for tab in get_browse_tabs(data):
        grid = tab.get("tabRenderer", {}).get("content", {}).get("richGridRenderer", {})
        for section in grid.get("contents", []):
            shelf = section.get("richSectionRenderer", {}).get("content", {}).get("richShelfRenderer", {})
            for item in shelf.get("contents", []):
                lockup = item.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel", {})
                playlist_id = lockup.get("contentId", "")
                if playlist_id.startswith(_RADIO_PLAYLIST_PREFIX):
                    title = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {})
                    playlists.append(make_playlist(playlist_id=playlist_id, title=title.get("content", "")))
    return playlists


async def get_topic_playlists(channel_id: str, proxy: str | None = None) -> list[dict]:
    """Featured radio playlists of a topic channel (e.g. Music), most prominent first."""
    api_key = await get_youtube_api_key(proxy=proxy)
    url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    async with create_httpx_client(proxy=proxy, headers=get_youtube_headers()) as client:
        resp = await client.post(url, json={"context": get_context(), "browseId": channel_id})
        resp.raise_for_status()
        data = resp.json()

    playlists = extract_topic_playlists(data)
    logger.info("[topic] channel=%s playlists=%d", channel_id, len(playlists))
    return playlists
