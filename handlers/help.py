import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display help information."""
    try:
        keyboard = [
            [InlineKeyboardButton("🛠️ Tools Guide", callback_data="help_tools")],
            [InlineKeyboardButton("💎 Premium Info", callback_data="help_premium")],
            [InlineKeyboardButton("👥 Referrals Help", callback_data="help_referrals")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="help_contact")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        help_text = (
            "📌 **Available Commands:**\n"
            "/start – Restart the bot\n"
            "/help – Show this help menu\n"
            "/upgrade – View premium plans\n"
            "/stats – View your usage stats\n"
            "/referral – Get your referral link\n"
            "/premium – Check your premium status"
        )

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Error showing help: {e}")
        error_message = "❌ Error loading help information."
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)

async def handle_help_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle help-related callback queries."""
    try:
        query = update.callback_query

        if data == "help_tools":
            await show_tools_help(query)
        elif data == "help_premium":
            await show_premium_help(query)
        elif data == "help_referrals":
            await show_referrals_help(query)
        elif data == "help_contact":
            await show_contact_help(query)
        elif data == "main_menu":
            await help_command(update, context) # Re-call help_command to show the main menu
        elif data == "help_menu": # Handle returning from sub-menus
            await help_command(update, context)


    except Exception as e:
        logger.error(f"Error handling help callback: {e}")
        await query.edit_message_text("❌ Error loading help section.")

async def show_tools_help(query):
    """Show detailed tools help."""
    keyboard = [[InlineKeyboardButton("🏠 Back to Help", callback_data="help_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = (
        "🛠️ **Tools Guide**\n\n"
        "**📝 Word to PDF:**\n"
        "• Supports .docx files\n"
        "• Preserves formatting\n"
        "• Max size: 50MB\n\n"
        "**📄 PDF to Word:**\n"
        "• Converts to editable .docx\n"
        "• Maintains layout\n"
        "• Text extraction included\n\n"
        "**🖼️ Image to PDF:**\n"
        "• Supports JPG, PNG\n"
        "• Multiple images → Single PDF\n"
        "• Auto-resize and optimize\n\n"
        "**🔗 Merge PDFs:**\n"
        "• Combine up to 10 PDFs\n"
        "• Maintains page order\n"
        "• Single output file\n\n"
        "**✂️ Split PDF:**\n"
        "• Extract individual pages\n"
        "• ZIP archive output\n"
        "• Page-by-page breakdown"
    )

    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_premium_help(query):
    """Show premium help information."""
    keyboard = [[InlineKeyboardButton("🏠 Back to Help", callback_data="help_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = (
        "💎 **Premium Information**\n\n"
        "**Free Plan:**\n"
        "• 3 tool uses per day\n"
        "• All tools available\n"
        "• Standard processing speed\n\n"
        "**Premium Plans:**\n"
        "💳 Weekly: ₦1,000\n"
        "💎 Monthly: ₦2,500\n\n"
        "**Premium Benefits:**\n"
        "• ✅ Unlimited tool usage\n"
        "• ✅ Priority processing\n"
        "• ✅ Larger file support\n"
        "• ✅ Advanced features\n"
        "• ✅ No daily limits\n\n"
        "**Payment:**\n"
        "Bank: Moniepoint\n"
        "Account: 9057203030\n"
        "Name: Ebere Nwankwo\n\n"
        "Send payment screenshot to activate!"
    )

    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_referrals_help(query):
    """Show referrals help information."""
    keyboard = [[InlineKeyboardButton("🏠 Back to Help", callback_data="help_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = (
        "👥 **Referrals Program**\n\n"
        "**How it works:**\n"
        "1. Get your unique referral link\n"
        "2. Share with friends and family\n"
        "3. Earn rewards when they join\n\n"
        "**Rewards:**\n"
        "🎁 +1 free use per referral\n"
        "🎁 Bonus uses stack up\n"
        "🎁 No limit on referrals\n\n"
        "**Tracking:**\n"
        "• View total referrals\n"
        "• See bonus uses earned\n"
        "• Real-time updates\n\n"
        "**Tips:**\n"
        "• Share on social media\n"
        "• Send to WhatsApp groups\n"
        "• Include in email signatures\n\n"
        "Start referring and earn more free uses!"
    )

    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_contact_help(query):
    """Show contact support information."""
    keyboard = [[InlineKeyboardButton("🏠 Back to Help", callback_data="help_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    help_text = (
        "📞 **Contact Support**\n\n"
        "**Need Help?**\n"
        "Our support team is here to assist you!\n\n"
        "**Contact Methods:**\n"
        "📧 Email: support@doculuna.com\n"
        "💬 Telegram: @DocuLunaSupport\n"
        "📱 WhatsApp: +234 xxx xxx xxxx\n\n"
        "**Response Times:**\n"
        "• Email: 24-48 hours\n"
        "• Telegram: 2-6 hours\n"
        "• WhatsApp: 1-4 hours\n\n"
        "**Before Contacting:**\n"
        "✅ Check this help section\n"
        "✅ Try restarting the bot\n"
        "✅ Ensure file formats are supported\n\n"
        "**Include in your message:**\n"
        "• Your user ID\n"
        "• Error description\n"
        "• Screenshots if applicable"
    )

    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')