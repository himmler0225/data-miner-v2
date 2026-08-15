"""Route coverage for /api/videos/* and /api/channels/* (YouTube crawl endpoints).

Auth checks are hermetic (no network). The "route exists" checks hit the real
crawler code against real YouTube — same lenient pattern already used in
test_api.py's TestVideoDetailEndpoint (accept 200 or a server error, since
these depend on an external site, and on this repo's third-party proxy pool,
so a live hiccup in either shouldn't fail CI).

TestPreviouslyBrokenCrawlers calls the crawler functions directly (bypassing
the HTTP route and its proxy selection) to verify parsing logic deterministically
for three endpoints that were fully broken as of 2026-08-14 and have since been
fixed here — see channel.py/playlist.py/transcript.py for the root causes.
"""

import pytest
from fastapi import status

pytestmark = pytest.mark.api

# A real, stable video/channel/playlist used only to prove the route is wired
# up and talks to a live crawler; not a strict content assertion.
VIDEO_ID = "dQw4w9WgXcQ"
CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"
PLAYLIST_ID = "PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI"

ROUTES = {
    "videos_by_topic": "/api/videos/by-topic?topic=gaming&limit=3",
    "videos_shorts": "/api/videos/shorts?limit=3",
    "videos_live": "/api/videos/live?q=news&limit=3",
    "videos_location": "/api/videos/location?gl=US&hl=en&query=news&max_results=5",
    "video_comments": f"/api/videos/{VIDEO_ID}/comments?limit=3",
    "comments_batch": f"/api/videos/comments/batch?video_ids={VIDEO_ID}",
    "channel_info": f"/api/channels/{CHANNEL_ID}",
    "channel_videos": f"/api/channels/{CHANNEL_ID}/videos?limit=3",
    "channel_playlists": f"/api/channels/{CHANNEL_ID}/playlists",
    "playlist_videos": f"/api/playlists/{PLAYLIST_ID}/videos",
    "video_transcript": f"/api/videos/{VIDEO_ID}/transcript",
    "transcript_batch": f"/api/videos/transcript/batch?video_ids={VIDEO_ID}",
}


class TestYoutubeRoutesRequireAuth:
    @pytest.mark.parametrize("path", list(ROUTES.values()), ids=list(ROUTES.keys()))
    def test_missing_api_key_is_rejected(self, client, path):
        response = client.get(path)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestYoutubeRoutesAreWired:
    """Hits the real crawlers over the network. Accepts 200 (worked) or 500/502
    (upstream/crawler error) so a live YouTube or proxy-pool hiccup doesn't fail
    CI — the point is proving the route reaches crawler code, not asserting
    content (see TestPreviouslyBrokenCrawlers for content-level checks)."""

    @pytest.mark.parametrize("name,path", list(ROUTES.items()), ids=list(ROUTES.keys()))
    def test_route_reaches_crawler(self, client, auth_headers, name, path):
        response = client.get(path, headers=auth_headers)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_502_BAD_GATEWAY,
        )


async def _retry(coro_fn, attempts=3):
    """YouTube occasionally omits a channel's Playlists tab from a response
    entirely (observed: swapped for a 'Shows' tab on ~1/6 real requests to the
    same channel, no code change) — real server-side variance, not a parsing
    bug. A couple of retries smooths that out here the same way a real caller
    would just refresh. Retries on both a raised exception and a falsy result,
    since get_transcript() reports failure by returning None rather than raising."""
    last_exc = None
    for _ in range(attempts):
        try:
            result = await coro_fn()
            if result:
                return result
        except Exception as e:  # noqa: BLE001
            last_exc = e
    if last_exc:
        raise last_exc
    return result


class TestPreviouslyBrokenCrawlers:
    """Calls crawler functions directly (proxy=None) instead of through the API
    route, so these assert the actual parsing fix rather than being at the mercy
    of the third-party proxy pool's availability too."""

    async def test_channel_videos_parses_lockup_view_model(self):
        from app.crawlers.youtube.channel.channel import get_channel_videos

        videos = await _retry(lambda: get_channel_videos(channel_id=CHANNEL_ID, max_results=3, proxy=None))
        assert len(videos) > 0
        assert videos[0]["videoId"]
        assert videos[0]["title"]

    async def test_channel_playlists_parses_lockup_view_model(self):
        from app.crawlers.youtube.playlist.playlist import get_playlist_videos

        playlists = await _retry(lambda: get_playlist_videos(CHANNEL_ID, proxy=None))
        assert len(playlists) > 0
        assert playlists[0]["playlistId"]
        assert playlists[0]["title"]

    async def test_video_transcript_is_fetched(self):
        from app.crawlers.youtube.transcript.transcript import get_transcript

        result = await _retry(lambda: get_transcript(VIDEO_ID))
        assert result is not None
        assert result["char_count"] > 0
