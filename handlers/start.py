# start.py - Updated with new UX flow
import logging
from datetime import datetime, date
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, create_user, update_user_data, track_referral, create_referral_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /start command with new UX flow."""
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"
    username = message.from_user.username
    
    command_args = message.text.split()
    referral_code = command_args[1] if len(command_args) > 1 else None
    
    try:
        user_data = await get_user_data(user_id)
        is_new_user = not user_data
        
        if is_new_user:
            await create_user({
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'created_at': datetime.utcnow().isoformat(),
                'usage_today': 0,
                'plan': 'free',
                'last_used_date': date.today().isoformat()
            })
            
            await create_referral_code(user_id)
            
            if referral_code and referral_code.startswith("DOCU"):
                try:
                    referrer_id = int(referral_code.replace("DOCU", ""))
                    if referrer_id != user_id:
                        success = await track_referral(referrer_id, user_id)
                        if success:
                            logger.info(f"Tracked referral: {referrer_id} -> {user_id}")
                except Exception as e:
                    logger.error(f"Error tracking referral: {e}")
            
            welcome_text = (
                f"👋 Hello {first_name}!\n\n"
                "Welcome to DocuLuna Bot 🌙 — your intelligent digital assistant for all document tasks.\n\n"
                "✨ With me, you can easily:\n"
                "• 📄 Convert between PDF ↔️ Word\n"
                "• 🖼️ Turn Images into PDF\n"
                "• 📊 Merge or Split PDF files\n"
                "• 🗜️ Compress large documents quickly\n\n"
                "🎁 You currently have 3 free uses per day.\n"
                "Upgrade to Premium for unlimited access, faster speed, and earn up to ₦500 with our referral system!\n\n"
                "Choose an option below 👇"
            )
            
        else:
            last_used = user_data.get('last_used_date', date.today().isoformat())
            today_str = date.today().isoformat()
            
            if last_used < today_str:
                await update_user_data(user_id, {
                    'usage_today': 0,
                    'last_used_date': today_str
                })
                
                welcome_text = (
                    f"👋 Welcome back, {first_name}!\n\n"
                    "Your daily free limit has been refreshed 🌙\n"
                    "Let's get your documents ready again."
                )
            else:
                welcome_text = (
                    f"👋 Hello {first_name}!\n\n"
                    "Welcome to DocuLuna Bot 🌙 — your intelligent digital assistant for all document tasks.\n\n"
                    "✨ With me, you can easily:\n"
                    "• 📄 Convert between PDF ↔️ Word\n"
                    "• 🖼️ Turn Images into PDF\n"
                    "• 📊 Merge or Split PDF files\n"
                    "• 🗜️ Compress large documents quickly\n\n"
                    "🎁 You currently have 3 free uses per day.\n"
                    "Upgrade to Premium for unlimited access, faster speed, and earn up to ₦500 with our referral system!\n\n"
                    "Choose an option below 👇"
                )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📂 Process Document", callback_data="process_document")
        builder.button(text="💎 Go Premium", callback_data="go_premium")
        builder.button(text="🏦 Wallet", callback_data="wallet")
        builder.button(text="👤 My Account", callback_data="my_account")
        builder.button(text="❓ Help", callback_data="help")
        builder.adjust(2, 2, 1)
        
        await message.reply(welcome_text, reply_markup=builder.as_markup())
        
        logger.info(f"Start command - user_id={user_id}, is_new={is_new_user}")
        
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await message.reply("❌ An error occurred. Please try again.")

async def process_referral(start_param: str, user_id: int):
    """Process referral code from start parameter."""
    if start_param and start_param.startswith('ref_'):
        referrer_id = start_param.replace('ref_', '')
        try:
            from handlers.referrals import record_referral_use
            await record_referral_use(int(referrer_id), user_id)
        except Exception as e:
            logger.error(f"Referral processing error: {e}")

async def get_user_preferences(user_id: int) -> dict:
    """Get user preferences and settings."""
    try:
        user_data = await get_user_data(user_id)
        if user_data:
            return {
                'language': user_data.get('language', 'en'),
                'notifications': user_data.get('notifications', True),
                'theme': user_data.get('theme', 'default')
            }
        return {'language': 'en', 'notifications': True, 'theme': 'default'}
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        return {'language': 'en', 'notifications': True, 'theme': 'default'}

def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command handlers."""
    dp.message.register(start_command_handler, Command("start"))
