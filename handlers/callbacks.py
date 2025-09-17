‎# handlers/callbacks.py
‎import logging
‎from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎
‎logger = logging.getLogger(__name__)
‎
‎async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        query = update.callback_query
‎        data = query.data
‎        if data == "main_menu":
‎            keyboard = [
‎                [InlineKeyboardButton("🛠 Tools", callback_data="tools_menu")],
‎                [InlineKeyboardButton("💎 Go Pro", callback_data="premium")],
‎                [InlineKeyboardButton("👥 Refer & Earn", callback_data="referrals")],
‎                [InlineKeyboardButton("📊 My Stats", callback_data="stats")]
‎            ]
‎            await query.edit_message_text(
‎                "📄 **DocuLuna Menu**\n\nChoose your action to manage WAEC, NYSC, or business docs!",
‎                reply_markup=InlineKeyboardMarkup(keyboard),
‎                parse_mode="Markdown"
‎            )
‎        else:
‎            await query.edit_message_text("❌ Unknown action. Return to menu.")
‎        await query.answer()
‎    except RetryAfter as e:
‎        logger.warning(f"Rate limit hit in callback_handler: {e}")
‎        await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in callback_handler: {e}")
‎        await query.edit_message_text("❌ Error navigating menu. Try again.")
