import logging
import shutil
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupSystem:
    """Simple backup system for bot data."""

    def __init__(self):
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self):
        """Create a backup of the database."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # Ensure database exists
            if os.path.exists("database/doculuna.db"):
                shutil.copy2("database/doculuna.db", backup_path)
                logger.info(f"Backup created: {backup_filename}")
                return True
            else:
                logger.warning("Database file not found for backup")
                return False
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def cleanup_old_backups(self, keep_days=30):
        """Clean up old backup files."""
        try:
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)

            for filename in os.listdir(self.backup_dir):
                filepath = os.path.join(self.backup_dir, filename)
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    logger.info(f"Removed old backup: {filename}")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
