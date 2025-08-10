
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
            [
                InlineKeyboardButton(
                    "👥 Referral System", callback_data="help_referrals"
                )
            ],
            [InlineKeyboardButton("📞 Contact Support", callback_data="help_contact")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        help_message = (
            "🔧 **DocuLuna Help Center**\n\n"
            "**Available Commands:**\n"
            "• /start - Start the bot\n"
            "• /help - Show this help menu\n"
            "• /premium - Check premium status\n"
            "• /upgrade - Upgrade to premium\n"
            "• /referral - Referral information\n\n"
            "**How to use:**\n"
            "1️⃣ Send any document or image\n"
            "2️⃣ Choose your processing option\n"
            "3️⃣ Download your converted file\n\n"
            "**Supported formats:**\n"
            "📄 PDF, Word (DOC/DOCX)\n"
            "🖼️ JPG, PNG, GIF\n\n"
            "Choose an option below for detailed help:"
        )

        await update.message.reply_text(
            help_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Help command used by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("❌ Error displaying help. Please try again.")
