import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, add_usage_log
from utils.usage_tracker import check_usage_limit, increment_usage

logger = logging.getLogger(__name__)


async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads and show tool options."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

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
                "Use /upgrade to get premium.",
                parse_mode="Markdown",
            )
            return

        # Get file info
        if update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name or "document"
            file_size = file_obj.file_size
        elif update.message.photo:
            file_obj = update.message.photo[-1]  # Get highest resolution
            file_name = "image.jpg"
            file_size = file_obj.file_size
        else:
            await update.message.reply_text("❌ Unsupported file type.")
            return

        # Check file size limits
        max_size = (
            100 * 1024 * 1024 if user["is_premium"] else 50 * 1024 * 1024
        )  # 100MB/50MB
        if file_size > max_size:
            limit_mb = 100 if user["is_premium"] else 50
            await update.message.reply_text(
                f"❌ File too large! Maximum size: {limit_mb}MB"
            )
            return

        # Store file info in context for later use
        context.user_data["file_obj"] = file_obj
        context.user_data["file_name"] = file_name
        context.user_data["file_size"] = file_size

        # Show tool selection based on file type
        keyboard = []

        if file_name.lower().endswith(".pdf"):
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton(
                            "📄 PDF to Word", callback_data="tool_pdf_to_word"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✂️ Split PDF", callback_data="tool_split_pdf"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🗜️ Compress PDF", callback_data="tool_compress"
                        )
                    ],
                ]
            )
        elif file_name.lower().endswith((".doc", ".docx")):
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton(
                            "📄 Word to PDF", callback_data="tool_word_to_pdf"
                        )
                    ],
                    [InlineKeyboardButton("🗜️ Compress", callback_data="tool_compress")],
                ]
            )
        elif file_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif")):
            keyboard.extend(
                [
                    [
                        InlineKeyboardButton(
                            "📄 Image to PDF", callback_data="tool_image_to_pdf"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🗜️ Compress Image", callback_data="tool_compress"
                        )
                    ],
                ]
            )
        else:
            keyboard.append(
                [InlineKeyboardButton("🗜️ Compress File", callback_data="tool_compress")]
            )

        # Add merge option (user can upload multiple files)
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔗 Merge with Other Files", callback_data="tool_merge"
                )
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📁 **File received:** {file_name}\n"
            f"📊 **Size:** {file_size / 1024 / 1024:.2f} MB\n\n"
            "🛠️ **Choose a tool:**",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing file. Please try again.")
