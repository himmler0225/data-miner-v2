"""Small in-process TTL cache for service-level results."""

import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from typing import Any


class TTLCache:
    """Per-entry TTL with LRU eviction beyond `max_size`. Not shared across
    processes/workers; meant to absorb repeated identical requests."""

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._store: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()

    def get(self, key: Hashable) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def put(self, key: Hashable, value: Any, ttl: float) -> None:
        self._store[key] = (time.monotonic() + ttl, value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    async def get_or_fetch(self, key: Hashable, ttl: float, fetch: Callable[[], Awaitable[Any]]) -> Any:
        """Cached value for `key`, or `await fetch()` and cache it. Errors aren't cached."""
        value = self.get(key)
        if value is None:
            value = await fetch()
            self.put(key, value, ttl)
        return value
