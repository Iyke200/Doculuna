
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.referrals import referrals, handle_referral_callbacks
from handlers.premium import premium_status
from handlers.upgrade import upgrade
from handlers.help import help_command
from config import ADMIN_USER_IDS

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries."""
    try:
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        # Main menu callbacks
        if data == "main_menu":
            await show_main_menu(query, context)
        elif data == "tools_menu":
            await show_tools_menu(query, context)
        elif data == "help_menu":
            await help_command(update, context)
        elif data.startswith("help_"):
            from handlers.help import handle_help_callbacks
            await handle_help_callbacks(update, context, data)
        elif data == "referrals_menu":
            await referrals(update, context)
        elif data == "upgrade_pro":
            await upgrade(update, context)
        elif data == "premium_status":
            await premium_status(update, context)
        
        # Tool callbacks
        elif data == "tool_pdf_to_word":
            await handle_tool_selection(query, context, "pdf_to_word")
        elif data == "tool_word_to_pdf":
            await handle_tool_selection(query, context, "word_to_pdf")
        elif data == "tool_image_to_pdf":
            await handle_tool_selection(query, context, "image_to_pdf")
        elif data == "tool_merge_pdf":
            await handle_tool_selection(query, context, "merge_pdf")
        elif data == "tool_split_pdf":
            await handle_tool_selection(query, context, "split_pdf")
        
        # Payment callbacks
        elif data == "pay_weekly":
            await show_payment_instructions(query, context, "weekly")
        elif data == "pay_monthly":
            await show_payment_instructions(query, context, "monthly")
        
        # Merge callbacks
        elif data.startswith("merge_now_"):
            await handle_merge_callbacks(query, context, data)
        elif data.startswith("merge_cancel_"):
            await handle_merge_callbacks(query, context, data)
        
        # Referral callbacks
        elif data.startswith("copy_referral_"):
            await handle_referral_callbacks(update, context, data)
        
        # Admin callbacks
        elif data == "admin_panel" and user_id in ADMIN_USER_IDS:
            from handlers.admin import admin_panel
            await admin_panel(update, context)
        elif data.startswith("admin_") and user_id in ADMIN_USER_IDS:
            from handlers.admin import handle_admin_callbacks
            await handle_admin_callbacks(update, context, data)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        try:
            await query.edit_message_text("❌ An error occurred. Please try again.")
        except:
            pass

async def show_main_menu(query, context):
    """Show the main menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
            [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🏠 **DocuLuna Main Menu**\n\n"
            "Choose an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")

async def show_tools_menu(query, context):
    """Show the tools menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("📝 Word to PDF", callback_data="tool_word_to_pdf")],
            [InlineKeyboardButton("📄 PDF to Word", callback_data="tool_pdf_to_word")],
            [InlineKeyboardButton("🖼️ Image to PDF", callback_data="tool_image_to_pdf")],
            [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
            [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🛠️ **Document Tools**\n\n"
            "Choose a tool to get started:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing tools menu: {e}")

async def handle_tool_selection(query, context, tool_type):
    """Handle tool selection."""
    try:
        instructions = {
            "pdf_to_word": "📄➡️📝 **PDF to Word**\n\nSend me a PDF file and I'll convert it to an editable Word document.",
            "word_to_pdf": "📝➡️📄 **Word to PDF**\n\nSend me a Word (.docx) file and I'll convert it to PDF format.",
            "image_to_pdf": "🖼️➡️📄 **Image to PDF**\n\nSend me image files (JPG, PNG) and I'll convert them to PDF.",
            "merge_pdf": "🔗 **Merge PDFs**\n\nSend me multiple PDF files and I'll combine them into one document.",
            "split_pdf": "✂️ **Split PDF**\n\nSend me a PDF file and I'll split it into individual pages."
        }
        
        context.user_data['selected_tool'] = tool_type
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            instructions.get(tool_type, "Please send your file."),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error handling tool selection: {e}")

async def show_payment_instructions(query, context, plan_type):
    """Show payment instructions."""
    try:
        amount = 1000 if plan_type == "weekly" else 2500
        
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"💳 **{plan_type.title()} Plan Payment**\n\n"
            f"💰 Amount: ₦{amount:,}\n\n"
            f"📱 **Payment Details:**\n"
            f"Account: 9057203030\n"
            f"Bank: Moniepoint\n"
            f"Name: Ebere Nwankwo\n\n"
            f"📸 **After payment:**\n"
            f"Send screenshot with caption '{plan_type}'"
        )
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing payment instructions: {e}")

async def handle_merge_callbacks(query, context, data):
    """Handle merge-specific callbacks."""
    try:
        if data.startswith("merge_now_"):
            user_id = int(data.split("_")[2])
            if query.from_user.id == user_id:
                from tools.merge import merge_pdfs
                fake_update = type('obj', (object,), {
                    'message': query.message,
                    'effective_user': query.from_user
                })
                await merge_pdfs(fake_update, context, user_id)
        elif data.startswith("merge_cancel_"):
            user_id = int(data.split("_")[2])
            if query.from_user.id == user_id:
                session_key = f"merge_files_{user_id}"
                context.bot_data[session_key] = []
                await query.edit_message_text("❌ Merge cancelled. Send a PDF to start over.")
    except Exception as e:
        logger.error(f"Error handling merge callback: {e}")
