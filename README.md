# Data Miner API

A production-style **FastAPI** service that scrapes structured data from **YouTube and TikTok** through their internal (reverse-engineered) APIs and exposes it as a clean, authenticated REST API.

Built to run behind rotating residential proxies, with centralised remote configuration, global rate limiting, and resilient parsing of constantly-changing upstream responses.

---

## Highlights

- **3 sources, one API** — YouTube (InnerTube + HTML), TikTok (native client with TikHub fallback), and web search (Tavily). Movie catalog data (KKPhim/OPhim/VSMOV) is no longer crawled here — ai-layer calls `movie-aggregator-api` directly for that.
- **Same logic, two protocols** — every crawler is exposed both as a plain REST endpoint (`api/`) and as an MCP tool (`mcp/`, `tools/`), so an LLM agent (ai-layer) and a regular HTTP client hit the exact same underlying code.
- **Resilient parsing** — upstream fields are accessed defensively; structural drift surfaces as a typed error (`YouTubeStructureChangedError`) with the exact key path instead of a random `KeyError`.
- **Rotating proxy pools** — separate VN / US residential pools with sticky TTL pinning and graceful direct-connection fallback.
- **Remote configuration** — proxies and rate limits are loaded from a Supabase `config` table at startup, so they can change without a redeploy.
- **Global rate limiting** — every endpoint is throttled per API key (or IP), with stricter per-route caps on hot endpoints.
- **Anti-bot tooling** — randomised User-Agent pool, warmed TikTok session pool (shared `ttwid`/`msToken`), and request-signature generation.

---

## Architecture

```
        Client
          │  X-API-Key
          ▼
   ┌──────────────────────────────────────────────┐
   │                FastAPI app                     │
   │  CORS → Rate limit → Logging → IP allowlist    │  middleware
   │                     │                          │
   │              verify_api_key (dep)              │
   │                     ▼                          │
   │     api/  ──►  crawlers/  ──►  upstream        │
   └──────────────────────────────────────────────┘
          │                         │
          ▼                         ▼
   ProxyManager (VN/US)      Supabase remote config
                             (proxies + rate limits)
```

---

## Tech stack

FastAPI · Pydantic · httpx · curl_cffi · slowapi · APScheduler · Supabase (REST) · Uvicorn

---

## Design notes

### Crawler-per-feature

Each data type is an independent module under `crawlers/<platform>/<feature>/` with no shared state, so a feature can be tested or replaced in isolation.

### Native-first, third-party fallback

TikTok tries the native (reverse-engineered) client first; if the native pool is exhausted or fails, it transparently falls back to the paid TikHub API (`crawlers/tiktok/native.py` → `tikhub.py`).

### Dual protocol: REST + MCP

Crawlers are called from two front doors that share the same business logic: `api/*.py` (plain REST, used by ai-layer's HTTP client and any external caller) and `mcp/server.py` + `tools/` (Model Context Protocol tools, used by ai-layer's agent for direct LLM tool-calling). For YouTube both are thin adapters over `services/youtube.py`, which owns input validation, `@handle` resolution, proxy selection, retries, caching and paging, so REST and MCP behave identically.

### Error classification

| Exception | Cause | Handling |
|-----------|-------|----------|
| `InvalidInputError` | Malformed id, bad parameter, oversized batch, bad cursor | No retry — HTTP 400 |
| `YouTubeNotFoundError` | Video/channel/playlist doesn't exist or is unavailable (incl. YouTube 400/404) | No retry — HTTP 404 |
| `YouTubeStructureChangedError` | Missing/moved key in the response JSON | No retry — HTTP 502, logged critical with the missing key path |
| `CrawlNetworkError`, transport errors, HTTP 5xx | Timeout / connection / proxy error, blocked request | Retried with linear backoff and proxy rotation (3 attempts), then HTTP 502 |
| HTTP 429 from upstream | Upstream throttling | Retried through a fresh proxy, then HTTP 503 |

### Safe navigation

Upstream JSON is parsed with defensive access (`dict.get()`, `or {}`, default indices) because YouTube/TikTok change their internal shapes without notice.

### Proxy rotation

`ProxyManager` pins one proxy from its pool for a TTL window, reuses it across requests, rotates on demand or on failure, and falls back to a direct connection when the pool is empty.

### Remote configuration

On startup, `config/remote.py` pulls the Supabase `config` table and applies `PROXY_VN`, `PROXY_US`, `RATE_LIMIT_DEFAULT`, and `RATE_LIMIT_BURST`.

### Logging

Structured console + JSON file logs. Convention: `logger.info("[module] message key=%s", value)`.

---

## Project structure

