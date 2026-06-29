from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.config.logger import Logger
from app.config.settings import CLEANUP_CRON, ENABLE_SCHEDULER, HEALTH_CHECK_INTERVAL
from app.scheduler.jobs.youtube import cleanup_old_data, health_check_job
from app.scheduler.scheduler import get_scheduler
logger = Logger.get(__name__)

def configure_jobs():
    scheduler = get_scheduler()
    enable_scheduler = ENABLE_SCHEDULER
    if not enable_scheduler:
        logger.info('Scheduler is disabled via ENABLE_SCHEDULER env var')
        return
    cleanup_schedule = CLEANUP_CRON
    scheduler.add_job(cleanup_old_data, trigger=CronTrigger.from_crontab(cleanup_schedule), id='cleanup_data', name='Cleanup Old Data', replace_existing=True, max_instances=1)
    logger.info(f'Scheduled job: Cleanup Old Data (cron: {cleanup_schedule})')
    health_interval_minutes = HEALTH_CHECK_INTERVAL
    scheduler.add_job(health_check_job, trigger=IntervalTrigger(minutes=health_interval_minutes), id='health_check', name='Periodic Health Check', replace_existing=True, max_instances=1)
    logger.info(f'Scheduled job: Health Check (every {health_interval_minutes} minutes)')
    logger.info(f'Total scheduled jobs: {len(scheduler.get_jobs())}')
    for job in scheduler.get_jobs():
        next_run = getattr(job, 'next_run_time', None)
        next_run_str = next_run.isoformat() if next_run else 'N/A'
        logger.info(f'  - {job.name} (ID: {job.id}, Next run: {next_run_str})')
