import logging
import os
import PyPDF2
from telegram import Update
from telegram.ext import ContextTypes
from utils.usage_tracker import increment_usage
from utils.premium_utils import is_premium

logger = logging.getLogger(__name__)

async def split_pdf(file_path, output_dir=None):
    """Split PDF into individual pages."""
    try:
        if not output_dir:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_dir = f"temp/{base_name}_split"

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Open PDF file
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)

            output_files = []
            for page_num in range(len(reader.pages)):
                writer = PyPDF2.PdfWriter()
                writer.add_page(reader.pages[page_num])

                output_path = os.path.join(output_dir, f"page_{page_num + 1}.pdf")
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)

                output_files.append(output_path)

        logger.info(f"Successfully split {file_path} into {len(output_files)} pages")
        return output_files

    except Exception as e:
        logger.error(f"Error splitting PDF: {e}")
        return None

async def handle_split_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF splitting request."""
    try:
        await update.message.reply_text("🔄 Splitting PDF...")

        # For now, return a placeholder response
        await update.message.reply_text(
            "⚠️ PDF splitting is under maintenance.\n"
            "Please try again later or contact support."
        )

        logger.info(f"PDF splitting requested by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in PDF splitting: {e}")
        await update.message.reply_text("❌ Error splitting file. Please try again.")