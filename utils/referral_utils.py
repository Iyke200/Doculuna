# utils/referral_utils.py - Advanced Production Referral System
import logging
import sqlite3
from database.db import (
    get_referral_stats, increment_referral_count, 
    add_referral_reward, get_user_by_id
)
from config import REFERRAL_REWARDS

logger = logging.getLogger(__name__)

async def process_referral_reward(referrer_id: int, plan_type: str):
    """Process referral reward for the referrer."""
    try:
        if plan_type not in REFERRAL_REWARDS:
            return False
            
        reward_amount = REFERRAL_REWARDS[plan_type]
        
        # Check if referrer exists
        referrer = get_user_by_id(referrer_id)
        if not referrer:
            return False
            
        # Add reward to referrer's account
        add_referral_reward(referrer_id, reward_amount, plan_type)
        
        # Increment referral count
        increment_referral_count(referrer_id, reward_amount)
        
        logger.info(f"Referral reward processed: User {referrer_id} earned ₦{reward_amount} for {plan_type} referral")
        return True
        
    except Exception as e:
        logger.error(f"Error processing referral reward: {e}")
        return False

async def get_referral_earnings(user_id: int):
    """Get total referral earnings for a user."""
    try:
        stats = get_referral_stats(user_id)
        return stats.get('total_earnings', 0)
    except Exception as e:
        logger.error(f"Error getting referral earnings: {e}")
        return 0

async def generate_referral_link(bot_username: str, user_id: int):
    """Generate referral link for user."""
    try:
        # Simple referral code based on user ID
        referral_code = f"ref_{user_id}"
        return f"https://t.me/{bot_username}?start={referral_code}"
    except Exception as e:
        logger.error(f"Error generating referral link: {e}")
        return None

def get_db_connection():
    """Get database connection."""
    return sqlite3.connect("database/doculuna.db")

def get_referral_count(user_id):
    """Get the number of successful referrals for a user."""
    try:
        conn = sqlite3.connect("database/doculuna.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
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
            conn = sqlite3.connect("database/doculuna.db")
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET usage_count = usage_count + ? WHERE user_id = ? AND is_premium = 0",
                (referral_count * 1, user_id),  # REFERRAL_BONUS
            )
            conn.commit()
            conn.close()
            logger.info(
                f"Granted {referral_count * 1} bonus uses to user {user_id}"
            )
    except Exception as e:
        logger.error(f"Error granting referral bonus to user {user_id}: {e}")