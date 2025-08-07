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

        is_premium = user.get('is_premium', 0)
        daily_uses = user.get('daily_uses', 3)

        if is_premium:
            expiry = user.get('premium_expiry', 'Unknown')
            plan_type = user.get('premium_type', 'Premium')
            status_text = f"💎 **{plan_type.title()} Plan Active**"
            usage_text = "✅ **Unlimited usage**"
            if plan_type == 'lifetime':
                expiry_text = "♾️ **Lifetime Access**"
            else:
                expiry_text = f"📅 Expires: {expiry}"
        else:
            status_text = "🆓 **Free Plan**"
            usage_text = f"📊 Daily uses remaining: {daily_uses}"
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