import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_all_users

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics."""
    try:
        user_id = update.effective_user.id

        # Get basic stats
        users = get_all_users()
        total_users = len(users)

        message = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🔧 Status: Running\n\n"
            f"Thank you for using DocuLuna!"
        )

        await update.message.reply_text(message, parse_mode="Markdown")

        logger.info(f"Stats shown to user {user_id}")

    except Exception as e:
        logger.error(f"Error showing stats to user {user_id}: {e}")
        await update.message.reply_text("❌ Error retrieving statistics.")
