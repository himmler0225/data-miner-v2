import os

from dotenv import load_dotenv

from app.config.rate_limits import (
    BURST_LIMITS,
    RATE_LIMIT_BURST,
    RATE_LIMIT_DEFAULT,
    RATE_LIMITS,
    SERVICE_RATE_LIMITS,
)

load_dotenv()

APP_ENV: str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",") if o.strip()
]
RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory://")
REQUIRE_SERVICE_AUTH: bool = (
    os.getenv("REQUIRE_SERVICE_AUTH", "true" if APP_ENV != "development" else "false").lower() == "true"
)
ENABLE_IP_WHITELIST: bool = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"
WHITELISTED_IPS: list[str] = [ip.strip() for ip in os.getenv("WHITELISTED_IPS", "").split(",") if ip.strip()]
WHITELISTED_SERVICES: list[str] = [s.strip() for s in os.getenv("WHITELISTED_SERVICES", "").split(",") if s.strip()]
ENABLE_SCHEDULER: bool = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
HEALTH_CHECK_INTERVAL: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
CLEANUP_CRON: str = os.getenv("CLEANUP_CRON", "0 2 * * 0")
TIKHUB_API_KEY: str = os.getenv("TIKHUB_API_KEY", "") or os.getenv("TIKAP_API_KEY", "")
TIKAP_API_KEY: str = TIKHUB_API_KEY
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
