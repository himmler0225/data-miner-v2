# scheduler

APScheduler-based job runner for periodic YouTube tasks.

## Files

| File | Role |
|------|------|
| `scheduler.py` | `AsyncIOScheduler` singleton (`get_scheduler()`), `start_scheduler()`, `shutdown_scheduler()` |
| `config.py` | `configure_jobs()` — registers all jobs into the scheduler; called once in FastAPI lifespan |
| `jobs/` | Job function implementations |

## Jobs

| Job ID | Default cron | What it does |
|--------|-------------|--------------|
| `cleanup_data` | `0 2 * * 0` | Placeholder — no delete logic yet. |
| `health_check` | every 60 min | Logs a DEBUG ping to confirm the scheduler is alive. |

All cron strings are overridable via env vars (`CLEANUP_CRON`). The health check interval is controlled by `HEALTH_CHECK_INTERVAL` (minutes, default 60).

Set `ENABLE_SCHEDULER=false` to start the app in API-only mode without registering any jobs.

Each job is registered with `max_instances=1` to prevent overlapping runs if a job overruns its cron window.
