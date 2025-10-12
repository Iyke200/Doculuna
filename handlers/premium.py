# premium.py - Updated with new UX flow
import logging
from datetime import datetime, timedelta
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, update_user_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEEKLY_PRICE = 1000
MONTHLY_PRICE = 3500

async def premium_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /premium command."""
    try:
        premium_text = (
            "💎 DocuLuna Premium Plans\n\n"
            "Unlock the full power of DocuLuna and enjoy:\n"
            "🚀 Unlimited document processing\n"
            "⚡ Lightning-fast conversions\n"
            "💰 ₦500 referral bonuses\n"
            "🎯 Priority customer support\n\n"
            "💰 Available Plans:\n"
            "• 📅 Weekly Plan — ₦1000\n"
            "• 📆 Monthly Plan — ₦3500\n\n"
            "Select your preferred plan below 👇"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📅 Weekly – ₦1000", callback_data="plan_weekly")
        builder.button(text="📆 Monthly – ₦3500", callback_data="plan_monthly")
        builder.button(text="🎁 Refer & Earn", callback_data="refer_and_earn")
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        builder.adjust(2, 1, 1)
        
        await message.reply(premium_text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Error in premium command: {e}", exc_info=True)
        await message.reply("Error loading premium plans")

async def handle_plan_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle plan selection (weekly/monthly)."""
    user_id = callback.from_user.id
    plan_type = callback.data.replace("plan_", "")
    
    try:
        price = WEEKLY_PRICE if plan_type == "weekly" else MONTHLY_PRICE
        duration = "7 days" if plan_type == "weekly" else "30 days"
        plan_name = "Weekly" if plan_type == "weekly" else "Monthly"
        
        payment_text = (
            f"💳 Premium Purchase - {plan_name} Plan\n\n"
            f"📋 Order Summary:\n"
            f"• Plan: {plan_name}\n"
            f"• Amount: ₦{price}\n"
            f"• Duration: {duration}\n\n"
            "💡 To complete your purchase:\n"
            "1. Make payment to the account below\n"
            "2. Send screenshot of payment confirmation\n\n"
            "📞 Contact @DocuLunaSupport for payment details"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back", callback_data="go_premium")
        
        await callback.message.edit_text(payment_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in plan selection: {e}", exc_info=True)
        await callback.answer("Error", show_alert=True)

def register_premium_handlers(dp: Dispatcher) -> None:
    """Register premium handlers."""
    dp.message.register(premium_command_handler, Command("premium"))
    dp.callback_query.register(handle_plan_selection, lambda c: c.data.startswith("plan_"))
