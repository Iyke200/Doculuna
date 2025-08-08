import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user
from handlers.start import start
from handlers.premium import premium_status
from handlers.upgrade import upgrade
from handlers.referrals import referrals
from handlers.stats import stats_command
from tools.pdf_to_word import handle_pdf_to_word
from tools.word_to_pdf import handle_word_to_pdf
from tools.image_to_pdf import handle_image_to_pdf
from tools.split import handle_split_pdf
from tools.merge import handle_merge_pdf
from tools.compress import handle_compress_pdf
from tools.file_processor import show_tools_menu

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    try:
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        if data == "main_menu":
            # Show main menu
            keyboard = [
                [InlineKeyboardButton("💎 Premium Status", callback_data="premium_status")],
                [InlineKeyboardButton("🔄 Upgrade", callback_data="upgrade")],
                [InlineKeyboardButton("👥 Referrals", callback_data="referrals")],
                [InlineKeyboardButton("📊 Stats", callback_data="stats")],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "🏠 **Main Menu**\n\nChoose an option:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif data == "tools_menu":
            await show_tools_menu(update, context)

        elif data == "premium_status":
            await premium_status(update, context)

        elif data == "upgrade":
            await upgrade(update, context)

        elif data == "referrals":
            await referrals(update, context)

        elif data == "stats":
            await stats_command(update, context)

        elif data == "help":
            help_text = (
                "🤖 **DocuLuna Help**\n\n"
                "📁 **Supported Tools:**\n"
                "• PDF to Word conversion\n"
                "• Word to PDF conversion\n"
                "• Image to PDF conversion\n"
                "• PDF splitting\n"
                "• PDF merging\n"
                "• File compression\n\n"
                "💡 **How to use:**\n"
                "1. Send any document or image\n"
                "2. Choose the tool you want\n"
                "3. Get your processed file\n\n"
                "🆓 **Free users:** 3 conversions per day\n"
                "💎 **Premium users:** Unlimited access"
            )

            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # Tool actions
        elif data == "tool_pdf_to_word":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_pdf_to_word(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif data == "tool_word_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_word_to_pdf(update, context)
            else:
                await query.edit_message_text("📝 Please upload a Word file first.")
        elif data == "tool_image_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_image_to_pdf(update, context)
            else:
                await query.edit_message_text("🖼 Please upload an image first.")
        elif data == "tool_split_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_split_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif data == "tool_merge_pdf":
            await handle_merge_pdf(update, context)
        elif data == "tool_compress_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_compress_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        
        # Admin callbacks
        elif data.startswith("admin_"):
            from handlers.admin import handle_admin_callback
            await handle_admin_callback(update, context)
        
        # Upgrade callbacks
        elif data.startswith("upgrade_"):
            from handlers.upgrade import handle_upgrade_callback
            await handle_upgrade_callback(update, context)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        try:
            await query.edit_message_text("❌ An error occurred. Please try again.")
        except:
            pass

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    keyboard = [
        [InlineKeyboardButton("🛠️ Tools", callback_data="tools_menu")],
        [InlineKeyboardButton("💎 Upgrade", callback_data="upgrade_menu")],
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