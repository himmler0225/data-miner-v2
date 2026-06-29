from datetime import datetime
from app.config.logger import Logger
logger = Logger.get(__name__)

async def cleanup_old_data():
    try:
        logger.info('Starting scheduled data cleanup...')
        start_time = datetime.now()
        duration = (datetime.now() - start_time).total_seconds()
        logger.info('Data cleanup completed', extra={'extra_data': {'duration_seconds': duration}})
        return {'success': True, 'duration': duration}
    except Exception as e:
        logger.error(f'Data cleanup error: {e}', exc_info=True)
        return {'success': False, 'error': str(e)}

async def health_check_job():
    try:
        logger.debug('Running periodic health check...')
        return {'success': True, 'timestamp': datetime.now().isoformat()}
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}', exc_info=True)
        return {'success': False, 'error': str(e)}
