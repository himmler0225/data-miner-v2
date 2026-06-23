# Data Miner API

A production-style **FastAPI** service that scrapes structured data from **YouTube, TikTok, Tiki, and FPT Shop** through their internal (reverse-engineered) APIs and exposes it as a clean, authenticated REST API.

Built to run behind rotating residential proxies, with centralised remote configuration, global rate limiting, and resilient parsing of constantly-changing upstream responses.

---

## Highlights

- **4 platforms, one API** — YouTube (InnerTube + HTML), TikTok (native client with TikHub fallback), Tiki e-commerce, and FPT Shop.
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

### Error classification

| Exception | Cause | Handling |
|-----------|-------|----------|
| `YouTubeStructureChangedError` | Missing/moved key in the response JSON | No retry — carries the missing key path for fast debugging |
| `CrawlNetworkError` | Timeout / connection error / HTTP 429 | Retried with linear backoff (up to 3 attempts) |

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
│   ├── tiki.py           # /api/tiki/*
│   ├── fpt_shop.py       # /api/fpt-shop/*
│   └── admin/            # /admin/proxy/*  (proxy management)
├── crawlers/
│   ├── youtube/          # InnerTube + HTML scrapers
│   ├── tiktok/           # native client + TikHub fallback
│   ├── tiki/             # product search, detail, reviews, sales
│   └── fpt_shop/         # product search, detail, reviews
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

`GET /videos/search` · `GET /videos/by-topic` · `GET /videos/shorts` · `GET /videos/live` · `GET /videos/location` · `GET /videos/{video_id}` · `GET /videos/{video_id}/comments` · `GET /videos/comments/batch` · `GET /videos/{video_id}/transcript` · `GET /videos/transcript/batch` · `GET /channels/{channel_id}` · `GET /channels/{channel_id}/videos` · `GET /channels/{channel_id}/playlists` · `GET /playlists/{playlist_id}/videos`

### TikTok — `/api/tiktok`

`GET /search` (cache → native → TikHub) · `GET /trending` · `GET /video-info` · `GET /comments` · `GET /profiles/{handle}` · `GET /transcript`

### Tiki — `/api/tiki`

`GET /products/search` · `GET /products/sales` · `GET /products/top-choice` · `GET /products/maybe-you-like` · `GET /products/{product_id}` · `GET /products/{product_id}/reviews`

### FPT Shop — `/api/fpt-shop`

`GET /products/search` — `q`, `page`, `limit`, `sort_method`, `price_range`  
`GET /products/detail/{upc}`  
`GET /products/{product_id}/reviews` — `page`, `limit`, `sort_method`

Per-route rate limit: `15/minute` (same as Tiki/TikTok).

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
