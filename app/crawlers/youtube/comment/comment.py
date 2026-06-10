import base64
from typing import List, Dict, Literal

from ....utils import get_youtube_api_key, get_context, create_httpx_client, parse_view_count
from ....config import get_youtube_api_url
from ....config.constants import ENDPOINT_NEXT
from ....exceptions import YouTubeStructureChangedError
from app.config.logger import Logger

logger = Logger.get(__name__)


def _build_comment_sort_token(video_id: str, sort: str = "top") -> str:
    """
    Construct YouTube comment continuation token with sort order.
    Protobuf reverse-engineered from YouTube InnerTube /next endpoint.
    sort="newest" → field 3 = 6 (COMMENT_SORT_ORDER_BY_TIME)
    sort="top"    → no sort field (YouTube default)
    """
    vid = video_id.encode()
    n = len(vid)

    inner_vid  = bytes([0x12, n]) + vid
    f2         = bytes([0x12, len(inner_vid)]) + inner_vid
    f3         = bytes([0x18, 0x06]) if sort == "newest" else b""

    inner4     = bytes([0x22, n]) + vid + bytes([0x30, 0x01, 0x78, 0x02])
    f4         = bytes([0x22, len(inner4)]) + inner4
    f8         = bytes([0x42, 0x10]) + b"comments-section"
    f6_content = f4 + f8
    f6         = bytes([0x32, len(f6_content)]) + f6_content

    return base64.urlsafe_b64encode(f2 + f3 + f6).decode().rstrip("=")


async def fetch_replies(client, continuation_token: str, context: dict, proxy: str = None, max_depth: int = 2) -> List[Dict]:
    replies = []
    api_key = await get_youtube_api_key(proxy=proxy)
    url_comment = get_youtube_api_url(ENDPOINT_NEXT, api_key)
    depth = 0

    while continuation_token and depth < max_depth:
        payload = {"context": context, "continuation": continuation_token}
        resp = await client.post(url_comment, json=payload)
        resp.raise_for_status()
        data = resp.json()
        entity_map = parse_comment_entities(data)
        continuation_token = None
        depth += 1

        for action in data.get("onResponseReceivedEndpoints", []):
            for item in action.get("appendContinuationItemsAction", {}).get("continuationItems", []):
                if "commentViewModel" in item:
                    comment_vm = item.get("commentViewModel", {})
                    comment_id = comment_vm.get("commentId")
                    entity = entity_map.get(comment_id, {})
                    if not entity:
                        logger.debug(f"Missing entity for reply commentId={comment_id}")
                        continue
                    replies.append({
                        "comment_id": comment_id,
                        "author": entity.get("author", ""),
                        "avatar": entity.get("avatar"),
                        "content": entity.get("content", ""),
                        "published_time": entity.get("published_time", ""),
                        "likes": entity.get("likes", 0),
                    })
                elif "continuationItemRenderer" in item:
                    continuation_token = (
                        item.get("continuationItemRenderer", {})
                        .get("button", {}).get("buttonRenderer", {})
                        .get("command", {}).get("continuationCommand", {}).get("token")
                    )

    return replies


def extract_comment_continuation_token(data: dict) -> str:
    # Path 1: onResponseReceivedEndpoints
    try:
        for ep in data.get("onResponseReceivedEndpoints", []):
            for action_key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
                for item in ep.get(action_key, {}).get("continuationItems", []):
                    token = (
                        item.get("continuationItemRenderer", {})
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {}).get("token")
                    )
                    if token:
                        return token
    except Exception as e:
        logger.debug(f"Path 1 (onResponseReceivedEndpoints) failed: {e}")

    # Path 2: twoColumnWatchNextResults
    try:
        results = (
            data.get("contents", {}).get("twoColumnWatchNextResults", {})
            .get("results", {}).get("results", {}).get("contents", [])
        )
        for item in results:
            for content in item.get("itemSectionRenderer", {}).get("contents", []):
                token = (
                    content.get("continuationItemRenderer", {})
                    .get("continuationEndpoint", {})
                    .get("continuationCommand", {}).get("token")
                )
                if token:
                    return token
    except Exception as e:
        logger.debug(f"Path 2 (twoColumnWatchNextResults) failed: {e}")

    # Path 3: engagementPanels
    try:
        for panel in data.get("engagementPanels", []):
            renderer = panel.get("engagementPanelSectionListRenderer", {})
            if "comment" not in renderer.get("panelIdentifier", "").lower():
                continue
            section = renderer.get("content", {}).get("sectionListRenderer", {})
            for cont in section.get("continuations", []):
                token = cont.get("nextContinuationData", {}).get("continuation")
                if token:
                    return token
    except Exception as e:
        logger.debug(f"Path 3 (engagementPanels) failed: {e}")

    # Path 4: frameworkUpdates mutations
    try:
        for m in data.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []):
            token = (
                m.get("payload", {}).get("continuationEndpoint", {})
                .get("continuationCommand", {}).get("token")
            )
            if token:
                return token
    except Exception as e:
        logger.debug(f"Path 4 (frameworkUpdates) failed: {e}")

    return None


