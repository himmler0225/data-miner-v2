from app.config.constants import ENDPOINT_BROWSE, YOUTUBE_BASE_URL
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url
from app.crawlers.youtube.utils import parse_count
from app.exceptions import YouTubeNotFoundError

# Header metadata texts are localized to the request's hl ("người đăng ký" for vi).
_SUBSCRIBER_WORDS = ("subscriber", "đăng ký")
_VIDEO_WORDS = ("video",)


def _last_source_url(sources: list[dict]) -> str | None:
    return sources[-1].get("url") if sources else None


def parse_channel_info(data: dict) -> dict:
    metadata = data.get("metadata", {}).get("channelMetadataRenderer", {})
    channel_id = metadata.get("externalId")
    if not channel_id:
        raise YouTubeNotFoundError("Channel not found (no channelMetadataRenderer in response)")

    header = data.get("header", {}).get("pageHeaderRenderer", {})
    header_vm = header.get("content", {}).get("pageHeaderViewModel", {})
    rows = header_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    handle = subscribers = videos = None
    for row in rows:
        for part in row.get("metadataParts", []):
            text = part.get("text", {}).get("content", "")
            lowered = text.lower()
            if text.startswith("@"):
                handle = text
            elif any(word in lowered for word in _SUBSCRIBER_WORDS):
                subscribers = text
            elif any(word in lowered for word in _VIDEO_WORDS):
                videos = text

    banner_sources = header_vm.get("banner", {}).get("imageBannerViewModel", {}).get("image", {}).get(
        "sources"
    ) or header.get("banner", {}).get("imageBannerViewModel", {}).get("image", {}).get("sources", [])
    return {
        "channel_id": channel_id,
        "url": f"{YOUTUBE_BASE_URL}/channel/{channel_id}",
        "channel_name": metadata.get("title", ""),
        "handle": handle,
        "description": metadata.get("description", ""),
        "avatar": _last_source_url(metadata.get("avatar", {}).get("thumbnails", [])),
        "banner": _last_source_url(banner_sources),
        "subscriber_count": parse_count(subscribers),
        "video_count": parse_count(videos),
    }


async def get_channel_info(channel_id: str, proxy: str | None = None) -> dict:
    api_key = await get_youtube_api_key(proxy=proxy)
    browse_url = get_youtube_api_url(ENDPOINT_BROWSE, api_key)
    async with create_httpx_client(proxy=proxy) as client:
        resp = await client.post(browse_url, json={"context": get_context(), "browseId": channel_id})
        resp.raise_for_status()
        data = resp.json()
    return parse_channel_info(data)
