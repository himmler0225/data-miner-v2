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

# Rate limits — sourced from Supabase remote config (config/remote.py), not from env.
RATE_LIMIT_DEFAULT: str = "100/hour"
RATE_LIMIT_BURST:   str = "20/minute"
RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory://")

ENABLE_IP_WHITELIST:  bool      = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"
WHITELISTED_IPS:      list[str] = [ip.strip() for ip in os.getenv("WHITELISTED_IPS", "").split(",") if ip.strip()]
WHITELISTED_SERVICES: list[str] = [s.strip()  for s in  os.getenv("WHITELISTED_SERVICES", "").split(",") if s.strip()]

ENABLE_SCHEDULER:      bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
HEALTH_CHECK_INTERVAL: int  = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))

CLEANUP_CRON:   str = os.getenv("CLEANUP_CRON",   "0 2 * * 0")

TIKAP_API_KEY: str = os.getenv("TIKAP_API_KEY", "")

# Supabase — remote config
SUPABASE_URL:         str = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY: str = os.getenv('SUPABASE_SERVICE_KEY', '')
