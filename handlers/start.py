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
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if existing_user:
            # Returning user
            welcome_message = f"👋 Welcome back, {first_name}! Use /help to explore features or upload a document to begin."
        else:
            # New user
            welcome_message = (
                f"🌟 **Welcome to DocuLuna, {first_name}!**\n\n"
                "🚀 Your ultimate document processing companion!\n\n"
                "✨ **What I can do:**\n"
                "📄 Convert PDF ↔ Word documents\n"
                "🖼️ Transform images to PDF\n"
                "✂️ Split & merge PDF files\n"
                "🗜️ Compress large documents\n\n"
                "🆓 **Free Plan:** 3 uses per day\n"
                "💎 **Premium:** Unlimited access\n\n"
                "Ready to get started? Choose an option below!"
            )

        await update.message.reply_text(
            welcome_message, reply_markup=reply_markup, parse_mode="Markdown"
        )

        logger.info(f"User {user_id} ({first_name}) started the bot")

    except Exception as e:
        logger.error(f"Error in start command for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Welcome! Something went wrong, but you can still use the bot."
        )
