import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import add_user, get_user

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    try:
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username

        # Add user to database
        add_user(user_id, first_name, username)

        # Check if user exists
        existing_user = get_user(user_id)

        keyboard = [
            [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
            [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if existing_user:
            # Returning user
            message = f"👋 Welcome back, {first_name}! Use /help to explore features or upload a document to begin."
        else:
            # New user
            message = (
                f"👋 Hello {first_name}!\n"
                f"Welcome to **DocuLuna** – your AI-powered document toolkit on Telegram.\n\n"
                f"Get started by sending a document or use /help to explore commands.\n"
                f"Need premium tools? Use /upgrade to unlock full access."
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