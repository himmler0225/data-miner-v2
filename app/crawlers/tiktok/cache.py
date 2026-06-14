"""Tiny in-memory TTL cache for TikTok search results.
Shared across all requests — cache hit skips both native and TikHub API calls."""
import time
import threading
from typing import Any, Dict, Optional, Tuple

_TTL      = 1800.0   # 30 min — search results are fresh enough for analysis
_MAX      = 500
_store: Dict[str, Tuple[float, Any]] = {}
_lock     = threading.Lock()


def _key(parts: Tuple) -> str:
    return "|".join(str(p) for p in parts)


def get(parts: Tuple) -> Optional[Any]:
    k = _key(parts)
    with _lock:
        entry = _store.get(k)
        if entry and time.time() - entry[0] < _TTL:
            return entry[1]
        if entry:
            _store.pop(k, None)
    return None


def put(parts: Tuple, value: Any) -> None:
    k = _key(parts)
    with _lock:
        if len(_store) >= _MAX:
            oldest = sorted(_store, key=lambda x: _store[x][0])[:50]
            for o in oldest:
                _store.pop(o, None)
        _store[k] = (time.time(), value)
