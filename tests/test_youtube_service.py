"""Hermetic tests for cursor paging, retry and the YouTube service layer
(validation, handle resolution, error mapping, caching, batches).

Crawler page functions are replaced with in-memory fakes, so no network."""

import httpx
import pytest

from app.crawlers import retry
from app.crawlers.youtube.shared.paging import MAX_PAGES_PER_CALL, collect_page, decode_cursor, encode_cursor
from app.exceptions import CrawlNetworkError, InvalidInputError, YouTubeNotFoundError, YouTubeStructureChangedError
from app.services import youtube as yt
from tests.youtube_fixtures import CHANNEL_ID

pytestmark = pytest.mark.unit

VIDEO_ID = "dQw4w9WgXcQ"


def videos(*ids):
    return [{"video_id": i} for i in ids]


def pager(pages):
    """PageFetcher over {token: (item ids, next token)}, recording requested tokens."""
    calls = []

    async def fetch(token):
        calls.append(token)
        item_ids, next_token = pages[token]
        return videos(*item_ids), next_token

    return fetch, calls


def http_error(status):
    request = httpx.Request("POST", "https://www.youtube.com/youtubei/v1/browse")
    return httpx.HTTPStatusError("err", request=request, response=httpx.Response(status, request=request))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    yt._cache.clear()

    async def no_proxy(*args):
        return None

    async def no_sleep(seconds):
        return None

    monkeypatch.setattr(yt, "get_proxy", no_proxy)
    monkeypatch.setattr(retry.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(retry.registry, "rotate", lambda *a: None)


# --- paging -----------------------------------------------------------------


class TestCursor:
    def test_roundtrip(self):
        assert decode_cursor(encode_cursor("tok", 7)) == ("tok", 7)
        assert decode_cursor(encode_cursor(None, 3)) == (None, 3)

    @pytest.mark.parametrize("cursor", ["not-base64!", "e30", encode_cursor("t", 0)[:-3] + "xyz"])
    def test_garbage_is_invalid_input(self, cursor):
        with pytest.raises(InvalidInputError):
            decode_cursor(cursor)


class TestCollectPage:
    PAGES = {None: (["a", "b", "c"], "t1"), "t1": (["d", "e"], "t2"), "t2": (["f"], None)}

    async def test_walks_pages_and_resumes_mid_page(self):
        fetch, _ = pager(self.PAGES)
        seen = []
        page = await collect_page(fetch, 2)
        while True:
            seen += [v["video_id"] for v in page.items]
            if not page.next_cursor:
                break
            page = await collect_page(fetch, 2, page.next_cursor)
        assert seen == ["a", "b", "c", "d", "e", "f"]

    async def test_limit_spanning_pages(self):
        fetch, calls = pager(self.PAGES)
        page = await collect_page(fetch, 4)
        assert [v["video_id"] for v in page.items] == ["a", "b", "c", "d"]
        assert calls == [None, "t1"]
        assert decode_cursor(page.next_cursor) == ("t1", 1)

    async def test_page_boundary_cursor_points_at_next_token(self):
        fetch, _ = pager(self.PAGES)
        page = await collect_page(fetch, 3)
        assert decode_cursor(page.next_cursor) == ("t1", 0)

    async def test_last_page_has_no_cursor(self):
        fetch, _ = pager(self.PAGES)
        page = await collect_page(fetch, 50)
        assert len(page.items) == 6 and page.next_cursor is None
        assert page.as_dict()["has_more"] is False

    async def test_dedupes_within_a_call(self):
        fetch, _ = pager({None: (["a", "b"], "t1"), "t1": (["b", "c"], None)})
        page = await collect_page(fetch, 10, key=lambda v: v["video_id"])
        assert [v["video_id"] for v in page.items] == ["a", "b", "c"]

    async def test_stops_after_max_pages_of_empty_results(self):
        pages = {None: ([], "p1"), **{f"p{i}": ([], f"p{i + 1}") for i in range(1, 50)}}
        fetch, calls = pager(pages)
        page = await collect_page(fetch, 5)
        assert page.items == [] and len(calls) == MAX_PAGES_PER_CALL
        assert page.next_cursor is not None


# --- retry ------------------------------------------------------------------


class TestRetry:
    async def test_retries_transient_then_succeeds(self):
        attempts = []

        async def fn():
            attempts.append(1)
            if len(attempts) < 3:
                raise http_error(503)
            return "ok"

        assert await retry.retry_async(fn) == "ok"
        assert len(attempts) == 3

    @pytest.mark.parametrize(
        "exc", [http_error(400), http_error(404), YouTubeStructureChangedError("x"), KeyError("k")]
    )
    async def test_does_not_retry_permanent_errors(self, exc):
        attempts = []

        async def fn():
            attempts.append(1)
            raise exc

        with pytest.raises(type(exc)):
            await retry.retry_async(fn)
        assert len(attempts) == 1

    @pytest.mark.parametrize("exc", [httpx.ConnectError("x"), http_error(429), CrawlNetworkError("blocked")])
    async def test_transient_errors(self, exc):
        assert retry.is_transient(exc)


# --- service ----------------------------------------------------------------


class TestValidation:
    @pytest.mark.parametrize(
        "call",
        [
            lambda: yt.video_detail("short"),
            lambda: yt.video_comments(VIDEO_ID, sort="oldest"),
            lambda: yt.search_videos("   "),
            lambda: yt.search_videos("q", sort="random"),
            lambda: yt.channel_info("not a channel"),
            lambda: yt.playlist_videos("bad id!"),
            lambda: yt.region_videos("q", gl="VNM"),
            lambda: yt.topic_videos("cooking"),
            lambda: yt.transcript_batch(""),
            lambda: yt.transcript_batch([VIDEO_ID] + [f"{i:011d}" for i in range(8)]),
            lambda: yt.search_videos("q", cursor="garbage!"),
        ],
    )
    async def test_invalid_input(self, call):
        with pytest.raises(InvalidInputError):
            await call()

    def test_parse_video_ids(self):
        assert yt.parse_video_ids(f" {VIDEO_ID}, {VIDEO_ID} ,,") == [VIDEO_ID]
        assert yt.parse_video_ids([VIDEO_ID]) == [VIDEO_ID]


class TestResolveChannel:
    async def test_channel_id_passes_through(self):
        assert await yt.resolve_channel(CHANNEL_ID) == CHANNEL_ID

    async def test_handle_resolved_once_then_cached(self, monkeypatch):
        calls = []

        async def resolve(handle, proxy=None):
            calls.append(handle)
            return CHANNEL_ID

        monkeypatch.setattr(yt, "resolve_channel_id_from_handle", resolve)
        assert await yt.resolve_channel("@MrBeast") == CHANNEL_ID
        assert await yt.resolve_channel("@mrbeast") == CHANNEL_ID
        assert calls == ["@MrBeast"]


class TestErrorMapping:
    @pytest.mark.parametrize("status", [400, 404])
    async def test_youtube_400_404_become_not_found(self, monkeypatch, status):
        async def detail(video_id, proxy=None):
            raise http_error(status)

        monkeypatch.setattr(yt, "get_video_detail", detail)
        with pytest.raises(YouTubeNotFoundError):
            await yt.video_detail(VIDEO_ID)

    async def test_5xx_retried_then_raised(self, monkeypatch):
        calls = []

        async def detail(video_id, proxy=None):
            calls.append(1)
            raise http_error(502)

        monkeypatch.setattr(yt, "get_video_detail", detail)
        with pytest.raises(httpx.HTTPStatusError):
            await yt.video_detail(VIDEO_ID)
        assert len(calls) == 3


class TestListOperations:
    async def test_channel_videos_pages_and_caches(self, monkeypatch):
        calls = []

        async def fetch_page(channel_id, token=None, proxy=None):
            calls.append((channel_id, token))
            return (videos("a", "b", "c"), "t1") if token is None else (videos("d"), None)

        monkeypatch.setattr(yt, "fetch_channel_videos_page", fetch_page)
        first = await yt.channel_videos(CHANNEL_ID, limit=2)
        assert first["channel_id"] == CHANNEL_ID
        assert [v["video_id"] for v in first["items"]] == ["a", "b"] and first["has_more"]

        again = await yt.channel_videos(CHANNEL_ID, limit=2)
        assert again == first and len(calls) == 1  # served from cache

        second = await yt.channel_videos(CHANNEL_ID, limit=2, cursor=first["next_cursor"])
        assert [v["video_id"] for v in second["items"]] == ["c", "d"]
        assert second["next_cursor"] is None and second["has_more"] is False

    async def test_limit_is_clamped(self, monkeypatch):
        async def fetch_page(query, **kwargs):
            return videos(*[f"v{i}" for i in range(80)]), None

        monkeypatch.setattr(yt, "fetch_search_page", fetch_page)
        page = await yt.search_videos("q", limit=500)
        assert len(page["items"]) == yt.MAX_PAGE_LIMIT

    async def test_region_search_uses_region_context_and_proxy(self, monkeypatch):
        seen = {}

        async def proxy_for(country="VN"):
            seen["country"] = country
            return None

        async def fetch_page(query, *, context=None, token=None, proxy=None, params=None):
            seen["gl"] = context["client"]["gl"]
            return videos("a"), None

        monkeypatch.setattr(yt, "get_proxy", proxy_for)
        monkeypatch.setattr(yt, "fetch_search_page", fetch_page)
        page = await yt.region_videos("tokyo", gl="us", hl="en")
        assert (page["gl"], seen["gl"], seen["country"]) == ("US", "US", "US")

    async def test_channel_topic_plays_featured_playlist(self, monkeypatch):
        async def topic_playlists(channel_id, proxy=None):
            return [{"playlist_id": "RDCLAK5uy_abcdefghijklmnop", "title": "Top"}]

        async def playlist_page(playlist_id, token=None, proxy=None):
            assert playlist_id == "RDCLAK5uy_abcdefghijklmnop"
            return videos("m1"), None

        monkeypatch.setattr(yt, "get_topic_playlists", topic_playlists)
        monkeypatch.setattr(yt, "fetch_playlist_videos_page", playlist_page)
        page = await yt.topic_videos("music")
        assert page["source"] == "channel" and page["featured_playlist"]["title"] == "Top"
        assert [v["video_id"] for v in page["items"]] == ["m1"]


class TestBatches:
    async def test_comments_batch_reports_per_video(self, monkeypatch):
        ok, empty, missing = "aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"

        async def comments_page(video_id, sort="top", token=None, proxy=None):
            if video_id == missing:
                raise http_error(404)
            return ([{"comment_id": "x"}] if video_id == ok else []), None

        monkeypatch.setattr(yt, "fetch_comments_page", comments_page)
        result = await yt.comments_batch([ok, empty, missing])
        assert (result["requested"], result["succeeded"], result["total_comments"]) == (3, 1, 1)
        assert [(i["video_id"], i["available"], i["reason"]) for i in result["items"]] == [
            (ok, True, None),
            (empty, False, "disabled_or_empty"),
            (missing, False, "not_found"),
        ]
        assert all("comments" in item for item in result["items"])

    async def test_transcript_batch(self, monkeypatch):
        async def transcript(video_id, proxy=None):
            if video_id == "bbbbbbbbbbb":
                raise CrawlNetworkError("blocked")
            return {"video_id": video_id, "available": True, "reason": None}

        monkeypatch.setattr(yt, "get_transcript", transcript)
        result = await yt.transcript_batch("aaaaaaaaaaa,bbbbbbbbbbb")
        assert (result["requested"], result["succeeded"]) == (2, 1)
        assert result["items"][1]["reason"] == "error"
