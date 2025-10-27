# referrals.py - Updated with new UX flow
import logging
from typing import Optional
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, update_user_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFERRAL_CONFIG = {
    'reward_referrer_monthly': {'value': 500},
    'reward_referrer_weekly': {'value': 150}
}

async def refer_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /refer command."""
    user_id = message.from_user.id
    bot_username = "DocuLunaBot"
    
    try:
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        monthly_reward = REFERRAL_CONFIG['reward_referrer_monthly']['value']
        weekly_reward = REFERRAL_CONFIG['reward_referrer_weekly']['value']
        
        referral_text = (
            "🎁 Earn with DocuLuna!\n\n"
            f"Share your referral link and earn:\n"
            f"💰 ₦{monthly_reward} per Monthly Premium signup\n"
            f"💰 ₦{weekly_reward} per Weekly Premium signup\n\n"
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
        await message.reply("Error generating referral link. Please try again later.")

async def record_referral_use(referrer_id: int, new_user_id: int) -> bool:
    """
    Record when a referral is used. Returns True if successfully recorded (new unique referral).
    
    Prevents double-counting by checking if the new user already has a referrer set.
    """
    try:
        # Check if new user already has a referrer
        new_user_data = await get_user_data(new_user_id)
        if new_user_data and new_user_data.get('referrer_id'):
            logger.info(f"Referral ignored (already claimed): referrer={referrer_id}, new_user={new_user_id}")
            return False
        
        # Set referrer for new user if not set
        if new_user_data:
            await update_user_data(new_user_id, {'referrer_id': referrer_id})
        else:
            # If new user doesn't exist yet, create with referrer
            await update_user_data(new_user_id, {'referrer_id': referrer_id})
        
        # Increment referrer's count
        referrer_data = await get_user_data(referrer_id)
        if referrer_data:
            current_referrals = referrer_data.get('referral_count', 0)
            await update_user_data(referrer_id, {'referral_count': current_referrals + 1})
            logger.info(f"Referral recorded: referrer={referrer_id}, new_user={new_user_id}")
            return True
        else:
            logger.warning(f"Referrer data not found: {referrer_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error recording referral: {e}", exc_info=True)
        return False

async def process_premium_conversion_reward(referrer_id: int, plan_type: str) -> bool:
    """
    Process reward for premium conversion via referral. Returns True if successfully processed.
    """
    try:
        config_key = f'reward_referrer_{plan_type}'
        if config_key not in REFERRAL_CONFIG:
            logger.error(f"Invalid plan_type: {plan_type}")
            return False
            
        reward_amount = REFERRAL_CONFIG[config_key]['value']
        user_data = await get_user_data(referrer_id)
        if user_data:
            current_earnings = user_data.get('referral_earnings', 0)
            await update_user_data(referrer_id, {'referral_earnings': current_earnings + reward_amount})
            logger.info(f"Referral reward processed: referrer={referrer_id}, plan={plan_type}, reward={reward_amount}")
            return True
        else:
            logger.warning(f"Referrer data not found for reward: {referrer_id}")
            return False
    except Exception as e:
        logger.error(f"Error processing referral reward: {e}", exc_info=True)
        return False

def register_referral_handlers(dp: Dispatcher) -> None:
    """Register referral handlers."""
    dp.message.register(refer_command_handler, Command("refer"))
