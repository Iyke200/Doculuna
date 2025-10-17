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
    """Handle 'My Account' button."""
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or "User"
    
    try:
        user_data = get_user_data(user_id)
        usage_today = user_data.get('usage_today', 0) if user_data else 0
        is_premium = user_data.get('is_premium', False) if user_data else False
        plan_expiry = user_data.get('premium_expiry', 'N/A') if user_data else 'N/A'
        
        status_text = "Premium" if is_premium else "Free"
        
        account_text = (
            "👤 Your Account Overview\n\n"
            f"🪪 Name: {first_name}\n"
            f"💎 Status: {status_text}\n"
            f"📊 Usage Today: {usage_today}/3 (Free plan limit)\n"
        )
        
        if is_premium and plan_expiry != 'N/A':
            account_text += f"⏳ Plan Expires: {plan_expiry}\n"
        
        account_text += "\nNeed more daily access or faster processing?\nUpgrade to Premium anytime 🚀"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Go Premium", callback_data="go_premium")
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        builder.adjust(1)
        
        await callback.message.edit_text(account_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in my_account: {e}", exc_info=True)
        await callback.answer("Error loading account", show_alert=True)

async def handle_help(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Help' button."""
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
        
        await callback.message.edit_text(help_text, reply_markup=builder.as_markup())
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in help: {e}", exc_info=True)
        await callback.answer("Error loading help", show_alert=True)

async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Back to Menu' button."""
    first_name = callback.from_user.first_name or "there"
    
    try:
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
        builder.button(text="👤 My Account", callback_data="my_account")
        builder.button(text="❓ Help", callback_data="help")
        builder.adjust(2, 2)
        
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
            "4️⃣ Compress PDF file size\n\n"
            "Select an option below 👇"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="📄 PDF ➡️ Word", callback_data="pdf_to_word")
        builder.button(text="📝 Word ➡️ PDF", callback_data="word_to_pdf")
        builder.button(text="🧩 Merge PDFs", callback_data="merge_pdf")
        builder.button(text="✂️ Split PDF", callback_data="split_pdf")
        builder.button(text="🗜️ Compress PDF", callback_data="compress_pdf")
        builder.button(text="⬅️ Back to Menu", callback_data="back_to_menu")
        builder.adjust(2, 2, 1, 1)

        await callback.message.edit_text(process_text, reply_markup=builder.as_markup())
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in process_document: {e}", exc_info=True)
        await callback.answer("Error loading tools", show_alert=True)

async def handle_refer_and_earn(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'Refer & Earn' button."""
    user_id = callback.from_user.id
    bot_username = "DocuLunaBot"
    
    try:
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
    }
    
    handler = handlers.get(callback_data)
    if handler:
        await handler(callback, state)
    else:
        await callback.answer("Unknown action", show_alert=True)

def register_callback_handlers(dp: Dispatcher) -> None:
    """Register all callback handlers."""
    dp.callback_query.register(callback_query_router)
