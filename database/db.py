# database/db.py
import sqlite3
import logging
import time
from datetime import datetime, date
from contextlib import contextmanager
from config import DB_PATH, FREE_USAGE_LIMIT, REFERRAL_BONUS

# Setup logging
logging.basicConfig(
    filename="doculuna.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Context manager for database connections with retry logic."""
    retries = 3
    for attempt in range(retries):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            logger.error(f"Database connection error: {e}, attempt {attempt + 1}/{retries}")
            time.sleep(1)
        finally:
            if 'conn' in locals():
                conn.close()
    logger.critical("Failed to connect to database after retries")
    raise Exception("Database connection failed")

def init_db():
    """Initialize database with schema."""
    try:
        with open("database/schema.sql", "r") as schema_file:
            schema = schema_file.read()
        with get_db_connection() as conn:
            conn.executescript(schema)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def reset_daily_uses_if_needed(user_id):
    """Reset daily uses if it's a new day."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            today = date.today().isoformat()
            cursor.execute("SELECT last_reset_date FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()

            if result and result["last_reset_date"] != today:
                cursor.execute(
                    "UPDATE users SET daily_uses = ?, last_reset_date = ? WHERE user_id = ?",
                    (FREE_USAGE_LIMIT, today, user_id)
                )
                logger.info(f"Reset daily uses for user {user_id}")
    except Exception as e:
        logger.error(f"Error resetting daily uses for user {user_id}: {e}")

def get_user(user_id):
    """Fetch user by ID and reset daily uses if needed."""
    try:
        reset_daily_uses_if_needed(user_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
        return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None

def get_user_by_username(username):
    """Fetch user by username."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
        return user
    except Exception as e:
        logger.error(f"Error fetching user by username {username}: {e}")
        return None

def add_user(user_id, username, first_name, last_name, referrer_id=None):
    """Add a new user and handle referral bonuses."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            today = date.today().isoformat()
            bonus_uses = REFERRAL_BONUS if referrer_id else 0

            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, daily_uses, last_reset_date) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, FREE_USAGE_LIMIT + bonus_uses, today)
            )

            if referrer_id and referrer_id != user_id:
                # Add referral record
                cursor.execute(
                    "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                    (referrer_id, user_id)
                )
                # Give referrer bonus uses
                cursor.execute(
                    "UPDATE users SET daily_uses = daily_uses + ? WHERE user_id = ?",
                    (REFERRAL_BONUS, referrer_id)
                )
                logger.info(f"Referral bonus granted to user {referrer_id}")

        logger.info(f"User {user_id} added successfully with referrer {referrer_id}")
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")

def add_usage(user_id, tool_name, file_size=0):
    """Log tool usage and decrease daily uses."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usage_logs (user_id, tool_name, file_size) VALUES (?, ?, ?)",
                (user_id, tool_name, file_size)
            )
            cursor.execute(
                "UPDATE users SET daily_uses = daily_uses - 1 WHERE user_id = ? AND is_premium = 0",
                (user_id,)
            )
        logger.info(f"Usage recorded for user {user_id}: {tool_name}")
    except Exception as e:
        logger.error(f"Error recording usage for user {user_id}: {e}")

def add_premium_payment(user_id, amount, plan_type, screenshot_path, expiry_date):
    """Record a premium payment submission."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO premium_payments (user_id, amount, plan_type, screenshot_path, expiry_date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, amount, plan_type, screenshot_path, expiry_date))
            conn.commit()
        logger.info(f"Premium payment recorded for user {user_id}: {plan_type}")
    except Exception as e:
        logger.error(f"Error recording premium payment for user {user_id}: {e}")

def get_referral_stats(user_id):
    """Get referral statistics for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?", (user_id,))
            result = cursor.fetchone()
            return result["count"] if result else 0
    except Exception as e:
        logger.error(f"Error getting referral stats for user {user_id}: {e}")
        return 0

def check_daily_limits(user_id):
    """Check if user has exceeded daily limits."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            today = date.today().isoformat()
            cursor.execute(
                "SELECT request_count FROM daily_stats WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            result = cursor.fetchone()
            count = result["request_count"] if result else 0

            if count == 0:
                cursor.execute(
                    "INSERT OR REPLACE INTO daily_stats (user_id, date, request_count) VALUES (?, ?, 1)",
                    (user_id, today)
                )
            else:
                cursor.execute(
                    "UPDATE daily_stats SET request_count = request_count + 1 WHERE user_id = ? AND date = ?",
                    (user_id, today)
                )
            return count + 1
    except Exception as e:
        logger.error(f"Error checking daily limits for user {user_id}: {e}")
        return 999

def get_pending_payments():
    """Get all pending payment submissions."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.first_name, u.last_name, u.username 
                FROM premium_payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.status = 'pending'
                ORDER BY p.created_at DESC
            """)
            payments = [dict(row) for row in cursor.fetchall()]
            return payments
    except Exception as e:
        logger.error(f"Database error getting pending payments: {e}")
        return []

def get_payment_by_id(payment_id):
    """Get payment by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.first_name, u.last_name, u.username 
                FROM premium_payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.id = ?
            """, (payment_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Database error getting payment {payment_id}: {e}")
        return None

def approve_payment_by_id(payment_id):
    """Approve a payment and activate premium."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get payment details
            cursor.execute("SELECT * FROM premium_payments WHERE id = ?", (payment_id,))
            payment = cursor.fetchone()
            if not payment:
                return False

            # Update payment status
            cursor.execute("""
                UPDATE premium_payments 
                SET status = 'approved', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (payment_id,))

            # Activate premium for user
            cursor.execute("""
                UPDATE users 
                SET is_premium = 1, premium_expiry = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (payment['expiry_date'], payment['user_id']))

            conn.commit()
            logger.info(f"Payment {payment_id} approved for user {payment['user_id']}")
            return True
    except Exception as e:
        logger.error(f"Database error approving payment {payment_id}: {e}")
        return False

