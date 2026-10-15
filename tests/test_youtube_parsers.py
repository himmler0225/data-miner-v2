"""Hermetic tests for YouTube parsing and the per-page crawler functions.

HTTP is replaced by a scripted fake client (tests/youtube_fixtures.py), so these
run without network. Live checks are in test_youtube_endpoints.py (`integration`).
"""

import pytest

from app.config.constants import CHANNEL_TAB_PLAYLISTS, CHANNEL_TAB_VIDEOS
from app.crawlers.youtube.channel import channel
from app.crawlers.youtube.channel.channel import extract_home_tab_videos
from app.crawlers.youtube.channel_info.channel_info import parse_channel_info
from app.crawlers.youtube.comment import comment
from app.crawlers.youtube.playlist import playlist
from app.crawlers.youtube.playlist.playlist import parse_playlist_items
from app.crawlers.youtube.search import search
from app.crawlers.youtube.shared.models import (
    extract_videos,
    video_from_lockup,
    video_from_playlist_renderer,
    video_from_renderer,
)
from app.crawlers.youtube.shared.parsers import find_tab_by_url_suffix, get_first_badge_text
from app.crawlers.youtube.utils import format_duration, parse_count, parse_duration_seconds
from app.exceptions import YouTubeNotFoundError, YouTubeStructureChangedError
from tests.youtube_fixtures import (
    CHANNEL_ID,
    badge,
    browse_response,
    continuation_item,
    continuation_response,
    install_fake_client,
    make_tab,
    playlist_lockup,
    playlist_page_response,
    playlist_video_renderer,
    playlists_grid,
    rich_grid,
    search_response,
    video_lockup,
    video_renderer,
)

pytestmark = pytest.mark.unit

VIDEO = "dQw4w9WgXcQ"


# --- utils ------------------------------------------------------------------


