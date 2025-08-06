
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded files and route to appropriate tool."""
    try:
        user_id = update.effective_user.id
        
        if update.message.document:
            document = update.message.document
            file_name = document.file_name.lower()
            
            if file_name.endswith('.pdf'):
                # Store PDF for later use
                context.user_data['last_pdf'] = document
                await update.message.reply_text(
                    "📄 PDF received! What would you like to do?\n\n"
                    "• Convert to Word\n"
                    "• Split into pages\n"
                    "• Use for merging\n\n"
                    "Use the tools menu to select an option."
                )
            elif file_name.endswith(('.docx', '.doc')):
                from tools.word_to_pdf import handle_word_to_pdf
                await handle_word_to_pdf(update, context)
            elif file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                from tools.image_to_pdf import handle_image_to_pdf
                await handle_image_to_pdf(update, context)
            else:
                await update.message.reply_text(
                    "❌ Unsupported file format. Supported formats:\n"
                    "• PDF files\n"
                    "• Word documents (.docx)\n"
                    "• Images (JPG, PNG, etc.)"
                )
        
        elif update.message.photo:
            from tools.image_to_pdf import handle_image_to_pdf
            await handle_image_to_pdf(update, context)
            
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing file. Please try again.")
