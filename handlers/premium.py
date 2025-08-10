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
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user

logger = logging.getLogger(__name__)

async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium information."""
    try:
        keyboard = [
            [InlineKeyboardButton("💳 Upgrade Now", callback_data="premium_upgrade")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "💎 **Premium Information**\n\n"
            "**Free Plan:**\n"
            "• 3 tool uses per day\n"
            "• All tools available\n"
            "• Standard processing speed\n\n"
            "**Premium Plans:**\n"
            "💳 Weekly: ₦1,000\n"
            "💎 Monthly: ₦2,500\n\n"
            "**Premium Benefits:**\n"
            "• ✅ Unlimited tool usage\n"
            "• ✅ Priority processing\n"
            "• ✅ Larger file support\n"
            "• ✅ Advanced features\n"
            "• ✅ No daily limits\n\n"
            "**Payment:**\n"
            "Bank: Moniepoint\n"
            "Account: 9057203030\n"
            "Name: Ebere Nwankwo\n\n"
            "Send payment screenshot to activate!"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing premium info: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def handle_premium_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle premium-related callbacks."""
    try:
        query = update.callback_query
        
        if data == "premium_upgrade":
            await query.edit_message_text(
                "💎 **Upgrade to Premium**\n\n"
                "To upgrade, please send payment to:\n\n"
                "**Bank:** Moniepoint\n"
                "**Account:** 9057203030\n"
                "**Name:** Ebere Nwankwo\n\n"
                "After payment, send the screenshot here for verification!"
            )
            
    except Exception as e:
        logger.error(f"Error handling premium callbacks: {e}")
        await query.answer("❌ Error occurred.", show_alert=True)ng premium callback: {e}")
        await query.edit_message_text("❌ An error occurred.")
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user
from datetime import datetime

logger = logging.getLogger(__name__)

async def premium_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium status information."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ Please register with /start first.")
            return

        keyboard = [
            [InlineKeyboardButton("💎 Upgrade to Premium", callback_data="upgrade_pro")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Check premium status
        is_premium = user[3] if len(user) > 3 else False  # Assuming premium status is at index 3
        
        if is_premium:
            # Check expiry date
            expiry_date = user[4] if len(user) > 4 else None  # Assuming expiry is at index 4
            if expiry_date:
                try:
                    if isinstance(expiry_date, str):
                        expiry_dt = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
                    else:
                        expiry_dt = expiry_date
                    
                    if expiry_dt > datetime.now():
                        days_left = (expiry_dt - datetime.now()).days
                        status_text = (
                            f"💎 **Premium Status: ACTIVE**\n\n"
                            f"✅ You have unlimited access!\n"
                            f"📅 Expires in: {days_left} days\n"
                            f"🗓️ Expiry date: {expiry_dt.strftime('%Y-%m-%d')}\n\n"
                            f"**Premium Benefits:**\n"
                            f"• Unlimited conversions\n"
                            f"• Priority processing\n"
                            f"• Larger file sizes\n"
                            f"• No ads\n"
                        )
                    else:
                        status_text = (
                            f"❌ **Premium Status: EXPIRED**\n\n"
                            f"Your premium subscription has expired.\n"
                            f"Upgrade now to continue enjoying unlimited access!"
                        )
                except Exception:
                    status_text = (
                        f"💎 **Premium Status: ACTIVE**\n\n"
                        f"✅ You have unlimited access!\n"
                        f"**Premium Benefits:**\n"
                        f"• Unlimited conversions\n"
                        f"• Priority processing\n"
                        f"• Larger file sizes\n"
                        f"• No ads\n"
                    )
            else:
                status_text = (
                    f"💎 **Premium Status: ACTIVE**\n\n"
                    f"✅ You have unlimited access!\n"
                    f"**Premium Benefits:**\n"
                    f"• Unlimited conversions\n"
                    f"• Priority processing\n"
                    f"• Larger file sizes\n"
                    f"• No ads\n"
                )
        else:
            status_text = (
                f"🆓 **Premium Status: FREE**\n\n"
                f"You're currently using the free version.\n\n"
                f"**Free Plan Limits:**\n"
                f"• 3 conversions per day\n"
                f"• Standard processing speed\n"
                f"• 10MB file size limit\n\n"
                f"**Upgrade to Premium for:**\n"
                f"• Unlimited conversions\n"
                f"• Priority processing\n"
                f"• 50MB file size limit\n"
                f"• No ads\n"
            )

        await update.message.reply_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Premium status shown to user {user_id}")

    except Exception as e:
        logger.error(f"Error showing premium status for user {user_id}: {e}")
        await update.message.reply_text("❌ Error retrieving premium status.")
