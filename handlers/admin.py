# handlers/admin.py
import logging
import sqlite3
import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import RetryAfter
from config import ADMIN_USER_IDS, DB_PATH as DATABASE_PATH

logger = logging.getLogger(__name__)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Unauthorized access. Contact support.")
            return
        await admin_stats(update, context)
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        await update.message.reply_text("❌ Error accessing admin panel.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Unauthorized access. Contact support.")
            return
        
        with sqlite3.connect(DATABASE_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            premium_count = cursor.fetchone()[0]
        
        message = (
            f"📊 **Admin Stats: Know Your Users!**\n\n"
            f"👤 Total Users: {user_count}\n"
            f"💎 Premium Users: {premium_count}\n"
            f"💰 Est. Monthly Revenue: {premium_count * 3500:,} NGN\n\n"
            "Keep growing with DocuLuna!"
        )
        for attempt in range(3):
            try:
                await update.message.reply_text(message, parse_mode="Markdown")
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in admin_stats: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        await update.message.reply_text("❌ Error fetching admin stats. Try again.")

async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium access."""
    try:
        await update.message.reply_text("🔧 Grant premium functionality coming soon!")
    except Exception as e:
        logger.error(f"Error in grant_premium_command: {e}")

async def revoke_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoke premium access.""" 
    try:
        await update.message.reply_text("🔧 Revoke premium functionality coming soon!")
    except Exception as e:
        logger.error(f"Error in revoke_premium_command: {e}")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to users."""
    try:
        await update.message.reply_text("📢 Broadcast functionality coming soon!")
    except Exception as e:
        logger.error(f"Error in broadcast_message: {e}")

async def force_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force upgrade user."""
    try:
        await update.message.reply_text("⚡ Force upgrade functionality coming soon!")
    except Exception as e:
        logger.error(f"Error in force_upgrade_command: {e}")

def register_admin_handlers(app):
    app.add_handler(CommandHandler("adminstats", admin_stats))