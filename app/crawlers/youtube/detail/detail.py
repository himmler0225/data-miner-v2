import json
from typing import Optional

from app.config.constants import (CLIENT_GL, CLIENT_HL, ENDPOINT_PLAYER,
                                  YOUTUBE_BASE_URL)
from app.config.headers import get_youtube_headers
from app.config.logger import Logger
from app.crawlers.youtube.client import (create_httpx_client, get_context,
                                         get_youtube_api_key, get_youtube_api_url)
from app.crawlers.youtube.utils import parse_view_count

logger = Logger.get(__name__)


def _extract_player_response(html: str) -> Optional[dict]:
    """
    Parse ytInitialPlayerResponse from YouTube watch page HTML.
    Uses brace-counting to extract the JSON blob reliably.
    """
    idx = html.find("ytInitialPlayerResponse")
    if idx == -1:
        return None
    start = html.find("{", idx)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


async def _get_via_watch_page(video_id: str, proxy: str = None) -> Optional[dict]:
    headers = get_youtube_headers()
    params = {"v": video_id, "hl": CLIENT_HL, "gl": CLIENT_GL}
    async with create_httpx_client(proxy=proxy, headers=headers, timeout=15) as client:
        resp = await client.get(f"{YOUTUBE_BASE_URL}/watch", params=params)
    if resp.status_code != 200:
        logger.warning(
            "[detail] watch_page HTTP %s for %s", resp.status_code, video_id
        )
        return None
    data = _extract_player_response(resp.text)
    if not data:
        logger.warning(
            "[detail] watch_page: ytInitialPlayerResponse not found for %s", video_id
        )
        return None
    return data


async def _get_via_api(video_id: str, proxy: str = None) -> Optional[dict]:
    try:
        api_key = await get_youtube_api_key(proxy=proxy)
    except Exception as e:
        logger.warning("[detail] API key failed: %s", e)
        return None
    url = get_youtube_api_url(ENDPOINT_PLAYER, api_key)
    headers = get_youtube_headers()
    payload = {
        "context": get_context(),
        "videoId": video_id,
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    async with create_httpx_client(proxy=proxy, headers=headers, timeout=10) as client:
        resp = await client.post(url, json=payload)
    if resp.status_code != 200:
        logger.warning("[detail] API HTTP %s for %s", resp.status_code, video_id)
        return None
    return resp.json()


def _parse_player_response(data: dict, video_id: str) -> dict:
    status = data.get("playabilityStatus", {})
    yt_status = status.get("status")
    if yt_status != "OK":
        return {
            "error": True,
            "reason": status.get("reason", "Unavailable"),
            "status": yt_status,
        }

    video_details = data.get("videoDetails", {})
    streaming_data = data.get("streamingData", {})
    microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {})
    description = (
        video_details.get("shortDescription")
        or microformat.get("description", {}).get("simpleText")
        or ""
    )
    thumbnails = video_details.get("thumbnail", {}).get("thumbnails", [])
    if not thumbnails:
        vid = video_details.get("videoId") or video_id
        thumbnails = [{"url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}]

    return {
        "video_id": video_details.get("videoId") or video_id,
        "title": video_details.get("title"),
        "author": video_details.get("author"),
        "channel_id": video_details.get("channelId") or None,
        "description": description,
        "length_seconds": video_details.get("lengthSeconds"),
        "views": parse_view_count(video_details.get("viewCount")),
        "is_live_content": video_details.get("isLiveContent"),
        "thumbnails": thumbnails,
        "formats": streaming_data.get("formats", []),
        "adaptive_formats": streaming_data.get("adaptiveFormats", []),
        "keywords": video_details.get("keywords", []),
        "category": microformat.get("category", ""),
        "publish_date": microformat.get("publishDate", ""),
    }


async def get_video_detail(video_id: str, proxy: str = None) -> dict:
    data = await _get_via_watch_page(video_id, proxy=proxy)
    result = (
        _parse_player_response(data, video_id)
        if data
        else {"error": True, "status": None}
    )

    if result.get("error"):
        logger.info(
            "[detail] watch_page blocked, trying API%s, trying player API for %s",
            result.get("status"),
            video_id,
        )
        api_data = await _get_via_api(video_id, proxy=proxy)
        if api_data:
            result = _parse_player_response(api_data, video_id)

    if result.get("error"):
        logger.warning(
            "[detail] both methods failed for %s (status=%s)",
            video_id,
            result.get("status"),
        )

    return result
