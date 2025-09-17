# utils/file_processor.py - Production File Processing System
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from database.db import get_user_by_id, add_usage_log
from utils.usage_tracker import check_usage_limit, increment_usage
from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM

logger = logging.getLogger(__name__)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads and show tool options."""
    try:
        user_id = update.effective_user.id
        user = get_user_by_id(user_id)

        if not user:
            await update.message.reply_text("❌ Please register with /start first.")
            return

        # Check usage limits
        can_use = await check_usage_limit(user_id)
        if not can_use:
            await update.message.reply_text(
                "❌ **Daily limit reached!**\n\n"
                "🆓 Free users get 3 conversions per day.\n"
                "💎 Upgrade to Premium for unlimited access!\n\n"
                "Use /premium to get premium.",
                parse_mode="Markdown",
            )
            return

        # Get file info
        if update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name or "document"
            file_size = file_obj.file_size or 0
        elif update.message.photo:
            file_obj = update.message.photo[-1]  # Get highest resolution
            file_name = "image.jpg"
            file_size = file_obj.file_size or 0
        else:
            await update.message.reply_text("❌ Unsupported file type.")
            return

        # Check file size limits
        is_premium = user[2] if len(user) > 2 else False
        max_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
        
        if file_size > max_size:
            limit_mb = max_size / 1024 / 1024
            await update.message.reply_text(
                f"❌ File too large! Maximum size: {limit_mb:.0f}MB\n"
                f"Upgrade to Pro for {MAX_FILE_SIZE_PREMIUM / 1024 / 1024:.0f}MB files!"
            )
            return

        # Store file info in context for tool processing
        context.user_data["file_obj"] = file_obj
        context.user_data["file_name"] = file_name
        context.user_data["file_size"] = file_size

        # Show tool selection based on file type
        keyboard = []
        
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        if file_ext == 'pdf':
            keyboard.extend([
                [InlineKeyboardButton("📄➡️📝 PDF to Word", callback_data="tool_pdf_to_word")],
                [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
                [InlineKeyboardButton("🗜️ Compress PDF", callback_data="tool_compress")]
            ])
        elif file_ext in ['doc', 'docx']:
            keyboard.extend([
                [InlineKeyboardButton("📝➡️📄 Word to PDF", callback_data="tool_word_to_pdf")],
                [InlineKeyboardButton("🗜️ Compress", callback_data="tool_compress")]
            ])
        elif file_ext in ['jpg', 'jpeg', 'png', 'bmp', 'gif']:
            keyboard.extend([
                [InlineKeyboardButton("🖼️➡️📄 Image to PDF", callback_data="tool_image_to_pdf")],
                [InlineKeyboardButton("🗜️ Compress Image", callback_data="tool_compress")]
            ])
        else:
            keyboard.append([InlineKeyboardButton("🗜️ Compress File", callback_data="tool_compress")])

        # Add merge option
        keyboard.append([InlineKeyboardButton("🔗 Merge Files", callback_data="tool_merge")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📁 **File Received:** {file_name}\n"
            f"📊 **Size:** {file_size / 1024 / 1024:.2f} MB\n\n"
            "🛠️ **Choose a conversion tool:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing file. Please try again.")