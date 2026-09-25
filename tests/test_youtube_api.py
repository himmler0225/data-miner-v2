"""REST layer for /api/videos, /api/channels, /api/playlists: parameter
plumbing, the response envelope and error -> HTTP status mapping.
The service layer is stubbed, so no network."""

import httpx
import pytest
from fastapi import status

from app.exceptions import (
    CrawlNetworkError,
    InvalidInputError,
    YouTubeNotFoundError,
    YouTubeStructureChangedError,
)
from app.middleware.rate_limit import limiter
from app.services import youtube as yt

pytestmark = pytest.mark.api

VIDEO_ID = "dQw4w9WgXcQ"
PAGE = {"items": [{"video_id": VIDEO_ID}], "next_cursor": "next", "has_more": True}


@pytest.fixture(autouse=True)
def no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def stub(monkeypatch):
    """Replace a service function; returns the list of (args, kwargs) it was called with."""

    def install(name, result=PAGE):
        calls = []

        async def fake(*args, **kwargs):
            calls.append((args, kwargs))
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(yt, name, fake)
        return calls

    return install


class TestParams:
    @pytest.mark.parametrize(
        "url,name,args,kwargs",
        [
            (
                "/api/videos/search?q=cat&sort=view_count&limit=5&cursor=c",
                "search_videos",
                ("cat",),
                {"sort": "view_count", "limit": 5, "cursor": "c"},
            ),
            ("/api/videos/by-topic?topic=news", "topic_videos", ("news",), {"limit": 20, "cursor": None}),
            ("/api/videos/live?q=x", "live_videos", ("x",), {"limit": 20, "cursor": None}),
            (
                "/api/videos/location?q=x&gl=JP&hl=ja",
                "region_videos",
                ("x",),
                {"gl": "JP", "hl": "ja", "limit": 20, "cursor": None},
            ),
            ("/api/videos/shorts?limit=3", "shorts_feed", (), {"limit": 3}),
            (f"/api/videos/{VIDEO_ID}", "video_detail", (VIDEO_ID,), {}),
            (
                f"/api/videos/{VIDEO_ID}/comments?sort=newest",
                "video_comments",
                (VIDEO_ID,),
                {"sort": "newest", "limit": 20, "cursor": None},
            ),
            (f"/api/videos/{VIDEO_ID}/transcript", "video_transcript", (VIDEO_ID,), {}),
            (
                f"/api/videos/comments/batch?video_ids={VIDEO_ID}",
                "comments_batch",
                (VIDEO_ID,),
                {"sort": "top", "limit": 20},
            ),
            (f"/api/videos/transcript/batch?video_ids={VIDEO_ID}", "transcript_batch", (VIDEO_ID,), {}),
            ("/api/channels/@handle", "channel_info", ("@handle",), {}),
            ("/api/channels/@handle/videos?cursor=c", "channel_videos", ("@handle",), {"limit": 20, "cursor": "c"}),
            ("/api/channels/@handle/playlists", "channel_playlists", ("@handle",), {"limit": 20, "cursor": None}),
            (
                "/api/playlists/PLabcdefghijkl/videos",
                "playlist_videos",
                ("PLabcdefghijkl",),
                {"limit": 20, "cursor": None},
            ),
        ],
    )
    def test_route_calls_service(self, client, auth_headers, stub, url, name, args, kwargs):
        calls = stub(name)
        response = client.get(url, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True and body["data"] == PAGE
        assert calls == [(args, kwargs)]

    @pytest.mark.parametrize(
        "url",
        [
            "/api/videos/search?q=x&limit=0",
            "/api/videos/search?q=x&limit=51",
            "/api/videos/search?q=x&sort=random",
            "/api/videos/search",
            f"/api/videos/{VIDEO_ID}/comments?sort=oldest",
            "/api/videos/location?q=x",
        ],
    )
    def test_invalid_query_params_are_422(self, client, auth_headers, url):
        assert client.get(url, headers=auth_headers).status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestErrors:
    @pytest.mark.parametrize(
        "exc,code",
        [
            (InvalidInputError("errors.invalid_id", kind="video_id", value="x"), status.HTTP_400_BAD_REQUEST),
            (YouTubeNotFoundError("video x"), status.HTTP_404_NOT_FOUND),
            (YouTubeStructureChangedError("moved"), status.HTTP_502_BAD_GATEWAY),
            (CrawlNetworkError("blocked"), status.HTTP_502_BAD_GATEWAY),
            (httpx.ConnectError("down"), status.HTTP_502_BAD_GATEWAY),
            (
                httpx.HTTPStatusError(
                    "429",
                    request=httpx.Request("POST", "https://x"),
                    response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
                ),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ),
            (KeyError("bug"), status.HTTP_500_INTERNAL_SERVER_ERROR),
        ],
    )
    def test_error_status(self, client, auth_headers, stub, exc, code):
        stub("video_detail", exc)
        response = client.get(f"/api/videos/{VIDEO_ID}", headers=auth_headers)
        assert response.status_code == code
        body = response.json()
        assert body["success"] is False and body["error"]

    def test_invalid_input_message_is_localized(self, client, auth_headers, stub):
        stub("video_detail", InvalidInputError("errors.invalid_id", kind="video_id", value="x"))
        headers = {**auth_headers, "Accept-Language": "en"}
        response = client.get(f"/api/videos/{VIDEO_ID}", headers=headers)
        assert response.json()["error"] == "Invalid video_id: x"
