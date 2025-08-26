# utils/backup.py
import logging
import os
import shutil
import time
import asyncio
from config import DATABASE_PATH, BACKUP_DIR, BACKUP_INTERVAL

logger = logging.getLogger(__name__)

async def async_backup_database():
    while True:
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            stat = shutil.disk_usage(BACKUP_DIR)
            if stat.free < 50 * 1024 * 1024:
                logger.warning("Low disk space, skipping backup")
                clean_old_backups()
                await asyncio.sleep(BACKUP_INTERVAL * 3600)
                continue
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
            shutil.copy(DATABASE_PATH, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            clean_old_backups()
        except Exception as e:
            logger.error(f"Error in backup: {e}")
        await asyncio.sleep(BACKUP_INTERVAL * 3600)

def clean_old_backups():
    try:
        retention_days = 2
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        for file_name in os.listdir(BACKUP_DIR):
            file_path = os.path.join(BACKUP_DIR, file_name)
            if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                os.remove(file_path)
                logger.info(f"Removed old backup: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning backups: {e}")
