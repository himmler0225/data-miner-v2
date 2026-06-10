"""
Central settings file — tất cả os.getenv tập trung tại đây.
Các module khác import từ đây thay vì gọi os.getenv trực tiếp.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ── App ───────────────────────────────────────────────────────────────────────
APP_ENV:   str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Auth ──────────────────────────────────────────────────────────────────────
API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

# ── Proxy ─────────────────────────────────────────────────────────────────────
PROXY_LIST: list[str] = [p.strip() for p in (os.getenv("PROXY_LIST") or "").split(",") if p.strip()]

# ── YouTube ───────────────────────────────────────────────────────────────────
YOUTUBE_BASE_URL: str = os.getenv("YOUTUBE_BASE_URL", "https://www.youtube.com")
YOUTUBE_API_BASE: str = os.getenv("YOUTUBE_API_BASE", "https://www.youtube.com/youtubei/v1")

# ── Ingest API ────────────────────────────────────────────────────────────────
INGEST_API_URL:     str = os.getenv("INGEST_API_URL",     "http://localhost:3000")
INGEST_SERVICE_KEY: str = os.getenv("INGEST_SERVICE_KEY", "")

# ── WebSocket (NestJS) ────────────────────────────────────────────────────────
NESTJS_WS_URL:  str = os.getenv("NESTJS_WS_URL",  "http://localhost:3000")
CRAWLER_WS_KEY: str = os.getenv("CRAWLER_WS_KEY", "")

# ── Rate limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "100/hour")
RATE_LIMIT_BURST:   str = os.getenv("RATE_LIMIT_BURST",   "20/minute")
RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory://")

# ── IP whitelist ──────────────────────────────────────────────────────────────
ENABLE_IP_WHITELIST:  bool      = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"
WHITELISTED_IPS:      list[str] = [ip.strip() for ip in os.getenv("WHITELISTED_IPS", "").split(",") if ip.strip()]
WHITELISTED_SERVICES: list[str] = [s.strip()  for s in  os.getenv("WHITELISTED_SERVICES", "").split(",") if s.strip()]

# ── Scheduler ─────────────────────────────────────────────────────────────────
ENABLE_SCHEDULER:      bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
BATCH_CONCURRENCY:     int  = int(os.getenv("BATCH_CONCURRENCY", "5"))
HEALTH_CHECK_INTERVAL: int  = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))

TRENDING_CRON:  str = os.getenv("TRENDING_CRON",  "0 7 * * *")
KEYWORDS_CRON:  str = os.getenv("KEYWORDS_CRON",  "0 8 * * *")
SHORTS_CRON:    str = os.getenv("SHORTS_CRON",    "0 9 * * *")
LIVE_CRON:      str = os.getenv("LIVE_CRON",      "*/5 * * * *")
LOCATION_CRON:  str = os.getenv("LOCATION_CRON",  "0 6 * * *")
CLEANUP_CRON:   str = os.getenv("CLEANUP_CRON",   "0 2 * * 0")

# ── Third-party APIs ──────────────────────────────────────────────────────────
SOCIAVAULT_API_KEY: str = os.getenv("SOCIAVAULT_API_KEY", "")
