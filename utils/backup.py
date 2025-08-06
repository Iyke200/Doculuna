
import os
import shutil
import sqlite3
import json
from datetime import datetime
from config import DB_PATH

class BackupSystem:
    def __init__(self):
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self):
        """Create a complete system backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"doculuna_backup_{timestamp}"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        os.makedirs(backup_path, exist_ok=True)
        
        # Backup database
        shutil.copy2(DB_PATH, os.path.join(backup_path, "doculuna.db"))
        
        # Backup payments folder
        if os.path.exists("payments"):
            shutil.copytree("payments", os.path.join(backup_path, "payments"))
        
        # Create backup manifest
        manifest = {
            "backup_time": timestamp,
            "files_backed_up": ["database", "payments"],
            "backup_size": self._get_directory_size(backup_path)
        }
        
        with open(os.path.join(backup_path, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        
        return backup_path
    
    def _get_directory_size(self, path):
        """Calculate directory size in bytes."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        return total_size
    
    def cleanup_old_backups(self, keep_days=30):
        """Remove backups older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        for backup_name in os.listdir(self.backup_dir):
            backup_path = os.path.join(self.backup_dir, backup_name)
            if os.path.isdir(backup_path):
                backup_time = os.path.getctime(backup_path)
                if datetime.fromtimestamp(backup_time) < cutoff_date:
                    shutil.rmtree(backup_path)

backup_system = BackupSystem()
import logging
import shutil
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class BackupSystem:
    """Simple backup system for database."""
    
    def __init__(self):
        self.backup_dir = "backups"
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self):
        """Create database backup."""
        try:
            from config import DB_PATH
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.backup_dir}/backup_{timestamp}.db"
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
import logging
import shutil
import os
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
            
            shutil.copy2("database/doculuna.db", backup_path)
            logger.info(f"Backup created: {backup_filename}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
