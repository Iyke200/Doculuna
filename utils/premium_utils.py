

import logging
from datetime import datetime
from database.db import get_user

logger = logging.getLogger(__name__)

def is_premium(user_id):
    """Check if user has active premium subscription."""
    try:
        user = get_user(user_id)
        if not user:
            return False
            
        if not user['is_premium']:
            return False
            
        # Check if premium has expired
        if user['premium_expiry']:
            expiry_date = datetime.strptime(user['premium_expiry'], '%Y-%m-%d').date()
            if expiry_date < datetime.now().date():
                # Premium expired, update database
                from database.db import update_premium_status
                update_premium_status(user_id, False, None)
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"Error checking premium status for user {user_id}: {e}")
        return False

async def is_premium_user(user_id):
    """Async wrapper for is_premium function for backwards compatibility."""
    return is_premium(user_id)

def get_premium_info(user_id):
    """Get premium subscription information."""
    try:
        user = get_user(user_id)
        if not user:
            return None
            
        return {
            'is_premium': user['is_premium'],
            'expiry_date': user['premium_expiry'],
            'days_remaining': get_days_remaining(user['premium_expiry']) if user['premium_expiry'] else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting premium info for user {user_id}: {e}")
        return None

def get_days_remaining(expiry_date_str):
    """Calculate days remaining in premium subscription."""
    try:
        if not expiry_date_str:
            return 0
            
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        if expiry_date <= today:
            return 0
            
        return (expiry_date - today).days
        
    except Exception as e:
        logger.error(f"Error calculating days remaining: {e}")
        return 0
