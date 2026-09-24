from app.config.constants import CHANNEL_TAB_PLAYLISTS, ENDPOINT_BROWSE
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeStructureChangedError
from ..shared.browse import fetch_channel_tab
from ..shared.parsers import get_first_badge_text

# YouTube intermittently serves a "Shows" tab in place of a channel's Playlists
# tab (observed on ~1 in 6 requests to the same channel), so retry before failing.
PLAYLISTS_TAB_ATTEMPTS = 3


def extract_title(title_obj):
    if "simpleText" in title_obj:
        return title_obj["simpleText"]
    elif "runs" in title_obj and title_obj["runs"]:
        return "".join([run.get("text", "") for run in title_obj["runs"]])
    return ""


def _extract_lockup_playlist(lockup: dict) -> dict | None:
    playlist_id = lockup.get("contentId")
    if not playlist_id:
        return None
    thumbnail_vm = (
        lockup.get("contentImage", {})
        .get("collectionThumbnailViewModel", {})
        .get("primaryThumbnail", {})
        .get("thumbnailViewModel", {})
    )
    sources = thumbnail_vm.get("image", {}).get("sources") or [{}]
    return {
        "playlistId": playlist_id,
        "title": lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", ""),
        "thumbnail": sources[-1].get("url", ""),
        "videoCount": get_first_badge_text(thumbnail_vm.get("overlays", [])),
    }


def extract_playlists_tab_items(playlists_tab: dict) -> list[dict]:
    """Playlists from the first page of a channel's Playlists tab. Grid items that
    aren't playlist lockups (e.g. the trailing continuationItemRenderer) are skipped."""
    content = playlists_tab.get("content", {})
    items = []
    for section in content.get("sectionListRenderer", {}).get("contents", []):
        for item in section.get("itemSectionRenderer", {}).get("contents", []):
            items += item.get("gridRenderer", {}).get("items", [])
    for entry in content.get("richGridRenderer", {}).get("contents", []):
        items.append(entry.get("richItemRenderer", {}).get("content", {}))

    playlists = []
    for item in items:
        parsed = _extract_lockup_playlist(item.get("lockupViewModel", {}))
        if parsed:
            playlists.append(parsed)
    return playlists


async def get_playlist_videos(channel_id: str, proxy: str = None) -> list[dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)

    async with create_httpx_client(proxy=proxy) as client:
        for _ in range(PLAYLISTS_TAB_ATTEMPTS):
            tabs, playlists_tab = await fetch_channel_tab(
                client, browse_url, channel_id, CHANNEL_TAB_PLAYLISTS, "/playlists"
            )
            if playlists_tab:
                return extract_playlists_tab_items(playlists_tab)

    raise YouTubeStructureChangedError(
        "Playlists tab not found for channel",
        context={"channel_id": channel_id, "attempts": PLAYLISTS_TAB_ATTEMPTS, "tabs_count": len(tabs)},
    )


async def get_videos_from_playlist(playlist_id: str, proxy: str = None) -> list[dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    payload = {"context": get_context(), "browseId": f"VL{playlist_id}"}
    videos = []

    async with create_httpx_client(proxy=proxy) as client:
        while True:
            resp = await client.post(browse_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if "contents" not in data:
                raise YouTubeStructureChangedError(
                    "Top-level 'contents' missing in playlist response",
                    context={"playlist_id": playlist_id, "top_keys": list(data.keys())},
                )

            tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            contents = (
                (tabs[0] if tabs else {})
                .get("tabRenderer", {})
                .get("content", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            playlist_items_list = (contents[0] if contents else {}).get("itemSectionRenderer", {}).get("contents", [])
            contents = (
                (playlist_items_list[0] if playlist_items_list else {})
                .get("playlistVideoListRenderer", {})
                .get("contents", [])
            )
            if not contents:
                break

            continuation_token = None
            for item in contents:
                if "playlistVideoRenderer" in item:
                    renderer = item["playlistVideoRenderer"]
                    videos.append(
                        {
                            "video_id": renderer.get("videoId"),
                            "title": extract_title(renderer.get("title", {})),
                            "published_time": renderer.get("publishedTimeText", {}).get("simpleText", ""),
                            "duration": renderer.get("lengthText", {}).get("simpleText", ""),
                            "thumbnail": (renderer.get("thumbnail", {}).get("thumbnails") or [{}])[-1].get("url", ""),
                        }
                    )
                elif "continuationItemRenderer" in item:
                    continuation_token = (
                        item.get("continuationItemRenderer", {})
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {})
                        .get("token")
                    )

            if continuation_token:
                payload = {"context": get_context(), "continuation": continuation_token}
            else:
                break

    return videos
