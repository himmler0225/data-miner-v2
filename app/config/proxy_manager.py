import random
from typing import List, Optional
from app.config.logger import Logger

logger = Logger.get(__name__)


class ProxyManager:
    def __init__(self, proxies: List[str]):
        self._proxies = [p for p in proxies if p]
        if self._proxies:
            hosts = [p.split("@")[-1] for p in self._proxies]
            logger.info("ProxyManager: %d proxy(ies) — %s", len(self._proxies), ", ".join(hosts))
        else:
            logger.warning("ProxyManager: no proxy configured — requests go direct")

    async def get_proxy(self) -> Optional[str]:
        if not self._proxies:
            return None
        return random.choice(self._proxies)

    def status(self) -> dict:
        return {
            "count":   len(self._proxies),
            "proxies": [p.split("@")[-1] for p in self._proxies],
        }
