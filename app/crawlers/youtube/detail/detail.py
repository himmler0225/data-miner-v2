import json

from app.config.constants import CLIENT_GL, CLIENT_HL, ENDPOINT_PLAYER, YOUTUBE_BASE_URL
from app.config.headers import get_youtube_headers
from app.config.logger import Logger
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url
from app.crawlers.youtube.utils import parse_count, parse_duration_seconds
from app.exceptions import CrawlNetworkError, YouTubeNotFoundError

from ..shared.models import make_video

logger = Logger.get(__name__)


def _extract_player_response(html: str) -> dict | None:
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


async def _get_via_watch_page(video_id: str, proxy: str = None) -> dict | None:
    headers = get_youtube_headers()
    params = {"v": video_id, "hl": CLIENT_HL, "gl": CLIENT_GL}
    async with create_httpx_client(proxy=proxy, headers=headers, timeout=15) as client:
        resp = await client.get(f"{YOUTUBE_BASE_URL}/watch", params=params)
    if resp.status_code != 200:
        logger.warning("[detail] watch_page HTTP %s for %s", resp.status_code, video_id)
        return None
    data = _extract_player_response(resp.text)
    if not data:
        logger.warning("[detail] watch_page: ytInitialPlayerResponse not found for %s", video_id)
        return None
    return data


async def _get_via_api(video_id: str, proxy: str = None) -> dict | None:
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
    video_details = data.get("videoDetails", {})
    streaming_data = data.get("streamingData", {})
    microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {})
    description = video_details.get("shortDescription") or microformat.get("description", {}).get("simpleText") or ""
    return {
        **make_video(
            video_id=video_details.get("videoId") or video_id,
            title=video_details.get("title", ""),
            description=description,
            channel_id=video_details.get("channelId"),
            channel_name=video_details.get("author", ""),
            thumbnails=video_details.get("thumbnail", {}).get("thumbnails"),
            duration_seconds=parse_duration_seconds(video_details.get("lengthSeconds")),
            view_count=parse_count(video_details.get("viewCount")),
            published_time=microformat.get("publishDate", ""),
            is_live=bool(video_details.get("isLive")),
            is_short=False,
        ),
        "is_live_content": bool(video_details.get("isLiveContent")),
        "keywords": video_details.get("keywords", []),
        "category": microformat.get("category", ""),
        "formats": streaming_data.get("formats", []),
        "adaptive_formats": streaming_data.get("adaptiveFormats", []),
    }


def _playability(data: dict | None) -> tuple[str | None, str]:
    status = (data or {}).get("playabilityStatus", {})
    return status.get("status"), status.get("reason", "")


async def get_video_detail(video_id: str, proxy: str | None = None) -> dict:
    """Full metadata of one video (watch page first, player API as fallback).

    Raises YouTubeNotFoundError when YouTube reports the video unplayable
    (removed, private, age/login-gated), CrawlNetworkError when neither source
    returned a player response at all."""
    data = await _get_via_watch_page(video_id, proxy=proxy)
    status, reason = _playability(data)
    if status != "OK":
        logger.info("[detail] watch page gave status=%s for %s, trying player API", status, video_id)
        api_data = await _get_via_api(video_id, proxy=proxy)
        if api_data:
            data = api_data
            status, reason = _playability(api_data)

    if status == "OK":
        return _parse_player_response(data, video_id)
    if status is None:
        raise CrawlNetworkError(f"Could not fetch a player response for video {video_id}")
    raise YouTubeNotFoundError(f"Video {video_id} is not available ({status}): {reason or 'no reason given'}")
