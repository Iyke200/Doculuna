
import logging
from database.db import get_user, increment_user_usage, add_usage_log
from config import FREE_DAILY_LIMIT, PREMIUM_DAILY_LIMIT

logger = logging.getLogger(__name__)

async def check_usage_limit(user_id):
    """Check if user has exceeded usage limit."""
    try:
        user = get_user(user_id)
        if not user:
            return True  # Allow usage for new users
            
        if user.get('is_premium', False):
            return True  # Premium users have unlimited access
            
        usage_count = user.get('usage_count', 0)
        if usage_count >= FREE_DAILY_LIMIT:
            return False  # Limit exceeded
            
        return True
        
    except Exception as e:
        logger.error(f"Error checking usage limit for user {user_id}: {e}")
        return True  # Allow usage on error

async def increment_usage(user_id, tool_used="unknown"):
    """Increment user's usage count."""
    try:
        increment_user_usage(user_id)
        add_usage_log(user_id, tool_used)
        
        logger.info(f"Usage incremented for user {user_id}: {tool_used}")
        
    except Exception as e:
        logger.error(f"Error incrementing usage for user {user_id}: {e}")

def add_watermark_to_file(file_path, is_premium=False):
    """Add watermark to files for free users."""
    if is_premium:
        return True

    try:
        # For now, just log the watermark action
        logger.info(f"Watermark would be added to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Error adding watermark: {e}")
        return False
