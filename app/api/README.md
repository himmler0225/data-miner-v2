# api

FastAPI routers for the public crawler endpoints and admin controls. Every route requires an `X-API-Key` header (`Depends(verify_api_key)`).

## Files

| File | Role |
|------|------|
| `youtube.py` | `GET /api/videos/*`, `/api/channels/*`, `/api/playlists/*` |
| `tiktok.py` | `GET /api/tiktok/*` |
| `tiki.py` | `GET /api/tiki/*` |
| `admin/` | `GET\|POST /admin/*` — proxy management only |
| `rate_limit_config.py` | Per-feature rate-limit constants |

---

## Rate limiting

A global limit (`RATE_LIMIT_DEFAULT` + `RATE_LIMIT_BURST`) is enforced on **every** endpoint via `SlowAPIMiddleware` (wired in `main.py`). Selected hot endpoints add a stricter per-route cap with `@limiter.limit(...)` (e.g. YouTube search `30/minute`, all TikTok/Tiki routes `15/minute`).

## `retry_on_failure`

Applied to most handlers' inner async function: 3 attempts, linear backoff (1 s × attempt).
- `YouTubeStructureChangedError` → no retry (structural parse failure won't recover).
- Other exceptions → retried, then surfaced as `HTTP 500`.

---

## YouTube — `/api/*`

| Method | Path | Key params |
|--------|------|-----------|
| `GET` | `/api/videos/by-topic` | `topic`, `limit`, `page` |
| `GET` | `/api/videos/search` | `q`, `page`, `limit`, `sort` |
| `GET` | `/api/videos/shorts` | `limit` |
| `GET` | `/api/videos/live` | `q`, `page`, `limit` |
| `GET` | `/api/videos/location` | `gl`, `hl`, `query`, `max_results` |
| `GET` | `/api/videos/{video_id}` | — |
| `GET` | `/api/videos/{video_id}/comments` | `page`, `limit`, `sort` |
| `GET` | `/api/videos/comments/batch` | `video_ids` (≤8), `limit`, `sort` |
| `GET` | `/api/videos/{video_id}/transcript` | — |
| `GET` | `/api/videos/transcript/batch` | `video_ids` (≤8) |
| `GET` | `/api/channels/{channel_id}` | — |
| `GET` | `/api/channels/{channel_id}/videos` | `page`, `limit` |
| `GET` | `/api/channels/{channel_id}/playlists` | — |
| `GET` | `/api/playlists/{playlist_id}/videos` | — |

Pagination is offset-based: the service fetches `(page-1)*limit + limit` items, then slices.

## TikTok — `/api/tiktok/*`

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/tiktok/search` | cache → native → TikHub fallback |
| `GET` | `/api/tiktok/trending` | native |
| `GET` | `/api/tiktok/video-info` | TikHub |
| `GET` | `/api/tiktok/comments` | TikHub |
| `GET` | `/api/tiktok/profiles/{handle}` | TikHub |
| `GET` | `/api/tiktok/transcript` | TikHub |

## Tiki — `/api/tiki/*`

| Method | Path |
|--------|------|
| `GET` | `/api/tiki/products/search` |
| `GET` | `/api/tiki/products/sales` |
| `GET` | `/api/tiki/products/top-choice` |
| `GET` | `/api/tiki/products/maybe-you-like` |
| `GET` | `/api/tiki/products/{product_id}` |
| `GET` | `/api/tiki/products/{product_id}/reviews` |

---

## Admin — `/admin/*`

Proxy management only.

| Method | Path | Behavior |
|--------|------|---------|
| `GET` | `/admin/proxy/status` | Pool state (VN + US): count, current exit, TTL remaining |
| `POST` | `/admin/proxy/rotate` | Force rotation on next request |
| `GET` | `/admin/proxy/test` | Fetch a proxy and verify exit IP via `httpbin.org/ip` (`?pool=vn\|us`) |
