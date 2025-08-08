
import logging
import os
import shutil
import sqlite3
import zipfile
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class AdvancedBackupSystem:
    """Comprehensive backup system with multiple storage options and automation"""
    
    def __init__(self):
        self.backup_dir = Path(Config.BACKUPS_DIR)
        self.backup_dir.mkdir(exist_ok=True)
        
        self.backup_config = {
            'retention_days': 30,
            'max_backups': 50,
            'compression_level': 6,
            'include_logs': True,
            'include_analytics': True,
            'include_temp_files': False,
            'storage_options': ['local', 'cloud'],  # Future: add cloud storage
            'backup_schedule': {
                'database': {'hours': 6},  # Every 6 hours
                'full_system': {'days': 1},  # Daily
                'user_data': {'hours': 12},  # Twice daily
                'logs': {'days': 7}  # Weekly
            }
        }
        
        self.backup_metadata = {}
        self._load_backup_metadata()
    
    def _load_backup_metadata(self):
        """Load backup metadata from file"""
        try:
            metadata_file = self.backup_dir / "backup_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    self.backup_metadata = json.load(f)
            else:
                self.backup_metadata = {
                    'created': datetime.now().isoformat(),
                    'backups': {},
                    'last_cleanup': None,
                    'total_backups': 0
                }
                self._save_backup_metadata()
        except Exception as e:
            logger.error(f"Error loading backup metadata: {e}")
            self.backup_metadata = {'backups': {}, 'total_backups': 0}
    
    def _save_backup_metadata(self):
        """Save backup metadata to file"""
        try:
            metadata_file = self.backup_dir / "backup_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(self.backup_metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving backup metadata: {e}")
    
    async def create_database_backup(self, backup_name: str = None) -> Dict[str, Any]:
        """Create a comprehensive database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = backup_name or f"database_backup_{timestamp}"
            
            backup_path = self.backup_dir / f"{backup_name}.zip"
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, 
                               compresslevel=self.backup_config['compression_level']) as zipf:
                
                # Add database file
                if os.path.exists(Config.DB_PATH):
                    zipf.write(Config.DB_PATH, "database/doculuna.db")
                
                # Add database schema
                schema_path = "database/schema.sql"
                if os.path.exists(schema_path):
                    zipf.write(schema_path, "database/schema.sql")
                
                # Export database as SQL
                sql_export = await self._export_database_to_sql()
                if sql_export:
                    zipf.writestr("database/export.sql", sql_export)
                
                # Add metadata
                metadata = {
                    'backup_type': 'database',
                    'created_at': datetime.now().isoformat(),
                    'created_by': 'automated_system',
                    'size_bytes': 0,  # Will be updated after creation
                    'tables_included': await self._get_table_list(),
                    'record_counts': await self._get_record_counts()
                }
                
                zipf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
            
            # Update metadata with file size
            backup_size = backup_path.stat().st_size
            metadata['size_bytes'] = backup_size
            
            # Store backup info
            self.backup_metadata['backups'][backup_name] = {
                'path': str(backup_path),
                'type': 'database',
                'created_at': datetime.now().isoformat(),
                'size_bytes': backup_size,
                'metadata': metadata
            }
            self.backup_metadata['total_backups'] += 1
            self._save_backup_metadata()
            
            logger.info(f"Database backup created: {backup_name} ({backup_size} bytes)")
            
            return {
                'success': True,
                'backup_name': backup_name,
                'backup_path': str(backup_path),
                'size_bytes': backup_size,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_full_system_backup(self, backup_name: str = None) -> Dict[str, Any]:
        """Create a full system backup including all data and configurations"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = backup_name or f"full_system_backup_{timestamp}"
            
            backup_path = self.backup_dir / f"{backup_name}.zip"
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED,
                               compresslevel=self.backup_config['compression_level']) as zipf:
                
                # Database
                if os.path.exists(Config.DB_PATH):
                    zipf.write(Config.DB_PATH, "database/doculuna.db")
                
                # Configuration
                zipf.write("config.py", "config.py")
                
                # Requirements
                if os.path.exists("requirements.txt"):
                    zipf.write("requirements.txt", "requirements.txt")
                
                # Analytics data
                if self.backup_config['include_analytics'] and os.path.exists(Config.ANALYTICS_DIR):
                    for root, dirs, files in os.walk(Config.ANALYTICS_DIR):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_path = os.path.relpath(file_path, ".")
                            zipf.write(file_path, arc_path)
                
                # Logs (if enabled)
                if self.backup_config['include_logs']:
                    log_files = ["doculuna.log", "error.log", "access.log"]
                    for log_file in log_files:
                        if os.path.exists(log_file):
                            zipf.write(log_file, f"logs/{log_file}")
                
                # Payment screenshots
                if os.path.exists(Config.PAYMENTS_DIR):
                    for root, dirs, files in os.walk(Config.PAYMENTS_DIR):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_path = os.path.relpath(file_path, ".")
                            zipf.write(file_path, arc_path)
                
                # System metadata
                system_metadata = {
                    'backup_type': 'full_system',
                    'created_at': datetime.now().isoformat(),
                    'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
                    'config': await self._get_system_config(),
                    'disk_usage': await self._get_disk_usage(),
                    'user_count': await self._get_user_count(),
                    'database_tables': await self._get_table_list()
                }
                
                zipf.writestr("system_metadata.json", json.dumps(system_metadata, indent=2, default=str))
            
            backup_size = backup_path.stat().st_size
            
            # Store backup info
            self.backup_metadata['backups'][backup_name] = {
                'path': str(backup_path),
                'type': 'full_system',
                'created_at': datetime.now().isoformat(),
                'size_bytes': backup_size,
                'metadata': system_metadata
            }
            self.backup_metadata['total_backups'] += 1
            self._save_backup_metadata()
            
            logger.info(f"Full system backup created: {backup_name} ({backup_size} bytes)")
            
            return {
                'success': True,
                'backup_name': backup_name,
                'backup_path': str(backup_path),
                'size_bytes': backup_size,
                'metadata': system_metadata
            }
            
        except Exception as e:
            logger.error(f"Error creating full system backup: {e}")
            return {'success': False, 'error': str(e)}
    
    async def restore_database_backup(self, backup_name: str) -> Dict[str, Any]:
        """Restore database from backup"""
        try:
            if backup_name not in self.backup_metadata['backups']:
                return {'success': False, 'error': 'Backup not found'}
            
            backup_info = self.backup_metadata['backups'][backup_name]
            backup_path = Path(backup_info['path'])
            
            if not backup_path.exists():
                return {'success': False, 'error': 'Backup file not found'}
            
            # Create backup of current database
            current_backup = await self.create_database_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Extract and restore
            restore_dir = self.backup_dir / "temp_restore"
            restore_dir.mkdir(exist_ok=True)
            
            try:
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(restore_dir)
                
                # Restore database file
                restored_db_path = restore_dir / "database" / "doculuna.db"
                if restored_db_path.exists():
                    shutil.copy2(restored_db_path, Config.DB_PATH)
                
                # Cleanup
                shutil.rmtree(restore_dir)
                
                logger.info(f"Database restored from backup: {backup_name}")
                
                return {
                    'success': True,
                    'backup_name': backup_name,
                    'pre_restore_backup': current_backup.get('backup_name'),
                    'restored_at': datetime.now().isoformat()
                }
                
            except Exception as e:
                # Cleanup on error
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)
                raise e
                
        except Exception as e:
            logger.error(f"Error restoring database backup: {e}")
            return {'success': False, 'error': str(e)}
    
    async def list_backups(self, backup_type: str = None) -> List[Dict[str, Any]]:
        """List available backups with filtering"""
        try:
            backups = []
            
            for name, info in self.backup_metadata['backups'].items():
                if backup_type and info.get('type') != backup_type:
                    continue
                
                backup_data = {
                    'name': name,
                    'type': info.get('type', 'unknown'),
                    'created_at': info.get('created_at'),
                    'size_bytes': info.get('size_bytes', 0),
                    'size_mb': round(info.get('size_bytes', 0) / (1024 * 1024), 2),
                    'exists': Path(info['path']).exists() if 'path' in info else False
                }
                
                backups.append(backup_data)
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []
    
    async def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backups based on retention policy"""
        try:
            cleaned_count = 0
            freed_bytes = 0
            errors = []
            
            cutoff_date = datetime.now() - timedelta(days=self.backup_config['retention_days'])
            
            # Get backups sorted by date
            backups_to_check = list(self.backup_metadata['backups'].items())
            backups_to_check.sort(key=lambda x: x[1].get('created_at', ''), reverse=True)
            
            # Keep at least the newest backups regardless of date
            backups_to_keep = backups_to_check[:10]
            backups_to_evaluate = backups_to_check[10:]
            
            for name, info in backups_to_evaluate:
                try:
                    created_at = datetime.fromisoformat(info.get('created_at', ''))
                    
                    if created_at < cutoff_date:
                        backup_path = Path(info['path'])
                        
                        if backup_path.exists():
                            size = backup_path.stat().st_size
                            backup_path.unlink()
                            freed_bytes += size
                        
                        del self.backup_metadata['backups'][name]
                        cleaned_count += 1
                        
                except Exception as e:
                    errors.append(f"Error cleaning backup {name}: {e}")
            
            # Also enforce max backup count
            if len(self.backup_metadata['backups']) > self.backup_config['max_backups']:
                excess_count = len(self.backup_metadata['backups']) - self.backup_config['max_backups']
                
                # Sort all backups by date and remove oldest
                all_backups = list(self.backup_metadata['backups'].items())
                all_backups.sort(key=lambda x: x[1].get('created_at', ''))
                
                for name, info in all_backups[:excess_count]:
                    try:
                        backup_path = Path(info['path'])
                        if backup_path.exists():
                            size = backup_path.stat().st_size
                            backup_path.unlink()
                            freed_bytes += size
                        
                        del self.backup_metadata['backups'][name]
                        cleaned_count += 1
                        
                    except Exception as e:
                        errors.append(f"Error removing excess backup {name}: {e}")
            
            self.backup_metadata['last_cleanup'] = datetime.now().isoformat()
            self._save_backup_metadata()
            
            logger.info(f"Backup cleanup complete: {cleaned_count} removed, {freed_bytes} bytes freed")
            
            return {
                'success': True,
                'cleaned_count': cleaned_count,
                'freed_bytes': freed_bytes,
                'freed_mb': round(freed_bytes / (1024 * 1024), 2),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _export_database_to_sql(self) -> Optional[str]:
        """Export database to SQL format"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            
            # Get SQL dump
            sql_dump = []
            for line in conn.iterdump():
                sql_dump.append(line)
            
            conn.close()
            return '\n'.join(sql_dump)
            
        except Exception as e:
            logger.error(f"Error exporting database to SQL: {e}")
            return None
    
    async def _get_table_list(self) -> List[str]:
        """Get list of database tables"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return tables
            
        except Exception as e:
            logger.error(f"Error getting table list: {e}")
            return []
    
    async def _get_record_counts(self) -> Dict[str, int]:
        """Get record counts for each table"""
        try:
            tables = await self._get_table_list()
            counts = {}
            
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            
            conn.close()
            return counts
            
        except Exception as e:
            logger.error(f"Error getting record counts: {e}")
            return {}
    
    async def _get_system_config(self) -> Dict[str, Any]:
        """Get system configuration summary"""
        try:
            return {
                'free_usage_limit': Config.FREE_USAGE_LIMIT,
                'max_file_size': Config.MAX_FILE_SIZE,
                'admin_count': len(Config.ADMIN_USER_IDS),
                'premium_prices': {
                    'daily': Config.DAILY_PREMIUM_PRICE,
                    'three_month': Config.THREE_MONTH_PREMIUM_PRICE,
                    'lifetime': Config.LIFETIME_PREMIUM_PRICE
                }
            }
        except Exception as e:
            logger.error(f"Error getting system config: {e}")
            return {}
    
    async def _get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            
            return {
                'total_bytes': disk.total,
                'used_bytes': disk.used,
                'free_bytes': disk.free,
                'percent_used': round((disk.used / disk.total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return {}
    
    async def _get_user_count(self) -> int:
        """Get total user count"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
            
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            return 0
    
    async def schedule_automatic_backups(self):
        """Schedule automatic backups based on configuration"""
        try:
            while True:
                now = datetime.now()
                
                # Check if we need database backup
                last_db_backup = await self._get_last_backup_time('database')
                if not last_db_backup or (now - last_db_backup).total_seconds() >= 6 * 3600:  # 6 hours
                    await self.create_database_backup()
                
                # Check if we need full system backup
                last_full_backup = await self._get_last_backup_time('full_system')
                if not last_full_backup or (now - last_full_backup).total_seconds() >= 24 * 3600:  # 24 hours
                    await self.create_full_system_backup()
                
                # Daily cleanup
                if self.backup_metadata.get('last_cleanup'):
                    last_cleanup = datetime.fromisoformat(self.backup_metadata['last_cleanup'])
                    if (now - last_cleanup).days >= 1:
                        await self.cleanup_old_backups()
                else:
                    await self.cleanup_old_backups()
                
                # Wait 1 hour before next check
                await asyncio.sleep(3600)
                
        except Exception as e:
            logger.error(f"Error in automatic backup scheduler: {e}")
            await asyncio.sleep(3600)  # Wait an hour on error
    
    async def _get_last_backup_time(self, backup_type: str) -> Optional[datetime]:
        """Get the time of the last backup of specified type"""
        try:
            last_time = None
            
            for backup_info in self.backup_metadata['backups'].values():
                if backup_info.get('type') == backup_type:
                    backup_time = datetime.fromisoformat(backup_info['created_at'])
                    if not last_time or backup_time > last_time:
                        last_time = backup_time
            
            return last_time
            
        except Exception as e:
            logger.error(f"Error getting last backup time: {e}")
            return None

# Global backup system instance
backup_system = AdvancedBackupSystem()

# Utility functions for easy access
async def create_database_backup(backup_name: str = None) -> Dict[str, Any]:
    """Create database backup - utility function"""
    return await backup_system.create_database_backup(backup_name)

async def create_full_backup(backup_name: str = None) -> Dict[str, Any]:
    """Create full system backup - utility function"""
    return await backup_system.create_full_system_backup(backup_name)

async def restore_backup(backup_name: str) -> Dict[str, Any]:
    """Restore backup - utility function"""
    return await backup_system.restore_database_backup(backup_name)

async def list_available_backups(backup_type: str = None) -> List[Dict[str, Any]]:
    """List backups - utility function"""
    return await backup_system.list_backups(backup_type)

async def cleanup_backups() -> Dict[str, Any]:
    """Cleanup old backups - utility function"""
    return await backup_system.cleanup_old_backups()

# Background task for automatic backups
async def start_backup_scheduler():
    """Start the automatic backup scheduler"""
    await backup_system.schedule_automatic_backups()
