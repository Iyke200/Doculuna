# utils/referral_utils.py
import logging
import sqlite3
from config import REFERRAL_BONUS

# Setup logging
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection."""
    return sqlite3.connect('database/doculuna.db')

def get_referral_count(user_id):
    """Get the number of successful referrals for a user."""
    try:
        conn = sqlite3.connect('database/doculuna.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Error getting referral count for user {user_id}: {e}")
        return 0

def grant_referral_bonus(user_id):
    """Grant referral bonus to users who have made referrals."""
    try:
        referral_count = get_referral_count(user_id)
        if referral_count > 0:
            conn = sqlite3.connect('database/doculuna.db')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET usage_count = usage_count + ? WHERE user_id = ? AND is_premium = 0",
                (referral_count * REFERRAL_BONUS, user_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Granted {referral_count * REFERRAL_BONUS} bonus uses to user {user_id}")
    except Exception as e:
        logger.error(f"Error granting referral bonus to user {user_id}: {e}")
