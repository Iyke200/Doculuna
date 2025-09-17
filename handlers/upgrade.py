‎# handlers/upgrade.py
‎import logging
‎from telegram import Update
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎from handlers.premium import show_premium_options
‎
‎logger = logging.getLogger(__name__)
‎
‎async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        for attempt in range(3):
‎            try:
‎                await show_premium_options(update, context)
‎                break
‎            except RetryAfter as e:
‎                logger.warning(f"Rate limit hit in upgrade: {e}")
‎                await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in upgrade: {e}")
‎        await update.message.reply_text("❌ Error showing Pro plans. Try again.")
