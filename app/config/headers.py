import random
from .constants import CLIENT_VERSION

_CHROME_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.116 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.100 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.116 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.116 Safari/537.36",
]

_EDGE_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36 Edg/131.0.2903.86",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.116 Safari/537.36 Edg/130.0.2849.68",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.205 Safari/537.36 Edg/131.0.2903.86",
]

_FIREFOX_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

_SAFARI_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
]

USER_AGENTS = (
    _CHROME_AGENTS * 5
    + _EDGE_AGENTS * 2
    + _FIREFOX_AGENTS * 2
    + _SAFARI_AGENTS * 1
)

ACCEPT_LANGUAGES = [
    "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "vi-VN,vi;q=0.9,en;q=0.8",
    "vi-VN,vi;q=1.0,en-US;q=0.8",
    "vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.6",
]

SCREEN_RESOLUTIONS = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
    (2560, 1440), (1600, 900), (1280, 720), (1920, 1200),
]

DEVICE_MEMORY = [4, 8, 8, 16, 16, 32]
HARDWARE_CONCURRENCY = [4, 6, 8, 8, 12, 16]

REFERERS = [
    "https://www.youtube.com/",
    "https://www.youtube.com/feed/trending",
    "https://www.youtube.com/results?search_query=music",
    "https://www.youtube.com/feed/subscriptions",
    "https://www.google.com/",
]

def _parse_ua_type(ua: str) -> str:
    if "Edg/" in ua:
        return "edge"
    if "Firefox/" in ua:
        return "firefox"
    if "Safari/" in ua and "Chrome" not in ua:
        return "safari"
    return "chrome"

def _chrome_version(ua: str) -> str:
    try:
        return ua.split("Chrome/")[1].split(".")[0]
    except IndexError:
        return "131"

def get_youtube_headers(visitor_data: str = None, client_version: str = None) -> dict:
    ua = random.choice(USER_AGENTS)
    ua_type = _parse_ua_type(ua)
    accept_language = random.choice(ACCEPT_LANGUAGES)
    screen_w, screen_h = random.choice(SCREEN_RESOLUTIONS)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate",
        "Origin": "https://www.youtube.com",
        "Referer": random.choice(REFERERS),
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": client_version or CLIENT_VERSION,
    }

    if visitor_data:
        headers["X-Goog-Visitor-Id"] = visitor_data

    if ua_type in ("chrome", "edge"):
        version = _chrome_version(ua)
        brand = "Microsoft Edge" if ua_type == "edge" else "Google Chrome"
        headers["sec-ch-ua"] = f'"Not A(Brand";v="8", "Chromium";v="{version}", "{brand}";v="{version}"'
        headers["sec-ch-ua-mobile"] = "?0"

        platform = "Windows"
        if "Macintosh" in ua or "Mac OS X" in ua:
            platform = "macOS"
        elif "Linux" in ua:
            platform = "Linux"
        headers["sec-ch-ua-platform"] = f'"{platform}"'

        if random.random() > 0.5:
            headers["sec-ch-ua-arch"] = '"x86"'
            headers["sec-ch-ua-bitness"] = '"64"'
            headers["sec-ch-ua-model"] = '""'
            pv = {"Windows": "15.0.0", "macOS": "14.7.2", "Linux": "6.5.0"}
            headers["sec-ch-ua-platform-version"] = f'"{pv.get(platform, "10.0.0")}"'

        headers["Device-Memory"] = str(random.choice(DEVICE_MEMORY))
        headers["Viewport-Width"] = str(screen_w - random.randint(0, 30))

    elif ua_type == "firefox":
        headers["DNT"] = "1"

    return headers
