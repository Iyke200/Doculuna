# handlers/stats.py
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from database.db import get_usage_count

logger = logging.getLogger(__name__)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user stats."""
    await show_stats(update, context)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        usage_count = get_usage_count(user_id)
        message = (
            f"📊 **Your Stats: See how much you're saving with DocuLuna!**\n\n"
            f"Daily Usage: {usage_count}/5 (Free)\n"
            "Go Pro for unlimited conversions and watermark-free outputs!"
        )
        for attempt in range(3):
            try:
                await update.message.reply_text(message, parse_mode="Markdown")
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in show_stats: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in show_stats: {e}")
        await update.message.reply_text("❌ Error fetching stats. Try again.")