"""
Client gửi data crawl đến youtube-api qua internal HTTP API.

Tất cả requests đều kèm header X-Service-Key để xác thực.
Lỗi HTTP được log cảnh báo nhưng không raise — crawl vẫn tiếp tục
dù ingest thất bại (data sẽ được crawl lại ở lần sau).
"""
import os
import httpx
from typing import Dict, List, Optional
from app.config.logging_config import get_logger
from app.types import ChannelInfo, SearchVideo, Comment

logger = get_logger(__name__)

INGEST_API_URL = os.getenv("INGEST_API_URL", "http://localhost:3000")
INGEST_SERVICE_KEY = os.getenv("INGEST_SERVICE_KEY", "")

_HEADERS = {
    "X-Service-Key": INGEST_SERVICE_KEY,
    "Content-Type": "application/json",
}


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=INGEST_API_URL, headers=_HEADERS, timeout=30)


def _safe_int(value) -> Optional[int]:
    """Parse int from possibly comma-formatted strings like '1,234,567'."""
    if value is None:
        return None
    cleaned = "".join(c for c in str(value) if c.isdigit())
    return int(cleaned) if cleaned else None


async def ingest_channel(data: ChannelInfo) -> bool:
    """Gửi thông tin channel lên API. Trả về True nếu thành công."""
    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/channel", json=data)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_channel failed: {e!r}")
            return False


async def ingest_search(
    query: str,
    videos: List[SearchVideo],
    sort: str = "relevance",
) -> bool:
    """Gửi kết quả tìm kiếm. Trả về True nếu thành công."""
    valid_videos = [v for v in videos if v.get("video_id")]
    if not valid_videos:
        return True
    payload = {"query": query, "sort": sort, "videos": valid_videos}

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/search", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_search failed (query='{query}'): {e!r}")
            return False


async def ingest_detail(
    video_id: str,
    detail: dict,
) -> bool:
    """
    Gửi chi tiết video. `detail` là dict từ get_video_detail():
    - Thành công: VideoDetail (có title, author, views...)
    - Lỗi: VideoDetailError (có error=True, reason, status)
    """
    if detail.get("error"):
        payload = {
            "video_id": video_id,
            "error": True,
            "reason": detail.get("reason"),
        }
    else:
        payload = {
            "video_id": video_id,
            "title": detail.get("title"),
            "author": detail.get("author"),
            "views": _safe_int(detail.get("views")),
            "length_seconds": _safe_int(detail.get("length_seconds")),
            "is_live_content": detail.get("is_live_content", False),
        }

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/detail", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_detail failed (video_id={video_id}): {e!r}")
            return False


async def ingest_trending(
    videos: List[Dict],
    category: Optional[str] = None,
) -> bool:
    """Gửi danh sách video trending. Trả về True nếu thành công."""
    valid_videos = [v for v in videos if v.get("video_id")]
    if not valid_videos:
        return True
    payload: Dict = {"videos": valid_videos}
    if category:
        payload["category"] = category

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/trending", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"ingest_trending failed (category={category!r}): {e!r}")
            return False


async def ingest_comments(
    video_id: str,
    comments: List[Comment],
) -> bool:
    """Gửi danh sách comment của video. Trả về True nếu thành công."""
    payload = {"video_id": video_id, "comments": comments}

    async with _make_client() as client:
        try:
            resp = await client.post("/internal/ingest/comments", json=payload)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.warning(
                f"ingest_comments failed (video_id={video_id}, "
                f"count={len(comments)}): {e!r}"
            )
            return False
