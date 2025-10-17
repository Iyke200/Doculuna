# database/db.py
import sqlite3
import logging
import os
import shutil
from config import DB_PATH as DATABASE_PATH

logger = logging.getLogger(__name__)

def init_db():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        stat = shutil.disk_usage(os.path.dirname(DATABASE_PATH))
        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
            logger.error("Insufficient storage for database initialization")
            raise Exception("Low disk space")
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            with open("database/schema.sql", "r") as f:
                conn.executescript(f.read())
            conn.commit()
            
            # Run migrations for existing databases
            cursor = conn.cursor()
            
            # Check if new columns exist, if not add them
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'usage_today' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN usage_today INTEGER DEFAULT 0")
                logger.info("Added usage_today column")
            
            if 'usage_reset_date' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN usage_reset_date DATE")
                cursor.execute("UPDATE users SET usage_reset_date = date('now') WHERE usage_reset_date IS NULL")
                logger.info("Added usage_reset_date column")
            
            if 'referral_count' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
                logger.info("Added referral_count column")
            
            if 'referral_earnings' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN referral_earnings INTEGER DEFAULT 0")
                logger.info("Added referral_earnings column")
            
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
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
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

def get_all_users():
    """Get all users from the database."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        return []

def get_pending_payments():
    """Get pending payments - placeholder function."""
    try:
        # For now, return empty list as payment system might need separate table
        return []
    except Exception as e:
        logger.error(f"Error fetching pending payments: {e}")
        return []

def get_user(user_id: int):
    """Alias for get_user_by_id for compatibility."""
    return get_user_by_id(user_id)

def add_payment_log(user_id: int, amount: int, plan_type: str, payment_method: str):
    """Log payment transaction."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payment_logs (user_id, amount, plan_type, payment_method, timestamp)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (user_id, amount, plan_type, payment_method))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging payment for user {user_id}: {e}")

def add_referral_reward(user_id: int, amount: int, plan_type: str):
    """Add referral reward to user."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO referral_rewards (user_id, amount, plan_type, timestamp)
                VALUES (?, ?, ?, datetime('now'))
            """, (user_id, amount, plan_type))
            # Also update referral stats
            cursor.execute("""
                UPDATE referrals 
                SET total_earnings = COALESCE(total_earnings, 0) + ?
                WHERE user_id = ?
            """, (amount, user_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding referral reward for user {user_id}: {e}")

def get_users_by_premium_status(is_premium: bool | None = None):
    """Get users filtered by premium status."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            if is_premium is None:
                cursor.execute("SELECT * FROM users")
            else:
                cursor.execute("SELECT * FROM users WHERE is_premium = ?", (1 if is_premium else 0,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting users by premium status: {e}")
        return []

# Compatibility wrapper functions for handlers
def get_user_data(user_id: int):
    """Wrapper for get_user_by_id for handler compatibility."""
    return get_user_by_id(user_id)

def create_user(user_data: dict):
    """Wrapper for add_user with dict input for handler compatibility."""
    user_id = user_data.get('user_id')
    username = user_data.get('username', '')
    if user_id:
        return add_user(user_id, username)
    return None

def update_user_data(user_id: int, data: dict):
    """Generic user data update function for handler compatibility."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Handle premium updates
            if 'is_premium' in data or 'premium_expiry' in data:
                if data.get('is_premium'):
                    days = 30  # default to 30 days if not specified
                    update_user_premium_status(user_id, days)
                    
            # Handle other user data updates
            update_fields = []
            values = []
            
            for key, value in data.items():
                if key in ['username', 'last_active', 'preferences', 'onboarding_complete', 
                          'onboarding_date', 'language', 'timezone', 'total_interactions',
                          'premium_status', 'referral_used']:
                    update_fields.append(f"{key} = ?")
                    values.append(str(value) if not isinstance(value, (int, float, bool)) else value)
            
            if update_fields:
                values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
                cursor.execute(query, values)
                conn.commit()
                
    except Exception as e:
        logger.error(f"Error updating user data for {user_id}: {e}")

# Placeholder functions for missing admin/role functionality
def get_user_role(user_id: int):
    """Placeholder function for user roles."""
    # For now, return 'user' for all users, 'superadmin' for admin IDs
    from config import ADMIN_USER_IDS
    if user_id in ADMIN_USER_IDS:
        return 'superadmin'
    return 'user'

def ban_user(user_id: int):
    """Placeholder function for banning users."""
    logger.info(f"User {user_id} would be banned (not implemented)")
    return True

def unban_user(user_id: int):
    """Placeholder function for unbanning users."""
    logger.info(f"User {user_id} would be unbanned (not implemented)")
    return True

def check_premium_expiry_warnings():
    """Check for users whose premium expires in 3 days."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, premium_expiry FROM users 
                WHERE is_premium = 1 AND premium_expiry IS NOT NULL
                AND date(premium_expiry) = date('now', '+3 days')
                AND user_id NOT IN (
                    SELECT user_id FROM premium_expiry_warnings 
                    WHERE date(warning_sent) = date('now')
                )
            """)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error checking premium expiry warnings: {e}")
        return []

def mark_expiry_warning_sent(user_id: int, expiry_date: str):
    """Mark that expiry warning has been sent."""
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO premium_expiry_warnings (user_id, warning_sent, expiry_date)
                VALUES (?, datetime('now'), ?)
            """, (user_id, expiry_date))
            conn.commit()
    except Exception as e:
        logger.error(f"Error marking expiry warning sent: {e}")
