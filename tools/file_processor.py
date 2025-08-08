import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user
from utils.usage_tracker import check_usage_limit

logger = logging.getLogger(__name__)


def get_file_type(file_name):
    """Determine file type based on file extension."""
    if file_name.endswith('.pdf'):
        return 'pdf'
    elif file_name.endswith(('.doc', '.docx')):
        return 'word'
    elif file_name.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
        return 'image'
    else:
        return 'unknown'


async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main tools menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("📄 PDF Tools", callback_data="menu_pdf_tools")],
            [InlineKeyboardButton("📝 Word Tools", callback_data="menu_word_tools")],
            [InlineKeyboardButton("🖼 Image Tools", callback_data="menu_image_tools")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = "🛠️ **DocuLuna Tools**\n\nChoose a category:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error showing tools menu: {e}")


async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded files and show tool options."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("❌ Please start the bot first with /start")
            return

        # Check usage limit
        if not await check_usage_limit(user_id):
            keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ You've reached your daily limit of 3 tool uses.\n\n"
                "Upgrade to **DocuLuna Pro** for unlimited access!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        if update.message.document:
            document = update.message.document
            file_name = document.file_name.lower()

            # Store file in context for later use
            context.user_data['last_file'] = document
            context.user_data['file_type'] = get_file_type(file_name)

            if file_name.endswith('.pdf'):
                await show_pdf_options(update, context)
            elif file_name.endswith(('.doc', '.docx')):
                await show_word_options(update, context)
            else:
                await update.message.reply_text("❌ Unsupported file type. Please upload PDF or Word documents.")

        elif update.message.photo:
            # Handle photo uploads
            context.user_data['last_file'] = update.message.photo[-1]  # Get highest resolution
            context.user_data['file_type'] = 'image'
            await show_image_options(update, context)

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing file. Please try again.")


async def show_pdf_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF processing options."""
    keyboard = [
        [InlineKeyboardButton("📝 Convert to Word", callback_data="tool_pdf_to_word")],
        [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
        [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
        [InlineKeyboardButton("🗜 Compress PDF", callback_data="tool_compress_pdf")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📄 **PDF received!** What would you like to do?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_word_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Word processing options."""
    keyboard = [
        [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_word_to_pdf")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📝 **Word document received!** What would you like to do?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_image_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show image processing options."""
    keyboard = [
        [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_image_to_pdf")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🖼 **Image received!** What would you like to do?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )