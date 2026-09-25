from app.config.constants import CHANNEL_TAB_PLAYLISTS, ENDPOINT_BROWSE
from app.config.logger import Logger
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeStructureChangedError
from ..shared.browse import fetch_channel_tab
from ..shared.parsers import extract_continuation_token, get_continuation_items, get_first_badge_text

logger = Logger.get(__name__)

# YouTube intermittently serves a "Shows" tab in place of a channel's Playlists
# tab (observed on ~1 in 6 requests to the same channel), so retry before failing.
PLAYLISTS_TAB_ATTEMPTS = 3
# Safety cap on continuation pages (~30 playlists each, so ~3000 playlists),
# in case YouTube keeps handing back tokens that never run out.
MAX_PLAYLIST_PAGES = 100


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
    continuation page). Returns `(playlists, next_continuation_token)`; entries
    that aren't playlist lockups are skipped."""
    playlists, token = [], None
    for item in items:
        if "continuationItemRenderer" in item:
            token = extract_continuation_token(item) or token
            continue
        content = item.get("richItemRenderer", {}).get("content", {}) or item
        parsed = _extract_lockup_playlist(content.get("lockupViewModel", {}))
        if parsed:
            playlists.append(parsed)
    return playlists, token


def extract_playlists_tab_items(playlists_tab: dict) -> tuple[list[dict], str | None]:
    """First page of a channel's Playlists tab, plus the continuation token for the next page."""
    return parse_playlist_items(_playlist_grid_items(playlists_tab))


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


async def get_playlist_videos(channel_id: str, proxy: str = None) -> list[dict]:
    """All playlists of a channel: the Playlists tab's first page, then every
    continuation page (about 30 playlists each) until YouTube stops returning a token."""
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)

    async with create_httpx_client(proxy=proxy) as client:
        playlists_tab = await _fetch_playlists_tab(client, browse_url, channel_id)
        playlists, token = extract_playlists_tab_items(playlists_tab)

        seen_tokens = set()
        pages = 0
        while token and token not in seen_tokens:
            if pages >= MAX_PLAYLIST_PAGES:
                logger.warning(
                    "[playlists] channel=%s stopped after %d continuation pages (%d playlists)",
                    channel_id,
                    pages,
                    len(playlists),
                )
                break
            seen_tokens.add(token)
            pages += 1
            resp = await client.post(browse_url, json={"context": get_context(), "continuation": token})
            resp.raise_for_status()
            page, token = parse_playlist_items(get_continuation_items(resp.json()))
            playlists += page

    unique, seen_ids = [], set()
    for item in playlists:
        if item["playlistId"] not in seen_ids:
            seen_ids.add(item["playlistId"])
            unique.append(item)
    return unique


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
