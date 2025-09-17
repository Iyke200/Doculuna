# handlers/callbacks.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    await callback_handler(update, context)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        data = query.data
        
        if data == "main_menu":
            keyboard = [
                [InlineKeyboardButton("🛠 Tools", callback_data="tools_menu")],
                [InlineKeyboardButton("💎 Go Pro", callback_data="premium")],
                [InlineKeyboardButton("👥 Refer & Earn", callback_data="referrals")],
                [InlineKeyboardButton("📊 My Stats", callback_data="stats")]
            ]
            await query.edit_message_text(
                "📄 **DocuLuna Menu**\n\nChoose your action to manage WAEC, NYSC, or business docs!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        elif data == "tools_menu":
            keyboard = [
                [InlineKeyboardButton("📄➡️📝 PDF to Word", callback_data="tool_pdf_to_word")],
                [InlineKeyboardButton("📝➡️📄 Word to PDF", callback_data="tool_word_to_pdf")], 
                [InlineKeyboardButton("🖼️➡️📄 Image to PDF", callback_data="tool_image_to_pdf")],
                [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge")],
                [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
                [InlineKeyboardButton("🗜️ Compress", callback_data="tool_compress")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                "🛠️ **Select a Tool**\n\nChoose the conversion tool you need:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        elif data == "tool_pdf_to_word":
            from tools.pdf_to_word import handle_pdf_to_word
            await handle_pdf_to_word(update, context)
        elif data == "tool_word_to_pdf":
            from tools.word_to_pdf import handle_word_to_pdf
            await handle_word_to_pdf(update, context)
        elif data == "tool_image_to_pdf":
            from tools.image_to_pdf import handle_image_to_pdf
            await handle_image_to_pdf(update, context)
        elif data in ["tool_split_pdf", "tool_compress", "tool_merge"]:
            await query.edit_message_text("🔧 This tool is coming soon! More features being added.")
        elif data == "premium_payment_weekly":
            from handlers.paystack import initiate_premium_payment
            context.user_data['selected_plan'] = 'weekly'
            await initiate_premium_payment(update, context)
        elif data == "premium_payment_monthly":
            from handlers.paystack import initiate_premium_payment  
            context.user_data['selected_plan'] = 'monthly'
            await initiate_premium_payment(update, context)
        else:
            await query.edit_message_text("❌ Unknown action. Please try again.")
            
        await query.answer()
    except RetryAfter as e:
        logger.warning(f"Rate limit hit in callback_handler: {e}")
        await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in callback_handler: {e}")
        await query.edit_message_text("❌ Error navigating menu. Try again.")