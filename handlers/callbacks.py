# handlers/callbacks.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    await callback_handler(update, context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        data = query.data
        
        if data == "main_menu":
            keyboard = [
                [InlineKeyboardButton("🛠 Tools", callback_data="tools_menu")],
                [InlineKeyboardButton("💎 Go Pro", callback_data="premium")],
                [InlineKeyboardButton("👥 Refer & Earn", callback_data="referrals")],
                [InlineKeyboardButton("📊 My Stats", callback_data="stats")]
            ]
            await query.edit_message_text(
                "📄 **DocuLuna Menu**\n\nChoose your action to manage WAEC, NYSC, or business docs!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        elif data == "tools_menu":
            keyboard = [
                [InlineKeyboardButton("📄➡️📝 PDF to Word", callback_data="pdf_to_word")],
                [InlineKeyboardButton("📝➡️📄 Word to PDF", callback_data="word_to_pdf")],
                [InlineKeyboardButton("🖼️➡️📄 Image to PDF", callback_data="image_to_pdf")],
                [InlineKeyboardButton("🔗 Merge PDFs", callback_data="merge_pdf")],
                [InlineKeyboardButton("✂️ Split PDF", callback_data="split_pdf")],
                [InlineKeyboardButton("🗜️ Compress", callback_data="compress")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                "🛠️ **Select a Tool**\n\nChoose the conversion tool you need:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Tool functionality coming soon! Check back later.")
            
        await query.answer()
    except RetryAfter as e:
        logger.warning(f"Rate limit hit in callback_handler: {e}")
        await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in callback_handler: {e}")
        await query.edit_message_text("❌ Error navigating menu. Try again.")