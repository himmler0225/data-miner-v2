import asyncio
import re
import json
import random
import httpx
from typing import List, Dict, Optional

from ....utils import get_youtube_api_key, get_context, get_httpx_proxies, create_httpx_client, get_client_version, get_visitor_data
from ....config import get_youtube_headers, get_youtube_api_url
from ....config.constants import ENDPOINT_BROWSE, ENDPOINT_SEARCH, SORT_VIEW_COUNT, DEFAULT_TIMEOUT
from ....config.headers import USER_AGENTS
from ....exceptions import YouTubeStructureChangedError
from app.config.logger import Logger
from ..shared import parse_video_renderer, extract_continuation_token, get_continuation_items
from .trending_constants import TRENDING_URL

logger = Logger.get(__name__)

def _is_live_video(video: Dict) -> bool:
    duration = video.get("duration", "")
    return duration in ("0:00", "00:00")

def extract_videos(items: List[Dict], rank_offset: int = 0, skip_live: bool = True) -> List[Dict]:
    results = []
    for item in items:
        video = item.get("videoRenderer") or item.get("gridVideoRenderer")
        if not video or not video.get("videoId"):
            continue
        if skip_live:
            overlays = video.get("thumbnailOverlays", [])
            is_live = any(
                "thumbnailOverlayTimeStatusRenderer" in o
                and o["thumbnailOverlayTimeStatusRenderer"].get("style", "") == "LIVE"
                for o in overlays
            )
            if is_live:
                continue
        parsed = parse_video_renderer(video)
        parsed["rank"] = rank_offset + len(results) + 1
        results.append(parsed)
    return results

def extract_videos_from_item(item: Dict, rank_offset: int = 0) -> List[Dict]:
    if "carouselRenderer" in item:
        return extract_videos(item["carouselRenderer"].get("contents", []), rank_offset)
    elif "shelfRenderer" in item:
        return extract_videos(
            item["shelfRenderer"]
            .get("content", {})
            .get("expandedShelfContentsRenderer", {})
            .get("items", []),
            rank_offset,
        )
    elif "richSectionRenderer" in item:
        content = item["richSectionRenderer"].get("content", {})
        if "richShelfRenderer" in content:
            return extract_videos(content["richShelfRenderer"].get("contents", []), rank_offset)
    return []

def _parse_yt_initial_data(html: str) -> dict:
    match = re.search(r'var ytInitialData\s*=\s*', html)
    if not match:
        raise YouTubeStructureChangedError(
            "ytInitialData not found in trending page HTML",
            context={"html_length": len(html)},
        )
    try:
        data, _ = json.JSONDecoder().raw_decode(html, match.end())
        return data
    except json.JSONDecodeError as e:
        raise YouTubeStructureChangedError(
            f"Failed to parse ytInitialData: {e}",
            context={"offset": match.end()},
        )

def _make_session(proxy: Optional[str], gl: str, hl: str) -> httpx.AsyncClient:
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": f"{hl}-{gl},{hl};q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    # PREF cookie sets region/language; SOCS bypasses consent gate
    cookies = {
        "PREF": f"tz=Asia%2FHo_Chi_Minh&hl={hl}&gl={gl}",
        "SOCS": "CAESEwgDEgk0ODE5Mzk4MTgaAmVuIAEaBgiA_LyaBg",
    }
    proxies = get_httpx_proxies(proxy)
    kwargs: dict = {
        "headers": headers,
        "cookies": cookies,
        "timeout": DEFAULT_TIMEOUT,
        "follow_redirects": True,
    }
    if proxies:
        kwargs["proxy"] = proxies
    return httpx.AsyncClient(**kwargs)

