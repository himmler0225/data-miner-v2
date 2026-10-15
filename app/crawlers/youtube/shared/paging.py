"""Cursor pagination over YouTube's continuation-token pages.

YouTube pages have their own size (~20-30 items) that doesn't line up with the
caller's `limit`, so a cursor is (continuation token of a YouTube page, how many
of that page's raw items were already returned). A None token means the first
page. Cursors are opaque base64 strings to callers.
"""

import base64
import binascii
import json
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass

from app.exceptions import InvalidInputError

# One YouTube page, given its continuation token (None = first page):
# returns (items, next continuation token or None).
PageFetcher = Callable[[str | None], Awaitable[tuple[list[dict], str | None]]]

# Upper bound on YouTube pages read to fill one call, so pages that come back
# empty (ads, shelves only) can't spin forever.
MAX_PAGES_PER_CALL = 10


@dataclass
class Page:
    items: list[dict]
    next_cursor: str | None

    def as_dict(self) -> dict:
        return {"items": self.items, "next_cursor": self.next_cursor, "has_more": self.next_cursor is not None}


def encode_cursor(token: str | None, skip: int) -> str:
    raw = json.dumps({"t": token, "s": skip}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[str | None, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        state = json.loads(raw)
        token, skip = state["t"], int(state["s"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise InvalidInputError("errors.invalid_cursor") from exc
    if (token is not None and not isinstance(token, str)) or skip < 0:
        raise InvalidInputError("errors.invalid_cursor")
    return token, skip


async def collect_page(
    fetch: PageFetcher,
    limit: int,
    cursor: str | None = None,
    key: Callable[[dict], Hashable] | None = None,
) -> Page:
    """Read YouTube pages starting at `cursor` until `limit` items are collected.
    `key` drops items already collected in this call (YouTube repeats some)."""
    token, skip = decode_cursor(cursor) if cursor else (None, 0)
    items: list[dict] = []
    seen: set = set()

    for _ in range(MAX_PAGES_PER_CALL):
        page_items, next_token = await fetch(token)
        for index in range(skip, len(page_items)):
            if len(items) == limit:
                return Page(items, encode_cursor(token, index))
            item = page_items[index]
            if key is not None:
                item_key = key(item)
                if item_key in seen:
                    continue
                seen.add(item_key)
            items.append(item)
        if not next_token:
            return Page(items, None)
        token, skip = next_token, 0
        if len(items) == limit:
            break

    return Page(items, encode_cursor(token, 0))
