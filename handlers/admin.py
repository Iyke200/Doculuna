‎# handlers/admin.py
‎import logging
‎from telegram import Update
‎from telegram.ext import CommandHandler, ContextTypes
‎from telegram.error import RetryAfter
‎from config import NOTIFY_CHAT_ID
‎from database.db import get_user_by_id, get_usage_count
‎
‎logger = logging.getLogger(__name__)
‎
‎async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        if str(update.effective_user.id) != NOTIFY_CHAT_ID:
‎            await update.message.reply_text("❌ Unauthorized access. Contact support.")
‎            return
‎        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
‎            cursor = conn.cursor()
‎            cursor.execute("SELECT COUNT(*) FROM users")
‎            user_count = cursor.fetchone()[0]
‎            cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
‎            premium_count = cursor.fetchone()[0]
‎        message = (
‎            f"📊 **Admin Stats: Know Your Users!**\n\n"
‎            f"👤 Total Users: {user_count}\n"
‎            f"💎 Premium Users: {premium_count}\n"
‎            f"💰 Est. Monthly Revenue: {premium_count * 3500:,} NGN\n\n"
‎            "Keep growing with DocuLuna!"
‎        )
‎        for attempt in range(3):
‎            try:
‎                await update.message.reply_text(message, parse_mode="Markdown")
‎                break
‎            except RetryAfter as e:
‎                logger.warning(f"Rate limit hit in admin_stats: {e}")
‎                await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in admin_stats: {e}")
‎        await update.message.reply_text("❌ Error fetching admin stats. Try again.")
‎
‎def register_admin_handlers(app):
‎    app.add_handler(CommandHandler("adminstats", admin_stats))
‎
