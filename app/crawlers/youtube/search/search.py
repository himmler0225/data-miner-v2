from typing import Dict, List

from app.config.constants import ENDPOINT_SEARCH
from app.config.headers import get_youtube_headers
from app.crawlers.youtube.client import (create_httpx_client, get_context,
                                         get_youtube_api_key, get_youtube_api_url)

from ....exceptions import YouTubeStructureChangedError
from ..shared.parsers import (extract_continuation_token, get_continuation_items,
                              parse_video_renderer)
from .search_constants import SORT_OPTIONS


def extract_video_items(items: List[Dict]) -> List[Dict]:
    results = []
    for item in items:
        if "richItemRenderer" in item:
            video = item["richItemRenderer"].get("content", {}).get("videoRenderer")
        else:
            video = item.get("videoRenderer")
        if not video or not video.get("videoId"):
            continue
        parsed = parse_video_renderer(video)
        runs = (
            video.get("detailedMetadataSnippets", [{}])[0]
            .get("snippetText", {})
            .get("runs", [])
        )
        parsed["description_snippet"] = "".join(r.get("text", "") for r in runs)
        results.append(parsed)
    return results


async def search_youtube(
    query: str, max_results: int = 20, proxy: str = None, sort: str = "relevance"
) -> List[Dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
    headers = get_youtube_headers()
    sort_param = SORT_OPTIONS.get(sort)

    collected = []
    continuation = None

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        payload = {"context": get_context(), "query": query}
        if sort_param:
            payload["params"] = sort_param

        resp = await client.post(search_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        sections = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents")
        )
        if not sections:
            raise YouTubeStructureChangedError(
                "sectionListRenderer.contents not found in search response",
                context={"top_keys": list(data.get("contents", {}).keys())},
            )

        for section in sections:
            if "itemSectionRenderer" in section:
                collected += extract_video_items(
                    section["itemSectionRenderer"].get("contents", [])
                )
            if "continuationItemRenderer" in section:
                continuation = extract_continuation_token(section)

        ctx = get_context()
        while continuation and len(collected) < max_results:
            token, continuation = continuation, None
            payload = {"context": ctx, "continuation": token}
            resp = await client.post(search_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            for section in get_continuation_items(data):
                if "itemSectionRenderer" in section:
                    collected += extract_video_items(
                        section["itemSectionRenderer"].get("contents", [])
                    )
                if "continuationItemRenderer" in section:
                    continuation = extract_continuation_token(section)

    deduped = list({v["video_id"]: v for v in collected if v.get("video_id")}.values())
    return deduped[:max_results]
