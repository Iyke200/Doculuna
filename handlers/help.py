import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    try:
        help_text = (
            "🤖 **DocuLuna Help**\n\n"
            "📁 **Supported Tools:**\n"
            "• PDF to Word conversion\n"
            "• Word to PDF conversion\n"
            "• Image to PDF conversion\n"
            "• PDF splitting\n"
            "• PDF merging\n"
            "• File compression\n\n"
            "💡 **How to use:**\n"
            "1. Send any document or image\n"
            "2. Choose the tool you want\n"
            "3. Get your processed file\n\n"
            "🆓 **Free users:** 3 conversions per day\n"
            "💎 **Premium users:** Unlimited access\n\n"
            "📝 **Commands:**\n"
            "/start - Start the bot\n"
            "/premium - Check premium status\n"
            "/upgrade - Upgrade to premium\n"
            "/referral - Get referral link\n"
            "/stats - View your statistics\n"
            "/help - Show this help"
        )

        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")