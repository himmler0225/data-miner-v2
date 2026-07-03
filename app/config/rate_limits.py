"""Rate limit configuration (defaults + per-endpoint overrides)."""

RATE_LIMIT_DEFAULT = "100/hour"
RATE_LIMIT_BURST = "20/minute"
DEFAULT_ENDPOINT_LIMIT = "30/minute"

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
    "movies": "60/minute",
}

BURST_LIMITS: dict[str, str] = {
    "search": "10/10seconds",
    "video_detail": "20/10seconds",
    "heavy": "3/10seconds",
}

SERVICE_RATE_LIMITS: dict[str, str] = {
    "ai-layer": "500/minute",
    "youtube-api": "200/minute",
    "default": "50/minute",
}
