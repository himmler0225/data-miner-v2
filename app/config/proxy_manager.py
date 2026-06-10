from __future__ import annotations

import random
import time
from typing import List, Optional
from app.config.logger import Logger

logger = Logger.get(__name__)

_DEFAULT_TTL = 900

class ProxyManager:

    def __init__(self, proxies: List[str], ttl: int = _DEFAULT_TTL):
        self._proxies:    List[str]     = [p for p in proxies if p]
        self._ttl:        int           = ttl
        self._current:    Optional[str] = None
        self._expires_at: float         = 0.0

        if self._proxies:
            hosts = [p.split("@")[-1] for p in self._proxies]
            logger.info(
                "ProxyManager: %d proxy(ies), sticky TTL=%ds — %s",
                len(self._proxies), ttl, ", ".join(hosts),
            )
        else:
            logger.warning("ProxyManager: no proxy configured — requests go direct")

    async def get_proxy(self) -> Optional[str]:
        if not self._proxies:
            return None

        now = time.monotonic()
        if self._current is None or now >= self._expires_at:
            self._current    = random.choice(self._proxies)
            self._expires_at = now + self._ttl
            host = self._current.split("@")[-1]
            logger.info("ProxyManager: pinned to %s for next %ds", host, self._ttl)

        return self._current

    def rotate(self) -> None:
        """Force immediate rotation on next request — call when a proxy fails."""
        self._expires_at = 0.0
        logger.info("ProxyManager: forced rotation scheduled")

    def status(self) -> dict:
        remaining = max(0, self._expires_at - time.monotonic())
        return {
            "count":         len(self._proxies),
            "current":       self._current.split("@")[-1] if self._current else None,
            "ttl_remaining": round(remaining),
            "proxies":       [p.split("@")[-1] for p in self._proxies],
        }
