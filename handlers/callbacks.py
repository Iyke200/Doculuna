
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user
from config import PREMIUM_PLANS, PAYMENT_ACCOUNT, PAYMENT_BANK, PAYMENT_NAME

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
            await handle_payment_proceed(update, context, callback_data)
        
        # Tool actions
        elif callback_data == "tool_pdf_to_word":
            await query.edit_message_text("📄 Please upload a PDF file to convert to Word.")
        elif callback_data == "tool_word_to_pdf":
            await query.edit_message_text("📝 Please upload a Word document to convert to PDF.")
        elif callback_data == "tool_image_to_pdf":
            await query.edit_message_text("🖼️ Please upload an image to convert to PDF.")
        
        # Admin callbacks
        elif callback_data.startswith("admin_"):
            from handlers.admin import handle_admin_callback
            await handle_admin_callback(update, context)

    except Exception as e:
        logger.error(f"Error handling callback query: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ Document Tools", callback_data="tools_menu")],
            [InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")],
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

async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tools menu."""
    keyboard = [
        [InlineKeyboardButton("📄 PDF Tools", callback_data="menu_pdf_tools")],
        [InlineKeyboardButton("📝 Word Tools", callback_data="menu_word_tools")],
        [InlineKeyboardButton("🖼️ Image Tools", callback_data="menu_image_tools")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "🛠️ **Document Tools**\n\nSelect a category:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_pdf_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📄➡️📝 PDF to Word", callback_data="tool_pdf_to_word")],
        [InlineKeyboardButton("📄✂️ Split PDF", callback_data="tool_split_pdf")],
        [InlineKeyboardButton("📄🔗 Merge PDF", callback_data="tool_merge_pdf")],
        [InlineKeyboardButton("📄🗜️ Compress PDF", callback_data="tool_compress_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📄 **PDF Tools**\n\nSelect a tool:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_word_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Word tools submenu."""
    keyboard = [
        [InlineKeyboardButton("📝➡️📄 Word to PDF", callback_data="tool_word_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "📝 **Word Tools**\n\nSelect a tool:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_image_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Image tools submenu."""
    keyboard = [
        [InlineKeyboardButton("🖼️➡️📄 Image to PDF", callback_data="tool_image_to_pdf")],
        [InlineKeyboardButton("🔙 Back", callback_data="tools_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        "🖼️ **Image Tools**\n\nSelect a tool:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_payment_selection(update, context, callback_data):
    """Handle payment plan selection."""
    plan_map = {
        "pay_daily": ("Daily", PREMIUM_PLANS['daily']['price'], "24 hours"),
        "pay_3month": ("3-Month", PREMIUM_PLANS['3month']['price'], "90 days"),
        "pay_lifetime": ("Lifetime", PREMIUM_PLANS['lifetime']['price'], "Forever")
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
            f"🏦 Bank: {PAYMENT_BANK}\n"
            f"🔢 Account: {PAYMENT_ACCOUNT}\n"
            f"👤 Name: {PAYMENT_NAME}\n\n"
            f"Click 'Proceed to Payment' to continue."
        )
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_payment_proceed(update, context, callback_data):
    """Handle payment proceed action."""
    plan_type = callback_data.replace("payment_", "")
    plan_info = PREMIUM_PLANS.get(plan_type, {})
    
    message = (
        f"💳 **Payment Instructions for {plan_info.get('name', 'Unknown')} Plan**\n\n"
        f"💰 **Amount to Pay:** ₦{plan_info.get('price', 0):,}\n\n"
        f"**Transfer Details:**\n"
        f"🏦 **Bank:** {PAYMENT_BANK}\n"
        f"🔢 **Account Number:** {PAYMENT_ACCOUNT}\n"
        f"👤 **Account Name:** {PAYMENT_NAME}\n\n"
        f"**After Payment:**\n"
        f"1. Take a screenshot of your payment confirmation\n"
        f"2. Send the screenshot here with caption '{plan_type}'\n"
        f"3. Wait for admin approval (usually within 24 hours)\n\n"
        f"⚠️ **Important:** Include '{plan_type}' in your screenshot caption!"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Plans", callback_data="upgrade_menu")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
