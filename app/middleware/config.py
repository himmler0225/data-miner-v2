"""Middleware configuration (paths, headers, pools)."""

API_KEY_HEADER = "X-API-Key"

PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc", "/mcp", "/mcp/sse"})

BOT_UA_FRAGMENTS = ("python", "httpx", "aiohttp", "curl", "wget", "go-http", "java", "libwww")
CLIENT_INFO_POOL_SIZE = 500
