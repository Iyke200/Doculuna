# utils/referral_utils.py
import logging
from database.db import get_db_connection

# Setup logging
logger = logging.getLogger(__name__)

def get_referral_count(user_id):
    """Get the number of successful referrals for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?",
                (user_id,)
            )
            count = cursor.fetchone()["count"]
        logger.info(f"Referral count for user {user_id}: {count}")
        return count
    except Exception as e:
        logger.error(f"Error getting referral count for user {user_id}: {e}")
        return 0

def grant_referral_bonus(user_id):
    """Grant bonus free uses based on referral count."""
    try:
        referral_count = get_referral_count(user_id)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET free_uses = free_uses + ? WHERE user_id = ? AND is_premium = 0",
                (referral_count, user_id)
            )
        logger.info(f"Granted {referral_count} bonus uses to user {user_id}")
    except Exception as e:
        logger.error(f"Error granting referral bonus for user {user_id}: {e}")
# utils/referral_utils.py
import logging
from database.db import get_db_connection
from config import REFERRAL_BONUS

# Setup logging
logger = logging.getLogger(__name__)

def get_referral_count(user_id):
    """Get the number of successful referrals for a user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                (user_id,)
            )
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting referral count for user {user_id}: {e}")
        return 0

def grant_referral_bonus(user_id):
    """Grant referral bonus to users who have made referrals."""
    try:
        referral_count = get_referral_count(user_id)
        if referral_count > 0:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET free_uses = free_uses + ? WHERE user_id = ? AND is_premium = 0",
                    (referral_count * REFERRAL_BONUS, user_id)
                )
            logger.info(f"Granted {referral_count * REFERRAL_BONUS} bonus uses to user {user_id}")
    except Exception as e:
        logger.error(f"Error granting referral bonus to user {user_id}: {e}")
