# history.py
"""History tracking module for DocuLuna.

Manages logging and retrieval of user operations history with async DB access.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

async def init_db(db_path: str) -> None:
    """Initialize the history database table."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.executescript('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT,
                    operation_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    duration REAL DEFAULT 0,
                    status TEXT DEFAULT 'success'
                );
                CREATE INDEX IF NOT EXISTS idx_history_user_id ON history(user_id);
                CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp);
            ''')
            await db.commit()
        logger.info("History database initialized.")
    except aiosqlite.Error as e:
        logger.error(f"History DB init error: {e}")
        raise

async def log_operation(user_id: int, operation: str, filename: str, duration: float = 0, status: str = 'success', db_path: str = "doculuna.db") -> None:
    """Log a user operation to the history."""
    await init_db(db_path)
    file_type = filename.rsplit('.', 1)[-1].lower() if '.' in filename else "unknown"
    ts = int(datetime.now().timestamp())
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                'INSERT INTO history (user_id, filename, file_type, operation_type, timestamp, duration, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (user_id, filename, file_type, operation, ts, duration, status)
            )
            await db.commit()
        logger.info(f"Logged operation {operation} for user {user_id}")
    except aiosqlite.Error as e:
        logger.error(f"Error logging operation for user {user_id}: {e}")

async def get_recent_history(user_id: int, limit: int = 10, db_path: str = "doculuna.db") -> List[Dict[str, Any]]:
    """Retrieve recent history for a user."""
    await init_db(db_path)
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                'SELECT filename, file_type, operation_type, timestamp, duration, status FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "filename": r[0], "file_type": r[1], "operation_type": r[2],
                "timestamp": r[3], "duration": round(r[4], 2), "status": r[5]
            } for r in rows
        ]
    except aiosqlite.Error as e:
        logger.error(f"Error getting history for user {user_id}: {e}")
        return []

async def clean_old_history(user_id: int, days_old: int = 30, db_path: str = "doculuna.db") -> int:
    """Clean old history entries for a user."""
    threshold = int((datetime.now() - timedelta(days=days_old)).timestamp())
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                'DELETE FROM history WHERE user_id = ? AND timestamp < ?',
                (user_id, threshold)
            ) as cursor:
                deleted = cursor.rowcount
            await db.commit()
        logger.info(f"Cleaned {deleted} old entries for user {user_id}")
        return deleted
    except aiosqlite.Error as e:
        logger.error(f"Error cleaning history for user {user_id}: {e}")
        return 0
