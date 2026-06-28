from typing import Dict, List

from app.config.constants import (ENDPOINT_SEARCH, SEARCH_FILTER_LIVE,
                                  YOUTUBE_BASE_URL)
from app.config.headers import get_youtube_headers
from app.crawlers.youtube.client import (create_httpx_client, get_context,
                                         get_youtube_api_key, get_youtube_api_url)
from app.crawlers.youtube.utils import parse_view_count

from ....exceptions import YouTubeStructureChangedError
from ..shared.parsers import (extract_continuation_token, get_continuation_items,
                              join_runs)


def extract_live_videos(items: List[Dict]) -> List[Dict]:
    videos = []
    for item in items:
        video = item.get("videoRenderer")
        if not video:
            continue
        views_raw = (
            join_runs(video.get("shortViewCountText", {}))
            if "shortViewCountText" in video
            else ""
        )
        videos.append(
            {
                "video_id": video.get("videoId"),
                "title": join_runs(video.get("title", {})),
                "thumbnail": video.get("thumbnail", {}).get("thumbnails", []),
                "channel_name": join_runs(video.get("ownerText", {})),
                "url": f"{YOUTUBE_BASE_URL}/watch?v={video.get('videoId')}",
                "view_count": parse_view_count(views_raw),
                "is_live": True,
            }
        )
    return videos


async def get_all_live_videos(
    q: str = "", proxy: str = None, max_results: int = 100
) -> List[Dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
    headers = get_youtube_headers()
    collected = []
    continuation = None

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        payload = {"context": get_context(), "query": q, "params": SEARCH_FILTER_LIVE}
        resp = await client.post(search_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        if not contents:
            raise YouTubeStructureChangedError(
                "sectionListRenderer.contents not found in live search response",
                context={"top_keys": list(data.get("contents", {}).keys())},
            )

        for section in contents:
            collected += extract_live_videos(
                section.get("itemSectionRenderer", {}).get("contents", [])
            )
        continuation = next(
            (
                extract_continuation_token(section)
                for section in contents
                if "continuationItemRenderer" in section
            ),
            None,
        )

        while continuation and len(collected) < max_results:
            payload = {"context": get_context(), "continuation": continuation}
            resp = await client.post(search_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            continuation_items = get_continuation_items(data)
            collected += extract_live_videos(continuation_items)
            continuation = next(
                (
                    extract_continuation_token(item)
                    for item in continuation_items
                    if "continuationItemRenderer" in item
                ),
                None,
            )

    return collected[:max_results]
