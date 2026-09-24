"""Hermetic tests for the YouTube channel videos/playlists crawlers.

Responses are hand-built innertube JSON trimmed to the fields the parsers read,
and HTTP is replaced by a scripted fake client, so these run without network
(the live checks are in test_youtube_endpoints.py, marked `integration`).
"""

import httpx
import pytest

from app.config.constants import CHANNEL_TAB_PLAYLISTS, CHANNEL_TAB_VIDEOS
from app.crawlers.youtube.channel import channel
from app.crawlers.youtube.channel.channel import (
    _extract_lockup_video,
    extract_home_tab_videos,
    extract_video_items,
)
from app.crawlers.youtube.playlist import playlist
from app.crawlers.youtube.playlist.playlist import extract_playlists_tab_items
from app.crawlers.youtube.shared.parsers import find_tab_by_url_suffix, get_first_badge_text
from app.exceptions import YouTubeStructureChangedError

pytestmark = pytest.mark.unit

CHANNEL_ID = "UC_test"


# --- builders ---------------------------------------------------------------


def make_tab(title, url_suffix, content=None, params="tab-params"):
    renderer = {
        "title": title,
        "endpoint": {
            "browseEndpoint": {"browseId": CHANNEL_ID, "params": params},
            "commandMetadata": {"webCommandMetadata": {"url": f"/@test{url_suffix}"}},
        },
    }
    if content is not None:
        renderer["content"] = content
    return {"tabRenderer": renderer}


