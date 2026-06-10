from typing import Optional
from app.config.proxy_manager import ProxyManager
from app.config.settings import YOUTUBE_BASE_URL, YOUTUBE_API_BASE, PROXY_LIST

proxy_manager = ProxyManager(PROXY_LIST)


def get_proxy() -> Optional[str]:
    """Legacy sync getter — returns None, use await proxy_manager.get_proxy() instead."""
    return None


def get_youtube_api_url(endpoint: str, api_key: str) -> str:
    return f"{YOUTUBE_API_BASE}/{endpoint}?key={api_key}"
