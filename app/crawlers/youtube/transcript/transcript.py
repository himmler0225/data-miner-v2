from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from app.config.logger import Logger

logger = Logger.get(__name__)

# Preferred language order for Vietnamese product review content
_LANG_PRIORITY = ["vi", "en", "a.vi", "a.en"]  # a.* = auto-generated


def _fetch_sync(video_id: str) -> Optional[Dict]:
    """Runs in a thread — youtube-transcript-api is synchronous."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

        api = YouTubeTranscriptApi()
        print(api)

        # List available transcripts
        try:
            transcript_list = api.list(video_id)
        except TranscriptsDisabled:
            logger.info("🟡 [transcript] disabled for %s", video_id)
            return None

        # Try preferred languages first
        for lang in _LANG_PRIORITY:
            try:
                transcript = transcript_list.find_transcript([lang])
                segments   = transcript.fetch()
                text       = " ".join(s.text for s in segments).strip()
                return {
                    "video_id":   video_id,
                    "language":   transcript.language_code,
                    "text":       text,
                    "char_count": len(text),
                    "segments":   len(segments),
                }
            except (NoTranscriptFound, Exception):
                continue

        # Last resort: use the first available transcript
        try:
            first    = next(iter(transcript_list))
            segments = first.fetch()
            text     = " ".join(s.text for s in segments).strip()
            return {
                "video_id":   video_id,
                "language":   first.language_code,
                "text":       text,
                "char_count": len(text),
                "segments":   len(segments),
            }
        except Exception:
            return None

    except Exception as e:
        logger.warning("🔴 [transcript] %s — %s", video_id, e)
        return None


async def get_transcript(video_id: str) -> Optional[Dict]:
    """Async wrapper around the synchronous youtube-transcript-api."""
    result = await asyncio.to_thread(_fetch_sync, video_id)
    if result:
        logger.info("🟢 [transcript] %s — lang=%s chars=%d",
                    video_id, result["language"], result["char_count"])
    return result


async def get_transcript_batch(
    video_ids: List[str],
    concurrency: int = 3,
) -> Dict[str, Optional[Dict]]:
    """Fetch transcripts for multiple videos in parallel."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(vid: str):
        async with sem:
            return vid, await get_transcript(vid)

    pairs = await asyncio.gather(*[_one(v) for v in video_ids])
    results = {vid: data for vid, data in pairs}
    found = sum(1 for v in results.values() if v)
    logger.info("🟢 [transcript/batch] %d/%d videos have transcripts",
                found, len(video_ids))
    return results