async def _api_trending(proxy, max_results, filter_params, gl, hl) -> List[Dict]:
    api_key = await get_youtube_api_key(proxy=proxy)
    headers = get_youtube_headers(visitor_data=get_visitor_data(), client_version=get_client_version())
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    context = get_context()
    context["client"]["gl"] = gl
    context["client"]["hl"] = hl
    payload: dict = {"context": context, "browseId": "FEtrending"}
    if filter_params:
        payload["params"] = filter_params

    collected: List[Dict] = []
    continuation: Optional[str] = None

    async with create_httpx_client(proxy=proxy, headers=headers) as client:
        resp = await client.post(browse_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        contents = data.get("contents", {})
        tabs = contents.get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
        if not tabs:
            raise YouTubeStructureChangedError(
                "API trending: twoColumnBrowseResultsRenderer.tabs missing",
                context={"contents_keys": list(contents.keys())},
            )
        first_tab = tabs[0].get("tabRenderer", {})
        tab_content = first_tab.get("content", {})
        if "richGridRenderer" in tab_content:
            renderers = tab_content["richGridRenderer"].get("contents", [])
        else:
            renderers = tab_content.get("sectionListRenderer", {}).get("contents", [])

        for item in renderers:
            if "richItemRenderer" in item:
                video = item["richItemRenderer"].get("content", {})
                collected += extract_videos([video], rank_offset=len(collected))
            elif "richSectionRenderer" in item or "shelfRenderer" in item or "carouselRenderer" in item:
                collected += extract_videos_from_item(item, rank_offset=len(collected))
            elif "continuationItemRenderer" in item:
                continuation = extract_continuation_token(item)
            if len(collected) >= max_results:
                return collected[:max_results]

        while continuation and len(collected) < max_results:
            cont_payload = {"context": context, "continuation": continuation}
            resp = await client.post(browse_url, json=cont_payload)
            resp.raise_for_status()
            cont_data = resp.json()
            items = get_continuation_items(cont_data)
            continuation = None
            for item in items:
                if "richItemRenderer" in item:
                    video = item["richItemRenderer"].get("content", {})
                    collected += extract_videos([video], rank_offset=len(collected))
                elif "itemSectionRenderer" in item:
                    for sub in item["itemSectionRenderer"].get("contents", []):
                        collected += extract_videos_from_item(sub, rank_offset=len(collected))
                elif "continuationItemRenderer" in item:
                    continuation = extract_continuation_token(item)
                if len(collected) >= max_results:
                    return collected[:max_results]

    return collected

async def _html_trending(proxy, max_results, filter_params, gl, hl) -> List[Dict]:
    params = f"gl={gl}&hl={hl}"
    if filter_params:
        params += f"&bp={filter_params}"
    page_url = f"{TRENDING_URL}?{params}"

    async with _make_session(proxy=proxy, gl=gl, hl=hl) as client:
        resp = await client.get(page_url)
        resp.raise_for_status()
        data = _parse_yt_initial_data(resp.text)

    contents = data.get("contents", {})
    tabs = contents.get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
    if not tabs:
        raise YouTubeStructureChangedError(
            "twoColumnBrowseResultsRenderer.tabs is empty or missing",
            context={"contents_keys": list(contents.keys())},
        )
    first_tab = tabs[0].get("tabRenderer", {})
    tab_content = first_tab.get("content", {})
    if "richGridRenderer" in tab_content:
        renderers = tab_content["richGridRenderer"].get("contents", [])
    else:
        renderers = tab_content.get("sectionListRenderer", {}).get("contents", [])

    collected: List[Dict] = []
    continuation: Optional[str] = None

    for item in renderers:
        if "richItemRenderer" in item:
            video = item["richItemRenderer"].get("content", {})
            collected += extract_videos([video], rank_offset=len(collected))
        elif "richSectionRenderer" in item or "shelfRenderer" in item or "carouselRenderer" in item:
            collected += extract_videos_from_item(item, rank_offset=len(collected))
        elif "continuationItemRenderer" in item:
            continuation = extract_continuation_token(item)
        if len(collected) >= max_results:
            return collected[:max_results]

    if continuation and len(collected) < max_results:
        api_key = await get_youtube_api_key(proxy=proxy)
        api_headers = get_youtube_headers(visitor_data=get_visitor_data(), client_version=get_client_version())
        browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
        ua = api_headers.get("User-Agent")
        async with create_httpx_client(proxy=proxy, headers=api_headers) as client:
            while continuation and len(collected) < max_results:
                payload = {
                    "context": get_context(original_url=TRENDING_URL, user_agent=ua),
                    "continuation": continuation,
                }
                resp = await client.post(browse_url, json=payload)
                resp.raise_for_status()
                cont_data = resp.json()
                items = get_continuation_items(cont_data)
                for item in items:
                    if "richItemRenderer" in item:
                        video = item["richItemRenderer"].get("content", {})
                        collected += extract_videos([video], rank_offset=len(collected))
                    elif "itemSectionRenderer" in item:
                        for sub in item["itemSectionRenderer"].get("contents", []):
                            collected += extract_videos_from_item(sub, rank_offset=len(collected))
                    if len(collected) >= max_results:
                        return collected[:max_results]
                continuation = next(
                    (extract_continuation_token(item) for item in items if "continuationItemRenderer" in item),
                    None,
                )

    return collected

async def _search_trending(proxy, max_results, gl, hl) -> List[Dict]:
    # Datacenter IPs get feedNudgeRenderer instead of trending — search by view count as proxy.
    api_key = await get_youtube_api_key(proxy=proxy)
    api_headers = get_youtube_headers(visitor_data=get_visitor_data(), client_version=get_client_version())
    search_url = get_youtube_api_url(ENDPOINT_SEARCH, api_key)
    context = get_context(original_url=TRENDING_URL, user_agent=api_headers.get("User-Agent"))
    context["client"]["hl"] = hl
    context["client"]["gl"] = gl
    payload = {"context": context, "query": "", "params": SORT_VIEW_COUNT}

    collected: List[Dict] = []
    continuation: Optional[str] = None

    async with create_httpx_client(proxy=proxy, headers=api_headers) as client:
        resp = await client.post(search_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        sections = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        for section in sections:
            if "itemSectionRenderer" in section:
                for item in section["itemSectionRenderer"].get("contents", []):
                    video = item.get("videoRenderer")
                    if not video or not video.get("videoId"):
                        continue
                    parsed = parse_video_renderer(video)
                    parsed["rank"] = len(collected) + 1
                    collected.append(parsed)
            if "continuationItemRenderer" in section:
                continuation = extract_continuation_token(section)
            if len(collected) >= max_results:
                return collected[:max_results]

        while continuation and len(collected) < max_results:
            token, continuation = continuation, None
            cont_payload = {"context": context, "continuation": token}
            resp = await client.post(search_url, json=cont_payload)
            resp.raise_for_status()
            cont_data = resp.json()
            for section in get_continuation_items(cont_data):
                if "itemSectionRenderer" in section:
                    for item in section["itemSectionRenderer"].get("contents", []):
                        video = item.get("videoRenderer")
                        if not video or not video.get("videoId"):
                            continue
                        parsed = parse_video_renderer(video)
                        parsed["rank"] = len(collected) + 1
                        collected.append(parsed)
                if "continuationItemRenderer" in section:
                    continuation = extract_continuation_token(section)
                if len(collected) >= max_results:
                    return collected[:max_results]

    return collected

async def _safe(coro, label: str):
    """Run a coroutine, returning (result, None) or (None, exc) — never raises."""
    try:
        return await coro, None
    except Exception as exc:
        return None, (label, exc)

async def get_trending_videos(
    proxy: Optional[str] = None,
    max_results: int = 100,
    filter_params: Optional[str] = None,
    gl: str = "VN",
    hl: str = "vi",
    skip_live: bool = True,
    skip_trending: bool = False,
) -> List[Dict]:
    logger.info("🟢 [trending] starting crawl gl=%s", gl)
    if skip_trending:
        return []

    # Run API and HTML methods in parallel — take first non-empty result.
    # This cuts wall-clock time roughly in half when one method is slow to fail.
    if proxy:
        (api_result, api_err), (html_result, html_err) = await asyncio.gather(
            _safe(_api_trending(proxy, max_results, filter_params, gl, hl),  "api"),
            _safe(_html_trending(proxy, max_results, filter_params, gl, hl), "html"),
        )
        if api_err:
            logger.warning("🔴 [trending] API failed: %s — %r", *api_err)
        if html_err:
            logger.warning("🔴 [trending] HTML failed: %s — %r", *html_err)

        collected = api_result or html_result or []
        if api_result:
            logger.info("🟢 [trending] API method: %d videos", len(api_result))
        elif html_result:
            logger.info("🟢 [trending] HTML method: %d videos", len(html_result))
    else:
        logger.info("🟡 [trending] no proxy — using HTML fallback")
        collected, err = await _safe(_html_trending(proxy, max_results, filter_params, gl, hl), "html")
        if err:
            logger.warning("🔴 [trending] HTML failed: %s — %r", *err)
        collected = collected or []

    if not collected:
        logger.warning("🔴 [trending] all methods failed — falling back to view-count search")
        collected = await _search_trending(proxy, max_results, gl, hl)
        logger.info("🟡 [trending] search fallback: %d videos", len(collected))

    if skip_live:
        before = len(collected)
        collected = [v for v in collected if not _is_live_video(v)]
        filtered = before - len(collected)
        if filtered:
            logger.info("🟢 [trending] filtered %d live videos", filtered)

    logger.info("🟢 [trending] done: %d videos", len(collected))
    return collected[:max_results]
