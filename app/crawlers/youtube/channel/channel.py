from app.config.constants import CHANNEL_TAB_VIDEOS, ENDPOINT_BROWSE
from app.config.headers import get_youtube_headers
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeStructureChangedError
from ..shared.browse import fetch_channel_tab
from ..shared.models import extract_videos
from ..shared.parsers import find_tab_by_url_suffix, first_continuation_token, get_continuation_items


def extract_home_tab_videos(home_tab: dict) -> list[dict]:
    """Videos from a channel's Home tab, used when the channel has no Videos tab
    (e.g. topic/auto-generated channels). Home is a list of shelves, served either
    as `richGridRenderer` + `richShelfRenderer` or `sectionListRenderer` + `shelfRenderer`.
    Home has no continuation, so this is all the videos it exposes."""
    content = home_tab.get("content", {})
    items = []
    for entry in content.get("richGridRenderer", {}).get("contents", []):
        shelf = entry.get("richSectionRenderer", {}).get("content", {}).get("richShelfRenderer")
        items += shelf.get("contents", []) if shelf else [entry]
    for section in content.get("sectionListRenderer", {}).get("contents", []):
        for entry in section.get("itemSectionRenderer", {}).get("contents", []):
            # horizontalListRenderer / expandedShelfContentsRenderer / gridRenderer
            for renderer in entry.get("shelfRenderer", {}).get("content", {}).values():
                if isinstance(renderer, dict):
                    items += renderer.get("items", [])

    videos, seen = [], set()
    for video in extract_videos(items):
        if video["video_id"] not in seen:
            seen.add(video["video_id"])
            videos.append(video)
    return videos


async def fetch_channel_videos_page(
    channel_id: str, token: str | None = None, proxy: str | None = None
) -> tuple[list[dict], str | None]:
    """One page of a channel's uploads (Videos tab, newest first): `(videos, next_token)`.
    Channels without a Videos tab fall back to the videos on their Home tab (one page)."""
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)

    async with create_httpx_client(proxy=proxy, headers=get_youtube_headers()) as client:
        if token:
            resp = await client.post(browse_url, json={"context": get_context(), "continuation": token})
            resp.raise_for_status()
            items = get_continuation_items(resp.json())
            return extract_videos(items), first_continuation_token(items)

        tabs, videos_tab = await fetch_channel_tab(client, browse_url, channel_id, CHANNEL_TAB_VIDEOS, "/videos")

    if not tabs:
        raise YouTubeStructureChangedError(
            "twoColumnBrowseResultsRenderer.tabs not found for channel",
            context={"channel_id": channel_id},
        )
    if videos_tab:
        items = videos_tab["content"].get("richGridRenderer", {}).get("contents", [])
        return extract_videos(items), first_continuation_token(items)

    home_tab = find_tab_by_url_suffix(tabs, "/featured")
    if not home_tab or "content" not in home_tab:
        raise YouTubeStructureChangedError(
            "Neither 'Videos' nor 'Home' tab found for channel",
            context={"channel_id": channel_id},
        )
    return extract_home_tab_videos(home_tab), None
