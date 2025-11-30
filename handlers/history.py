# history.py
"""History tracking module for DocuLuna.

Manages logging and retrieval of user operations history with async DB access.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_history_db(db_path: str = None) -> None:
    """Initialize the history database table."""
    db_path = db_path or DB_PATH
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT,
                    operation_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    duration REAL DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    file_size INTEGER DEFAULT 0,
                    output_filename TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_history_user_id ON operation_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_history_timestamp ON operation_history(timestamp);
                CREATE INDEX IF NOT EXISTS idx_history_operation ON operation_history(operation_type);
            ''')
            await db.commit()
        logger.info("History database initialized.")
    except aiosqlite.Error as e:
        logger.error(f"History DB init error: {e}")
        raise


async def log_operation(
    user_id: int, 
    operation: str, 
    filename: str, 
    duration: float = 0, 
    status: str = 'success', 
    file_size: int = 0,
    output_filename: str = None,
    db_path: str = None
) -> bool:
    """Log a user operation to the history."""
    db_path = db_path or DB_PATH
    await init_history_db(db_path)
    
    file_type = filename.rsplit('.', 1)[-1].lower() if '.' in filename else "unknown"
    ts = int(datetime.now().timestamp())
    
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                '''INSERT INTO operation_history 
                   (user_id, filename, file_type, operation_type, timestamp, duration, status, file_size, output_filename) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, filename, file_type, operation, ts, duration, status, file_size, output_filename)
            )
            await db.commit()
        logger.info(f"Logged operation {operation} for user {user_id}: {filename}")
        return True
    except aiosqlite.Error as e:
        logger.error(f"Error logging operation for user {user_id}: {e}")
        return False


async def get_recent_history(
    user_id: int, 
    limit: int = 10, 
    db_path: str = None
) -> List[Dict[str, Any]]:
    """Retrieve recent history for a user."""
    db_path = db_path or DB_PATH
    await init_history_db(db_path)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                '''SELECT filename, file_type, operation_type, timestamp, duration, status, file_size, output_filename 
                   FROM operation_history 
                   WHERE user_id = ? 
                   ORDER BY timestamp DESC 
                   LIMIT ?''',
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        
        return [
            {
                "filename": r[0], 
                "file_type": r[1], 
                "operation_type": r[2],
                "timestamp": r[3], 
                "duration": round(r[4], 2), 
                "status": r[5],
                "file_size": r[6],
                "output_filename": r[7],
                "formatted_time": datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d %H:%M")
            } for r in rows
        ]
    except aiosqlite.Error as e:
        logger.error(f"Error getting history for user {user_id}: {e}")
        return []


async def get_history_count(user_id: int, db_path: str = None) -> int:
    """Get total history count for a user."""
    db_path = db_path or DB_PATH
    await init_history_db(db_path)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                'SELECT COUNT(*) FROM operation_history WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except aiosqlite.Error as e:
        logger.error(f"Error getting history count for user {user_id}: {e}")
        return 0


async def get_history_stats(user_id: int, db_path: str = None) -> Dict[str, Any]:
    """Get aggregated statistics from user's history."""
    db_path = db_path or DB_PATH
    await init_history_db(db_path)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Total operations
            async with db.execute(
                'SELECT COUNT(*) FROM operation_history WHERE user_id = ?',
                (user_id,)
            ) as cursor:
                total = (await cursor.fetchone())[0]
            
            # Operations by type
            async with db.execute(
                '''SELECT operation_type, COUNT(*) 
                   FROM operation_history 
                   WHERE user_id = ? 
                   GROUP BY operation_type 
                   ORDER BY COUNT(*) DESC''',
                (user_id,)
            ) as cursor:
                by_type = {r[0]: r[1] for r in await cursor.fetchall()}
            
            # Success rate
            async with db.execute(
                '''SELECT 
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                    COUNT(*) as total
                   FROM operation_history 
                   WHERE user_id = ?''',
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                success_rate = (row[0] / row[1] * 100) if row[1] > 0 else 100
            
            # Most used file types
            async with db.execute(
                '''SELECT file_type, COUNT(*) 
                   FROM operation_history 
                   WHERE user_id = ? 
                   GROUP BY file_type 
                   ORDER BY COUNT(*) DESC 
                   LIMIT 5''',
                (user_id,)
            ) as cursor:
                file_types = {r[0]: r[1] for r in await cursor.fetchall()}
            
            # Average processing time
            async with db.execute(
                'SELECT AVG(duration) FROM operation_history WHERE user_id = ? AND duration > 0',
                (user_id,)
            ) as cursor:
                avg_duration = (await cursor.fetchone())[0] or 0
            
            return {
                "total_operations": total,
                "by_type": by_type,
                "success_rate": round(success_rate, 1),
                "file_types": file_types,
                "avg_duration": round(avg_duration, 2)
            }
    except aiosqlite.Error as e:
        logger.error(f"Error getting history stats for user {user_id}: {e}")
        return {
            "total_operations": 0,
            "by_type": {},
            "success_rate": 100,
            "file_types": {},
            "avg_duration": 0
        }


async def clean_old_history(
    user_id: int, 
    days_old: int = 30, 
    db_path: str = None
) -> int:
    """Clean old history entries for a user."""
    db_path = db_path or DB_PATH
    threshold = int((datetime.now() - timedelta(days=days_old)).timestamp())
    
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                'DELETE FROM operation_history WHERE user_id = ? AND timestamp < ?',
                (user_id, threshold)
            )
            deleted = cursor.rowcount
            await db.commit()
        logger.info(f"Cleaned {deleted} old entries for user {user_id}")
        return deleted
    except aiosqlite.Error as e:
        logger.error(f"Error cleaning history for user {user_id}: {e}")
        return 0


async def clear_all_history(user_id: int, db_path: str = None) -> int:
    """Clear all history for a user."""
    db_path = db_path or DB_PATH
    
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                'DELETE FROM operation_history WHERE user_id = ?',
                (user_id,)
            )
            deleted = cursor.rowcount
            await db.commit()
        logger.info(f"Cleared all {deleted} history entries for user {user_id}")
        return deleted
    except aiosqlite.Error as e:
        logger.error(f"Error clearing history for user {user_id}: {e}")
        return 0
