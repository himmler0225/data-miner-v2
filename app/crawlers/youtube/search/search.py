from app.config.constants import ENDPOINT_SEARCH
from app.config.headers import get_youtube_headers
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url

from ....exceptions import YouTubeStructureChangedError
from ..shared.models import extract_videos
from ..shared.parsers import extract_continuation_token, get_continuation_items


def _parse_sections(sections: list[dict]) -> tuple[list[dict], str | None]:
    videos, token = [], None
    for section in sections:
        if "itemSectionRenderer" in section:
            videos += extract_videos(section["itemSectionRenderer"].get("contents", []))
        elif "continuationItemRenderer" in section:
            token = extract_continuation_token(section)
    return videos, token


async def fetch_search_page(
    query: str,
    *,
    params: str | None = None,
    context: dict | None = None,
    token: str | None = None,
    proxy: str | None = None,
) -> tuple[list[dict], str | None]:
    """One page of YouTube search results: `(videos, next_token)`.

    `params` is the search filter/sort protobuf (sort order, live-only, ...) and
    `context` overrides the InnerTube context (e.g. another country's gl/hl);
    pass the same `context` for continuation pages. `token` continues a previous
    page; None fetches the first one."""
    api_key = await get_youtube_api_key(proxy=proxy)
    search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
    payload: dict = {"context": context or get_context()}
    if token:
        payload["continuation"] = token
    else:
        payload["query"] = query
        if params:
            payload["params"] = params

    async with create_httpx_client(proxy=proxy, headers=get_youtube_headers()) as client:
        resp = await client.post(search_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if token:
        return _parse_sections(get_continuation_items(data))

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
            context={"query": query, "top_keys": list(data.get("contents", {}).keys())},
        )
    return _parse_sections(sections)
