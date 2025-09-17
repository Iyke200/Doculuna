# handlers/payments.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from database.db import update_user_premium_status, get_user_by_id

logger = logging.getLogger(__name__)

# Default premium days
PREMIUM_DAYS_PER_PAYMENT = 30

async def initiate_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = get_user_by_id(user_id)
        if not user:
            await update.callback_query.edit_message_text("❌ Register with /start first.")
            return
        
        plan = context.user_data.get("selected_plan", update.callback_query.data.split("_")[-1])
        context.user_data["selected_plan"] = plan
        amount = {"monthly": 3500, "weekly": 1000, "midtier": 2000}.get(plan, 3500)
        plan_name = {"monthly": "Monthly", "weekly": "Weekly", "midtier": "Mid-Tier"}.get(plan, "Monthly")
        
        keyboard = [[InlineKeyboardButton("✅ Confirm Mock Payment", callback_data="verify_payment")]]
        for attempt in range(3):
            try:
                await update.callback_query.edit_message_text(
                    f"💸 Confirm {plan_name} plan ({amount} NGN) for watermark-free PDFs and unlimited conversions!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                await update.callback_query.answer()
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in initiate_payment: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Payment error for user {user_id}: {e}")
        await update.callback_query.edit_message_text("❌ Error initiating payment. Try again.")

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        plan = context.user_data.get("selected_plan", "monthly")
        days = {"monthly": PREMIUM_DAYS_PER_PAYMENT, "weekly": 7, "midtier": 30}.get(plan, 30)
        update_user_premium_status(user_id, days)
        
        for attempt in range(3):
            try:
                await update.callback_query.edit_message_text(
                    "✅ **Mock Payment Successful!**\n\nPremium features activated! Enjoy watermark-free conversions.",
                    parse_mode="Markdown"
                )
                await update.callback_query.answer()
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in verify_payment: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Payment verification error for user {user_id}: {e}")
        await update.callback_query.edit_message_text("❌ Payment verification failed. Try again.")