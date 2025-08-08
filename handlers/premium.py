# handlers/premium.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user
from datetime import datetime

logger = logging.getLogger(__name__)

async def premium_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's premium status and usage."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ Please register with /start first.")
            return

        is_premium = user.get('is_premium', False)
        premium_type = user.get('premium_type', None)
        premium_expires = user.get('premium_expires', None)

        if is_premium and premium_type:
            if premium_type == 'lifetime':
                status_text = f"💎 **Lifetime Plan**"
                expiry_text = "♾️ **Permanent access, all features unlocked forever**"
            elif premium_type == 'daily':
                status_text = f"🔓 **Daily Plan**"
                expiry_text = f"📅 **Expires:** {premium_expires}" if premium_expires else "📅 **Valid for 24 hours**"
            elif premium_type == '3month':
                status_text = f"📅 **3-Month Plan**"
                expiry_text = f"📅 **Expires:** {premium_expires}" if premium_expires else "📅 **Valid for 90 days**"
            else:
                status_text = f"💎 **Premium Plan**"
                expiry_text = f"📅 **Expires:** {premium_expires}" if premium_expires else ""
            usage_text = "✅ **Unlimited usage**"
        else:
            status_text = "🆓 **Free Plan**"
            usage_text = f"📊 Daily uses remaining: 3"
            expiry_text = ""

        keyboard = [
            [InlineKeyboardButton("💎 Upgrade to Premium", callback_data="upgrade")],
            [InlineKeyboardButton("👥 Get More Uses (Referrals)", callback_data="referrals")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            f"{status_text}\n\n"
            f"{usage_text}\n"
            f"{expiry_text}\n\n"
            f"🎁 **Get more uses:**\n"
            f"• Invite friends (+1 use per referral)\n"
            f"• Upgrade to Premium (unlimited)"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Premium status sent to user {user_id}")

    except Exception as e:
        logger.error(f"Error in premium status for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")