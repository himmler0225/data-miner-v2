import re
import json
import random
import httpx
from typing import List, Dict, Optional
from ..utils import get_youtube_api_key, get_context, get_httpx_proxies, create_httpx_client, parse_view_count
from ..config import get_youtube_headers, get_youtube_api_url
from ..config.constants import ENDPOINT_BROWSE, DEFAULT_TIMEOUT
from ..config.headers import USER_AGENTS, ACCEPT_LANGUAGES
from ..exceptions import YouTubeStructureChangedError
from ..config.logging_config import get_logger

logger = get_logger(__name__)

TRENDING_URL = "https://www.youtube.com/feed/trending"
_YT_HOME = "https://www.youtube.com/"


def _get_page_headers(hl: str = "vi", gl: str = "VN") -> dict:
    ua = random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": f"{hl}-{gl},{hl};q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def _make_session(proxy: Optional[str], headers: dict, gl: str, hl: str) -> httpx.AsyncClient:
    # PREF cookie sets region/language so YouTube serves the correct trending feed
    proxies = get_httpx_proxies(proxy)
    kwargs: dict = {
        "headers": headers,
        "cookies": {"PREF": f"tz=Asia%2FHo_Chi_Minh&f6=40000000&hl={hl}&gl={gl}"},
        "timeout": DEFAULT_TIMEOUT,
        "follow_redirects": True,
    }
    if proxies:
        kwargs["proxies"] = proxies
    return httpx.AsyncClient(**kwargs)


def extract_videos(items: List[Dict], rank_offset: int = 0) -> List[Dict]:
    results = []
    for item in items:
        video = item.get("videoRenderer") or item.get("gridVideoRenderer")
        if not video:
            continue

        video_id = video.get("videoId")
        if not video_id:
            continue

        owner_runs = video.get("ownerText", {}).get("runs", [{}])
        channel_id = (
            owner_runs[0]
            .get("navigationEndpoint", {})
            .get("browseEndpoint", {})
            .get("browseId")
        )

        results.append({
            "video_id": video_id,
            "rank": rank_offset + len(results) + 1,
            "title": video.get("title", {}).get("runs", [{}])[0].get("text", ""),
            "thumbnails": video.get("thumbnail", {}).get("thumbnails", []),
            "channel": video.get("shortBylineText", {}).get("runs", [{}])[0].get("text", ""),
            "channel_id": channel_id,
            "view_count": parse_view_count(video.get("shortViewCountText", {}).get("simpleText", "")),
            "duration": video.get("lengthText", {}).get("simpleText", ""),
            "published_time": video.get("publishedTimeText", {}).get("simpleText", ""),
        })
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
    # Uses Python's JSON decoder to find the object boundary — more reliable than regex brace-counting
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


async def get_trending_videos(
    proxy: Optional[str] = None,
    max_results: int = 100,
    filter_params: Optional[str] = None,
    gl: str = "VN",
    hl: str = "vi",
) -> List[Dict]:
    page_headers = _get_page_headers(hl=hl, gl=gl)
    api_headers = get_youtube_headers()

    collected: List[Dict] = []
    continuation: Optional[str] = None

    params = f"gl={gl}&hl={hl}"
    if filter_params:
        params += f"&bp={filter_params}"
    page_url = f"{TRENDING_URL}?{params}"

    logger.info(f"Fetching trending page gl={gl}")

    async with _make_session(proxy=proxy, headers=page_headers, gl=gl, hl=hl) as client:
        # Visit homepage first so YouTube sets VISITOR_INFO1_LIVE + YSC session cookies
        await client.get(_YT_HOME)

        resp = await client.get(page_url)
        resp.raise_for_status()
        data = _parse_yt_initial_data(resp.text)

    tabs = (
        data.get("contents", {})
        .get("twoColumnBrowseResultsRenderer", {})
        .get("tabs", [])
    )
    if not tabs:
        raise YouTubeStructureChangedError(
            "twoColumnBrowseResultsRenderer.tabs is empty or missing",
            context={"contents_keys": list(data.get("contents", {}).keys())},
        )

    tab_content = tabs[0].get("tabRenderer", {}).get("content", {})

    # Trending uses richGridRenderer; other browse pages use sectionListRenderer
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
            continuation = (
                item["continuationItemRenderer"]
                .get("continuationEndpoint", {})
                .get("continuationCommand", {})
                .get("token")
            )

        if len(collected) >= max_results:
            return collected[:max_results]

    if not collected:
        dump_path = "/tmp/yt_trending_debug.json"
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.warning(f"No videos collected — ytInitialData saved to {dump_path}")

    if continuation and len(collected) < max_results:
        api_key = await get_youtube_api_key(proxy=proxy)
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

                items = (
                    cont_data.get("onResponseReceivedActions", [{}])[0]
                    .get("appendContinuationItemsAction", {})
                    .get("continuationItems", [])
                )

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
                    (
                        item.get("continuationItemRenderer", {})
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {})
                        .get("token")
                        for item in items
                        if "continuationItemRenderer" in item
                    ),
                    None,
                )

    logger.info(f"Trending crawl done: {len(collected)} videos")
    return collected[:max_results]
