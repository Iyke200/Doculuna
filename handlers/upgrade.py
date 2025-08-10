import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, save_payment_request
from config import PREMIUM_PLANS, PAYMENT_METHODS
import os
from datetime import datetime

logger = logging.getLogger(__name__)


async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /upgrade command."""
    try:
        user_id = update.effective_user.id

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔓 Daily Plan - ₦{PREMIUM_PLANS['daily']['price']}",
                    callback_data="pay_daily",
                )
            ],
            [
                InlineKeyboardButton(
                    f"📅 3-Month Plan - ₦{PREMIUM_PLANS['3month']['price']}",
                    callback_data="pay_3month",
                )
            ],
            [
                InlineKeyboardButton(
                    f"💎 Lifetime Plan - ₦{PREMIUM_PLANS['lifetime']['price']}",
                    callback_data="pay_lifetime",
                )
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
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
            f"🔓 **Daily Plan** – ₦{PREMIUM_PLANS['daily']['price']}\n"
            "Valid for 24 hours\n\n"
            f"📅 **3-Month Plan** – ₦{PREMIUM_PLANS['3month']['price']}\n"
            "Valid for 90 days\n\n"
            f"💎 **Lifetime Plan** – ₦{PREMIUM_PLANS['lifetime']['price']}\n"
            "Permanent access, all features unlocked forever\n\n"
            "Select a plan below to continue:"
        )

        await update.message.reply_text(
            message, reply_markup=reply_markup, parse_mode="Markdown"
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
            amount = PREMIUM_PLANS["daily"]["price"]
        elif "3month" in caption or "3-month" in caption:
            plan_type = "3month"
            amount = PREMIUM_PLANS["3month"]["price"]
        elif "lifetime" in caption:
            plan_type = "lifetime"
            amount = PREMIUM_PLANS["lifetime"]["price"]
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
        await update.message.reply_text(
            "❌ Error processing payment. Please try again."
        )


import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import PREMIUM_PLANS, PAYMENT_ACCOUNT, PAYMENT_BANK, PAYMENT_NAME

logger = logging.getLogger(__name__)


async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show upgrade options."""
    try:
        keyboard = [
            [InlineKeyboardButton("💰 Daily Plan - ₦3,500", callback_data="pay_daily")],
            [
                InlineKeyboardButton(
                    "📅 3-Month Plan - ₦9,000", callback_data="pay_3month"
                )
            ],
            [
                InlineKeyboardButton(
                    "♾️ Lifetime Plan - ₦25,000", callback_data="pay_lifetime"
                )
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        upgrade_text = (
            "💎 **Upgrade to Premium**\n\n"
            "Choose your premium plan:\n\n"
            "**🔥 Most Popular: 3-Month Plan**\n"
            "✅ Best value for money\n"
            "✅ 90 days of unlimited access\n\n"
            "**⚡ Quick Access: Daily Plan**\n"
            "✅ Perfect for occasional use\n"
            "✅ 24 hours of unlimited access\n\n"
            "**💯 Best Deal: Lifetime Plan**\n"
            "✅ One-time payment\n"
            "✅ Unlimited access forever\n\n"
            "**All plans include:**\n"
            "• Unlimited conversions\n"
            "• Priority processing\n"
            "• Larger file sizes (50MB)\n"
            "• No advertisements\n"
            "• Premium support\n"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                upgrade_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                upgrade_text, reply_markup=reply_markup, parse_mode="Markdown"
            )

        logger.info(f"Upgrade options shown to user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error showing upgrade options: {e}")


async def handle_payment_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle payment plan selection."""
    try:
        query = update.callback_query
        plan_type = callback_data.replace("pay_", "")

        plan_info = PREMIUM_PLANS.get(plan_type)
        if not plan_info:
            await query.answer("❌ Invalid plan selected.", show_alert=True)
            return

        payment_text = (
            f"💳 **Payment for {plan_info['name']}**\n\n"
            f"💰 Amount: ₦{plan_info['price']:,}\n"
            f"⏱️ Duration: {plan_info['duration_days']} days\n\n"
            f"**Payment Details:**\n"
            f"🏦 Bank: {PAYMENT_BANK}\n"
            f"💳 Account: {PAYMENT_ACCOUNT}\n"
            f"👤 Name: {PAYMENT_NAME}\n\n"
            f"**Instructions:**\n"
            f"1. Transfer ₦{plan_info['price']:,} to the account above\n"
            f"2. Take a screenshot of the payment\n"
            f"3. Send the screenshot to this bot\n"
            f"4. Your premium will be activated within 1 hour\n\n"
            f"⚠️ **Important:** Include your Telegram username in the transfer narration."
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ I've Made Payment", callback_data=f"payment_made_{plan_type}"
                )
            ],
            [InlineKeyboardButton("🔙 Back to Plans", callback_data="upgrade_pro")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            payment_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error handling payment selection: {e}")


async def handle_payment_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment proof submission."""
    try:
        user_id = update.effective_user.id

        # This would handle payment proof images
        await update.message.reply_text(
            "📸 **Payment proof received!**\n\n"
            "✅ Your payment is being verified\n"
            "⏱️ You'll be notified within 1 hour\n"
            "📞 Contact @support if you need assistance\n\n"
            "Thank you for choosing DocuLuna Premium! 🌟"
        )

        logger.info(f"Payment proof submitted by user {user_id}")

    except Exception as e:
        logger.error(f"Error handling payment submission: {e}")


async def handle_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle payment-related callbacks."""
    try:
        query = update.callback_query

        if callback_data.startswith("payment_made_"):
            plan_type = callback_data.replace("payment_made_", "")

            await query.edit_message_text(
                "📸 **Submit Payment Proof**\n\n"
                "Please send a screenshot of your payment receipt.\n"
                "Make sure the amount and timestamp are clearly visible.\n\n"
                "Your premium will be activated once verified! ✨"
            )

    except Exception as e:
        logger.error(f"Error handling payment callback: {e}")
