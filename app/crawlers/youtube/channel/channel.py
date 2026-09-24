from app.config.constants import CHANNEL_TAB_VIDEOS, ENDPOINT_BROWSE, YOUTUBE_BASE_URL
from app.config.headers import get_youtube_headers
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeStructureChangedError
from ..shared.browse import fetch_channel_tab
from ..shared.parsers import (
    extract_continuation_token,
    find_tab_by_url_suffix,
    get_continuation_items,
    get_first_badge_text,
    join_runs,
)


def _extract_lockup_video(lockup: dict) -> dict | None:
    """Parse a channel-grid video item in the newer `lockupViewModel` shape
    (YouTube has been migrating channel/playlist grids to this component model;
    it replaces the older `videoRenderer`/`gridVideoRenderer` shape)."""
    if lockup.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None
    video_id = lockup.get("contentId")
    if not video_id:
        return None
    metadata_vm = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = metadata_vm.get("title", {}).get("content", "")
    rows = metadata_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    # Channel-grid lockups have a single [views, published] row; lockups that also
    # show the channel name put it in an earlier row, so views/date is the last row.
    rows = [row for row in rows if row.get("metadataParts")]
    parts = rows[-1]["metadataParts"] if rows else []
    views = parts[0].get("text", {}).get("content", "") if len(parts) > 0 else ""
    published = parts[1].get("text", {}).get("content", "") if len(parts) > 1 else ""
    thumbnail_vm = lockup.get("contentImage", {}).get("thumbnailViewModel", {})
    return {
        "title": title,
        "videoId": video_id,
        "url": f"{YOUTUBE_BASE_URL}/watch?v={video_id}",
        "duration": get_first_badge_text(thumbnail_vm.get("overlays", [])),
        "views": views,
        "thumbnail": thumbnail_vm.get("image", {}).get("sources", []),
        "public": published,
    }


def extract_video_items(items: list[dict]) -> list[dict]:
    videos = []
    for item in items:
        content = item.get("richItemRenderer", {}).get("content", {}) or item
        lockup = content.get("lockupViewModel")
        if lockup:
            parsed = _extract_lockup_video(lockup)
            if parsed:
                videos.append(parsed)
            continue
        video = content.get("videoRenderer") or content.get("gridVideoRenderer")
        if not video or not video.get("videoId"):
            continue
        videos.append(
            {
                "title": join_runs(video.get("title", {})),
                "videoId": video.get("videoId"),
                "url": f"{YOUTUBE_BASE_URL}/watch?v={video.get('videoId')}",
                "duration": video.get("lengthText", {}).get("simpleText", ""),
                "views": video.get("viewCountText", {}).get("simpleText", ""),
                "thumbnail": video.get("thumbnail", {}).get("thumbnails", []),
                "public": video.get("publishedTimeText", {}).get("simpleText", ""),
            }
        )
    return videos


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
    for video in extract_video_items(items):
        if video["videoId"] not in seen:
            seen.add(video["videoId"])
            videos.append(video)
    return videos


def _first_continuation_token(items: list[dict]) -> str | None:
    return next((extract_continuation_token(i) for i in items if "continuationItemRenderer" in i), None)


async def get_channel_videos(channel_id: str, proxy: str = None, max_results: int = 100) -> list[dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    headers = get_youtube_headers()

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        tabs, videos_tab = await fetch_channel_tab(client, browse_url, channel_id, CHANNEL_TAB_VIDEOS, "/videos")
        if not tabs:
            raise YouTubeStructureChangedError(
                "twoColumnBrowseResultsRenderer.tabs not found for channel",
                context={"channel_id": channel_id},
            )

        if not videos_tab:
            home_tab = find_tab_by_url_suffix(tabs, "/featured")
            if not home_tab or "content" not in home_tab:
                raise YouTubeStructureChangedError(
                    "Neither 'Videos' nor 'Home' tab found for channel",
                    context={"channel_id": channel_id},
                )
            return extract_home_tab_videos(home_tab)[:max_results]

        section = videos_tab["content"].get("richGridRenderer", {}).get("contents", [])
        collected = extract_video_items(section)
        continuation = _first_continuation_token(section)

        while continuation and len(collected) < max_results:
            resp = await client.post(browse_url, json={"context": get_context(), "continuation": continuation})
            resp.raise_for_status()
            continuation_items = get_continuation_items(resp.json())
            if not continuation_items:
                break
            collected += extract_video_items(continuation_items)
            continuation = _first_continuation_token(continuation_items)

    return collected[:max_results]
