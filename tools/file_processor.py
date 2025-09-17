‎# tools/file_processor.py
‎import logging
‎import os
‎import shutil
‎from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎from config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
‎from database.db import get_user_by_id, get_usage_count
‎
‎logger = logging.getLogger(__name__)
‎
‎async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        stat = shutil.disk_usage("data")
‎        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
‎            logger.error("Low storage, cannot process file")
‎            await update.message.reply_text("❌ Server storage full. Try again later.")
‎            return
‎        user_id = update.effective_user.id
‎        user = get_user_by_id(user_id)
‎        if not user:
‎            await update.message.reply_text("❌ Register with /start first.")
‎            return
‎        is_premium = user[2]
‎        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
‎        document = update.message.document or update.message.photo[-1] if update.message.photo else None
‎        if not document:
‎            await update.message.reply_text("❌ Upload a valid PDF, Word, or image file.")
‎            return
‎        file_size = document.file_size if hasattr(document, "file_size") else 0
‎        if file_size > max_file_size:
‎            await update.message.reply_text(f"❌ File too large. Max: {max_file_size / 1024 / 1024} MB. Go Pro for 50 MB files!")
‎            return
‎        if not is_premium and get_usage_count(user_id) >= 5:
‎            await update.message.reply_text("❌ Hit your 5/day free limit. Unlock unlimited with /premium!")
‎            return
‎        file_ext = os.path.splitext(document.file_name)[1].lower() if hasattr(document, "file_name") else ".jpg"
‎        if file_ext not in ALLOWED_EXTENSIONS:
‎            await update.message.reply_text(f"❌ Unsupported file. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
‎            return
‎        context.user_data["last_file"] = document
‎        await show_tools_menu(update, context)
‎    except RetryAfter as e:
‎        logger.warning(f"Rate limit hit in process_file: {e}")
‎        await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in process_file: {e}")
‎        await update.message.reply_text("❌ Error processing file. Try again.")
‎
‎async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        keyboard = [
‎            [InlineKeyboardButton("📝 Word to PDF", callback_data="tool_word_to_pdf")],
‎            [InlineKeyboardButton("📄 PDF to Word", callback_data="tool_pdf_to_word")],
‎            [InlineKeyboardButton("🖼 Image to PDF", callback_data="tool_image_to_pdf")],
‎            [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
‎            [InlineKeyboardButton("🗂 Merge PDF", callback_data="tool_merge_pdf")],
‎            [InlineKeyboardButton("📐 Compress PDF", callback_data="tool_compress_pdf")],
‎            [InlineKeyboardButton("📄 Create CV", callback_data="tool_cv_template")],
‎            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
‎        ]
‎        for attempt in range(3):
‎            try:
‎                await update.callback_query.edit_message_text(
‎                    "🛠 **Choose a Tool to Transform Your WAEC or NYSC Docs!**",
‎                    reply_markup=InlineKeyboardMarkup(keyboard),
‎                    parse_mode="Markdown"
‎                )
‎                await update.callback_query.answer()
‎                break
‎            except RetryAfter as e:
‎                logger.warning(f"Rate limit hit in show_tools_menu: {e}")
‎                await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in show_tools_menu: {e}")
‎        await update.callback_query.edit_message_text("❌ Error showing tools. Try again.")
‎
