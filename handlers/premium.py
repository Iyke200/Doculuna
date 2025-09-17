# handlers/premium.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def premium_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium status and options."""
    await show_premium_options(update, context)

async def show_premium_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = (
            "💎 **DocuLuna Pro – Elevate Your Docs!**\n\n"
            "Unlock watermark-free PDFs, 50 MB file support, and unlimited conversions for WAEC, NYSC, or business needs!\n\n"
            "📅 **Monthly**: 3,500 NGN – Unlimited access\n"
            "📆 **Weekly**: 1,000 NGN – Perfect for quick tasks\n"
            "📈 **Mid-Tier**: 2,000 NGN – 20 uses/day, no watermarks"
        )
        keyboard = [
            [InlineKeyboardButton("📅 Monthly (3,500 NGN)", callback_data="initiate_payment_monthly")],
            [InlineKeyboardButton("📆 Weekly (1,000 NGN)", callback_data="initiate_payment_weekly")],
            [InlineKeyboardButton("📈 Mid-Tier (2,000 NGN)", callback_data="initiate_payment_midtier")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        for attempt in range(3):
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(
                        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                    )
                    await update.callback_query.answer()
                else:
                    await update.message.reply_text(
                        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                    )
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in show_premium_options: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in show_premium_options: {e}")
        error_message = "❌ Error showing Pro plans. Try again."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)