# tools/file_processor.py - Professional File Processing Engine
import logging
import os
import shutil
import asyncio
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineKeyboardBuilder
from config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
from database.db import get_user_by_id, get_usage_count

logger = logging.getLogger(__name__)

async def process_file(message: types.Message):
    """🚀 DocuLuna's Professional File Processing Engine - Beat Google's Tools!"""
    try:
        # Enterprise-grade storage check
        stat = shutil.disk_usage("data")
        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
            logger.error("Low storage, cannot process file")
            await message.reply("⚠️ Server optimizing storage. Please retry in 30 seconds.")
            return

        user_id = message.from_user.id
        user = get_user_by_id(user_id)
        if not user:
            await message.reply("🔐 Please register with /start to access DocuLuna's professional tools.")
            return

        is_premium = user[2] if len(user) > 2 else False
        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
        
        # Smart file detection (document or photo)
        document = update.message.document or (update.message.photo[-1] if update.message.photo else None)
        if not document:
            await update.message.reply_text(
                "📎 **Upload Your Document**\n\n"
                "✅ Supported: PDF, Word, Images\n"
                "⚡ Instant processing with professional quality\n"
                "🎯 Better than Google's tools - Try it!"
            )
            return

        # File size validation with professional messaging
        file_size = document.file_size if hasattr(document, "file_size") else 0
        if file_size > max_file_size:
            size_limit = max_file_size / 1024 / 1024
            await update.message.reply_text(
                f"📊 **File Size: {file_size / 1024 / 1024:.1f}MB**\n\n"
                f"💼 Your limit: {size_limit:.0f}MB\n"
                f"🚀 Upgrade to Pro for {MAX_FILE_SIZE_PREMIUM / 1024 / 1024:.0f}MB files!\n\n"
                "⭐ Pro users get unlimited processing power!"
            )
            return

        # Usage limit check with upgrade incentive
        if not is_premium and get_usage_count(user_id) >= 5:
            await update.message.reply_text(
                "🎯 **Daily Limit Reached (5/5)**\n\n"
                "🔥 You've experienced DocuLuna's power!\n"
                "⚡ Upgrade to Pro for unlimited processing\n"
                "💎 Better quality than Google Docs\n\n"
                "Use /premium to unlock unlimited access!"
            )
            return

        # File extension validation
        file_ext = os.path.splitext(document.file_name)[1].lower() if hasattr(document, "file_name") else ".jpg"
        if file_ext not in ALLOWED_EXTENSIONS:
            await update.message.reply_text(
                f"❌ **Unsupported Format: {file_ext}**\n\n"
                f"✅ **Supported:** {', '.join(ALLOWED_EXTENSIONS)}\n"
                "🔥 More formats than Google's tools!"
            )
            return

        # Store file for processing
        context.user_data["last_file"] = document
        context.user_data["file_obj"] = document
        await show_professional_tools_menu(update, context)

    except RetryAfter as e:
        logger.warning(f"Rate limit hit in process_file: {e}")
        await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in process_file: {e}")
        await update.message.reply_text("⚠️ Processing error. Our engineers are on it! Try again.")

async def show_professional_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎯 Professional Tools Menu - Superior to Google's Document Tools"""
    try:
        keyboard = [
            [InlineKeyboardButton("📝 PDF → Word (AI Enhanced)", callback_data="tool_pdf_to_word")],
            [InlineKeyboardButton("📄 Word → PDF (Professional)", callback_data="tool_word_to_pdf")],
            [InlineKeyboardButton("🖼️ Image → PDF (OCR Ready)", callback_data="tool_image_to_pdf")],
            [InlineKeyboardButton("✂️ Split PDF (Precise)", callback_data="tool_split_pdf")],
            [InlineKeyboardButton("🔗 Merge PDF (Smart)", callback_data="tool_merge_pdf")],
            [InlineKeyboardButton("⚡ Compress (Advanced)", callback_data="tool_compress_pdf")],
            [InlineKeyboardButton("🎯 CV Templates (Pro)", callback_data="tool_cv_template")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        message = (
            "🚀 **DocuLuna Professional Tools**\n\n"
            "⚡ **Faster than Google Docs**\n"
            "🎯 **Better quality than Adobe**\n"
            "💎 **More features than competitors**\n\n"
            "Choose your transformation:"
        )
        
        for attempt in range(3):
            try:
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        message,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
                    await update.callback_query.answer()
                else:
                    await update.message.reply_text(
                        message,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in show_professional_tools_menu: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in show_professional_tools_menu: {e}")
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text("⚠️ Menu loading error. Try again.")
            else:
                await update.message.reply_text("⚠️ Menu loading error. Try again.")
        except:
            pass