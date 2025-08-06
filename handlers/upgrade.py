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
            [InlineKeyboardButton("💳 Pay Weekly ₦1,000", callback_data="pay_weekly")],
            [InlineKeyboardButton("💎 Pay Monthly ₦2,500", callback_data="pay_monthly")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "💼 **Upgrade to DocuLuna Pro**\n\n"
            "Tired of daily limits and watermarks? Go Pro and get:\n\n"
            "✅ Unlimited file conversions\n"
            "✅ No watermarks\n"
            "✅ Faster processing\n"
            "✅ Priority access\n"
            "✅ File size up to 25MB\n"
            "✅ Access bonus tools as we add them\n\n"
            "💰 **Pricing Plans:**\n"
            "• Weekly Plan: ₦1,000\n"
            "• Monthly Plan: ₦2,500 (save ₦500)\n\n"
            "🛒 **How to Pay:**\n"
            "1. Send payment to:\n"
            "   *Account Name:* Ebere Nwankwo\n"
            "   *Bank/Wallet:* Moniepoint\n"
            "   *Amount:* ₦1,000 or ₦2,500\n"
            "   *Note:* Add your Telegram username in the transfer note\n\n"
            "2. After payment, send a screenshot or transaction ID to this bot\n\n"
            "⏳ We'll activate your Pro access within minutes!\n\n"
            "🎁 Bonus: Refer 3 people and get 1 week free! Use `/referrals` to invite now."
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

        if "weekly" in caption:
            plan_type = "weekly"
            amount = WEEKLY_PREMIUM_PRICE
        elif "monthly" in caption:
            plan_type = "monthly"
            amount = MONTHLY_PREMIUM_PRICE
        else:
            await update.message.reply_text(
                "❌ Please send screenshot with caption 'weekly' or 'monthly'"
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