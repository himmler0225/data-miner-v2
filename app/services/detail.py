import json
from typing import Optional
from ..utils import create_httpx_client, get_youtube_api_key, get_context, parse_view_count
from ..config import get_youtube_headers, get_youtube_api_url
from ..config.constants import ENDPOINT_PLAYER, CLIENT_HL, CLIENT_GL
from ..config.logging_config import get_logger

logger = get_logger(__name__)

YOUTUBE_WATCH_URL = "https://www.youtube.com/watch"


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
                    return json.loads(html[start: i + 1])
                except json.JSONDecodeError:
                    return None
    return None


async def _get_via_watch_page(video_id: str, proxy: str = None) -> Optional[dict]:
    """
    Primary method: GET youtube.com/watch like a real browser.
    Returns raw ytInitialPlayerResponse dict, or None on failure.
    """
    headers = get_youtube_headers()
    params = {"v": video_id, "hl": CLIENT_HL, "gl": CLIENT_GL}

    async with create_httpx_client(proxy=proxy, headers=headers, timeout=15) as client:
        resp = await client.get(YOUTUBE_WATCH_URL, params=params)

    if resp.status_code != 200:
        logger.warning(f"[detail/watch_page] HTTP {resp.status_code} for {video_id}")
        return None

    data = _extract_player_response(resp.text)
    if not data:
        logger.warning(f"[detail/watch_page] ytInitialPlayerResponse not found for {video_id}")
        return None

    return data


async def _get_via_api(video_id: str, proxy: str = None) -> Optional[dict]:
    """
    Fallback method: POST to /youtubei/v1/player with WEB client + extracted key.
    Works for most public videos when watch page is blocked by consent wall.
    """
    try:
        api_key = await get_youtube_api_key(proxy=proxy)
    except Exception as e:
        logger.warning(f"[detail/api] Failed to get API key: {e!r}")
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
        logger.warning(f"[detail/api] HTTP {resp.status_code} for {video_id}")
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
    return {
        "video_id": video_details.get("videoId") or video_id,
        "title": video_details.get("title"),
        "author": video_details.get("author"),
        "length_seconds": video_details.get("lengthSeconds"),
        "views": parse_view_count(video_details.get("viewCount")),
        "is_live_content": video_details.get("isLiveContent"),
        "formats": streaming_data.get("formats", []),
        "adaptive_formats": streaming_data.get("adaptiveFormats", []),
    }


async def get_video_detail(video_id: str, proxy: str = None) -> dict:
    # Try watch page first (most reliable — no API key, real browser fingerprint)
    data = await _get_via_watch_page(video_id, proxy=proxy)

    if data is None:
        logger.info(f"[detail] watch_page failed, falling back to API for {video_id}")
        data = await _get_via_api(video_id, proxy=proxy)

    if data is None:
        logger.error(f"[detail] All methods failed for {video_id}")
        return {"error": True, "reason": "All methods failed", "status": "UNAVAILABLE"}

    result = _parse_player_response(data, video_id)

    if result.get("error"):
        status = result.get("status")
        # LOGIN_REQUIRED on watch page → try API (different client context)
        if status == "LOGIN_REQUIRED":
            logger.info(f"[detail] LOGIN_REQUIRED via watch_page, trying API for {video_id}")
            api_data = await _get_via_api(video_id, proxy=proxy)
            if api_data:
                result = _parse_player_response(api_data, video_id)

    logger.debug(f"[detail] {video_id} → error={result.get('error')} status={result.get('status')}")
    return result
