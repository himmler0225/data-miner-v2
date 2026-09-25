import asyncio

import requests
from youtube_transcript_api import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from app.config.logger import Logger
from app.exceptions import CrawlNetworkError, YouTubeNotFoundError

logger = Logger.get(__name__)

# Preferred caption languages; find_transcript() tries manual captions before
# auto-generated ones for each. Falls back to whatever language exists.
_LANG_PRIORITY = ["vi", "en"]

_VIDEO_UNAVAILABLE = (VideoUnavailable, InvalidVideoId, VideoUnplayable, AgeRestricted)


def _result(video_id: str, *, reason: str | None = None, language=None, segments=None) -> dict:
    text = " ".join(s.text for s in segments).strip() if segments is not None else None
    return {
        "video_id": video_id,
        "available": text is not None,
        "reason": reason,
        "language": language,
        "text": text,
        "char_count": len(text) if text is not None else 0,
        "segment_count": len(segments) if segments is not None else 0,
    }


def _fetch_sync(video_id: str, proxy_url: str | None) -> dict:
    proxy_config = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url) if proxy_url else None
    api = YouTubeTranscriptApi(proxy_config=proxy_config)
    try:
        transcripts = api.list(video_id)
        try:
            transcript = transcripts.find_transcript(_LANG_PRIORITY)
        except NoTranscriptFound:
            transcript = next(iter(transcripts), None)
        if transcript is None:
            return _result(video_id, reason="no_transcript")
        return _result(video_id, language=transcript.language_code, segments=transcript.fetch())
    except TranscriptsDisabled:
        return _result(video_id, reason="disabled")
    except _VIDEO_UNAVAILABLE as exc:
        raise YouTubeNotFoundError(f"Video {video_id} is not available: {type(exc).__name__}") from exc
    except (CouldNotRetrieveTranscript, requests.RequestException) as exc:
        # RequestBlocked / IpBlocked / YouTubeRequestFailed / PoTokenRequired, or a
        # network/proxy failure in the `requests` session the library uses.
        raise CrawlNetworkError(f"Transcript request failed for {video_id}: {type(exc).__name__}") from exc


async def get_transcript(video_id: str, proxy: str | None = None) -> dict:
    """Transcript of one video. `available=False` with a `reason` ("disabled",
    "no_transcript") when the video has no captions; raises YouTubeNotFoundError
    for unavailable videos and CrawlNetworkError when YouTube blocks the request."""
    result = await asyncio.to_thread(_fetch_sync, video_id, proxy)
    if result["available"]:
        logger.info("[transcript] %s lang=%s chars=%d", video_id, result["language"], result["char_count"])
    else:
        logger.info("[transcript] %s not available (%s)", video_id, result["reason"])
    return result
