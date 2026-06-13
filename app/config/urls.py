from app.config.proxy_manager import ProxyManager
from app.config.settings import YOUTUBE_BASE_URL, YOUTUBE_API_BASE, PROXY_VN, PROXY_US

# VN = default for YouTube / TikTok / Tiki (all VN-focused, bandwidth-heavy).
proxy_manager    = ProxyManager(PROXY_VN)
# US (ZingProxy, ~1GB) = only for explicit US-geo requests.
proxy_manager_us = ProxyManager(PROXY_US)

def get_youtube_api_url(endpoint: str, api_key: str) -> str:
    return f"{YOUTUBE_API_BASE}/{endpoint}?key={api_key}"
