import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, save_payment_request
from config import WEEKLY_PREMIUM_PRICE, MONTHLY_PREMIUM_PRICE, PAYMENT_ACCOUNT, PAYMENT_BANK, PAYMENT_NAME
import os
from datetime import datetime

logger = logging.getLogger(__name__)

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /upgrade command."""
    try:
        user_id = update.effective_user.id

        keyboard = [
            [InlineKeyboardButton("🔓 Daily Plan - ₦3,500", callback_data="pay_daily")],
            [InlineKeyboardButton("📅 3-Month Plan - ₦9,000", callback_data="pay_3month")],
            [InlineKeyboardButton("💎 Lifetime Plan - ₦25,000", callback_data="pay_lifetime")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "💼 **Upgrade to DocuLuna Premium**\n\n"
            "Unlock unlimited document processing with premium features:\n\n"
            "✅ Unlimited file conversions\n"
            "✅ No watermarks\n"
            "✅ Faster processing\n"
            "✅ Priority support\n"
            "✅ Larger file support\n"
            "✅ Advanced tools access\n\n"
            "💰 **Choose Your Plan:**\n\n"
            "🔓 **Daily Plan** – ₦3,500\n"
            "Valid for 24 hours\n\n"
            "📅 **3-Month Plan** – ₦9,000\n"
            "Valid for 90 days\n\n"
            "💎 **Lifetime Plan** – ₦25,000\n"
            "Permanent access, all features unlocked forever\n\n"
            "Select a plan below to continue:"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Upgrade options shown to user {user_id}")

    except Exception as e:
        logger.error(f"Error in upgrade command for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def handle_payment_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment screenshot submission."""
    try:
        user_id = update.effective_user.id
        caption = update.message.caption.lower() if update.message.caption else ""

        # Determine plan type from caption
        plan_type = None
        amount = 0

        if "daily" in caption:
            plan_type = "daily"
            amount = 3500
        elif "3month" in caption or "3-month" in caption:
            plan_type = "3month"
            amount = 9000
        elif "lifetime" in caption:
            plan_type = "lifetime"
            amount = 25000
        else:
            await update.message.reply_text(
                "❌ Please send screenshot with caption 'daily', '3month', or 'lifetime'"
            )
            return

        # Download and save screenshot
        photo = update.message.photo[-1]  # Get highest resolution
        file = await context.bot.get_file(photo.file_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"payment_{user_id}_{timestamp}.jpg"
        filepath = os.path.join("payments", filename)

        await file.download_to_drive(filepath)

        # Save payment request to database
        save_payment_request(user_id, amount, plan_type, filepath)

        await update.message.reply_text(
            f"✅ **Payment Submitted!**\n\n"
            f"Plan: {plan_type.title()}\n"
            f"Amount: ₦{amount}\n\n"
            f"⏳ Your payment is being reviewed.\n"
            f"You'll be notified once approved (usually within 24 hours).\n\n"
            f"📧 Contact support if you have questions."
        )

        logger.info(f"Payment screenshot submitted by user {user_id}: {plan_type}")

    except Exception as e:
        logger.error(f"Error handling payment submission from user {user_id}: {e}")
        await update.message.reply_text("❌ Error processing payment. Please try again.")