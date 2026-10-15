"""Live checks for the YouTube endpoints and crawlers, against real YouTube.

Everything network-dependent here is marked `integration`; deselect with
`-m "not integration"` for an offline run. Hermetic coverage of the same code
lives in test_youtube_parsers.py (parsing + crawler pages), test_youtube_service.py
(paging, validation, errors) and test_youtube_api.py (routes).

- TestYoutubeRoutesRequireAuth: hermetic, every route rejects a missing API key.
- TestYoutubeRoutesAreWired: each route reaches its crawler. Accepts 200 or an
  upstream error (502/503: live YouTube or proxy-pool hiccup), never 500 (a bug).
- TestLiveCrawlers: crawler page functions called directly with proxy=None
  (bypassing the proxy pool), asserting real parsing on the first page and on a
  continuation page.
"""

import pytest
from fastapi import status

pytestmark = pytest.mark.api

# Real, stable ids used to prove the routes/crawlers work end to end.
VIDEO_ID = "dQw4w9WgXcQ"
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"
CHANNEL_HANDLE = "@MrBeast"
PLAYLIST_ID = "PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI"

ROUTES = {
    "videos_search": "/api/videos/search?q=news&limit=3",
    "videos_by_topic": "/api/videos/by-topic?topic=gaming&limit=3",
    "videos_shorts": "/api/videos/shorts?limit=3",
    "videos_live": "/api/videos/live?q=news&limit=3",
    "videos_location": "/api/videos/location?gl=US&hl=en&q=news&limit=5",
    "video_detail": f"/api/videos/{VIDEO_ID}",
    "video_comments": f"/api/videos/{VIDEO_ID}/comments?limit=3",
    "comments_batch": f"/api/videos/comments/batch?video_ids={VIDEO_ID}",
    "video_transcript": f"/api/videos/{VIDEO_ID}/transcript",
    "transcript_batch": f"/api/videos/transcript/batch?video_ids={VIDEO_ID}",
    "channel_info": f"/api/channels/{CHANNEL_ID}",
    "channel_videos": f"/api/channels/{CHANNEL_HANDLE}/videos?limit=3",
    "channel_playlists": f"/api/channels/{CHANNEL_ID}/playlists?limit=3",
    "playlist_videos": f"/api/playlists/{PLAYLIST_ID}/videos?limit=3",
}


class TestYoutubeRoutesRequireAuth:
    @pytest.mark.parametrize("path", list(ROUTES.values()), ids=list(ROUTES.keys()))
    def test_missing_api_key_is_rejected(self, client, path):
        response = client.get(path)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.integration
class TestYoutubeRoutesAreWired:
    @pytest.mark.parametrize("name,path", list(ROUTES.items()), ids=list(ROUTES.keys()))
    def test_route_reaches_crawler(self, client, auth_headers, name, path):
        response = client.get(path, headers=auth_headers)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_502_BAD_GATEWAY,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ), response.text


async def _first_and_next(fetch_page, **kwargs):
    """First page, then the continuation page when the first one has a token."""
    items, token = await fetch_page(**kwargs)
    assert items, "first page is empty"
    next_items = None
    if token:
        next_items, _ = await fetch_page(**kwargs, token=token)
        assert next_items, "continuation page is empty"
    return items, next_items


@pytest.mark.integration
class TestLiveCrawlers:
    async def test_channel_videos_pages(self):
        from app.crawlers.youtube.channel.channel import fetch_channel_videos_page

        videos, more = await _first_and_next(fetch_channel_videos_page, channel_id=CHANNEL_ID)
        assert videos[0]["video_id"] and videos[0]["title"] and videos[0]["view_count"]
        assert more is not None, "MrBeast has more than one page of uploads"

    async def test_channel_playlists_pages(self):
        from app.crawlers.youtube.playlist.playlist import fetch_channel_playlists_page

        playlists, _ = await _first_and_next(fetch_channel_playlists_page, channel_id=CHANNEL_ID)
        assert playlists[0]["playlist_id"] and playlists[0]["title"]

    async def test_playlist_videos_pages(self):
        from app.crawlers.youtube.playlist.playlist import fetch_playlist_videos_page

        videos, _ = await _first_and_next(fetch_playlist_videos_page, playlist_id=PLAYLIST_ID)
        assert videos[0]["video_id"] and videos[0]["duration_seconds"]

    async def test_search_pages(self):
        from app.crawlers.youtube.search.search import fetch_search_page

        videos, more = await _first_and_next(fetch_search_page, query="lofi")
        assert videos[0]["video_id"] and videos[0]["channel_id"]
        assert more is not None

    async def test_comments_page(self):
        from app.crawlers.youtube.comment.comment import fetch_comments_page

        comments, token = await fetch_comments_page(VIDEO_ID, "top")
        assert comments and comments[0]["content"] and token

    async def test_video_detail(self):
        from app.crawlers.youtube.detail.detail import get_video_detail

        detail = await get_video_detail(VIDEO_ID)
        assert detail["title"] and detail["view_count"] > 0 and detail["duration_seconds"] > 0

    async def test_channel_info_and_handle(self):
        from app.crawlers.youtube.channel_info.channel_info import get_channel_info
        from app.crawlers.youtube.client import resolve_channel_id_from_handle

        assert await resolve_channel_id_from_handle(CHANNEL_HANDLE) == CHANNEL_ID
        info = await get_channel_info(CHANNEL_ID)
        assert info["channel_id"] == CHANNEL_ID and info["subscriber_count"] > 0

    async def test_video_transcript(self):
        from app.crawlers.youtube.transcript.transcript import get_transcript

        result = await get_transcript(VIDEO_ID)
        assert result["available"] and result["char_count"] > 0
