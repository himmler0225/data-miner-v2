from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV:   str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

# Proxy pools — sourced from Supabase remote config (config/remote.py), not from env.
PROXY_VN:   list[str] = []
PROXY_US:   list[str] = []
PROXY_LIST: list[str] = []

YOUTUBE_BASE_URL: str = os.getenv("YOUTUBE_BASE_URL", "https://www.youtube.com")
YOUTUBE_API_BASE: str = os.getenv("YOUTUBE_API_BASE", "https://www.youtube.com/youtubei/v1")

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    if o.strip()
]

# Rate limits — global defaults from Supabase (RATE_LIMIT_DEFAULT / RATE_LIMIT_BURST).
# Per-endpoint maps from Supabase JSON keys (RATE_LIMITS, BURST_LIMITS, SERVICE_RATE_LIMITS).
RATE_LIMIT_DEFAULT: str = "100/hour"
RATE_LIMIT_BURST:   str = "20/minute"
RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory://")

RATE_LIMITS: dict[str, str] = {
    "search": "30/minute",
    "trending": "20/minute",
    "live": "20/minute",
    "video_detail": "60/minute",
    "channel_info": "60/minute",
    "channel_videos": "10/minute",
    "playlist": "10/minute",
    "comments": "15/minute",
    "location": "5/minute",
    "tiktok": "15/minute",
    "tiki": "15/minute",
    "fptshop": "15/minute",
}

BURST_LIMITS: dict[str, str] = {
    "search": "10/10seconds",
    "video_detail": "20/10seconds",
    "heavy": "3/10seconds",
}

SERVICE_RATE_LIMITS: dict[str, str] = {
    "youtube-api": "200/minute",
    "default": "50/minute",
}

ENABLE_IP_WHITELIST:  bool      = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"
WHITELISTED_IPS:      list[str] = [ip.strip() for ip in os.getenv("WHITELISTED_IPS", "").split(",") if ip.strip()]
WHITELISTED_SERVICES: list[str] = [s.strip()  for s in  os.getenv("WHITELISTED_SERVICES", "").split(",") if s.strip()]

ENABLE_SCHEDULER:      bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
HEALTH_CHECK_INTERVAL: int  = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))

# BFF guard — Tiki / FPT Shop chỉ nhận request từ ai-chatbot (header X-Rm-Bff)
BFF_CLIENT_TOKEN: str = os.getenv("BFF_CLIENT_TOKEN", "")
BFF_GUARD_ENABLED: bool = (
    os.getenv("BFF_GUARD_ENABLED", "true" if APP_ENV != "development" else "false").lower() == "true"
)

CLEANUP_CRON:   str = os.getenv("CLEANUP_CRON",   "0 2 * * 0")

TIKAP_API_KEY: str = os.getenv("TIKAP_API_KEY", "")

# Supabase — remote config
SUPABASE_URL:         str = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY: str = os.getenv('SUPABASE_SERVICE_KEY', '')
