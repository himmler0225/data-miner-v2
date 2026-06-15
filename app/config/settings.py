"""
Central settings file — tất cả os.getenv tập trung tại đây.
Các module khác import từ đây thay vì gọi os.getenv trực tiếp.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV:   str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

def _proxy_list(env: str) -> list[str]:
    return [p.strip() for p in (os.getenv(env) or "").split(",") if p.strip()]

# VN residential (rotating, unmetered) — workhorse for all VN-focused crawling.
PROXY_VN: list[str] = _proxy_list("PROXY_VN")
# US residential (ZingProxy, ~1GB cap) — reserved for explicit US-geo requests only.
PROXY_US: list[str] = _proxy_list("PROXY_US")
# Back-compat: PROXY_LIST falls back to VN pool if the split vars aren't set.
PROXY_LIST: list[str] = PROXY_VN or _proxy_list("PROXY_LIST")

YOUTUBE_BASE_URL: str = os.getenv("YOUTUBE_BASE_URL", "https://www.youtube.com")
YOUTUBE_API_BASE: str = os.getenv("YOUTUBE_API_BASE", "https://www.youtube.com/youtubei/v1")

INGEST_API_URL:     str = os.getenv("INGEST_API_URL",     "http://localhost:3000")
INGEST_SERVICE_KEY: str = os.getenv("INGEST_SERVICE_KEY", "")

NESTJS_WS_URL:  str = os.getenv("NESTJS_WS_URL",  "http://localhost:3000")
CRAWLER_WS_KEY: str = os.getenv("CRAWLER_WS_KEY", "")

RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "100/hour")
RATE_LIMIT_BURST:   str = os.getenv("RATE_LIMIT_BURST",   "20/minute")
RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory://")

ENABLE_IP_WHITELIST:  bool      = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"
WHITELISTED_IPS:      list[str] = [ip.strip() for ip in os.getenv("WHITELISTED_IPS", "").split(",") if ip.strip()]
WHITELISTED_SERVICES: list[str] = [s.strip()  for s in  os.getenv("WHITELISTED_SERVICES", "").split(",") if s.strip()]

ENABLE_SCHEDULER:      bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
BATCH_CONCURRENCY:     int  = int(os.getenv("BATCH_CONCURRENCY", "5"))
HEALTH_CHECK_INTERVAL: int  = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))

TRENDING_CRON:  str = os.getenv("TRENDING_CRON",  "0 7 * * *")
KEYWORDS_CRON:  str = os.getenv("KEYWORDS_CRON",  "0 8 * * *")
SHORTS_CRON:    str = os.getenv("SHORTS_CRON",    "0 9 * * *")
LIVE_CRON:      str = os.getenv("LIVE_CRON",      "*/5 * * * *")
LOCATION_CRON:  str = os.getenv("LOCATION_CRON",  "0 6 * * *")
CLEANUP_CRON:   str = os.getenv("CLEANUP_CRON",   "0 2 * * 0")

TIKAP_API_KEY: str = os.getenv("TIKAP_API_KEY", "")

# Supabase — remote config
SUPABASE_URL:         str = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY: str = os.getenv('SUPABASE_SERVICE_KEY', '')
