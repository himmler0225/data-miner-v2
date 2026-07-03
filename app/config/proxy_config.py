"""Proxy pool configuration."""

import os

DEFAULT_COUNTRY = "VN"
TIKTOK_COUNTRY = "US"
PROXY_API_TTL = int(os.getenv("PROXY_API_TTL", "45"))
DIRECT_PROXY_TTL = 900
PUBLIC_IP: str = os.getenv("PUBLIC_IP", "")
