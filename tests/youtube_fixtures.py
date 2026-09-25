"""Hand-built InnerTube JSON (trimmed to the fields the parsers read) and a
scripted fake HTTP client, shared by the hermetic YouTube tests."""

import httpx

CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"


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


def continuation_response(items):
    return {"onResponseReceivedActions": [{"appendContinuationItemsAction": {"continuationItems": items}}]}


def badge(text, shape="bottom"):
    if shape == "bottom":
        return {"thumbnailBottomOverlayViewModel": {"badges": [{"thumbnailBadgeViewModel": {"text": text}}]}}
    return {"thumbnailOverlayBadgeViewModel": {"thumbnailBadges": [{"thumbnailBadgeViewModel": {"text": text}}]}}


def video_lockup(video_id, title="t", rows=(("1,2 Tr lượt xem", "2 ngày trước"),), overlays=None):
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


def video_renderer(video_id, title="Video", live=False):
    renderer = {
        "videoId": video_id,
        "title": {"runs": [{"text": title}]},
        "ownerText": {"runs": [{"text": "Owner", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCowner"}}}]},
        "detailedMetadataSnippets": [{"snippetText": {"runs": [{"text": "snip"}, {"text": "pet"}]}}],
        "thumbnail": {"thumbnails": [{"url": "https://i.ytimg.com/v.jpg"}]},
        "lengthText": {"simpleText": "3:21"},
        "viewCountText": {"simpleText": "1.234.567 lượt xem"},
        "publishedTimeText": {"simpleText": "1 năm trước"},
    }
    if live:
        del renderer["lengthText"]
        renderer["viewCountText"] = {"runs": [{"text": "1.234"}, {"text": " đang xem"}]}
        renderer["badges"] = [{"metadataBadgeRenderer": {"style": "BADGE_STYLE_TYPE_LIVE_NOW"}}]
    return {"videoRenderer": renderer}


def playlist_video_renderer(video_id, title="PV"):
    return {
        "playlistVideoRenderer": {
            "videoId": video_id,
            "title": {"runs": [{"text": title}]},
            "shortBylineText": {
                "runs": [{"text": "Owner", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCowner"}}}]
            },
            "lengthText": {"simpleText": "4:05"},
            "lengthSeconds": "245",
            "videoInfo": {"runs": [{"text": "3,4 N lượt xem"}, {"text": " • "}, {"text": "2 năm trước"}]},
            "thumbnail": {"thumbnails": [{"url": "a"}]},
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


def search_response(*items):
    sections = [{"itemSectionRenderer": {"contents": [i for i in items if "continuationItemRenderer" not in i]}}]
    sections += [i for i in items if "continuationItemRenderer" in i]
    return {
        "contents": {
            "twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": sections}}}
        }
    }


def playlist_page_response(*items):
    list_renderer = {"playlistVideoListRenderer": {"contents": list(items)}}
    section = {"itemSectionRenderer": {"contents": [list_renderer]}}
    return browse_response({"tabRenderer": {"content": {"sectionListRenderer": {"contents": [section]}}}})


class FakeClient:
    """Answers each POST/GET by calling `handler(payload_or_url)`, recording every
    request. A handler may return an int status code to simulate an HTTP error."""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def _respond(self, method, url, result):
        request = httpx.Request(method, url)
        if isinstance(result, int):
            return httpx.Response(result, request=request)
        return httpx.Response(200, json=result, request=request)

    async def post(self, url, json):
        self.requests.append(json)
        return self._respond("POST", url, self.handler(json))


def install_fake_client(monkeypatch, module, handler) -> FakeClient:
    client = FakeClient(handler)

    async def fake_api_key(proxy=None):
        return "key"

    monkeypatch.setattr(module, "create_httpx_client", lambda **kwargs: client)
    monkeypatch.setattr(module, "get_youtube_api_key", fake_api_key)
    return client
