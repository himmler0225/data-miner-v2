import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.config.constants import TIKTOK_CACHE_MAX_SIZE, TIKTOK_CACHE_TTL

_store: Dict[str, Tuple[float, Any]] = {}
_lock = threading.Lock()


def _key(parts: Tuple) -> str:
    return "|".join(str(p) for p in parts)


def get(parts: Tuple) -> Optional[Any]:
    k = _key(parts)
    with _lock:
        entry = _store.get(k)
        if entry and time.time() - entry[0] < TIKTOK_CACHE_TTL:
            return entry[1]
        if entry:
            _store.pop(k, None)
    return None


def put(parts: Tuple, value: Any) -> None:
    k = _key(parts)
    with _lock:
        if len(_store) >= TIKTOK_CACHE_MAX_SIZE:
            oldest = sorted(_store, key=lambda x: _store[x][0])[:50]
            for o in oldest:
                _store.pop(o, None)
        _store[k] = (time.time(), value)
