from __future__ import annotations
from typing import Dict, List, Optional

import urllib.parse
import httpx

from app.config.logger import Logger
import app.config.settings as _s
from app.config.constants import TIKHUB_TIMEOUT, TIKHUB_MAX_CONN, TIKHUB_MAX_KEEPALIVE
from app.exceptions import TikHubError

logger = Logger.get(__name__)

_BASE = "https://api.tikhub.io"

_http: Optional[httpx.AsyncClient] = None


def _get_headers() -> dict:
    return {"Authorization": f"Bearer {_s.TIKAP_API_KEY}"}


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            base_url=_BASE,
            timeout=TIKHUB_TIMEOUT,
            limits=httpx.Limits(max_connections=TIKHUB_MAX_CONN, max_keepalive_connections=TIKHUB_MAX_KEEPALIVE),
        )
    return _http


async def _get(path: str, params: dict = None) -> Dict:
    try:
        r = await _client().get(path, params=params or {}, headers=_get_headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise TikHubError(f"TikHub {e.response.status_code} on {path}") from e
    except httpx.TimeoutException as e:
        raise TikHubError(f"TikHub timeout on {path}") from e
    except httpx.NetworkError as e:
        raise TikHubError(f"TikHub network error on {path}") from e


async def search_videos(
    keyword: str,
    cursor: int = 0,
    count: int = 20,
    sort_type: int = 0,
) -> Dict:
    query = urllib.parse.urlencode(
        {"keyword": keyword, "cursor": cursor, "count": count, "sort_type": sort_type},
        quote_via=urllib.parse.quote
    )
    result = await _get(f"/api/v1/tiktok/app/v3/fetch_video_search_result?{query}")
    logger.info("🟡 [tikhub] search keyword=%r cursor=%d", keyword, cursor)
    return result

def format_search(raw: Dict) -> Dict:
    data   = raw.get("data") or {}
    items  = data.get("aweme_list") or []
    videos = [_fmt_video(v) for v in items if v.get("aweme_id")]
    return {
        "success":  bool(videos),
        "count":    len(videos),
        "has_more": bool(data.get("has_more")),
        "cursor":   data.get("cursor", 0),
        "videos":   videos,
        "source":   "tikhub",
    }

async def get_video_info(url: str) -> Dict:
    result = await _get("/api/v1/tiktok/app/v3/fetch_one_video_by_share_url", {"share_url": url})
    logger.info("🟡 [tikhub] video-info url=%s", url[:60])
    return result

async def get_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> Dict:
    result = await _get("/api/v1/tiktok/app/v3/fetch_video_comments",
                        {"aweme_id": aweme_id, "cursor": cursor, "count": count})
    logger.info("🟡 [tikhub] comments aweme_id=%s cursor=%d", aweme_id, cursor)
    return result

def format_comments(raw: Dict) -> List[Dict]:
    data     = raw.get("data") or {}
    comments = data.get("comments") or []
    return [
        {
            "comment_id":     c.get("cid"),
            "content":        (c.get("text") or ""),
            "author":         (c.get("user") or {}).get("nickname", ""),
            "likes":          c.get("digg_count", 0),
            "replies_count":  c.get("reply_comment_total", 0),
            "published_time": str(c.get("create_time", "")),
        }
        for c in comments
        if c.get("cid")
    ]

async def get_profile(unique_id: str) -> Dict:
    result = await _get("/api/v1/tiktok/web/fetch_user_profile", {"unique_id": unique_id})
    logger.info("🟡 [tikhub] profile unique_id=%s", unique_id)
    return result


async def get_transcript(aweme_id: str) -> Dict:
    result = await _get("/api/v1/tiktok/app/v3/fetch_video_caption", {"aweme_id": aweme_id})
    logger.info("🟡 [tikhub] transcript aweme_id=%s", aweme_id)
    return result


def format_transcript(raw: Dict) -> Optional[Dict]:
    data     = raw.get("data") or {}
    captions = data.get("caption_info_list") or []
    if not captions:
        return None
    for lang in ("vie", "eng"):
        cap = next((c for c in captions if c.get("language_code") == lang), None)
        if cap:
            break
    else:
        cap = captions[0]

    text = cap.get("caption_text") or ""
    vid = data.get("aweme_id", "")
    return {
        "aweme_id":   vid,
        "language":   cap.get("language_code", ""),
        "text":       text,
        "char_count": len(text),
        "available":  bool(text),
    }


def _fmt_video(v: Dict) -> Dict:
    author = v.get("author") or {}
    stats  = v.get("statistics") or {}
    music  = v.get("music") or {}
    vid    = v.get("video") or {}
    tags   = [t["hashtag_name"] for t in v.get("text_extra", [])
              if isinstance(t, dict) and t.get("hashtag_name")]
    uid    = author.get("unique_id") or "_"

    def _cover(obj: Dict) -> Optional[str]:
        urls = (obj or {}).get("url_list") or []
        return urls[0] if urls else None

    return {
        "video_id":    v.get("aweme_id"),
        "desc":        v.get("desc", ""),
        "create_time": v.get("create_time"),
        "url":         f"https://www.tiktok.com/@{uid}/video/{v.get('aweme_id')}",
        "cover":       _cover(vid.get("cover")),
        "duration":    vid.get("duration"),
        "author": {
            "id":        author.get("uid"),
            "sec_uid":   author.get("sec_uid"),
            "unique_id": uid,
            "nickname":  author.get("nickname"),
            "avatar":    _cover(author.get("avatar_thumb")),
        },
        "stats": {
            "play":    stats.get("play_count"),
            "like":    stats.get("digg_count"),
            "comment": stats.get("comment_count"),
            "share":   stats.get("share_count"),
            "collect": stats.get("collect_count"),
        },
        "music": {"title": music.get("title"), "author": music.get("author")},
        "tags":  tags,
    }
