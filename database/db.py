# database/db.py
import sqlite3
import logging
import os
import shutil
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def init_db():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        stat = shutil.disk_usage(os.path.dirname(DATABASE_PATH))
        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
            logger.error("Insufficient storage for database initialization")
            raise Exception("Low disk space")
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            with open("schema.sql", "r") as f:
                conn.executescript(f.read())
            conn.commit()
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

def add_user(user_id: int, username: str):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, username, is_premium) VALUES (?, ?, ?)",
                (user_id, username, 0)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")

def get_user_by_id(user_id: int):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None

def update_user_premium_status(user_id: int, days: int):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET is_premium = 1,
                    premium_expiry = datetime('now', '+' || ? || ' days')
                WHERE user_id = ?
            """, (days, user_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating premium status for user {user_id}: {e}")

def add_usage_log(user_id: int, tool: str, is_success: bool):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usage_logs (user_id, tool, timestamp, is_success) VALUES (?, ?, datetime('now'), ?)",
                (user_id, tool, 1 if is_success else 0)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding usage log for user {user_id}: {e}")

def get_usage_count(user_id: int):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM usage_logs
                WHERE user_id = ? AND date(timestamp) = date('now') AND is_success = 1
            """, (user_id,))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error fetching usage count for user {user_id}: {e}")
        return 0

def add_referral_code(user_id: int, referral_code: str):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO referrals (user_id, referral_code, referral_count) VALUES (?, ?, 0)",
                (user_id, referral_code)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding referral code for user {user_id}: {e}")

def increment_referral_count(referred_by_id: int, premium_days: int):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE referrals
                SET referral_count = referral_count + 1,
                    premium_days_earned = premium_days_earned + ?
                WHERE user_id = ?
            """, (premium_days, referred_by_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing referral count for user {referred_by_id}: {e}")

def get_referral_stats(user_id: int):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referral_count, premium_days_earned FROM referrals WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return {"referral_count": result[0], "premium_days_earned": result[1]} if result else {"referral_count": 0, "premium_days_earned": 0}
    except Exception as e:
        logger.error(f"Error fetching referral stats for user {user_id}: {e}")
        return {"referral_count": 0, "premium_days_earned": 0}

def get_top_referrers(limit=5):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username, r.referral_count
                FROM users u
                JOIN referrals r ON u.user_id = r.user_id
                ORDER BY r.referral_count DESC
                LIMIT ?
            """, (limit,))
            return [{"username": row[0], "referral_count": row[1]} for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching top referrers: {e}")
        return []

def get_high_usage_users():
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, COUNT(*) as uses
                FROM usage_logs
                WHERE date(timestamp) = date('now') AND is_success = 1
                GROUP BY user_id
                HAVING uses > 3
            """)
            return [{"user_id": row[0]} for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching high-usage users: {e}")
        return []

def add_feedback(user_id: int, feedback: str):
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedback (user_id, feedback, timestamp) VALUES (?, ?, datetime('now'))",
                (user_id, feedback)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding feedback for user {user_id}: {e}")
