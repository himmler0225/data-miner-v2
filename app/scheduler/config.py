from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.scheduler.scheduler import get_scheduler
from app.scheduler.jobs import (
    crawl_trending_videos,
    crawl_shorts_videos,
    crawl_location_videos,
    crawl_popular_keywords,
    crawl_live_videos,
    cleanup_old_data,
    health_check_job,
)
from app.config.logger import Logger
from app.config.settings import (
    ENABLE_SCHEDULER,
    TRENDING_CRON, KEYWORDS_CRON, SHORTS_CRON,
    LIVE_CRON, LOCATION_CRON, CLEANUP_CRON,
    HEALTH_CHECK_INTERVAL,
)

logger = Logger.get(__name__)

def configure_jobs():
    scheduler = get_scheduler()

    enable_scheduler = ENABLE_SCHEDULER
    if not enable_scheduler:
        logger.info("Scheduler is disabled via ENABLE_SCHEDULER env var")
        return

    trending_schedule = TRENDING_CRON
    scheduler.add_job(
        crawl_trending_videos,
        trigger=CronTrigger.from_crontab(trending_schedule),
        id="crawl_trending",
        name="Crawl Trending Videos",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Crawl Trending Videos (cron: {trending_schedule})")

    shorts_schedule = SHORTS_CRON
    scheduler.add_job(
        crawl_shorts_videos,
        trigger=CronTrigger.from_crontab(shorts_schedule),
        id="crawl_shorts",
        name="Crawl Shorts Feed",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Crawl Shorts Feed (cron: {shorts_schedule})")

    location_schedule = LOCATION_CRON
    scheduler.add_job(
        crawl_location_videos,
        trigger=CronTrigger.from_crontab(location_schedule),
        id="crawl_location",
        name="Crawl Location Videos",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Crawl Location Videos (cron: {location_schedule})")

    keywords_schedule = KEYWORDS_CRON
    scheduler.add_job(
        crawl_popular_keywords,
        trigger=CronTrigger.from_crontab(keywords_schedule),
        id="crawl_keywords",
        name="Crawl Popular Keywords",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Crawl Popular Keywords (cron: {keywords_schedule})")

    live_schedule = LIVE_CRON
    scheduler.add_job(
        crawl_live_videos,
        trigger=CronTrigger.from_crontab(live_schedule),
        id="crawl_live",
        name="Crawl Live Videos",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Crawl Live Videos (cron: {live_schedule})")

    cleanup_schedule = CLEANUP_CRON
    scheduler.add_job(
        cleanup_old_data,
        trigger=CronTrigger.from_crontab(cleanup_schedule),
        id="cleanup_data",
        name="Cleanup Old Data",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Cleanup Old Data (cron: {cleanup_schedule})")

    health_interval_minutes = HEALTH_CHECK_INTERVAL
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(minutes=health_interval_minutes),
        id="health_check",
        name="Periodic Health Check",
        replace_existing=True,
        max_instances=1,
    )
    logger.info(f"Scheduled job: Health Check (every {health_interval_minutes} minutes)")

    logger.info(f"Total scheduled jobs: {len(scheduler.get_jobs())}")
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        next_run_str = next_run.isoformat() if next_run else "N/A"
        logger.info(f"  - {job.name} (ID: {job.id}, Next run: {next_run_str})")
