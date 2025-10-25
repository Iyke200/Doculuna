# database/db.py
import aiosqlite
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from config import DB_PATH as DATABASE_PATH

logger = logging.getLogger(__name__)

# Minimal schema fallback if schema.sql missing
MINIMAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_premium INTEGER DEFAULT 0,
    premium_expiry DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    usage_today INTEGER DEFAULT 0,
    usage_reset_date DATE DEFAULT CURRENT_DATE,
    referral_count INTEGER DEFAULT 0,
    referral_earnings INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tool TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_success INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    referral_code TEXT UNIQUE,
    referral_count INTEGER DEFAULT 0,
    premium_days_earned INTEGER DEFAULT 0,
    total_earnings INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    payment_method TEXT,
    status TEXT DEFAULT 'pending',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    feedback TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS referral_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS premium_expiry_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    warning_sent DATETIME DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE
);
"""

async def init_db():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        stat = shutil.disk_usage(os.path.dirname(DATABASE_PATH))
        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
            logger.error("Insufficient storage for database initialization")
            raise Exception("Low disk space")
        
        schema_sql = MINIMAL_SCHEMA  # Fallback
        schema_file = "database/schema.sql"
        if os.path.exists(schema_file):
            with open(schema_file, "r") as f:
                schema_sql = f.read()
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.executescript(schema_sql)
            
            # Check table existence before migrations
            async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'") as cursor:
                if not await cursor.fetchone():
                    logger.warning("Users table missing; using minimal schema")
            
            # Migrations
            async with conn.execute("PRAGMA table_info(users)") as cursor:
                columns = [column[1] for column in await cursor.fetchall()]
            
            if 'usage_today' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN usage_today INTEGER DEFAULT 0")
                logger.info("Added usage_today column")
            
            if 'usage_reset_date' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN usage_reset_date DATE")
                await conn.execute("UPDATE users SET usage_reset_date = date('now') WHERE usage_reset_date IS NULL")
                logger.info("Added usage_reset_date column")
            
            if 'referral_count' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
                logger.info("Added referral_count column")
            
            if 'referral_earnings' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN referral_earnings INTEGER DEFAULT 0")
                logger.info("Added referral_earnings column")
            
            # Add is_banned for ban functionality
            if 'is_banned' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
                logger.info("Added is_banned column")
            
            # Referral columns
            async with conn.execute("PRAGMA table_info(referrals)") as cursor:
                ref_columns = [column[1] for column in await cursor.fetchall()]
            if 'premium_days_earned' not in ref_columns:
                await conn.execute("ALTER TABLE referrals ADD COLUMN premium_days_earned INTEGER DEFAULT 0")
                logger.info("Added premium_days_earned to referrals")
            if 'total_earnings' not in ref_columns:
                await conn.execute("ALTER TABLE referrals ADD COLUMN total_earnings INTEGER DEFAULT 0")
                logger.info("Added total_earnings to referrals")
            
            await conn.commit()
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# [Rest of functions unchanged, except ban/unban impl and transactions]

async def ban_user(user_id: int) -> bool:
    """Ban user by setting is_banned=1."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error banning user {user_id}: {e}")
        return False

async def unban_user(user_id: int) -> bool:
    """Unban user by setting is_banned=0."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error unbanning user {user_id}: {e}")
        return False

async def add_referral_reward(user_id: int, amount: int, plan_type: str):
    """Add referral reward to user with transaction."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("BEGIN")
            try:
                await conn.execute("""
                    INSERT INTO referral_rewards (user_id, amount, plan_type, timestamp)
                    VALUES (?, ?, ?, datetime('now'))
                """, (user_id, amount, plan_type))
                await conn.execute("""
                    UPDATE referrals 
                    SET total_earnings = COALESCE(total_earnings, 0) + ?
                    WHERE user_id = ?
                """, (amount, user_id))
                await conn.commit()
            except:
                await conn.rollback()
                raise
    except Exception as e:
        logger.error(f"Error adding referral reward for user {user_id}: {e}")

async def update_user_data(user_id: int, data: Dict[str, Any]):
    """Generic user data update with type guards."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            # Premium handling
            if 'is_premium' in data or 'premium_expiry' in data:
                if data.get('is_premium'):
                    days = data.get('days', 30)
                    await update_user_premium_status(user_id, days)
            
            # Other updates
            update_fields = []
            values = []
            for key, value in data.items():
                if key in ['username', 'last_active', 'preferences', 'onboarding_complete', 
                          'onboarding_date', 'language', 'timezone', 'total_interactions',
                          'premium_status', 'referral_used', 'usage_today', 'usage_reset_date']:
                    if isinstance(value, (str, int, float, bool)):
                        update_fields.append(f"{key} = ?")
                        values.append(value)
                    else:
                        logger.warning(f"Skipping non-primitive value for {key}: {type(value)}")
            
            if update_fields:
                values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
                await conn.execute(query, values)
                await conn.commit()
    except Exception as e:
        logger.error(f"Error updating user data for {user_id}: {e}")

# [Include all other functions from previous version unchanged]
# ... (e.g., add_user, get_user_by_id, etc.)
