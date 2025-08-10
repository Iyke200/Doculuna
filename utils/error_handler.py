import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


async def error_handler(update, context):
    """Global error handler for the bot."""
    try:
        logger.error(f"Update {update} caused error {context.error}")

        # Log the full traceback
        tb_lines = traceback.format_exception(
            type(context.error), context.error, context.error.__traceback__
        )
        tb_string = "".join(tb_lines)

        log_error(
            error_type=type(context.error).__name__,
            error_message=str(context.error),
            traceback=tb_string,
            update_data=str(update) if update else None,
        )

        # Send user-friendly error message
        if update and update.effective_chat:
            try:
                error_message = format_error_for_user(context.error)
                await update.effective_chat.send_message(error_message)
            except Exception as e:
                logger.error(f"Could not send error message to user: {e}")

    except Exception as e:
        logger.error(f"Error in error handler: {e}")


def log_error(error_type, error_message, traceback=None, update_data=None):
    """Log error details to file."""
    try:
        import os

        os.makedirs("logs", exist_ok=True)

        with open("logs/errors.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Error Type: {error_type}\n")
            f.write(f"Error Message: {error_message}\n")
            if traceback:
                f.write(f"Traceback:\n{traceback}\n")
            if update_data:
                f.write(f"Update Data: {update_data}\n")
            f.write(f"{'='*50}\n")

    except Exception as e:
        logger.error(f"Failed to log error to file: {e}")


def format_error_for_user(error):
    """Format error message for user display."""
    if "file not found" in str(error).lower():
        return "❌ File not found. Please try uploading the file again."
    elif "timeout" in str(error).lower():
        return "❌ Processing timeout. Please try with a smaller file."
    elif "permission" in str(error).lower():
        return "❌ Permission error. Please try again."
    elif "network" in str(error).lower():
        return "❌ Network error. Please check your connection and try again."
    elif "invalid" in str(error).lower():
        return "❌ Invalid file format. Please check supported formats."
    else:
        return "❌ An unexpected error occurred. Please try again later."
