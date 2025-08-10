import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, get_referral_stats

logger = logging.getLogger(__name__)


async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle referrals command with improved UI."""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ Please register with /start first.")
            return

        # Get referral stats
        referral_count = get_referral_stats(user_id)

        # Create referral link using username if available, otherwise user_id
        if username:
            referral_link = f"https://t.me/DocuLunaBot?start={username}"
        else:
            referral_link = f"https://t.me/DocuLunaBot?start=ref_{user_id}"

        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 Copy Link", callback_data=f"copy_referral_{user_id}"
                )
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Calculate stats for the exact message format
        total_invited = referral_count
        successful_activations = referral_count  # Assuming all referrals are successful
        free_weeks_earned = referral_count // 3  # 3 referrals = 1 week

        message = (
            f"🔗 **Your referral link:**\n"
            f"{referral_link}\n\n"
            f"📊 **Your Referral Stats:**\n"
            f"👥 Total Invited: {total_invited}\n"
            f"✅ Active Referrals: {successful_activations}\n"
            f"🎁 Bonus Days Earned: {referral_count}\n\n"
            f"💡 **How it works:**\n"
            f"• Share your link with friends\n"
            f"• When they join and use the bot, you both get 1 day free premium!\n"
            f"• No limit on referrals - keep sharing and earning! 🚀"
        )

        await update.message.reply_text(
            message, reply_markup=reply_markup, parse_mode="Markdown"
        )

        logger.info(f"Referrals info sent to user {user_id}")

    except Exception as e:
        logger.error(f"Error in referrals command for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")


async def handle_referral_callbacks(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
):
    """Handle referral-related callbacks."""
    try:
        query = update.callback_query
        user_id = query.from_user.id

        if data.startswith("copy_referral_"):
            referral_user_id = int(data.split("_")[2])
            if user_id == referral_user_id:
                username = query.from_user.username
                if username:
                    referral_link = f"https://t.me/DocuLunaBot?start={username}"
                else:
                    referral_link = f"https://t.me/DocuLunaBot?start=ref_{user_id}"

                await query.edit_message_text(
                    f"📋 **Copy Your Referral Link:**\n\n"
                    f"`{referral_link}`\n\n"
                    f"Share this link to earn bonus uses! 🎉",
                    parse_mode="Markdown",
                )

    except Exception as e:
        logger.error(f"Error handling referral callback: {e}")
