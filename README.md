# youtube-crawler

FastAPI service that scrapes YouTube via the internal InnerTube API and pushes structured data to `youtube-api`.

---

## Architecture

```
                    ┌────────────────────────────────────────────┐
                    │              APScheduler (cron)             │
                    │                                            │
                    │  crawl_trending ──────────────────────┐   │
                    │  crawl_shorts  ────────────────────┐  │   │
                    │  crawl_location (26 cities) ────┐  │  │   │
                    │  crawl_keywords ─────────────┐  │  │  │   │
                    └──────────────────────────────│──│──│──│───┘
                                                   │  │  │  │
                                                   ▼  ▼  ▼  ▼
                                          ingest_client.py
                                          POST /internal/ingest/*
                                                   │
                                                   ▼
                                             youtube-api

     youtube-api (real-time, on cache miss)
         │
         ▼
     GET /api/video/:id
     GET /api/video/:id/comments
     GET /api/videos/live
     GET /api/videos/shorts
```

---

## Design Patterns

### 1. Service-per-Feature Layer

Each data type has its own service module with a single responsibility:

```
services/
  trending.py        → top-level trending feed (HTML scrape + InnerTube fallback)
  shorts.py          → Shorts Shelf
  search.py          → keyword search with continuation token pagination
  live.py            → live stream search
  detail.py          → single video full metadata
  comment.py         → comments + nested replies
  channel.py         → channel video list
  channel_info.py    → channel metadata
  playlist.py        → playlist videos
  location.py        → region-targeted search (gl/hl parameters)
```

Services share no state and have no cross-dependencies — each can be tested or swapped independently.

### 2. Error Classification + Retry Strategy

Two exception types enforce different recovery paths:

| Exception | Cause | Retry behaviour |
|-----------|-------|-----------------|
| `YouTubeStructureChangedError` | Missing/moved key in response JSON | No retry — trips circuit breaker immediately, requires developer fix |
| `CrawlNetworkError` | Timeout, connection error, HTTP 429 | Linear backoff, up to 3 attempts |

This distinction prevents retry storms when YouTube changes its response shape — a structural error on attempt 1 would fail identically on attempts 2 and 3.

### 3. Circuit Breaker

Each scheduled job runs inside a circuit breaker:

```
CLOSED  (normal)
  │  5 consecutive failures
  ▼
OPEN    (job skipped, logs warning)
  │  app restart  /  manual reset via admin API
  ▼
CLOSED
```

A `YouTubeStructureChangedError` trips the circuit on the first failure. Transient network errors require 5 consecutive failures. This prevents a broken job from burning through rate limits or filling logs with identical stack traces.

### 4. Safe Navigation

All InnerTube response parsing uses safe access (`dict.get()`, `or {}`, optional chaining). YouTube changes its internal JSON structure regularly and without notice. Every key access is treated as potentially absent:

```python
title = (
    renderer
    .get("title", {})
    .get("runs", [{}])[0]
    .get("text", "")
)
```

Structural failures surface as `YouTubeStructureChangedError` with the exact missing key path, not as a generic `KeyError`.

### 5. Dedicated Ingest Client

`ingest_client.py` is the sole component that calls `youtube-api`. It:
- Owns all HTTP retry logic for the outbound connection
- Never raises exceptions — crawl jobs continue even if the API is down
- Normalises field names (camelCase → snake_case where needed) before sending
- Keeps `0` as-is and never coerces numeric zeros to `None`

This means a service failure in `youtube-api` never aborts an ongoing crawl job.

### 6. Middleware Stack

Applied in registration order (innermost first at request time):

```
RateLimitMiddleware    → per-key or per-IP throttle (slowapi)
AuthMiddleware         → validate X-API-Key header
LoggingMiddleware      → structured request/response log + X-Request-ID
IPWhitelistMiddleware  → optional IP allowlist with service token bypass
```

Auth and rate-limit are placed before logging so rejected requests are still logged with their status.

### 7. Proxy Rotation with Caching

`ProxyManager` wraps a rotating residential proxy provider:
- Caches the current proxy URL with its TTL so the rotation API is not called on every request
- Parses TTL from the provider's human-readable message (`"proxy will expire in 1777s"`)
- Falls back gracefully (direct connection) when no proxy key is configured