def parse_comment_entities(data: dict) -> dict:
    result = {}
    for m in data.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []):
        payload = m.get("payload", {})
        comment = payload.get("commentEntityPayload", {})
        props = comment.get("properties", {})
        comment_id = props.get("commentId")
        raw_content = props.get("content", {}).get("content", "")
        if not isinstance(raw_content, str):
            continue
        if comment_id:
            result[comment_id] = {
                "content": raw_content,
                "author": comment.get("author", {}).get("displayName", ""),
                "avatar": comment.get("author", {}).get("avatarThumbnailUrl", ""),
                "published_time": props.get("publishedTime", "Unknown"),
                "likes": parse_view_count(comment.get("toolbar", {}).get("likeCountLiked")),
                "replies": parse_view_count(comment.get("toolbar", {}).get("replyCount")),
            }
    return result


async def get_video_comments(
    video_id: str,
    proxy: str = None,
    max_comments: int = 100,
    sort: Literal["top", "newest"] = "top",
) -> List[Dict]:
    api_key  = await get_youtube_api_key(proxy=proxy)
    url_next = get_youtube_api_url(ENDPOINT_NEXT, api_key)
    context  = get_context()
    comments = []

    async with create_httpx_client(proxy=proxy) as client:
        if sort == "newest":
            # Skip the page-load step — use a pre-built sort token directly
            continuation_token = _build_comment_sort_token(video_id, "newest")
            logger.info("Using pre-built newest-sort token for %s", video_id)
        else:
            resp = await client.post(url_next, json={"context": context, "videoId": video_id})
            resp.raise_for_status()
            data = resp.json()
            continuation_token = extract_comment_continuation_token(data)
            if not continuation_token:
                logger.warning("No comment continuation token for %s — comments may be disabled", video_id)
                return []

        while continuation_token and len(comments) < max_comments:
            resp = await client.post(url_next, json={"context": context, "continuation": continuation_token})
            resp.raise_for_status()
            data = resp.json()
            entity_map = parse_comment_entities(data)
            continuation_token = None

            for action in data.get("onResponseReceivedEndpoints", []):
                items = (
                    action.get("reloadContinuationItemsCommand", {}).get("continuationItems", []) or
                    action.get("appendContinuationItemsAction", {}).get("continuationItems", [])
                )
                for item in items:
                    if "commentThreadRenderer" in item:
                        thread = item["commentThreadRenderer"]
                        comment_vm = thread.get("commentViewModel", {}).get("commentViewModel", {})
                        comment_id = comment_vm.get("commentId")
                        entity = entity_map.get(comment_id, {})
                        if not entity:
                            continue
                        content = entity.get("content", "")
                        if not isinstance(content, str):
                            continue

                        comment_data = {
                            "comment_id": comment_id,
                            "author": entity.get("author", ""),
                            "avatar": entity.get("avatar"),
                            "content": content,
                            "published_time": entity.get("published_time", ""),
                            "likes": entity.get("likes", 0),
                            "replies_count": entity.get("replies", 0),
                            "replies": [],
                        }

                        reply_token = None
                        for c in thread.get("replies", {}).get("commentRepliesRenderer", {}).get("contents", []):
                            continuation = (
                                c.get("continuationItemRenderer", {})
                                .get("continuationEndpoint", {})
                                .get("continuationCommand", {}).get("token")
                            )
                            if continuation:
                                reply_token = continuation
                                break

                        if reply_token:
                            logger.debug(f"Fetching replies for comment {comment_id}")
                            comment_data["replies"] = await fetch_replies(client, reply_token, context, proxy=proxy)

                        comments.append(comment_data)
                        if len(comments) >= max_comments:
                            break

                    elif "continuationItemRenderer" in item:
                        continuation_token = (
                            item.get("continuationItemRenderer", )
                            .get("continuationEndpoint", {})
                            .get("continuationCommand", {}).get("token")
                        )

                if len(comments) >= max_comments:
                    break

    return comments[:max_comments]
