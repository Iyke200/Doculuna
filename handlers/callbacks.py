
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries."""
    try:
        query = update.callback_query
        await query.answer()
        callback_data = query.data

        # Main menu options
        if callback_data == "main_menu":
            await show_main_menu(update, context)
        elif callback_data == "tools_menu":
            # Lazy import to avoid loading tool modules at startup
            from tools.file_processor import show_tools_menu
            await show_tools_menu(update, context)
        elif callback_data == "upgrade_menu":
            from handlers.upgrade import upgrade
            await upgrade(update, context)
        elif callback_data == "help_menu":
            from handlers.help import help_command
            await help_command(update, context)

        # Tool categories
        elif callback_data == "menu_pdf_tools":
            await show_pdf_tools_menu(update, context)
        elif callback_data == "menu_word_tools":
            await show_word_tools_menu(update, context)
        elif callback_data == "menu_image_tools":
            await show_image_tools_menu(update, context)

        # Tool actions (lazy import heavy handlers)
        elif callback_data == "tool_pdf_to_word":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                from tools.pdf_to_word import handle_pdf_to_word
                await handle_pdf_to_word(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif callback_data == "tool_word_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                from tools.word_to_pdf import handle_word_to_pdf
                await handle_word_to_pdf(update, context)
            else:
                await query.edit_message_text("📝 Please upload a Word file first.")
        elif callback_data == "tool_image_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['photo'] = context.user_data['last_file']
                from tools.image_to_pdf import handle_image_to_pdf
                await handle_image_to_pdf(update, context)
            else:
                await query.edit_message_text("🖼 Please upload an image first.")
        elif callback_data == "tool_split_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                from tools.split import handle_split_pdf
                await handle_split_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif callback_data == "tool_merge_pdf":
            from tools.merge import handle_merge_pdf
            await handle_merge_pdf(update, context)
        elif callback_data == "tool_compress_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                from tools.compress import handle_compress_pdf
                await handle_compress_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")

        # Admin callbacks
        elif callback_data.startswith("admin_"):
            from handlers.admin import handle_admin_callback
            await handle_admin_callback(update, context)

        # Upgrade callbacks
        elif callback_data.startswith("upgrade_"):
            from handlers.upgrade import handle_upgrade_callback
            await handle_upgrade_callback(update, context)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade", callback_data="upgrade_menu")],
            [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            "🌟 **Welcome to DocuLuna!**\n\n"
            "Your all-in-one document processing bot.\n\n"
            "✨ **Features:**\n"
            "• PDF ↔ Word conversion\n"
            "• Image to PDF\n"
            "• PDF splitting & merging\n"
            "• Document compression\n\n"
            "Choose an option below:"
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error showing main menu: {e}")


async def show_pdf_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📄➡️📝 PDF to Word", callback_data="info_pdf_to_word")],
        [InlineKeyboardButton("✂️ Split PDF", callback_data="info_split_pdf")],
        [InlineKeyboardButton("🔗 Merge PDFs", callback_data="info_merge_pdf")],
        [InlineKeyboardButton("🗜 Compress PDF", callback_data="info_compress_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📄 **PDF Tools**\n\nSelect a tool or upload a PDF file to get started:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_word_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Word tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📝➡️📄 Word to PDF", callback_data="info_word_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📝 **Word Tools**\n\nSelect a tool or upload a Word document to get started:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_image_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Image tools submenu."""
    keyboard = [
        [InlineKeyboardButton("🖼➡️📄 Image to PDF", callback_data="info_image_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "🖼 **Image Tools**\n\nSelect a tool or upload an image to get started:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