def browse_response(*tabs):
    return {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": list(tabs)}}}


def badge(text, shape="bottom"):
    if shape == "bottom":
        return {"thumbnailBottomOverlayViewModel": {"badges": [{"thumbnailBadgeViewModel": {"text": text}}]}}
    return {"thumbnailOverlayBadgeViewModel": {"thumbnailBadges": [{"thumbnailBadgeViewModel": {"text": text}}]}}


def video_lockup(video_id, title="t", rows=(("1 N lượt xem", "2 ngày trước"),), overlays=None):
    return {
        "lockupViewModel": {
            "contentId": video_id,
            "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
            "metadata": {
                "lockupMetadataViewModel": {
                    "title": {"content": title},
                    "metadata": {
                        "contentMetadataViewModel": {
                            "metadataRows": [{"metadataParts": [{"text": {"content": p}} for p in row]} for row in rows]
                        }
                    },
                }
            },
            "contentImage": {
                "thumbnailViewModel": {
                    "image": {"sources": [{"url": "https://i.ytimg.com/x.jpg"}]},
                    "overlays": overlays if overlays is not None else [badge("10:00")],
                }
            },
        }
    }


def playlist_lockup(playlist_id, title="p", sources=None, overlays=None):
    return {
        "lockupViewModel": {
            "contentId": playlist_id,
            "contentType": "LOCKUP_CONTENT_TYPE_PLAYLIST",
            "metadata": {"lockupMetadataViewModel": {"title": {"content": title}}},
            "contentImage": {
                "collectionThumbnailViewModel": {
                    "primaryThumbnail": {
                        "thumbnailViewModel": {
                            "image": {"sources": sources if sources is not None else [{"url": "a"}, {"url": "b"}]},
                            "overlays": overlays if overlays is not None else [badge("12 video", "overlay")],
                        }
                    }
                }
            },
        }
    }


def continuation_item(token):
    return {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": token}}}}


def rich_grid(*items):
    # Continuation entries sit at the grid's top level, not inside richItemRenderer.
    return {
        "richGridRenderer": {
            "contents": [i if "continuationItemRenderer" in i else {"richItemRenderer": {"content": i}} for i in items]
        }
    }


def playlists_grid(*items):
    return {
        "sectionListRenderer": {
            "contents": [{"itemSectionRenderer": {"contents": [{"gridRenderer": {"items": list(items)}}]}}]
        }
    }


# --- fake HTTP --------------------------------------------------------------


class FakeClient:
    """Answers each POST by calling `handler(payload)`, recording every payload.
    A handler may return an int status code to simulate an HTTP error."""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json):
        self.requests.append(json)
        result = self.handler(json)
        request = httpx.Request("POST", url)
        if isinstance(result, int):
            return httpx.Response(result, request=request)
        return httpx.Response(200, json=result, request=request)


@pytest.fixture
def fake_youtube(monkeypatch):
    def install(module, handler):
        client = FakeClient(handler)

        async def fake_api_key(proxy=None):
            return "key"

        monkeypatch.setattr(module, "create_httpx_client", lambda **kwargs: client)
        monkeypatch.setattr(module, "get_youtube_api_key", fake_api_key)
        return client

    return install


# --- parsers ----------------------------------------------------------------


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


class TestExtractLockupVideo:
    def test_parses_channel_grid_lockup(self):
        video = _extract_lockup_video(video_lockup("vid1", "Title")["lockupViewModel"])
        assert video == {
            "title": "Title",
            "videoId": "vid1",
            "url": "https://www.youtube.com/watch?v=vid1",
            "duration": "10:00",
            "views": "1 N lượt xem",
            "thumbnail": [{"url": "https://i.ytimg.com/x.jpg"}],
            "public": "2 ngày trước",
        }

    def test_views_and_date_come_from_last_row_when_channel_row_present(self):
        lockup = video_lockup("vid1", rows=(("Channel name",), ("5 N lượt xem", "1 tuần trước")))
        video = _extract_lockup_video(lockup["lockupViewModel"])
        assert (video["views"], video["public"]) == ("5 N lượt xem", "1 tuần trước")

    def test_duration_from_overlay_badge_shape(self):
        lockup = video_lockup("vid1", overlays=[badge("1:02:03", "overlay")])
        assert _extract_lockup_video(lockup["lockupViewModel"])["duration"] == "1:02:03"

    def test_skips_missing_content_id(self):
        lockup = video_lockup("vid1")["lockupViewModel"]
        del lockup["contentId"]
        assert _extract_lockup_video(lockup) is None

    def test_skips_non_video_lockups(self):
        lockup = playlist_lockup("PL1")["lockupViewModel"]
        assert _extract_lockup_video(lockup) is None


class TestExtractVideoItems:
    def test_mixes_lockup_and_legacy_shapes_and_skips_junk(self):
        legacy = {"videoRenderer": {"videoId": "old1", "title": {"runs": [{"text": "Old"}]}}}
        items = [
            {"richItemRenderer": {"content": video_lockup("new1")}},
            {"richItemRenderer": {"content": legacy}},
            {"richItemRenderer": {"content": {"videoRenderer": {"title": {"simpleText": "no id"}}}}},
            continuation_item("tok"),
        ]
        assert [v["videoId"] for v in extract_video_items(items)] == ["new1", "old1"]


class TestExtractHomeTabVideos:
    def test_rich_grid_shelves(self):
        home = make_tab(
            "Trang chủ",
            "/featured",
            {
                "richGridRenderer": {
                    "contents": [
                        {
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
                        },
                        {"richItemRenderer": {"content": video_lockup("b")}},
                    ]
                }
            },
        )["tabRenderer"]
        assert [v["videoId"] for v in extract_home_tab_videos(home)] == ["a", "b"]

    def test_section_list_shelves_deduplicated(self):
        def shelf(*items):
            return {
                "shelfRenderer": {"content": {"horizontalListRenderer": {"items": list(items)}}},
            }

        home = make_tab(
            "Home",
            "/featured",
            {
                "sectionListRenderer": {
                    "contents": [
                        {"itemSectionRenderer": {"contents": [shelf({"gridVideoRenderer": {"videoId": "a"}})]}},
                        {"itemSectionRenderer": {"contents": [shelf(video_lockup("a"), video_lockup("c"))]}},
                    ]
                }
            },
        )["tabRenderer"]
        assert [v["videoId"] for v in extract_home_tab_videos(home)] == ["a", "c"]


class TestExtractPlaylistsTabItems:
    def test_skips_continuation_and_tolerates_missing_thumbnail(self):
        tab = {
            "content": playlists_grid(
                playlist_lockup("PL1", "First"),
                playlist_lockup("PL2", "Second", sources=[], overlays=[badge("3 video", "bottom")]),
                continuation_item("tok"),
            )
        }
        assert extract_playlists_tab_items(tab) == [
            {"playlistId": "PL1", "title": "First", "thumbnail": "b", "videoCount": "12 video"},
            {"playlistId": "PL2", "title": "Second", "thumbnail": "", "videoCount": "3 video"},
        ]


# --- crawler flows ----------------------------------------------------------


class TestGetChannelVideos:
    async def test_single_request_when_params_select_videos_tab(self, fake_youtube):
        client = fake_youtube(
            channel,
            lambda p: browse_response(
                make_tab("Trang chủ", "/featured"), make_tab("Video", "/videos", rich_grid(video_lockup("v1")))
            ),
        )
        videos = await channel.get_channel_videos(CHANNEL_ID, max_results=10)
        assert [v["videoId"] for v in videos] == ["v1"]
        assert len(client.requests) == 1
        assert client.requests[0]["params"] == CHANNEL_TAB_VIDEOS

    async def test_follows_tab_endpoint_when_params_ignored(self, fake_youtube):
        def handler(payload):
            if payload["params"] == CHANNEL_TAB_VIDEOS:  # Home served, Videos tab not selected
                return browse_response(make_tab("Trang chủ", "/featured", {}), make_tab("Video", "/videos"))
            return browse_response(make_tab("Video", "/videos", rich_grid(video_lockup("v1"))))

        client = fake_youtube(channel, handler)
        videos = await channel.get_channel_videos(CHANNEL_ID)
        assert [v["videoId"] for v in videos] == ["v1"]
        assert client.requests[1]["params"] == "tab-params"

    async def test_retries_without_params_on_400(self, fake_youtube):
        def handler(payload):
            if "params" in payload and payload["params"] == CHANNEL_TAB_VIDEOS:
                return 400
            return browse_response(make_tab("Video", "/videos", rich_grid(video_lockup("v1"))))

        client = fake_youtube(channel, handler)
        assert [v["videoId"] for v in await channel.get_channel_videos(CHANNEL_ID)] == ["v1"]
        assert "params" not in client.requests[1]

    async def test_paginates_with_continuation_up_to_max_results(self, fake_youtube):
        def handler(payload):
            if "continuation" in payload:
                items = [video_lockup("v2"), video_lockup("v3"), continuation_item("tok2")]
                return {"onResponseReceivedActions": [{"appendContinuationItemsAction": {"continuationItems": items}}]}
            return browse_response(
                make_tab("Video", "/videos", rich_grid(video_lockup("v1"), continuation_item("tok1")))
            )

        client = fake_youtube(channel, handler)
        videos = await channel.get_channel_videos(CHANNEL_ID, max_results=2)
        assert [v["videoId"] for v in videos] == ["v1", "v2"]
        assert client.requests[1]["continuation"] == "tok1"
        assert len(client.requests) == 2

    async def test_falls_back_to_home_tab_videos(self, fake_youtube):
        home = {"richGridRenderer": {"contents": [{"richItemRenderer": {"content": video_lockup("h1")}}]}}
        fake_youtube(channel, lambda p: browse_response(make_tab("Trang chủ", "/featured", home)))
        assert [v["videoId"] for v in await channel.get_channel_videos(CHANNEL_ID)] == ["h1"]

    async def test_raises_when_no_videos_or_home_tab(self, fake_youtube):
        fake_youtube(channel, lambda p: browse_response(make_tab("Shorts", "/shorts", {})))
        with pytest.raises(YouTubeStructureChangedError):
            await channel.get_channel_videos(CHANNEL_ID)


class TestGetPlaylistVideos:
    async def test_requests_playlists_tab_directly(self, fake_youtube):
        client = fake_youtube(
            playlist,
            lambda p: browse_response(make_tab("Danh sách phát", "/playlists", playlists_grid(playlist_lockup("PL1")))),
        )
        playlists = await playlist.get_playlist_videos(CHANNEL_ID)
        assert [p["playlistId"] for p in playlists] == ["PL1"]
        assert len(client.requests) == 1
        assert client.requests[0]["params"] == CHANNEL_TAB_PLAYLISTS

    async def test_works_for_channel_without_videos_tab(self, fake_youtube):
        fake_youtube(
            playlist,
            lambda p: browse_response(
                make_tab("Trang chủ", "/featured"),
                make_tab("Danh sách phát", "/playlists", playlists_grid(playlist_lockup("PL1"))),
            ),
        )
        assert [p["playlistId"] for p in await playlist.get_playlist_videos(CHANNEL_ID)] == ["PL1"]

    async def test_retries_when_playlists_tab_swapped_for_shows(self, fake_youtube):
        responses = iter(
            [
                browse_response(make_tab("Trang chủ", "/featured", {}), make_tab("Chương trình", "/podcasts")),
                browse_response(make_tab("Danh sách phát", "/playlists", playlists_grid(playlist_lockup("PL1")))),
            ]
        )
        client = fake_youtube(playlist, lambda p: next(responses))
        assert [p["playlistId"] for p in await playlist.get_playlist_videos(CHANNEL_ID)] == ["PL1"]
        assert len(client.requests) == 2

    async def test_raises_after_all_attempts_without_playlists_tab(self, fake_youtube):
        client = fake_youtube(playlist, lambda p: browse_response(make_tab("Trang chủ", "/featured", {})))
        with pytest.raises(YouTubeStructureChangedError):
            await playlist.get_playlist_videos(CHANNEL_ID)
        assert len(client.requests) == playlist.PLAYLISTS_TAB_ATTEMPTS
