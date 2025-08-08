
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from tools.pdf_to_word import handle_pdf_to_word
from tools.word_to_pdf import handle_word_to_pdf
from tools.image_to_pdf import handle_image_to_pdf
from tools.split import handle_split_pdf
from tools.merge import handle_merge_pdf
from tools.compress import handle_compress_pdf
from tools.file_processor import show_tools_menu

logger = logging.getLogger(__name__)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu - temporary placeholder"""
    try:
        from handlers.start import show_main_menu as start_main_menu
        await start_main_menu(update, context)
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        await update.callback_query.edit_message_text("❌ Error loading main menu.")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries with enhanced routing."""
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        # Main menu options
        if callback_data == "main_menu":
            from handlers.start import show_main_menu
            await show_main_menu(update, context)
        elif callback_data == "tools_menu":
            await show_tools_menu(update, context)
        elif callback_data == "upgrade_menu":
            from handlers.upgrade import upgrade
            await upgrade(update, context)
        elif callback_data == "help_menu":
            from handlers.help import help_command
            await help_command(update, context)
        
        # User dashboard and profile
        elif callback_data == "user_dashboard":
            from handlers.start import show_user_dashboard
            await show_user_dashboard(update, context)
        elif callback_data == "quick_start_guide":
            from handlers.start import show_quick_start_guide
            await show_quick_start_guide(update, context)
        elif callback_data == "referral_menu":
            from handlers.referrals import referrals
            await referrals(update, context)
        elif callback_data == "user_stats":
            from handlers.stats import stats_command
            await stats_command(update, context)
        
        # Admin features
        elif callback_data == "admin_panel":
            from handlers.admin import admin_panel
            await admin_panel(update, context)
        elif callback_data == "show_analytics":
            from admin.dashboard import admin_dashboard
            await admin_dashboard.show_advanced_analytics(update, context)
        elif callback_data == "refresh_dashboard":
            from admin.dashboard import show_admin_dashboard
            await show_admin_dashboard(update, context)
        
        # Tool categories
        elif callback_data == "menu_pdf_tools":
            await show_pdf_tools_menu(update, context)
        elif callback_data == "menu_word_tools":
            await show_word_tools_menu(update, context)
        elif callback_data == "menu_image_tools":
            await show_image_tools_menu(update, context)
        
        # Tool actions
        elif callback_data == "tool_pdf_to_word":
            if 'last_file' in context.user_data:
                # Process the stored file
                context.user_data['document'] = context.user_data['last_file']
                await handle_pdf_to_word(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif callback_data == "tool_word_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_word_to_pdf(update, context)
            else:
                await query.edit_message_text("📝 Please upload a Word file first.")
        elif callback_data == "tool_image_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['photo'] = context.user_data['last_file']
                await handle_image_to_pdf(update, context)
            else:
                await query.edit_message_text("🖼 Please upload an image first.")
        elif callback_data == "tool_split_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_split_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif callback_data == "tool_merge_pdf":
            await handle_merge_pdf(update, context)
        elif callback_data == "tool_compress_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
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
        parse_mode='Markdown'.")
        elif callback_data == "tool_word_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_word_to_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a Word file first.")
        elif callback_data == "tool_image_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_image_to_pdf(update, context)
            else:
                await query.edit_message_text("📷 Please upload an image file first.")
        elif callback_data == "tool_split_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_split_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        elif callback_data == "tool_merge_pdf":
            await handle_merge_pdf(update, context)
        elif callback_data == "tool_compress_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_compress_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        
        # Referral callbacks
        elif callback_data.startswith("copy_referral_"):
            from handlers.referrals import handle_referral_callbacks
            await handle_referral_callbacks(update, context, callback_data)
        
        # Premium callbacks
        elif callback_data == "upgrade_pro":
            from handlers.upgrade import upgrade
            await upgrade(update, context)
        
        # Admin callbacks
        elif callback_data.startswith("admin_"):
            from handlers.admin import handle_admin_callbacks
            await handle_admin_callbacks(update, context, callback_data)
            
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        try:
            await query.edit_message_text("❌ An error occurred. Please try again later.")
        except:
            pass

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    keyboard = [
        [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
        [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
        [InlineKeyboardButton("👥 Referrals", callback_data="referrals_menu")],
        [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.callback_query.edit_message_text(
            "🏠 **Main Menu**\n\nChoose an option:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")

async def show_pdf_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF tools menu."""
    keyboard = [
        [InlineKeyboardButton("📝 Convert to Word", callback_data="tool_pdf_to_word")],
        [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
        [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
        [InlineKeyboardButton("🗜 Compress PDF", callback_data="tool_compress_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.callback_query.edit_message_text(
            "📄 **PDF Tools**\n\nSelect a tool:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing PDF tools menu: {e}")

async def show_word_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Word tools menu."""
    keyboard = [
        [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_word_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.callback_query.edit_message_text(
            "📝 **Word Tools**\n\nSelect a tool:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing Word tools menu: {e}")

async def show_image_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Image tools menu."""
    keyboard = [
        [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_image_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.callback_query.edit_message_text(
            "📷 **Image Tools**\n\nSelect a tool:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error showing Image tools menu: {e}").")
        
        elif callback_data == "tool_word_to_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_word_to_pdf(update, context)
            else:
                await query.edit_message_text("📝 Please upload a Word document first.")
        
        elif callback_data == "tool_image_to_pdf":
            if 'last_file' in context.user_data or 'last_photo' in context.user_data:
                await handle_image_to_pdf(update, context)
            else:
                await query.edit_message_text("🖼️ Please upload an image first.")
        
        elif callback_data == "tool_split_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_split_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        
        elif callback_data == "tool_compress_pdf":
            if 'last_file' in context.user_data:
                context.user_data['document'] = context.user_data['last_file']
                await handle_compress_pdf(update, context)
            else:
                await query.edit_message_text("📄 Please upload a PDF file first.")
        
        elif callback_data == "tool_merge_pdf":
            await handle_merge_pdf(update, context)
        
        # Payment callbacks
        elif callback_data.startswith("pay_"):
            await handle_payment_selection(update, context, callback_data)
        
    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        await query.edit_message_text("❌ An error occurred. Please try again.")

async def show_main_menu(update, context):
    """Show the main menu."""
    keyboard = [
        [InlineKeyboardButton("🛠️ Tools", callback_data="tools_menu")],
        [InlineKeyboardButton("💎 Upgrade", callback_data="upgrade_menu")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🏠 **DocuLuna Main Menu**\n\n"
        "Welcome to your AI-powered document toolkit!\n\n"
        "🛠️ **Tools** - Access all document tools\n"
        "💎 **Upgrade** - Get premium features\n"
        "ℹ️ **Help** - Commands and support\n"
        "📊 **Stats** - View your usage statistics"
    )
    
    await update.callback_query.edit_message_text(
        message, reply_markup=reply_markup, parse_mode='Markdown'
    )

async def show_pdf_tools_menu(update, context):
    """Show PDF tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📝 PDF to Word", callback_data="request_pdf_upload_word")],
        [InlineKeyboardButton("✂️ Split PDF", callback_data="request_pdf_upload_split")],
        [InlineKeyboardButton("🗜️ Compress PDF", callback_data="request_pdf_upload_compress")],
        [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
        [InlineKeyboardButton("⬅️ Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📄 **PDF Tools**\n\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_word_tools_menu(update, context):
    """Show Word tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📄 Word to PDF", callback_data="request_word_upload")],
        [InlineKeyboardButton("⬅️ Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📝 **Word Tools**\n\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_image_tools_menu(update, context):
    """Show Image tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📄 Image to PDF", callback_data="request_image_upload")],
        [InlineKeyboardButton("⬅️ Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "🖼️ **Image Tools**\n\nChoose an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_payment_selection(update, context, callback_data):
    """Handle payment plan selection."""
    plan_map = {
        "pay_daily": ("Daily", 3500, "24 hours"),
        "pay_3month": ("3-Month", 9000, "90 days"),
        "pay_lifetime": ("Lifetime", 25000, "Forever")
    }
    
    plan_type = callback_data.replace("pay_", "")
    if plan_type in ["daily", "3month", "lifetime"]:
        plan_name, amount, duration = plan_map.get(callback_data, ("Unknown", 0, "Unknown"))
        
        keyboard = [
            [InlineKeyboardButton("💳 Proceed to Payment", callback_data=f"payment_{plan_type}")],
            [InlineKeyboardButton("⬅️ Back to Plans", callback_data="upgrade_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"💰 **{plan_name} Plan Selected**\n\n"
            f"💵 **Amount:** ₦{amount:,}\n"
            f"⏰ **Duration:** {duration}\n\n"
            f"**Payment Details:**\n"
            f"🏦 Bank: Moniepoint\n"
            f"🔢 Account: 9057203030\n"
            f"👤 Name: Ebere Nwankwo\n\n"
            f"After payment, send screenshot with caption '{plan_type}'"
        )
        
        await update.callback_query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode='Markdown'
        )
