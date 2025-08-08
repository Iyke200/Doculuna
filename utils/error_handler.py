
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

async def error_handler(update, context):
    """Handle errors in bot operations."""
    try:
        error_msg = str(context.error)
        user_id = update.effective_user.id if update and update.effective_user else "Unknown"
        
        logger.error(f"Error for user {user_id}: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        if update and update.effective_chat:
            await update.effective_chat.send_message(
                "❌ An error occurred. Our team has been notified."
            )
            
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

def log_error(error, context="Unknown"):
    """Log error with context."""
    timestamp = datetime.now().isoformat()
    logger.error(f"[{timestamp}] {context}: {error}")
    logger.error(f"Traceback: {traceback.format_exc()}")
