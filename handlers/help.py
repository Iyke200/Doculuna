# help.py - Updated with new UX flow
import logging
from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def help_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /help command with new UX flow."""
    user_id = message.from_user.id
    
    try:
        help_text = (
            "📖 How to Use DocuLuna\n\n"
            "1️⃣ Send or upload a file (PDF, Word, or Image)\n"
            "2️⃣ Choose what you want to do (convert, merge, split, compress)\n"
            "3️⃣ Wait a few seconds while I process your file ⏳\n"
            "4️⃣ Get your clean, ready-to-use document instantly!\n\n"
            "⚙️ Free Plan: 3 uses per day\n"
            "💎 Premium Plan: Unlimited + Faster + Referral Bonuses\n\n"
            "💬 Need help or have a question?\n"
            "Contact @DocuLunaSupport"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back to Menu", callback_data="back_to_menu")
        
        await message.reply(help_text, reply_markup=builder.as_markup())
        logger.info(f"Help shown - user_id={user_id}")
        
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        await message.reply("Type /start to restart")

def register_help_handlers(dp: Dispatcher) -> None:
    """Register help command handlers."""
    dp.message.register(help_command_handler, Command("help"))
