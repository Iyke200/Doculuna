import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, add_user, get_user_by_username
from config import FREE_USAGE_LIMIT, REFERRAL_BONUS

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name

        # Check for referral code
        referrer_id = None
        if context.args:
            referral_code = context.args[0]
            if referral_code.startswith("ref_"):
                referrer_id = int(referral_code.replace("ref_", ""))
            else:
                # Username-based referral
                referrer = get_user_by_username(referral_code)
                if referrer:
                    referrer_id = referrer['user_id']

        # Check if user exists
        existing_user = get_user(user_id)

        if not existing_user:
            # New user
            add_user(user_id, username, first_name, last_name, referrer_id)

        keyboard = [
            [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
            [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "👋 Welcome to **DocuLuna** — your smart document assistant right here on Telegram!\n\n"
            "Need to convert, merge, split, or transform files like Word, PDF, or images? You're in the right place.\n\n"
            "🚀 **What You Can Do:**\n"
            "• Word ➡️ PDF\n"
            "• PDF ➡️ Word\n"
            "• Merge multiple PDFs\n"
            "• Split PDF pages\n"
            "• Image ➡️ PDF\n\n"
            "🎁 You're currently on the **Free Plan** — enjoy up to 3 tools per day!\n\n"
            "🔓 Want unlimited access + faster speed + watermark-free downloads?\n"
            "👉 Upgrade to **DocuLuna Pro** starting from just ₦1,000/week.\n\n"
            "🔗 Use the buttons below to get started:"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Start command processed for user {user_id}")

    except Exception as e:
        logger.error(f"Error in start command for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")