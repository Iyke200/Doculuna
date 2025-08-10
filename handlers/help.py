
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ How to Use Tools", callback_data="help_tools")],
            [InlineKeyboardButton("💎 About Premium", callback_data="help_premium")],
            [InlineKeyboardButton("👥 Referral System", callback_data="help_referrals")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="help_contact")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        help_text = (
            "❓ **DocuLuna Help Center**\n\n"
            "Welcome to DocuLuna! Here's how to get started:\n\n"
            "**📄 Document Conversion:**\n"
            "• Upload any supported file (PDF, DOCX, images)\n"
            "• Choose your conversion option\n"
            "• Download your converted file\n\n"
            "**🆓 Free Usage:**\n"
            "• 3 free conversions per day\n"
            "• Basic features included\n\n"
            "**💎 Premium Benefits:**\n"
            "• Unlimited conversions\n"
            "• No watermarks\n"
            "• Faster processing\n"
            "• Priority support\n\n"
            "**📱 How to Use:**\n"
            "1. Send a document or image\n"
            "2. Select conversion type\n"
            "3. Wait for processing\n"
            "4. Download result\n\n"
            "Need more help? Choose an option below:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")
