"""
TikHub API client (tikhub.io) — replaces SociaVault.
Endpoints: /api/v1/tiktok/...
Auth: Authorization: Bearer <TIKAP_API_KEY>
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.config.logger import Logger
from app.config.settings import TIKAP_API_KEY

logger = Logger.get(__name__)

_BASE = "https://api.tikhub.io"
_HEADERS = {"Authorization": f"Bearer {TIKAP_API_KEY}"}

_http: Optional[httpx.AsyncClient] = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            base_url=_BASE,
            headers=_HEADERS,
            timeout=20,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http


# ── Search ────────────────────────────────────────────────────────────────────

async def search_videos(
    keyword: str,
    cursor: int = 0,
    count: int = 20,
    sort_type: int = 0,  # 0=relevance, 1=most-liked
) -> Dict:
    r = await _client().get(
        "/api/v1/tiktok/app/v3/fetch_video_search_result",
        params={"keyword": keyword, "cursor": cursor, "count": count, "sort_type": sort_type},
    )
    r.raise_for_status()
    logger.info("🟡 [tikhub] search keyword=%r cursor=%d", keyword, cursor)
    return r.json()


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


# ── Video info ────────────────────────────────────────────────────────────────

async def get_video_info(url: str) -> Dict:
    r = await _client().get(
        "/api/v1/tiktok/app/v3/fetch_one_video_by_share_url",
        params={"share_url": url},
    )
    r.raise_for_status()
    logger.info("🟡 [tikhub] video-info url=%s", url[:60])
    return r.json()


# ── Comments ──────────────────────────────────────────────────────────────────

async def get_comments(aweme_id: str, cursor: int = 0, count: int = 20) -> Dict:
    r = await _client().get(
        "/api/v1/tiktok/app/v3/fetch_video_comments",
        params={"aweme_id": aweme_id, "cursor": cursor, "count": count},
    )
    r.raise_for_status()
    logger.info("🟡 [tikhub] comments aweme_id=%s cursor=%d", aweme_id, cursor)
    return r.json()


def format_comments(raw: Dict) -> List[Dict]:
    data     = raw.get("data") or {}
    comments = data.get("comments") or []
    return [
        {
            "comment_id":    c.get("cid"),
            "content":       (c.get("text") or ""),
            "author":        (c.get("user") or {}).get("nickname", ""),
            "likes":         c.get("digg_count", 0),
            "replies_count": c.get("reply_comment_total", 0),
            "published_time": str(c.get("create_time", "")),
        }
        for c in comments
        if c.get("cid")
    ]


# ── Profile ───────────────────────────────────────────────────────────────────

async def get_profile(unique_id: str) -> Dict:
    r = await _client().get(
        "/api/v1/tiktok/web/fetch_user_profile",
        params={"unique_id": unique_id},
    )
    r.raise_for_status()
    logger.info("🟡 [tikhub] profile unique_id=%s", unique_id)
    return r.json()


# ── Internal formatter ────────────────────────────────────────────────────────

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
