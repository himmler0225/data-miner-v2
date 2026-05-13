import random
from typing import List, Dict, Optional

from ..utils import (
    get_youtube_api_key, get_visitor_data, get_client_version,
    create_httpx_client, parse_view_count,
)
from ..config import get_youtube_headers, get_youtube_api_url
from ..config.constants import ENDPOINT_SEARCH, CLIENT_NAME
from ..exceptions import YouTubeStructureChangedError
from ..config.logging_config import get_logger

logger = get_logger(__name__)

# Timezone hint per country — makes the context more realistic
_GL_TIMEZONE = {
    "VN": "Asia/Ho_Chi_Minh",
    "TH": "Asia/Bangkok",
    "ID": "Asia/Jakarta",
    "SG": "Asia/Singapore",
    "PH": "Asia/Manila",
    "MY": "Asia/Kuala_Lumpur",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "CN": "Asia/Shanghai",
    "IN": "Asia/Kolkata",
    "AE": "Asia/Dubai",
    "EG": "Africa/Cairo",
    "GB": "Europe/London",
    "FR": "Europe/Paris",
    "DE": "Europe/Berlin",
    "RU": "Europe/Moscow",
    "US": "America/New_York",
    "CA": "America/Toronto",
    "MX": "America/Mexico_City",
    "BR": "America/Sao_Paulo",
    "AR": "America/Argentina/Buenos_Aires",
    "NG": "Africa/Lagos",
    "ZA": "Africa/Johannesburg",
    "AU": "Australia/Sydney",
}


def _get_region_context(gl: str, hl: str) -> dict:
    """
    InnerTube context with overridden gl/hl for geographic targeting.
    Only used by location.py — does not modify the shared get_context().
    """
    client: dict = {
        "hl": hl,
        "gl": gl,
        "clientName": CLIENT_NAME,
        "clientVersion": get_client_version(),
        "platform": "DESKTOP",
        "clientFormFactor": "UNKNOWN_FORM_FACTOR",
        "timeZone": _GL_TIMEZONE.get(gl, "America/New_York"),
        "screenWidthPoints": random.choice([1280, 1366, 1440, 1920]),
        "screenHeightPoints": random.choice([720, 768, 900, 1080]),
        "screenPixelDensity": random.choice([1, 2]),
    }
    visitor_data = get_visitor_data()
    if visitor_data:
        client["visitorData"] = visitor_data

    return {
        "client": client,
        "user": {"lockedSafetyMode": False},
        "request": {
            "useSsl": True,
            "internalExperimentFlags": [],
            "consistencyTokenJars": [],
        },
    }


def _extract_videos(items: List[Dict]) -> List[Dict]:
    results = []
    for item in items:
        # Handles both direct videoRenderer and richItemRenderer wrapper
        if "richItemRenderer" in item:
            content = item["richItemRenderer"].get("content", {})
        else:
            content = item
        video = content.get("videoRenderer")
        if not video:
            continue
        views_raw = (
            video.get("viewCountText", {}).get("simpleText", "")
            or video.get("shortViewCountText", {}).get("simpleText", "")
        )
        results.append({
            "video_id": video.get("videoId"),
            "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
            "channel_name": video.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
            "view_count": parse_view_count(views_raw),
            "published_time": video.get("publishedTimeText", {}).get("simpleText", ""),
            "url": f"https://www.youtube.com/watch?v={video.get('videoId')}",
        })
    return results


async def get_videos_by_region(
    gl: str,
    hl: str,
    query: str,
    proxy: Optional[str] = None,
    max_results: int = 50,
) -> List[Dict]:
    """
    Search YouTube with a specific country context (gl/hl) to get region-relevant results.
    Replaces the broken lat/lng approach — YouTube internal API ignores location/locationRadius.
    """
    api_key = await get_youtube_api_key(proxy=proxy)
    search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
    headers = get_youtube_headers()
    context = _get_region_context(gl, hl)

    collected: List[Dict] = []

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        resp = await client.post(search_url, json={"context": context, "query": query})
        resp.raise_for_status()
        data = resp.json()

        section_contents = (
            data
            .get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        if not section_contents:
            raise YouTubeStructureChangedError(
                "sectionListRenderer.contents not found in region search response",
                context={"gl": gl, "query": query, "top_keys": list(data.get("contents", {}).keys())},
            )

        continuation = None
        for section in section_contents:
            if "itemSectionRenderer" in section:
                items = section["itemSectionRenderer"].get("contents", [])
                collected.extend(_extract_videos(items))
            if "continuationItemRenderer" in section:
                continuation = (
                    section["continuationItemRenderer"]
                    .get("continuationEndpoint", {})
                    .get("continuationCommand", {})
                    .get("token")
                )

        while continuation and len(collected) < max_results:
            resp = await client.post(
                search_url,
                json={"context": context, "continuation": continuation},
            )
            resp.raise_for_status()
            data = resp.json()

            commands = data.get("onResponseReceivedCommands", [])
            continuation_items = (
                commands[0].get("appendContinuationItemsAction", {}).get("continuationItems", [])
                if commands else []
            )

            continuation = None
            for section in continuation_items:
                if "itemSectionRenderer" in section:
                    items = section["itemSectionRenderer"].get("contents", [])
                    collected.extend(_extract_videos(items))
                if "continuationItemRenderer" in section:
                    continuation = (
                        section["continuationItemRenderer"]
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {})
                        .get("token")
                    )

    # Deduplicate
    seen: set = set()
    unique: List[Dict] = []
    for v in collected:
        vid = v.get("video_id")
        if vid and vid not in seen:
            seen.add(vid)
            unique.append(v)

    logger.info(f"[location] gl={gl} query='{query}' → {len(unique)} videos")
    return unique[:max_results]
