# handlers/premium.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def premium_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium status and options."""
    await show_premium_options(update, context)

async def show_premium_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from config import PREMIUM_PLANS
        weekly_plan = PREMIUM_PLANS["weekly"]
        monthly_plan = PREMIUM_PLANS["monthly"]
        
        message = (
            "💎 **DocuLuna Pro – Compete with the Best!**\n\n"
            "🚀 **Premium Quality. Professional Results.**\n\n"
            f"📆 **{weekly_plan['name']}**: ₦{weekly_plan['price']:,}\n"
            f"   ✨ {weekly_plan['description']}\n"
            f"   ⏰ {weekly_plan['duration_days']} days access\n\n"
            f"📅 **{monthly_plan['name']}**: ₦{monthly_plan['price']:,}\n"
            f"   ✨ {monthly_plan['description']}\n" 
            f"   ⏰ {monthly_plan['duration_days']} days access\n\n"
            "**What You Get:**\n"
            "✅ Unlimited conversions\n"
            "✅ Zero watermarks\n"
            "✅ Lightning-fast processing\n"
            "✅ Large files up to 50MB\n"
            "✅ Priority support"
        )
        keyboard = [
            [InlineKeyboardButton(f"📆 {weekly_plan['name']} - ₦{weekly_plan['price']:,}", callback_data="premium_payment_weekly")],
            [InlineKeyboardButton(f"📅 {monthly_plan['name']} - ₦{monthly_plan['price']:,}", callback_data="premium_payment_monthly")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        for attempt in range(3):
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(
                        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                    )
                    await update.callback_query.answer()
                else:
                    await update.message.reply_text(
                        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                    )
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in show_premium_options: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in show_premium_options: {e}")
        error_message = "❌ Error showing Pro plans. Try again."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)