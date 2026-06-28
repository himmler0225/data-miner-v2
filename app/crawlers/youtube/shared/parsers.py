from typing import Dict, List, Optional

from app.config.constants import YOUTUBE_BASE_URL
from app.crawlers.youtube.utils import parse_view_count


def join_runs(node: dict) -> str:
    """Concatenate all `runs[].text` — YouTube splits text at styled/bolded spans."""
    runs = node.get("runs") if isinstance(node, dict) else None
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return node.get("simpleText", "") if isinstance(node, dict) else ""


def get_channel_id_from_owner(video: dict) -> Optional[str]:
    owner_runs = video.get("ownerText", {}).get("runs", [{}])
    return (
        owner_runs[0]
        .get("navigationEndpoint", {})
        .get("browseEndpoint", {})
        .get("browseId")
    )


def extract_continuation_token(item: dict) -> Optional[str]:
    return (
        item.get("continuationItemRenderer", {})
        .get("continuationEndpoint", {})
        .get("continuationCommand", {})
        .get("token")
    )


def get_continuation_items(data: dict) -> List[dict]:
    commands = (
        data.get("onResponseReceivedCommands")
        or data.get("onResponseReceivedActions")
        or []
    )
    return (
        (
            commands[0]
            .get("appendContinuationItemsAction", {})
            .get("continuationItems", [])
        )
        if commands
        else []
    )


def parse_video_renderer(video: dict) -> Dict:
    views_raw = video.get("viewCountText", {}).get("simpleText", "") or video.get(
        "shortViewCountText", {}
    ).get("simpleText", "")
    video_id = video.get("videoId")
    return {
        "video_id": video_id,
        "title": join_runs(video.get("title", {})),
        "channel": join_runs(video.get("ownerText", {})),
        "channel_id": get_channel_id_from_owner(video),
        "view_count": parse_view_count(views_raw),
        "duration": video.get("lengthText", {}).get("simpleText", ""),
        "published_time": video.get("publishedTimeText", {}).get("simpleText", ""),
        "thumbnails": video.get("thumbnail", {}).get("thumbnails", []),
        "url": f"{YOUTUBE_BASE_URL}/watch?v={video_id}",
    }
