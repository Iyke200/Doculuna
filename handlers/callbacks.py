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
            await show_tools_menu(update, context)
        elif callback_data == "upgrade_menu" or callback_data == "upgrade_pro":
            from handlers.upgrade import upgrade

            await upgrade(update, context)
        elif callback_data == "help_menu":
            from handlers.help import help_command

            await help_command(update, context)
        elif callback_data == "referrals_menu":
            from handlers.referrals import referrals

            await referrals(update, context)

        # Tool categories
        elif callback_data == "menu_pdf_tools":
            await show_pdf_tools_menu(update, context)
        elif callback_data == "menu_word_tools":
            await show_word_tools_menu(update, context)
        elif callback_data == "menu_image_tools":
            await show_image_tools_menu(update, context)

        # Payment callbacks
        elif callback_data.startswith("pay_"):
            await handle_payment_selection(update, context, callback_data)
        elif callback_data.startswith("payment_"):
            await handle_payment_callback(update, context, callback_data)

        # Admin callbacks
        elif callback_data.startswith("admin_"):
            from handlers.admin import handle_admin_callback

            await handle_admin_callback(update, context, callback_data)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        if update.callback_query:
            await update.callback_query.answer(
                "❌ An error occurred. Please try again.", show_alert=True
            )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
            [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
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
                welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error showing main menu: {e}")


async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show document tools menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("📄 PDF Tools", callback_data="menu_pdf_tools")],
            [InlineKeyboardButton("📝 Word Tools", callback_data="menu_word_tools")],
            [InlineKeyboardButton("🖼️ Image Tools", callback_data="menu_image_tools")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        tools_text = "🛠️ **Document Tools**\n\n" "Choose a category:"

        await update.callback_query.edit_message_text(
            tools_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error showing tools menu: {e}")


async def show_pdf_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF tools submenu."""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    "📄→📝 PDF to Word", callback_data="tool_pdf_to_word"
                )
            ],
            [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
            [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
            [InlineKeyboardButton("🗜️ Compress PDF", callback_data="tool_compress_pdf")],
            [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(
            "📄 **PDF Tools**\n\nSelect a PDF operation:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error showing PDF tools menu: {e}")


async def show_word_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Word tools submenu."""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    "📝→📄 Word to PDF", callback_data="tool_word_to_pdf"
                )
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(
            "📝 **Word Tools**\n\nSelect a Word operation:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error showing Word tools menu: {e}")


async def show_image_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Image tools submenu."""
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🖼️→📄 Image to PDF", callback_data="tool_image_to_pdf"
                )
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(
            "🖼️ **Image Tools**\n\nSelect an image operation:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error showing Image tools menu: {e}")


async def handle_payment_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle payment plan selection."""
    try:
        from handlers.upgrade import handle_payment_selection as upgrade_payment_handler

        await upgrade_payment_handler(update, context, callback_data)
    except Exception as e:
        logger.error(f"Error handling payment selection: {e}")


async def handle_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str
):
    """Handle payment-related callbacks."""
    try:
        from handlers.upgrade import handle_payment_callback as upgrade_payment_callback

        await upgrade_payment_callback(update, context, callback_data)
    except Exception as e:
        logger.error(f"Error handling payment callback: {e}")
