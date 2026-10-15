import asyncio
import base64
from typing import Literal

from app.config.constants import ENDPOINT_NEXT
from app.config.logger import Logger
from app.crawlers.youtube.client import create_httpx_client, get_context, get_youtube_api_key, get_youtube_api_url
from app.crawlers.youtube.utils import parse_count

from ..shared.parsers import extract_continuation_token, first_continuation_token

logger = Logger.get(__name__)

CommentSort = Literal["top", "newest"]

# "Show more replies" pages followed per comment thread.
MAX_REPLY_PAGES = 2


def _build_comment_sort_token(video_id: str, sort: str = "top") -> str:
    vid = video_id.encode()
    n = len(vid)

    inner_vid = bytes([0x12, n]) + vid
    f2 = bytes([0x12, len(inner_vid)]) + inner_vid
    f3 = bytes([0x18, 0x06]) if sort == "newest" else b""

    inner4 = bytes([0x22, n]) + vid + bytes([0x30, 0x01, 0x78, 0x02])
    f4 = bytes([0x22, len(inner4)]) + inner4
    f8 = bytes([0x42, 0x10]) + b"comments-section"
    f6_content = f4 + f8
    f6 = bytes([0x32, len(f6_content)]) + f6_content

    return base64.urlsafe_b64encode(f2 + f3 + f6).decode().rstrip("=")


def extract_comment_continuation_token(data: dict) -> str | None:
    # Path 1: onResponseReceivedEndpoints
    try:
        for ep in data.get("onResponseReceivedEndpoints", []):
            for action_key in (
                "reloadContinuationItemsCommand",
                "appendContinuationItemsAction",
            ):
                for item in ep.get(action_key, {}).get("continuationItems", []):
                    token = (
                        item.get("continuationItemRenderer", {})
                        .get("continuationEndpoint", {})
                        .get("continuationCommand", {})
                        .get("token")
                    )
                    if token:
                        return token
    except Exception as e:
        logger.debug("Path 1 (onResponseReceivedEndpoints) failed: %s", e)

    # Path 2: twoColumnWatchNextResults
    try:
        results = (
            data.get("contents", {})
            .get("twoColumnWatchNextResults", {})
            .get("results", {})
            .get("results", {})
            .get("contents", [])
        )
        for item in results:
            for content in item.get("itemSectionRenderer", {}).get("contents", []):
                token = (
                    content.get("continuationItemRenderer", {})
                    .get("continuationEndpoint", {})
                    .get("continuationCommand", {})
                    .get("token")
                )
                if token:
                    return token
    except Exception as e:
        logger.debug("Path 2 (twoColumnWatchNextResults) failed: %s", e)

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
        logger.debug("Path 3 (engagementPanels) failed: %s", e)

    # Path 4: frameworkUpdates mutations
    try:
        for m in data.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []):
            token = m.get("payload", {}).get("continuationEndpoint", {}).get("continuationCommand", {}).get("token")
            if token:
                return token
    except Exception as e:
        logger.debug("Path 4 (frameworkUpdates) failed: %s", e)

    return None


def parse_comment_entities(data: dict) -> dict[str, dict]:
    """Comment payloads by commentId. The comment list itself only carries ids;
    text/author/counts live in `frameworkUpdates` entity mutations."""
    result = {}
    for mutation in data.get("frameworkUpdates", {}).get("entityBatchUpdate", {}).get("mutations", []):
        comment = mutation.get("payload", {}).get("commentEntityPayload", {})
        props = comment.get("properties", {})
        comment_id = props.get("commentId")
        content = props.get("content", {}).get("content", "")
        if not comment_id or not isinstance(content, str):
            continue
        toolbar = comment.get("toolbar", {})
        # likeCountLiked is the count as shown after *you* liked it (+1).
        likes = toolbar.get("likeCountNotliked", toolbar.get("likeCountLiked"))
        result[comment_id] = {
            "comment_id": comment_id,
            "author": comment.get("author", {}).get("displayName", ""),
            "author_avatar": comment.get("author", {}).get("avatarThumbnailUrl", ""),
            "content": content,
            "published_time": props.get("publishedTime", ""),
            "like_count": parse_count(likes) or 0,
            "reply_count": parse_count(toolbar.get("replyCount")) or 0,
        }
    return result


