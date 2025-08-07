
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user

logger = logging.getLogger(__name__)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded files and show tool options."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        if not user:
            await update.message.reply_text("❌ Please start the bot first with /start")
            return
        
        if update.message.document:
            document = update.message.document
            file_name = document.file_name.lower()
            
            # Store file in context for later use
            context.user_data['last_file'] = document
            context.user_data['file_type'] = get_file_type(file_name)
            
            # Show appropriate tools based on file type
            if file_name.endswith('.pdf'):
                keyboard = [
                    [InlineKeyboardButton("📝 Convert to Word", callback_data="tool_pdf_to_word")],
                    [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
                    [InlineKeyboardButton("🗜️ Compress PDF", callback_data="tool_compress_pdf")],
                    [InlineKeyboardButton("🔗 Merge with Another PDF", callback_data="tool_merge_pdf")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "📄 **PDF file received!**\n\n"
                    "What would you like to do with this PDF?\n"
                    "Choose an option below:",
                    reply_markup=reply_markup
                )
                
            elif file_name.endswith(('.docx', '.doc')):
                keyboard = [
                    [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_word_to_pdf")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "📝 **Word document received!**\n\n"
                    "What would you like to do?",
                    reply_markup=reply_markup
                )
                
            elif file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                keyboard = [
                    [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_image_to_pdf")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🖼️ **Image received!**\n\n"
                    "What would you like to do?",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "❌ **Unsupported file format**\n\n"
                    "Supported formats:\n"
                    "• PDF files (.pdf)\n"
                    "• Word documents (.docx, .doc)\n"
                    "• Images (.jpg, .png, .gif, .bmp)\n\n"
                    "Please send a supported file type."
                )
        
        elif update.message.photo:
            # Handle photos
            context.user_data['last_photo'] = update.message.photo[-1]
            context.user_data['file_type'] = 'image'
            
            keyboard = [
                [InlineKeyboardButton("📄 Convert to PDF", callback_data="tool_image_to_pdf")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🖼️ **Photo received!**\n\n"
                "What would you like to do?",
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing file. Please try again.")

def get_file_type(filename):
    """Determine file type from filename."""
    if filename.endswith('.pdf'):
        return 'pdf'
    elif filename.endswith(('.docx', '.doc')):
        return 'word'
    elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
        return 'image'
    else:
        return 'unknown'

async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main tools menu."""
    keyboard = [
        [InlineKeyboardButton("📄 PDF Tools", callback_data="menu_pdf_tools")],
        [InlineKeyboardButton("📝 Word Tools", callback_data="menu_word_tools")],
        [InlineKeyboardButton("🖼️ Image Tools", callback_data="menu_image_tools")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "🛠️ **DocuLuna Tools**\n\n"
        "Choose a category or upload a file to get started:\n\n"
        "📄 **PDF Tools** - Convert, split, merge, compress\n"
        "📝 **Word Tools** - Convert Word to PDF\n"
        "🖼️ **Image Tools** - Convert images to PDF\n\n"
        "💡 **Tip:** Upload a file to see available options!"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, reply_markup=reply_markup, parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message, reply_markup=reply_markup, parse_mode='Markdown'
        )