### 8. Typed Data Contracts

All inter-module data shapes are defined as `TypedDict` in `types.py`. Service functions return typed dicts; `ingest_client.py` accepts them directly. No untyped `dict` passed between layers.

---

## Project Structure

```
app/
├── api/
│   ├── routes.py              Real-time endpoints (X-API-Key required)
│   └── admin.py               Manual job triggers, circuit breaker reset, proxy debug
├── config/
│   ├── constants.py           InnerTube endpoint names, filter params, sort codes
│   ├── headers.py             Randomised User-Agent pool (Chrome weight ~65%)
│   ├── urls.py                Base URLs, proxy manager instance
│   └── logging_config.py      Structured logger — console + file handlers
├── middleware/
│   ├── auth_middleware.py      X-API-Key validation
│   ├── ip_whitelist.py         IP allowlist
│   ├── rate_limit_config.py    slowapi limiter setup
│   └── logging_middleware.py   Request/response logging, X-Request-ID injection
├── scheduler/
│   ├── scheduler.py            APScheduler singleton (asyncio)
│   ├── config.py               Job registration with cron triggers
│   └── jobs.py                 Job implementations — retry, circuit breaker, batching
├── services/                   One module per data type (see above)
├── ingest_client.py            HTTP push layer → youtube-api
├── exceptions.py               YouTubeStructureChangedError, CrawlNetworkError
├── types.py                    TypedDicts for all data shapes
└── utils.py                    httpx factory, proxy helpers, parse_view_count
```

---

## API Reference

All endpoints require `X-API-Key` header.

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| GET | `/api/videos/search` | `q`, `page`, `limit`, `sort` | Keyword search |
| GET | `/api/videos/trending` | `limit` | Trending feed |
| GET | `/api/videos/live` | `q`, `page`, `limit` | Live streams |
| GET | `/api/videos/shorts` | `limit` | Shorts feed |
| GET | `/api/videos/location` | `gl`, `hl`, `query`, `max_results` | Region-targeted search |
| GET | `/api/video/{video_id}` | — | Full video detail |
| GET | `/api/video/{video_id}/comments` | `page`, `limit` | Comments + replies |
| GET | `/api/channel/{channel_id}` | — | Channel metadata |
| GET | `/api/channel/{channel_id}/videos` | `page`, `limit` | Channel videos |
| GET | `/api/channel/{channel_id}/playlists` | — | Channel playlists |
| GET | `/api/playlist/{playlist_id}/videos` | — | Playlist videos |

> `gl` uses ISO 3166-1 alpha-2 country codes. YouTube ignores lat/lng — geographic targeting works only via `gl`/`hl` in the InnerTube request context.

---

## Scheduled Jobs

| Job | Default cron | Output |
|-----|-------------|--------|
| `crawl_trending_videos` | `0 7 * * *` | Top 100 trending → `ingest/trending` |
| `crawl_shorts_videos` | `0 9 * * *` | Shorts feed → `ingest/shorts` |
| `crawl_location_videos` | `0 6 * * *` | 26 city/language pairs → `ingest/search` |
| `crawl_popular_keywords` | `0 8 * * *` | Fixed keyword list → `ingest/search` |
| `cleanup_old_data` | `0 2 * * 0` | Weekly cleanup |
| `health_check_job` | every 60 min | System ping |

Cron expressions can be overridden via environment variables (e.g. `TRENDING_CRON`).

---

## Environment Variables

```env
PORT=8000

API_KEYS=key1,key2

IP_WHITELIST=
IP_WHITELIST_ENABLED=false
SERVICE_TOKENS=name:token

PROXY_URL=
PROXY_KEYS=

ENABLE_SCHEDULER=true
TRENDING_CRON=0 7 * * *
SHORTS_CRON=0 9 * * *
LOCATION_CRON=0 6 * * *
KEYWORDS_CRON=0 8 * * *
CLEANUP_CRON=0 2 * * 0
HEALTH_CHECK_INTERVAL=60

INGEST_API_URL=http://localhost:3000
INGEST_SERVICE_KEY=
```

`INGEST_SERVICE_KEY` must match `INTERNAL_SERVICE_KEY` in `youtube-api`.

---

## Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`
