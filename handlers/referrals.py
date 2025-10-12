# referrals.py - Updated with new UX flow
import logging
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, update_user_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def refer_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /refer command."""
    user_id = message.from_user.id
    bot_username = "DocuLunaBot"
    
    try:
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        referral_text = (
            "🎁 Earn with DocuLuna!\n\n"
            "Share your referral link and earn:\n"
            "💰 ₦500 per Monthly Premium signup\n"
            "💰 ₦150 per Weekly Premium signup\n\n"
            "Invite your friends and get rewarded instantly 🌙\n\n"
            f"Your referral link:\n{referral_link}"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Copy My Referral Link", url=referral_link)
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        builder.adjust(1)
        
        await message.reply(referral_text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Error in refer command: {e}", exc_info=True)
        await message.reply("Error generating referral link")

async def record_referral_use(referrer_id: int, new_user_id: int):
    """Record when a referral is used."""
    try:
        user_data = get_user_data(referrer_id)
        if user_data:
            current_referrals = user_data.get('referral_count', 0)
            update_user_data(referrer_id, {'referral_count': current_referrals + 1})
            logger.info(f"Referral recorded: referrer={referrer_id}, new_user={new_user_id}")
    except Exception as e:
        logger.error(f"Error recording referral: {e}")

def register_referral_handlers(dp: Dispatcher) -> None:
    """Register referral handlers."""
    dp.message.register(refer_command_handler, Command("refer"))

REFERRAL_CONFIG = {
    'reward_referrer_monthly': {'value': 500},
    'reward_referrer_weekly': {'value': 150}
}