```
app/
├── api/
│   ├── youtube.py        # /api/videos, /api/channels, /api/playlists
│   ├── tiktok.py         # /api/tiktok/*
│   ├── google.py         # /api/google/search (Tavily)
│   └── admin/            # /admin/proxy/*  (proxy management)
├── crawlers/
│   ├── youtube/          # InnerTube + HTML scrapers
│   ├── tiktok/           # native client + TikHub fallback
│   └── google/           # Tavily web search
├── mcp/                  # MCP server (server.py, sse.py) — same crawlers as MCP tools
├── tools/                # MCP tool schemas + registry/handlers
├── i18n/                 # request-locale error messages (vi/en)
├── config/               # settings, remote, proxy_manager, logger
├── middleware/           # auth, rate_limit, logging, ip_whitelist
├── scheduler/            # APScheduler (cleanup, health)
├── schemas/              # ApiResponse envelope
├── exceptions.py
├── types.py
└── utils.py
```

---

## API reference

All endpoints require an `X-API-Key` header.

### YouTube — `/api`

| Endpoint | Params | Returns |
|----------|--------|---------|
| `GET /videos/search` | `q`, `sort` (relevance · upload_date · view_count · rating) | page of videos |
| `GET /videos/by-topic` | `topic` | page of videos (+ `featured_playlist` for channel topics) |
| `GET /videos/live` | `q` (optional) | page of videos |
| `GET /videos/location` | `q`, `gl`, `hl` | page of videos |
| `GET /videos/shorts` | `limit` | videos (no cursor: the feed is randomized) |
| `GET /videos/{video_id}` | | video + `keywords`, `category`, `formats`, ... |
| `GET /videos/{video_id}/comments` | `sort` (top · newest) | page of comments (with replies) |
| `GET /videos/{video_id}/transcript` | | transcript (`available`, `reason`) |
| `GET /videos/comments/batch` | `video_ids` (≤ 8, comma-separated), `sort`, `limit` | per-video comments |
| `GET /videos/transcript/batch` | `video_ids` (≤ 8) | per-video transcripts |
| `GET /channels/{channel_id}` | | channel |
| `GET /channels/{channel_id}/videos` | | page of videos (newest first) |
| `GET /channels/{channel_id}/playlists` | | page of playlists |
| `GET /playlists/{playlist_id}/videos` | | page of videos |

`{channel_id}` accepts a channel id (`UC...`) or an `@handle`.

**Paging.** List endpoints take `limit` (1–50, default 20) and `cursor`, and return `{"items": [...], "next_cursor": "...", "has_more": true, ...}`. Pass `next_cursor` back as `cursor` for the next page; `next_cursor` is `null` on the last page. Cursors are opaque.

**Item shapes** (snake_case, the same whichever YouTube renderer they came from — see `crawlers/youtube/shared/models.py`):

- video: `video_id`, `url`, `title`, `description`, `channel_id`, `channel_name`, `thumbnails`, `duration`, `duration_seconds`, `view_count`, `published_time`, `is_live`, `is_short`
- playlist: `playlist_id`, `url`, `title`, `thumbnails`, `video_count`
- comment: `comment_id`, `author`, `author_avatar`, `content`, `published_time`, `like_count`, `reply_count`, `replies`
- channel: `channel_id`, `url`, `channel_name`, `handle`, `description`, `avatar`, `banner`, `subscriber_count`, `video_count`

Counts are integers (`null` when YouTube doesn't show one). Responses are cached in-process for a few minutes.

### TikTok — `/api/tiktok`

`GET /search` (cache → native → TikHub) · `GET /trending` · `GET /video-info` · `GET /comments` · `GET /profiles/{handle}` · `GET /transcript`

### Web search — `/api/google`

`GET /search` (Tavily-backed)

### Admin — `/admin`

`GET /proxy/status` · `POST /proxy/rotate` · `GET /proxy/test`

Full interactive docs at `http://localhost:8000/docs`.

---

## Rate limiting

A global limit (`RATE_LIMIT_DEFAULT` + `RATE_LIMIT_BURST`) is enforced on every endpoint via `SlowAPIMiddleware`, keyed by API-key prefix (falling back to client IP). Hot endpoints add stricter per-route caps via `@limiter.limit(...)`. Values are managed remotely via Supabase.

---

## Configuration

Most settings come from environment variables; **proxies and rate limits are sourced from the Supabase `config` table** (see `config/remote.py`).

```env
APP_ENV=development
LOG_LEVEL=INFO

# Auth
API_KEYS=key1,key2
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# IP allowlist (optional)
ENABLE_IP_WHITELIST=false
WHITELISTED_IPS=
WHITELISTED_SERVICES=

# Scheduler
ENABLE_SCHEDULER=true
CLEANUP_CRON=0 2 * * 0
HEALTH_CHECK_INTERVAL=60

# Rate-limit backend (limit values themselves come from Supabase)
RATE_LIMIT_STORAGE=memory://

# TikTok TikHub fallback
TIKAP_API_KEY=

# Supabase remote config (proxies + rate limits)
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
```

---

## Getting started

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open `http://localhost:8000/docs` and authorise with your `X-API-Key`.
