"""Backward-compatible re-exports — prefer importing from module config files."""

from app.config.http import (
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE,
    REMOTE_CONFIG_TIMEOUT,
)
from app.crawlers.youtube.config import (
    CHANNEL_TAB_VIDEOS,
    CLIENT_GL,
    CLIENT_HL,
    CLIENT_NAME,
    CLIENT_VERSION,
    DEFAULT_TIMEOUT,
    ENDPOINT_BROWSE,
    ENDPOINT_NEXT,
    ENDPOINT_PLAYER,
    ENDPOINT_SEARCH,
    INNERTUBE_API_KEY,
    SEARCH_FILTER_LIVE,
    SORT_RATING,
    SORT_RELEVANCE,
    SORT_UPLOAD_DATE,
    SORT_VIEW_COUNT,
    YOUTUBE_API_BASE,
    YOUTUBE_BASE_URL,
    YOUTUBE_KEY_TTL,
)

# TikTok — lazy names for legacy imports; source of truth is app.crawlers.tiktok.config
from app.crawlers.tiktok import config as _tiktok_cfg

MSTOKEN_TTL = _tiktok_cfg.MSTOKEN_TTL
POOL_REFRESH_INTERVAL = _tiktok_cfg.POOL_REFRESH_INTERVAL
TIKHUB_MAX_CONN = _tiktok_cfg.TIKHUB_MAX_CONN
TIKHUB_MAX_KEEPALIVE = _tiktok_cfg.TIKHUB_MAX_KEEPALIVE
TIKHUB_TIMEOUT = _tiktok_cfg.TIKHUB_TIMEOUT
TIKTOK_CACHE_MAX_SIZE = _tiktok_cfg.TIKTOK_CACHE_MAX_SIZE
TIKTOK_CACHE_TTL = _tiktok_cfg.TIKTOK_CACHE_TTL
TIKTOK_NATIVE_TIMEOUT = _tiktok_cfg.TIKTOK_NATIVE_TIMEOUT
TIKTOK_POOL_SIZE = _tiktok_cfg.TIKTOK_POOL_SIZE
TIKTOK_WARM_EXPLORE = _tiktok_cfg.TIKTOK_WARM_EXPLORE
TIKTOK_WARM_TIMEOUT = _tiktok_cfg.TIKTOK_WARM_TIMEOUT
TIKTOK_WARM_TIMEOUT_2 = _tiktok_cfg.TIKTOK_WARM_TIMEOUT_2
