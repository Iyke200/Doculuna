# handlers/start.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from database.db import add_user

logger = logging.getLogger(__name__)

# Welcome message
WELCOME_MESSAGE = """
🌟 *Welcome to DocuLuna Bot!* 🌟

Your all-in-one document processing assistant. I can help you with:

📄 PDF to Word conversion
📝 Word to PDF conversion  
🖼️ Image to PDF conversion
📊 PDF merging and splitting
🗜️ File compression

Click the button below to get started!
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        add_user(user_id, username)
        keyboard = [[InlineKeyboardButton("🛠 Start Converting", callback_data="tools_menu")]]
        for attempt in range(3):
            try:
                await update.message.reply_text(
                    WELCOME_MESSAGE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                )
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in start: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("❌ Error starting bot. Try again.")