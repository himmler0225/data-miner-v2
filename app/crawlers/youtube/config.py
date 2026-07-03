"""YouTube crawler constants (endpoints, client identity, URLs)."""

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
INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
DEFAULT_TIMEOUT = 15
YOUTUBE_KEY_TTL = 86400
YOUTUBE_BASE_URL = "https://www.youtube.com"
YOUTUBE_API_BASE = "https://www.youtube.com/youtubei/v1"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Topic maps for agent tools and /api/videos/by-topic
CHANNEL_TOPICS: dict[str, str] = {"music": "UC-9-kyTW8ZkZNDHQJ6FgpwQ"}
SEARCH_TOPICS: dict[str, tuple[str, str]] = {
    "gaming": ("gaming highlights", "view_count"),
    "news": ("tin tức việt nam hôm nay", "upload_date"),
    "sports": ("thể thao việt nam", "view_count"),
    "tech": ("review công nghệ", "view_count"),
    "beauty": ("beauty skincare review", "view_count"),
    "food": ("ẩm thực việt nam", "view_count"),
    "travel": ("du lịch việt nam", "view_count"),
}
ALL_TOPICS = list(CHANNEL_TOPICS.keys()) + list(SEARCH_TOPICS.keys())
