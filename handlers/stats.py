
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, get_referral_stats, get_user_usage_stats

logger = logging.getLogger(__name__)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ Please register with /start first.")
            return

        # Get user stats
        referrals = get_referral_stats(user_id)
        usage_stats = get_user_usage_stats(user_id)
        
        is_premium = user.get('is_premium', 0)
        premium_status = "💎 Premium" if is_premium else "🆓 Free"
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            f"📊 **Your DocuLuna Stats**\n\n"
            f"👤 **Account Status:** {premium_status}\n"
            f"📁 **Documents Processed:** {usage_stats.get('total_documents', 0)}\n"
            f"🛠️ **Tools Used:** {usage_stats.get('tools_used', 0)}\n"
            f"👥 **Referrals Made:** {referrals}\n"
            f"🎁 **Bonus Days Earned:** {referrals} days\n\n"
            f"Keep using DocuLuna and invite friends for more bonuses! 🚀"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Stats displayed for user {user_id}")

    except Exception as e:
        logger.error(f"Error showing stats for user {user_id}: {e}")
        await update.message.reply_text("❌ Error loading statistics. Please try again.")
import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_user, get_all_users
from config import ADMIN_USER_IDS

logger = logging.getLogger(__name__)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user or system stats."""
    try:
        user_id = update.effective_user.id
        
        if user_id in ADMIN_USER_IDS:
            # Admin stats
            users = get_all_users()
            total_users = len(users)
            premium_users = len([u for u in users if u['is_premium']])
            
            message = (
                f"📊 **System Statistics**\n\n"
                f"👥 Total Users: {total_users}\n"
                f"💎 Premium Users: {premium_users}\n"
                f"🆓 Free Users: {total_users - premium_users}\n"
            )
        else:
            # User stats
            user = get_user(user_id)
            if user:
                message = (
                    f"📊 **Your Statistics**\n\n"
                    f"👤 User ID: {user['user_id']}\n"
                    f"💎 Status: {'Premium' if user['is_premium'] else 'Free'}\n"
                    f"📈 Usage Count: {user['usage_count']}\n"
                    f"👥 Referrals: {user['referral_count']}\n"
                )
            else:
                message = "❌ User not found. Please use /start first."
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await update.message.reply_text("❌ An error occurred.")