async def _post(client, url: str, continuation: str) -> dict:
    resp = await client.post(url, json={"context": get_context(), "continuation": continuation})
    resp.raise_for_status()
    return resp.json()


async def fetch_replies(client, url: str, token: str) -> list[dict]:
    """Replies of one comment thread, up to MAX_REPLY_PAGES pages."""
    replies = []
    for _ in range(MAX_REPLY_PAGES):
        if not token:
            break
        data = await _post(client, url, token)
        entities = parse_comment_entities(data)
        token = None
        for action in data.get("onResponseReceivedEndpoints", []):
            for item in action.get("appendContinuationItemsAction", {}).get("continuationItems", []):
                if "commentViewModel" in item:
                    reply = entities.get(item["commentViewModel"].get("commentId"))
                    if reply:
                        reply.pop("reply_count", None)
                        replies.append(reply)
                elif "continuationItemRenderer" in item:
                    token = (
                        item["continuationItemRenderer"]
                        .get("button", {})
                        .get("buttonRenderer", {})
                        .get("command", {})
                        .get("continuationCommand", {})
                        .get("token")
                    )
    return replies


def _parse_comment_page(data: dict) -> tuple[list[dict], list[str | None], str | None]:
    """(comments, reply token per comment, next page token) of one comments page."""
    entities = parse_comment_entities(data)
    comments, reply_tokens, next_token = [], [], None
    for action in data.get("onResponseReceivedEndpoints", []):
        items = action.get("reloadContinuationItemsCommand", {}).get("continuationItems", []) or action.get(
            "appendContinuationItemsAction", {}
        ).get("continuationItems", [])
        for item in items:
            if "continuationItemRenderer" in item:
                next_token = extract_continuation_token(item) or next_token
                continue
            thread = item.get("commentThreadRenderer")
            if not thread:
                continue
            comment_id = thread.get("commentViewModel", {}).get("commentViewModel", {}).get("commentId")
            comment = entities.get(comment_id)
            if not comment:
                continue
            reply_contents = thread.get("replies", {}).get("commentRepliesRenderer", {}).get("contents", [])
            comments.append({**comment, "replies": []})
            reply_tokens.append(first_continuation_token(reply_contents))
    return comments, reply_tokens, next_token


async def fetch_comments_page(
    video_id: str, sort: CommentSort = "top", token: str | None = None, proxy: str | None = None
) -> tuple[list[dict], str | None]:
    """One page of a video's comments (~20), each with its replies: `(comments, next_token)`.
    A video with comments disabled returns `([], None)`."""
    api_key = await get_youtube_api_key(proxy=proxy)
    url = get_youtube_api_url(ENDPOINT_NEXT, api_key)

    async with create_httpx_client(proxy=proxy) as client:
        if not token:
            if sort == "newest":
                # A pre-built protobuf token works reliably for newest-first.
                token = _build_comment_sort_token(video_id, "newest")
            else:
                # Top comments need a session token from the watch-next response.
                resp = await client.post(url, json={"context": get_context(), "videoId": video_id})
                resp.raise_for_status()
                token = extract_comment_continuation_token(resp.json())
                if not token:
                    logger.info("[comments] no comments token for %s ; comments may be disabled", video_id)
                    return [], None

        comments, reply_tokens, next_token = _parse_comment_page(await _post(client, url, token))

        pending = [(comment, tok) for comment, tok in zip(comments, reply_tokens, strict=True) if tok]
        results = await asyncio.gather(*(fetch_replies(client, url, tok) for _, tok in pending), return_exceptions=True)
        for (comment, _), replies in zip(pending, results, strict=True):
            if isinstance(replies, list):
                comment["replies"] = replies
            else:
                logger.warning("[comments] replies of %s failed: %r", comment["comment_id"], replies)

    return comments, next_token
