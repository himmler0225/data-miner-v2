from app.config.constants import CHANNEL_TAB_PLAYLISTS, ENDPOINT_BROWSE
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeNotFoundError, YouTubeStructureChangedError
from ..shared.browse import fetch_channel_tab
from ..shared.models import extract_videos, playlist_from_lockup
from ..shared.parsers import extract_continuation_token, first_continuation_token, get_continuation_items

# YouTube intermittently serves a "Shows" tab in place of a channel's Playlists
# tab (observed on ~1 in 6 requests to the same channel), so retry before failing.
PLAYLISTS_TAB_ATTEMPTS = 3


def _playlist_grid_items(playlists_tab: dict) -> list[dict]:
    """Raw grid entries of a channel's Playlists tab, served either as
    `sectionListRenderer` + `gridRenderer` or as `richGridRenderer`."""
    content = playlists_tab.get("content", {})
    items = []
    for section in content.get("sectionListRenderer", {}).get("contents", []):
        for item in section.get("itemSectionRenderer", {}).get("contents", []):
            items += item.get("gridRenderer", {}).get("items", [])
    items += content.get("richGridRenderer", {}).get("contents", [])
    return items


def parse_playlist_items(items: list[dict]) -> tuple[list[dict], str | None]:
    """Parse one page of Playlists-tab grid entries (the tab's first page, or a
    continuation page). Returns `(playlists, next_token)`; entries that aren't
    playlist lockups are skipped."""
    playlists, token = [], None
    for item in items:
        if "continuationItemRenderer" in item:
            token = extract_continuation_token(item) or token
            continue
        content = item.get("richItemRenderer", {}).get("content", {}) or item
        playlist = playlist_from_lockup(content.get("lockupViewModel", {}))
        if playlist:
            playlists.append(playlist)
    return playlists, token


async def _fetch_playlists_tab(client, browse_url: str, channel_id: str) -> dict:
    for _ in range(PLAYLISTS_TAB_ATTEMPTS):
        tabs, playlists_tab = await fetch_channel_tab(
            client, browse_url, channel_id, CHANNEL_TAB_PLAYLISTS, "/playlists"
        )
        if playlists_tab:
            return playlists_tab
    raise YouTubeStructureChangedError(
        "Playlists tab not found for channel",
        context={"channel_id": channel_id, "attempts": PLAYLISTS_TAB_ATTEMPTS, "tabs_count": len(tabs)},
    )


async def fetch_channel_playlists_page(
    channel_id: str, token: str | None = None, proxy: str | None = None
) -> tuple[list[dict], str | None]:
    """One page of a channel's playlists (~30 per page): `(playlists, next_token)`."""
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)

    async with create_httpx_client(proxy=proxy) as client:
        if token:
            resp = await client.post(browse_url, json={"context": get_context(), "continuation": token})
            resp.raise_for_status()
            return parse_playlist_items(get_continuation_items(resp.json()))
        playlists_tab = await _fetch_playlists_tab(client, browse_url, channel_id)
    return parse_playlist_items(_playlist_grid_items(playlists_tab))


def _playlist_first_page_items(data: dict, playlist_id: str) -> list[dict]:
    if "contents" not in data:
        if data.get("alerts"):  # "This playlist does not exist" / is private
            raise YouTubeNotFoundError(f"Playlist {playlist_id} not found or private")
        raise YouTubeStructureChangedError(
            "Top-level 'contents' missing in playlist response",
            context={"playlist_id": playlist_id, "top_keys": list(data.keys())},
        )
    tabs = data["contents"].get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
    sections = (tabs[0] if tabs else {}).get("tabRenderer", {}).get("content", {}).get("sectionListRenderer", {})
    section_items = (sections.get("contents") or [{}])[0].get("itemSectionRenderer", {}).get("contents", [])
    return (section_items or [{}])[0].get("playlistVideoListRenderer", {}).get("contents", [])


async def fetch_playlist_videos_page(
    playlist_id: str, token: str | None = None, proxy: str | None = None
) -> tuple[list[dict], str | None]:
    """One page of a playlist's videos (~100 per page): `(videos, next_token)`."""
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    payload = {"context": get_context()}
    if token:
        payload["continuation"] = token
    else:
        payload["browseId"] = f"VL{playlist_id}"

    async with create_httpx_client(proxy=proxy) as client:
        resp = await client.post(browse_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    items = get_continuation_items(data) if token else _playlist_first_page_items(data, playlist_id)
    return extract_videos(items), first_continuation_token(items)
