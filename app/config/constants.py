ENDPOINT_BROWSE = "browse"
ENDPOINT_SEARCH = "search"
ENDPOINT_PLAYER = "player"
ENDPOINT_NEXT = "next"

BROWSE_ID_TRENDING = "FEtrending"

SEARCH_FILTER_LIVE = "EgJAAQ%3D%3D"
SEARCH_FILTER_LOCATION = "EgIIAQ%3D%3D"

SORT_RELEVANCE = None
SORT_UPLOAD_DATE = "CAISAhAB"
SORT_VIEW_COUNT = "CAMSAhAB"
SORT_RATING = "CAESAhAB"

CHANNEL_TAB_VIDEOS = "EgZ2aWRlb3M"

TRENDING_FILTER_NOW = None
TRENDING_FILTER_MUSIC = "EgZtdXNpYw%3D%3D"
TRENDING_FILTER_GAMES = "EgZnYW1pbmc%3D"
TRENDING_FILTER_MOVIES = "EgZtb3ZpZXM%3D"

CLIENT_NAME = "WEB"
CLIENT_VERSION = "2.20260603.05.00"
CLIENT_HL = "vi"
CLIENT_GL = "VN"

# Public InnerTube WEB client key — static for years, same for everyone.
INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

DEFAULT_TIMEOUT = 15

# TikTok session pool
TIKTOK_POOL_SIZE = 3
TIKTOK_NATIVE_TIMEOUT = 25.0  # seconds — hard cap per search
TIKTOK_WARM_TIMEOUT = 25.0  # first warm attempt
TIKTOK_WARM_TIMEOUT_2 = 30.0  # retry warm attempt
TIKTOK_WARM_EXPLORE = 20.0  # /explore page warm
MSTOKEN_TTL = 50.0  # reuse within session; TikTok expires ~55s
POOL_REFRESH_INTERVAL = 600.0  # 10 min — stay within sticky-proxy window

# TikTok search cache
TIKTOK_CACHE_TTL = 1800.0  # 30 min
TIKTOK_CACHE_MAX_SIZE = 500

# TikHub API client
TIKHUB_TIMEOUT = 20.0
TIKHUB_MAX_CONN = 10
TIKHUB_MAX_KEEPALIVE = 5

REMOTE_CONFIG_TIMEOUT = 5

# YouTube / HTTP
YOUTUBE_KEY_TTL = 86400  # 24h
HTTP_MAX_CONNECTIONS = 20
HTTP_MAX_KEEPALIVE = 10

YOUTUBE_BASE_URL = "https://www.youtube.com"
YOUTUBE_API_BASE = "https://www.youtube.com/youtubei/v1"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