def reject_payment_by_id(payment_id):
    """Reject a payment."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE premium_payments 
                SET status = 'rejected', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (payment_id,))
            conn.commit()
        logger.info(f"Payment {payment_id} rejected")
        return True
    except Exception as e:
        logger.error(f"Database error rejecting payment {payment_id}: {e}")
        return False

def get_all_payments():
    """Get all payments for admin statistics."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM premium_payments ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error getting all payments: {e}")
        return []

def get_all_users():
    """Get all users for admin management."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error getting all users: {e}")
        return []


def get_payment_by_id(payment_id):
    """Get payment by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM premium_payments WHERE id = ?", (payment_id,))
            return dict(cursor.fetchone()) if cursor.fetchone() else None
    except Exception as e:
        logger.error(f"Database error getting payment {payment_id}: {e}")
        return None

def get_pending_payments():
    """Get all pending payments."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM premium_payments WHERE status = 'pending' ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error getting pending payments: {e}")
        return []

def approve_payment_by_id(payment_id):
    """Approve a payment by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE premium_payments 
                SET status = 'approved', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (payment_id,))
            conn.commit()
        logger.info(f"Payment {payment_id} approved")
        return True
    except Exception as e:
        logger.error(f"Database error approving payment {payment_id}: {e}")
        return False


def create_user(user_id, username, first_name, last_name=None):
    """Create a new user (alias for add_user for compatibility)."""
    add_user(user_id, username, first_name, last_name)

def save_payment_request(user_id, amount, plan_type, screenshot_path):
    """Save a payment request to the database."""
    try:
        from datetime import datetime, timedelta
        
        # Calculate expiry date based on plan type
        if plan_type == "monthly":
            expiry_days = 30
        else:
            expiry_days = 7
            
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d')
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO premium_payments (user_id, amount, plan_type, screenshot_path, expiry_date, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (user_id, amount, plan_type, screenshot_path, expiry_date))
            conn.commit()
        logger.info(f"Payment request saved for user {user_id}: {plan_type}")
    except Exception as e:
        logger.error(f"Error saving payment request for user {user_id}: {e}")

def add_referral(referrer_id, referred_id):
    """Add a referral relationship between users."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Add referral record
            cursor.execute(
                "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referrer_id, referred_id)
            )
            # Give referrer bonus uses
            cursor.execute(
                "UPDATE users SET daily_uses = daily_uses + ? WHERE user_id = ?",
                (REFERRAL_BONUS, referrer_id)
            )
            # Give referred user bonus uses  
            cursor.execute(
                "UPDATE users SET daily_uses = daily_uses + ? WHERE user_id = ?",
                (REFERRAL_BONUS, referred_id)
            )
            conn.commit()
        logger.info(f"Referral added: {referrer_id} -> {referred_id}")
    except Exception as e:
        logger.error(f"Error adding referral {referrer_id} -> {referred_id}: {e}")

def update_premium_status(user_id, is_premium, expiry_date=None, plan_type=None):
    """Update premium status for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET is_premium = ?, premium_expiry = ?, premium_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (is_premium, expiry_date, plan_type, user_id))
            conn.commit()
        logger.info(f"Premium status updated for user {user_id}: premium={is_premium}, type={plan_type}")
        return True
    except Exception as e:
        logger.error(f"Error updating premium status for user {user_id}: {e}")
        return False

def get_user_usage_stats(user_id):
    """Get usage statistics for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_documents FROM usage_logs WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            total_documents = result["total_documents"] if result else 0
            
            cursor.execute("SELECT COUNT(DISTINCT tool_name) as tools_used FROM usage_logs WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            tools_used = result["tools_used"] if result else 0
            
            return {
                'total_documents': total_documents,
                'tools_used': tools_used
            }
    except Exception as e:
        logger.error(f"Error getting usage stats for user {user_id}: {e}")
        return {'total_documents': 0, 'tools_used': 0}

if __name__ == "__main__":
    init_db()
    logger.info("Database initialization test completed")