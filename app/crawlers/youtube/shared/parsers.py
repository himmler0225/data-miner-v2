from typing import Dict, List, Optional


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
        commands[0]
        .get("appendContinuationItemsAction", {})
        .get("continuationItems", [])
    ) if commands else []


def parse_video_renderer(video: dict) -> Dict:
    from ....utils import parse_view_count
    owner_runs = video.get("ownerText", {}).get("runs", [{}])
    views_raw = (
        video.get("viewCountText", {}).get("simpleText", "")
        or video.get("shortViewCountText", {}).get("simpleText", "")
    )
    video_id = video.get("videoId")
    return {
        "video_id": video_id,
        "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
        "channel": owner_runs[0].get("text", ""),
        "channel_id": get_channel_id_from_owner(video),
        "view_count": parse_view_count(views_raw),
        "duration": video.get("lengthText", {}).get("simpleText", ""),
        "published_time": video.get("publishedTimeText", {}).get("simpleText", ""),
        "thumbnails": video.get("thumbnail", {}).get("thumbnails", []),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
