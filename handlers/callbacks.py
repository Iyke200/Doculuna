# callbacks.py - Updated with new UX flow
import logging
from datetime import datetime, date
from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, update_user_data
from tools.pdf_to_word import register_pdf_to_word, handle_pdf_to_word_callback
from tools.word_to_pdf import register_word_to_pdf, handle_word_to_pdf_callback
from tools.merge import register_merge_pdf, handle_merge_pdf_callback
from tools.split import register_split_pdf, handle_split_pdf_callback
from tools.compress import register_compress_pdf, handle_compress_pdf_callback
from tools.text_to_pdf import register_text_to_pdf, handle_text_to_pdf_callback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_go_premium(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Go Premium' button."""
    user_id = callback.from_user.id
    
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
        
        await callback.message.edit_text(premium_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in go_premium: {e}", exc_info=True)
        await callback.answer("Error loading premium plans", show_alert=True)

async def handle_my_account(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'My Account' button - show gamification profile."""
    user_id = callback.from_user.id
    
    try:
        # Import gamification to show profile
        from handlers.gamification import gamification_engine
        from handlers.profile_handlers import format_profile_message
        from config import FREE_USAGE_LIMIT
        
        # Ensure user exists
        await gamification_engine.ensure_user(user_id)
        
        # Get gamification profile
        profile_text = await format_profile_message(user_id, callback.from_user.username)
        
        # Add premium/usage info
        user_data = await get_user_data(user_id)
        is_premium = user_data.get('is_premium', False) if user_data else False
        
        if is_premium:
            profile_text += "\n\n💎 <b>Premium Account</b>"
        else:
            usage_today = user_data.get('usage_today', 0) if user_data else 0
            remaining = max(0, FREE_USAGE_LIMIT - usage_today)
            profile_text += f"\n\n📊 Usage: {usage_today}/{FREE_USAGE_LIMIT} (Free)\n{remaining} uses remaining today"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎯 Get Recommendations", callback_data="show_recommendations")
        builder.button(text="💎 Go Premium", callback_data="go_premium")
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        builder.adjust(1, 1, 1)
        
        await callback.message.edit_text(profile_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in my_account: {e}", exc_info=True)
        await callback.answer("Error loading profile", show_alert=True)

async def handle_help(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Help' button."""
    try:
        help_text = """📖 <b>How to Use DocuLuna</b>

<b>The Process:</b>
1️⃣ Send or upload a file (PDF, Word, Image)
2️⃣ Choose what to do (convert, merge, compress)
3️⃣ Wait a few seconds ⏳
4️⃣ Download your result!

<b>Plans:</b>
⚙️ <b>Free:</b> 3 uses/day • Watermarked files
💎 <b>Premium:</b> Unlimited • Watermark-free • Faster • Referral $$$

<b>Supported Formats:</b>
📄 PDF  •  📝 Word  •  🖼️ Images  •  📝 Text

<b>Questions?</b>
💬 Contact @DocuLunaSupport
📧 Check pinned messages for FAQs
"""
        
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        
        await callback.message.edit_text(help_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in help: {e}", exc_info=True)
        await callback.answer("Error loading help", show_alert=True)

async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Back to Menu' button."""
    first_name = callback.from_user.first_name or "there"
    
    try:
        from utils.messages import WELCOME_MSG
        welcome_text = f"👋 Welcome back, {first_name}!\n\n{WELCOME_MSG}"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📂 Process Document", callback_data="process_document")
        builder.button(text="💎 Go Premium", callback_data="go_premium")
        builder.button(text="🏦 Wallet", callback_data="wallet")
        builder.button(text="👤 My Account", callback_data="my_account")
        builder.button(text="❓ Help", callback_data="help")
        builder.adjust(2, 2, 1)
        
        await callback.message.edit_text(welcome_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in back_to_menu: {e}", exc_info=True)
        await callback.answer("Error", show_alert=True)

async def handle_process_document(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Process Document' button."""
    try:
        process_text = (
            "🧰 Choose what you want to do with your document:\n\n"
            "1️⃣ Convert PDF ↔️ Word\n"
            "2️⃣ Merge multiple PDFs\n"
            "3️⃣ Split pages from a PDF\n"
            "4️⃣ Compress PDF file size\n"
            "5️⃣ Convert Text to PDF\n\n"
            "Select an option below 👇"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="📄 PDF ↔️ Word", callback_data="pdf_to_word")
        builder.button(text="🖼️ Image → PDF", callback_data="image_to_pdf")
        builder.button(text="🧩 Merge PDFs", callback_data="merge_pdf")
        builder.button(text="✂️ Split PDF", callback_data="split_pdf")
        builder.button(text="🗜️ Compress PDF", callback_data="compress_pdf")
        builder.button(text="🔤 Text → PDF", callback_data="text_to_pdf")
        builder.button(text="⬅️ Back to Menu", callback_data="back_to_menu")
        builder.adjust(2, 2, 2, 1)

        await callback.message.edit_text(process_text, reply_markup=builder.as_markup())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in process_document: {e}", exc_info=True)
        await callback.answer("Error loading tools", show_alert=True)

async def handle_refer_and_earn(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Refer & Earn' button."""
    user_id = callback.from_user.id
    
    try:
        bot = callback.bot
        bot_info = await bot.get_me()
        bot_username = bot_info.username or "DocuLuna_OfficialBot"
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        referral_text = (
            "🎁 Earn with DocuLuna!\n\n"
            "Share your referral link and earn:\n"
            "💰 ₦500 per Monthly Premium signup\n"
            "💰 ₦150 per Weekly Premium signup\n\n"
            "Invite your friends and get rewarded instantly 🌙"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔗 Copy My Referral Link", url=referral_link)
        builder.button(text="⬅️ Back", callback_data="go_premium")
        builder.adjust(1)
        
        await callback.message.edit_text(referral_text, reply_markup=builder.as_markup())
        await callback.answer(f"Your link: {referral_link}")
        
    except Exception as e:
        logger.error(f"Error in refer_and_earn: {e}", exc_info=True)
        await callback.answer("Error loading referral", show_alert=True)

async def callback_query_router(callback: CallbackQuery, state: FSMContext) -> None:
    """Route callback queries to appropriate handlers."""
    callback_data = callback.data
    
    # Handle show_recommendations callback
    if callback_data == "show_recommendations":
        try:
            from handlers.profile_handlers import cmd_recommend
            # Create a fake message object for the recommend command
            await cmd_recommend(callback.message)
        except Exception as e:
            logger.error(f"Error in show_recommendations: {e}")
            await callback.answer("Error loading recommendations", show_alert=True)
        return
    
    handlers = {
        "go_premium": handle_go_premium,
        "my_account": handle_my_account,
        "help": handle_help,
        "back_to_menu": handle_back_to_menu,
        "process_document": handle_process_document,
        "refer_and_earn": handle_refer_and_earn,
        "pdf_to_word": handle_pdf_to_word_callback,
        "word_to_pdf": handle_word_to_pdf_callback,
        "merge_pdf": handle_merge_pdf_callback,
        "split_pdf": handle_split_pdf_callback,
        "compress_pdf": handle_compress_pdf_callback,
        "text_to_pdf": handle_text_to_pdf_callback,
    }
    
    handler = handlers.get(callback_data)
    if handler:
        await handler(callback, state)
    else:
        await callback.answer("Unknown action", show_alert=True)

def register_callback_handlers(dp: Dispatcher) -> None:
    """Register all callback handlers."""
    dp.callback_query.register(callback_query_router)
