"""Shared business logic for YouTube — used by REST API and MCP tools."""

from app.config.proxy import get_proxy
from app.crawlers.youtube.config import CHANNEL_TOPICS, SEARCH_TOPICS
from app.crawlers.youtube.search.search import search_youtube
from app.crawlers.youtube.topic.topic import browse_topic_channel


async def get_videos_by_topic(topic: str, *, limit: int = 20, page: int = 1) -> dict:
    t = topic.lower()
    proxy = await get_proxy()
    start = (page - 1) * limit

    if t in CHANNEL_TOPICS:
        result = await browse_topic_channel(CHANNEL_TOPICS[t], max_videos=start + limit, proxy=proxy)
        videos = result["videos"][start:]
        return {
            "topic": topic,
            "source": "channel_browse",
            "playlists": result.get("playlists", []),
            "featured": result.get("featured_playlist"),
            "total": len(videos),
            "videos": videos,
        }

    query, sort = SEARCH_TOPICS[t]
    results = await search_youtube(query, max_results=start + limit, sort=sort, proxy=proxy)
    return {
        "topic": topic,
        "source": "search",
        "query": query,
        "page": page,
        "total": len(results),
        "videos": results[start : start + limit],
    }
