import logging
import traceback
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def error_handler(func):
    """Decorator to handle errors in handler functions."""

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            logger.error(traceback.format_exc())

            # Try to send error message to user
            try:
                if update.message:
                    await update.message.reply_text(
                        "❌ An error occurred. Please try again later."
                    )
                elif update.callback_query:
                    await update.callback_query.edit_message_text(
                        "❌ An error occurred. Please try again later."
                    )
            except:
                pass  # Ignore if we can't send error message

            return None

    return wrapper


def log_error(error_message, user_id=None, additional_info=None):
    """Log error with additional context."""
    log_msg = f"Error: {error_message}"
    if user_id:
        log_msg += f" | User: {user_id}"
    if additional_info:
        log_msg += f" | Info: {additional_info}"

    logger.error(log_msg)


def format_error_for_user(error):
    """Format error message for user display."""
    if "file not found" in str(error).lower():
        return "❌ File not found. Please try uploading the file again."
    elif "timeout" in str(error).lower():
        return "❌ Processing timeout. Please try with a smaller file."
    elif "permission" in str(error).lower():
        return "❌ Permission error. Please try again."
    else:
        return "❌ An unexpected error occurred. Please try again later."