class TestParseCount:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("1.234.567 lượt xem", 1_234_567),
            ("1,234,567 views", 1_234_567),
            ("1,2 Tr lượt xem", 1_200_000),
            ("3,4 N lượt xem", 3_400),
            ("1,5 T lượt xem", 1_500_000_000),
            ("12K views", 12_000),
            ("1.2M subscribers", 1_200_000),
            ("2,5 Tr người đăng ký", 2_500_000),
            ("12 video", 12),
            ("1.234 đang xem", 1_234),
            (987, 987),
            ("Chưa có lượt xem", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_count(self, text, expected):
        assert parse_count(text) == expected

    @pytest.mark.parametrize(
        "text,expected", [("3:21", 201), ("1:02:03", 3723), ("245", 245), ("", None), ("LIVE", None)]
    )
    def test_parse_duration_seconds(self, text, expected):
        assert parse_duration_seconds(text) == expected

    @pytest.mark.parametrize("seconds,expected", [(201, "3:21"), (3723, "1:02:03"), (5, "0:05"), (None, "")])
    def test_format_duration(self, seconds, expected):
        assert format_duration(seconds) == expected


# --- parsers / models -------------------------------------------------------


class TestFindTabByUrlSuffix:
    def test_matches_localized_tabs_by_url(self):
        tabs = [
            make_tab("Trang chủ", "/featured"),
            make_tab("Video", "/videos"),
            make_tab("Danh sách phát", "/playlists"),
        ]
        assert find_tab_by_url_suffix(tabs, "/videos")["title"] == "Video"
        assert find_tab_by_url_suffix(tabs, "/playlists")["title"] == "Danh sách phát"
        assert find_tab_by_url_suffix(tabs, "/streams") is None

    def test_ignores_tabs_without_endpoint(self):
        assert find_tab_by_url_suffix([{"expandableTabRenderer": {}}, {}], "/videos") is None


class TestFirstBadgeText:
    @pytest.mark.parametrize("shape", ["bottom", "overlay"])
    def test_reads_both_badge_shapes(self, shape):
        assert get_first_badge_text([{"thumbnailHoverOverlayViewModel": {}}, badge("3:21", shape)]) == "3:21"

    def test_empty(self):
        assert get_first_badge_text([]) == ""


class TestVideoModels:
    def test_lockup(self):
        assert video_from_lockup(video_lockup("vid1", "Title")["lockupViewModel"]) == {
            "video_id": "vid1",
            "url": "https://www.youtube.com/watch?v=vid1",
            "title": "Title",
            "description": "",
            "channel_id": None,
            "channel_name": "",
            "thumbnails": [{"url": "https://i.ytimg.com/x.jpg"}],
            "duration": "10:00",
            "duration_seconds": 600,
            "view_count": 1_200_000,
            "published_time": "2 ngày trước",
            "is_live": False,
            "is_short": False,
        }

    def test_lockup_views_from_last_row_and_overlay_badge(self):
        lockup = video_lockup(
            "vid1", rows=(("Channel name",), ("5 N lượt xem", "1 tuần trước")), overlays=[badge("1:02:03", "overlay")]
        )
        video = video_from_lockup(lockup["lockupViewModel"])
        assert (video["view_count"], video["published_time"], video["duration_seconds"]) == (5000, "1 tuần trước", 3723)

    def test_lockup_skips_missing_id_and_non_videos(self):
        lockup = video_lockup("vid1")["lockupViewModel"]
        del lockup["contentId"]
        assert video_from_lockup(lockup) is None
        assert video_from_lockup(playlist_lockup("PL1")["lockupViewModel"]) is None

    def test_search_renderer(self):
        video = video_from_renderer(video_renderer("abc", "Hello")["videoRenderer"])
        assert video["title"] == "Hello"
        assert (video["channel_id"], video["channel_name"]) == ("UCowner", "Owner")
        assert video["description"] == "snippet"
        assert (video["duration"], video["duration_seconds"]) == ("3:21", 201)
        assert video["view_count"] == 1_234_567
        assert video["is_live"] is False

    def test_live_renderer(self):
        video = video_from_renderer(video_renderer("abc", live=True)["videoRenderer"])
        assert video["is_live"] is True
        assert video["view_count"] == 1234
        assert video["duration"] == "" and video["duration_seconds"] is None

    def test_playlist_renderer(self):
        video = video_from_playlist_renderer(playlist_video_renderer("pv1")["playlistVideoRenderer"])
        assert (video["duration_seconds"], video["view_count"], video["published_time"]) == (245, 3400, "2 năm trước")
        assert video["channel_name"] == "Owner"

    def test_extract_videos_mixes_shapes_and_skips_junk(self):
        items = [
            {"richItemRenderer": {"content": video_lockup("new1")}},
            {"richItemRenderer": {"content": {"gridVideoRenderer": {"videoId": "old1"}}}},
            video_renderer("s1"),
            playlist_video_renderer("p1"),
            {"richItemRenderer": {"content": {"videoRenderer": {"title": {"simpleText": "no id"}}}}},
            continuation_item("tok"),
        ]
        assert [v["video_id"] for v in extract_videos(items)] == ["new1", "old1", "s1", "p1"]


class TestHomeTab:
    def test_rich_grid_shelves(self):
        shelf = {
            "richSectionRenderer": {
                "content": {
                    "richShelfRenderer": {
                        "contents": [
                            {"richItemRenderer": {"content": video_lockup("a")}},
                            {"richItemRenderer": {"content": playlist_lockup("RDCLAK1")}},
                        ]
                    }
                }
            }
        }
        grid = {"richGridRenderer": {"contents": [shelf, {"richItemRenderer": {"content": video_lockup("b")}}]}}
        assert [v["video_id"] for v in extract_home_tab_videos({"content": grid})] == ["a", "b"]

    def test_section_list_shelves_deduplicated(self):
        def shelf(*items):
            return {"shelfRenderer": {"content": {"horizontalListRenderer": {"items": list(items)}}}}

        sections = [
            {"itemSectionRenderer": {"contents": [shelf({"gridVideoRenderer": {"videoId": "a"}})]}},
            {"itemSectionRenderer": {"contents": [shelf(video_lockup("a"), video_lockup("c"))]}},
        ]
        home = {"content": {"sectionListRenderer": {"contents": sections}}}
        assert [v["video_id"] for v in extract_home_tab_videos(home)] == ["a", "c"]


class TestPlaylistItems:
    def test_grid_page(self):
        items = [
            playlist_lockup("PL1", "First"),
            playlist_lockup("PL2", "Second", sources=[], overlays=[badge("3 video", "bottom")]),
            continuation_item("tok"),
        ]
        playlists, token = parse_playlist_items(items)
        assert token == "tok"
        assert playlists == [
            {
                "playlist_id": "PL1",
                "url": "https://www.youtube.com/playlist?list=PL1",
                "title": "First",
                "thumbnails": [{"url": "a"}, {"url": "b"}],
                "video_count": 12,
            },
            {
                "playlist_id": "PL2",
                "url": "https://www.youtube.com/playlist?list=PL2",
                "title": "Second",
                "thumbnails": [],
                "video_count": 3,
            },
        ]

    def test_rich_grid_page(self):
        items = rich_grid(playlist_lockup("PL1"), continuation_item("tok"))["richGridRenderer"]["contents"]
        playlists, token = parse_playlist_items(items)
        assert [p["playlist_id"] for p in playlists] == ["PL1"]
        assert token == "tok"


class TestChannelInfo:
    def _data(self, rows):
        metadata_rows = [{"metadataParts": [{"text": {"content": p}} for p in row]} for row in rows]
        header_vm = {"metadata": {"contentMetadataViewModel": {"metadataRows": metadata_rows}}}
        return {
            "metadata": {
                "channelMetadataRenderer": {
                    "externalId": CHANNEL_ID,
                    "title": "Name",
                    "description": "d",
                    "avatar": {"thumbnails": [{"url": "s"}, {"url": "l"}]},
                }
            },
            "header": {"pageHeaderRenderer": {"content": {"pageHeaderViewModel": header_vm}}},
        }

    @pytest.mark.parametrize(
        "rows",
        [
            (("@name",), ("2,5 Tr người đăng ký", "1.234 video")),
            (("@name",), ("2.5M subscribers", "1,234 videos")),
        ],
    )
    def test_counts_in_both_locales(self, rows):
        info = parse_channel_info(self._data(rows))
        assert (info["handle"], info["subscriber_count"], info["video_count"]) == ("@name", 2_500_000, 1234)
        assert info["avatar"] == "l"

    def test_missing_channel_is_not_found(self):
        with pytest.raises(YouTubeNotFoundError):
            parse_channel_info({"responseContext": {}})


# --- crawler pages ----------------------------------------------------------


def videos_tab(*items):
    return make_tab("Video", "/videos", rich_grid(*items))


def playlists_tab(*items):
    return make_tab("Danh sách phát", "/playlists", playlists_grid(*items))


def ids(items, key="video_id"):
    return [item[key] for item in items]


class TestChannelVideosPage:
    async def test_params_select_videos_tab_in_one_request(self, monkeypatch):
        client = install_fake_client(
            monkeypatch,
            channel,
            lambda p: browse_response(make_tab("Trang chủ", "/featured"), videos_tab(video_lockup("v1"))),
        )
        videos, token = await channel.fetch_channel_videos_page(CHANNEL_ID)
        assert (ids(videos), token) == (["v1"], None)
        assert len(client.requests) == 1
        assert client.requests[0]["params"] == CHANNEL_TAB_VIDEOS

    async def test_follows_tab_endpoint_when_params_ignored(self, monkeypatch):
        def handler(payload):
            if payload["params"] == CHANNEL_TAB_VIDEOS:  # Home served, Videos tab not selected
                return browse_response(make_tab("Trang chủ", "/featured", {}), make_tab("Video", "/videos"))
            return browse_response(videos_tab(video_lockup("v1")))

        client = install_fake_client(monkeypatch, channel, handler)
        videos, _ = await channel.fetch_channel_videos_page(CHANNEL_ID)
        assert ids(videos) == ["v1"]
        assert client.requests[1]["params"] == "tab-params"

    async def test_retries_without_params_on_400(self, monkeypatch):
        def handler(payload):
            if payload.get("params") == CHANNEL_TAB_VIDEOS:
                return 400
            return browse_response(videos_tab(video_lockup("v1")))

        client = install_fake_client(monkeypatch, channel, handler)
        videos, _ = await channel.fetch_channel_videos_page(CHANNEL_ID)
        assert ids(videos) == ["v1"]
        assert "params" not in client.requests[1]

    async def test_first_page_token_then_continuation_page(self, monkeypatch):
        def handler(payload):
            if "continuation" in payload:
                return continuation_response([video_lockup("v2"), continuation_item("tok2")])
            return browse_response(videos_tab(video_lockup("v1"), continuation_item("tok1")))

        client = install_fake_client(monkeypatch, channel, handler)
        videos, token = await channel.fetch_channel_videos_page(CHANNEL_ID)
        assert (ids(videos), token) == (["v1"], "tok1")
        videos, token = await channel.fetch_channel_videos_page(CHANNEL_ID, token="tok1")
        assert (ids(videos), token) == (["v2"], "tok2")
        assert client.requests[-1]["continuation"] == "tok1"

    async def test_falls_back_to_home_tab(self, monkeypatch):
        home = {"richGridRenderer": {"contents": [{"richItemRenderer": {"content": video_lockup("h1")}}]}}
        install_fake_client(monkeypatch, channel, lambda p: browse_response(make_tab("Trang chủ", "/featured", home)))
        videos, token = await channel.fetch_channel_videos_page(CHANNEL_ID)
        assert (ids(videos), token) == (["h1"], None)

    async def test_raises_when_no_videos_or_home_tab(self, monkeypatch):
        install_fake_client(monkeypatch, channel, lambda p: browse_response(make_tab("Shorts", "/shorts", {})))
        with pytest.raises(YouTubeStructureChangedError):
            await channel.fetch_channel_videos_page(CHANNEL_ID)


class TestChannelPlaylistsPage:
    async def test_requests_playlists_tab_directly(self, monkeypatch):
        client = install_fake_client(
            monkeypatch,
            playlist,
            lambda p: browse_response(playlists_tab(playlist_lockup("PL1"), continuation_item("t"))),
        )
        playlists, token = await playlist.fetch_channel_playlists_page(CHANNEL_ID)
        assert (ids(playlists, "playlist_id"), token) == (["PL1"], "t")
        assert len(client.requests) == 1
        assert client.requests[0]["params"] == CHANNEL_TAB_PLAYLISTS

    async def test_works_for_channel_without_videos_tab(self, monkeypatch):
        install_fake_client(
            monkeypatch,
            playlist,
            lambda p: browse_response(make_tab("Trang chủ", "/featured"), playlists_tab(playlist_lockup("PL1"))),
        )
        playlists, _ = await playlist.fetch_channel_playlists_page(CHANNEL_ID)
        assert ids(playlists, "playlist_id") == ["PL1"]

    async def test_retries_when_playlists_tab_swapped_for_shows(self, monkeypatch):
        responses = iter(
            [
                browse_response(make_tab("Trang chủ", "/featured", {}), make_tab("Chương trình", "/podcasts")),
                browse_response(playlists_tab(playlist_lockup("PL1"))),
            ]
        )
        client = install_fake_client(monkeypatch, playlist, lambda p: next(responses))
        playlists, _ = await playlist.fetch_channel_playlists_page(CHANNEL_ID)
        assert ids(playlists, "playlist_id") == ["PL1"]
        assert len(client.requests) == 2

    async def test_raises_after_all_attempts_without_playlists_tab(self, monkeypatch):
        client = install_fake_client(
            monkeypatch, playlist, lambda p: browse_response(make_tab("Trang chủ", "/featured", {}))
        )
        with pytest.raises(YouTubeStructureChangedError):
            await playlist.fetch_channel_playlists_page(CHANNEL_ID)
        assert len(client.requests) == playlist.PLAYLISTS_TAB_ATTEMPTS

    async def test_continuation_page(self, monkeypatch):
        install_fake_client(monkeypatch, playlist, lambda p: continuation_response([playlist_lockup("PL9")]))
        playlists, token = await playlist.fetch_channel_playlists_page(CHANNEL_ID, token="t")
        assert (ids(playlists, "playlist_id"), token) == (["PL9"], None)


class TestPlaylistVideosPage:
    async def test_first_page(self, monkeypatch):
        client = install_fake_client(
            monkeypatch,
            playlist,
            lambda p: playlist_page_response(playlist_video_renderer("a"), continuation_item("t1")),
        )
        videos, token = await playlist.fetch_playlist_videos_page("PLabcdefghijkl")
        assert (ids(videos), token) == (["a"], "t1")
        assert client.requests[0]["browseId"] == "VLPLabcdefghijkl"

    async def test_continuation_page_has_no_contents_key(self, monkeypatch):
        # Continuation responses carry onResponseReceivedActions, not "contents".
        install_fake_client(monkeypatch, playlist, lambda p: continuation_response([playlist_video_renderer("b")]))
        videos, token = await playlist.fetch_playlist_videos_page("PLabcdefghijkl", token="t1")
        assert (ids(videos), token) == (["b"], None)

    async def test_missing_playlist_is_not_found(self, monkeypatch):
        install_fake_client(monkeypatch, playlist, lambda p: {"alerts": [{"alertRenderer": {}}]})
        with pytest.raises(YouTubeNotFoundError):
            await playlist.fetch_playlist_videos_page("PLabcdefghijkl")


class TestSearchPage:
    async def test_first_page_and_continuation(self, monkeypatch):
        def handler(payload):
            if "continuation" in payload:
                return continuation_response([{"itemSectionRenderer": {"contents": [video_renderer("s2")]}}])
            return search_response(video_renderer("s1"), continuation_item("t"))

        client = install_fake_client(monkeypatch, search, handler)
        videos, token = await search.fetch_search_page("q", params="SORT")
        assert (ids(videos), token) == (["s1"], "t")
        assert (client.requests[0]["query"], client.requests[0]["params"]) == ("q", "SORT")
        videos, token = await search.fetch_search_page("q", token="t")
        assert (ids(videos), token) == (["s2"], None)

    async def test_uses_given_context(self, monkeypatch):
        client = install_fake_client(monkeypatch, search, lambda p: search_response(video_renderer("s1")))
        await search.fetch_search_page("q", context={"client": {"gl": "JP"}})
        assert client.requests[0]["context"] == {"client": {"gl": "JP"}}

    async def test_structure_change(self, monkeypatch):
        install_fake_client(monkeypatch, search, lambda p: {"contents": {}})
        with pytest.raises(YouTubeStructureChangedError):
            await search.fetch_search_page("q")


def comment_entity(comment_id, text, likes="12", liked="13", replies="1"):
    return {
        "payload": {
            "commentEntityPayload": {
                "properties": {"commentId": comment_id, "content": {"content": text}, "publishedTime": "1 ngày trước"},
                "author": {"displayName": "A", "avatarThumbnailUrl": "av"},
                "toolbar": {"likeCountNotliked": likes, "likeCountLiked": liked, "replyCount": replies},
            }
        }
    }


def comments_response(threads, entities, next_token=None, reply_tokens=None):
    items = []
    for i, comment_id in enumerate(threads):
        thread = {"commentViewModel": {"commentViewModel": {"commentId": comment_id}}}
        if reply_tokens and reply_tokens[i]:
            thread["replies"] = {"commentRepliesRenderer": {"contents": [continuation_item(reply_tokens[i])]}}
        items.append({"commentThreadRenderer": thread})
    if next_token:
        items.append(continuation_item(next_token))
    return {
        "onResponseReceivedEndpoints": [{"reloadContinuationItemsCommand": {"continuationItems": items}}],
        "frameworkUpdates": {"entityBatchUpdate": {"mutations": entities}},
    }


class TestCommentsPage:
    async def test_top_comments_with_replies(self, monkeypatch):
        def handler(payload):
            if "videoId" in payload:  # watch-next response carries the comments token
                action = {"appendContinuationItemsAction": {"continuationItems": [continuation_item("c0")]}}
                return {"onResponseReceivedEndpoints": [action]}
            if payload["continuation"] == "c0":
                return comments_response(
                    ["c1", "c2"],
                    [comment_entity("c1", "hello"), comment_entity("c2", "world", likes="")],
                    next_token="c-next",
                    reply_tokens=["r1", None],
                )
            if payload["continuation"] == "r1":
                reply_item = {"commentViewModel": {"commentId": "r1a"}}
                return {
                    "onResponseReceivedEndpoints": [
                        {"appendContinuationItemsAction": {"continuationItems": [reply_item]}}
                    ],
                    "frameworkUpdates": {"entityBatchUpdate": {"mutations": [comment_entity("r1a", "reply")]}},
                }
            raise AssertionError(payload)

        install_fake_client(monkeypatch, comment, handler)
        comments, token = await comment.fetch_comments_page("dQw4w9WgXcQ", "top")
        assert token == "c-next"
        assert [(c["comment_id"], c["content"], c["like_count"]) for c in comments] == [
            ("c1", "hello", 12),  # likeCountNotliked, not likeCountLiked (13)
            ("c2", "world", 0),
        ]
        assert ids(comments[0]["replies"], "comment_id") == ["r1a"]
        assert "reply_count" not in comments[0]["replies"][0]
        assert comments[1]["replies"] == []

    async def test_newest_uses_prebuilt_token(self, monkeypatch):
        client = install_fake_client(monkeypatch, comment, lambda p: comments_response([], []))
        assert await comment.fetch_comments_page("dQw4w9WgXcQ", "newest") == ([], None)
        assert len(client.requests) == 1 and "continuation" in client.requests[0]

    async def test_comments_disabled(self, monkeypatch):
        install_fake_client(monkeypatch, comment, lambda p: {"contents": {}})
        assert await comment.fetch_comments_page("dQw4w9WgXcQ", "top") == ([], None)


class TestTranscript:
    @pytest.fixture
    def fake_api(self, monkeypatch):
        from app.crawlers.youtube.transcript import transcript

        def install(list_result):
            class FakeApi:
                def __init__(self, proxy_config=None):
                    pass

                def list(self, video_id):
                    if isinstance(list_result, Exception):
                        raise list_result
                    return list_result

            monkeypatch.setattr(transcript, "YouTubeTranscriptApi", FakeApi)
            return transcript

        return install

    def test_available(self, fake_api):
        class Segment:
            def __init__(self, text):
                self.text = text

        class Transcript:
            language_code = "vi"

            def fetch(self):
                return [Segment("xin"), Segment("chào")]

        class Transcripts(list):
            def find_transcript(self, languages):
                return Transcript()

        transcript = fake_api(Transcripts([Transcript()]))
        result = transcript._fetch_sync(VIDEO, None)
        assert (result["available"], result["text"], result["segment_count"], result["reason"]) == (
            True,
            "xin chào",
            2,
            None,
        )

    def test_disabled(self, fake_api):
        from youtube_transcript_api import TranscriptsDisabled

        result = fake_api(TranscriptsDisabled(VIDEO))._fetch_sync(VIDEO, None)
        assert (result["available"], result["reason"], result["text"]) == (False, "disabled", None)

    def test_unavailable_video_is_not_found(self, fake_api):
        from youtube_transcript_api import VideoUnavailable

        with pytest.raises(YouTubeNotFoundError):
            fake_api(VideoUnavailable(VIDEO))._fetch_sync(VIDEO, None)

    @pytest.mark.parametrize("exc", ["blocked", "network"])
    def test_blocked_or_network_error_is_upstream_error(self, fake_api, exc):
        import requests
        from youtube_transcript_api import RequestBlocked

        from app.exceptions import CrawlNetworkError

        error = RequestBlocked(VIDEO) if exc == "blocked" else requests.exceptions.ProxyError("tunnel 403")
        with pytest.raises(CrawlNetworkError):
            fake_api(error)._fetch_sync(VIDEO, None)
