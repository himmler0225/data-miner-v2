"""Canonical output shapes for YouTube items.

Every crawler builds its items through these helpers, so each kind of item has
the same snake_case keys whichever YouTube renderer it was parsed from.
Counts are ints (None when YouTube doesn't show one), times are YouTube's own
display text (relative, localized).
"""

from app.config.constants import YOUTUBE_BASE_URL
from app.crawlers.youtube.utils import format_duration, parse_count, parse_duration_seconds

from .parsers import get_first_badge_text, join_runs


def _fallback_thumbnails(video_id: str) -> list[dict]:
    return [{"url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"}]


def make_video(
    *,
    video_id: str,
    title: str = "",
    description: str = "",
    channel_id: str | None = None,
    channel_name: str = "",
    thumbnails: list[dict] | None = None,
    duration: str = "",
    duration_seconds: int | None = None,
    view_count: int | None = None,
    published_time: str = "",
    is_live: bool = False,
    is_short: bool = False,
) -> dict:
    path = f"/shorts/{video_id}" if is_short else f"/watch?v={video_id}"
    if duration_seconds is None:
        duration_seconds = parse_duration_seconds(duration)
    if not duration and not is_live:
        duration = format_duration(duration_seconds)
    return {
        "video_id": video_id,
        "url": f"{YOUTUBE_BASE_URL}{path}",
        "title": title,
        "description": description,
        "channel_id": channel_id or None,
        "channel_name": channel_name,
        "thumbnails": thumbnails or _fallback_thumbnails(video_id),
        "duration": duration,
        "duration_seconds": duration_seconds,
        "view_count": view_count,
        "published_time": published_time,
        "is_live": is_live,
        "is_short": is_short,
    }


def make_playlist(*, playlist_id: str, title: str = "", thumbnails: list[dict] | None = None, video_count=None) -> dict:
    return {
        "playlist_id": playlist_id,
        "url": f"{YOUTUBE_BASE_URL}/playlist?list={playlist_id}",
        "title": title,
        "thumbnails": thumbnails or [],
        "video_count": parse_count(video_count),
    }


def _byline_channel(video: dict) -> tuple[str | None, str]:
    for key in ("ownerText", "shortBylineText", "longBylineText"):
        node = video.get(key)
        if node:
            runs = node.get("runs") or [{}]
            channel_id = runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId")
            return channel_id, join_runs(node)
    return None, ""


def _is_live_renderer(video: dict) -> bool:
    for badge in video.get("badges", []):
        if badge.get("metadataBadgeRenderer", {}).get("style") == "BADGE_STYLE_TYPE_LIVE_NOW":
            return True
    for overlay in video.get("thumbnailOverlays", []):
        if overlay.get("thumbnailOverlayTimeStatusRenderer", {}).get("style") == "LIVE":
            return True
    return False


def video_from_renderer(video: dict) -> dict | None:
    """`videoRenderer` / `gridVideoRenderer` (search results, older channel grids)."""
    video_id = video.get("videoId")
    if not video_id:
        return None
    channel_id, channel_name = _byline_channel(video)
    snippets = video.get("detailedMetadataSnippets") or [{}]
    description = join_runs(snippets[0].get("snippetText", {})) or join_runs(video.get("descriptionSnippet", {}))
    duration = join_runs(video.get("lengthText", {}))
    if not duration:
        for overlay in video.get("thumbnailOverlays", []):
            duration = join_runs(overlay.get("thumbnailOverlayTimeStatusRenderer", {}).get("text", {}))
            if duration:
                break
    views = join_runs(video.get("viewCountText", {})) or join_runs(video.get("shortViewCountText", {}))
    is_live = _is_live_renderer(video)
    return make_video(
        video_id=video_id,
        title=join_runs(video.get("title", {})),
        description=description,
        channel_id=channel_id,
        channel_name=channel_name,
        thumbnails=video.get("thumbnail", {}).get("thumbnails"),
        duration="" if is_live else duration,
        view_count=parse_count(views),
        published_time=join_runs(video.get("publishedTimeText", {})),
        is_live=is_live,
    )


def video_from_lockup(lockup: dict) -> dict | None:
    """`lockupViewModel` of a video (channel grids and Home shelves)."""
    if lockup.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None
    video_id = lockup.get("contentId")
    if not video_id:
        return None
    metadata_vm = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = metadata_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    # Channel-grid lockups have a single [views, published] row; lockups that also
    # show the channel name put it in an earlier row, so views/date is the last row.
    rows = [row for row in rows if row.get("metadataParts")]
    parts = rows[-1]["metadataParts"] if rows else []
    views = parts[0].get("text", {}).get("content", "") if len(parts) > 0 else ""
    published = parts[1].get("text", {}).get("content", "") if len(parts) > 1 else ""
    thumbnail_vm = lockup.get("contentImage", {}).get("thumbnailViewModel", {})
    return make_video(
        video_id=video_id,
        title=metadata_vm.get("title", {}).get("content", ""),
        thumbnails=thumbnail_vm.get("image", {}).get("sources"),
        duration=get_first_badge_text(thumbnail_vm.get("overlays", [])),
        view_count=parse_count(views),
        published_time=published,
    )


def video_from_playlist_renderer(renderer: dict) -> dict | None:
    """`playlistVideoRenderer` (items of a playlist)."""
    video_id = renderer.get("videoId")
    if not video_id:
        return None
    channel_id, channel_name = _byline_channel(renderer)
    # videoInfo runs: ["1,2 Tr lượt xem", " • ", "2 năm trước"]
    info = [r.get("text", "") for r in renderer.get("videoInfo", {}).get("runs", []) if r.get("text", "").strip(" •")]
    return make_video(
        video_id=video_id,
        title=join_runs(renderer.get("title", {})),
        channel_id=channel_id,
        channel_name=channel_name,
        thumbnails=renderer.get("thumbnail", {}).get("thumbnails"),
        duration=join_runs(renderer.get("lengthText", {})),
        duration_seconds=parse_duration_seconds(renderer.get("lengthSeconds")),
        view_count=parse_count(info[0]) if info else None,
        published_time=info[1] if len(info) > 1 else "",
    )


def extract_videos(items: list[dict]) -> list[dict]:
    """Videos from a list of grid/section entries, whatever renderer each uses.
    Entries that aren't videos (shelves, continuations, playlists, ads) are skipped."""
    videos = []
    for item in items:
        content = item.get("richItemRenderer", {}).get("content", {}) or item
        if "lockupViewModel" in content:
            video = video_from_lockup(content["lockupViewModel"])
        elif "playlistVideoRenderer" in content:
            video = video_from_playlist_renderer(content["playlistVideoRenderer"])
        else:
            renderer = content.get("videoRenderer") or content.get("gridVideoRenderer")
            video = video_from_renderer(renderer) if renderer else None
        if video:
            videos.append(video)
    return videos


def playlist_from_lockup(lockup: dict) -> dict | None:
    """`lockupViewModel` of a playlist (a channel's Playlists tab)."""
    playlist_id = lockup.get("contentId")
    if not playlist_id or lockup.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO":
        return None
    thumbnail_vm = (
        lockup.get("contentImage", {})
        .get("collectionThumbnailViewModel", {})
        .get("primaryThumbnail", {})
        .get("thumbnailViewModel", {})
    )
    return make_playlist(
        playlist_id=playlist_id,
        title=lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content", ""),
        thumbnails=thumbnail_vm.get("image", {}).get("sources"),
        video_count=get_first_badge_text(thumbnail_vm.get("overlays", [])),
    )
