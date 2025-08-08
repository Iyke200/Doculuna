
import logging
import os
import PyPDF2
from telegram import Update
from telegram.ext import ContextTypes
from utils.usage_tracker import increment_usage
from utils.premium_utils import is_premium

logger = logging.getLogger(__name__)

async def merge_pdfs(file_paths, output_path=None):
    """Merge multiple PDF files."""
    try:
        if not output_path:
            output_path = "temp/merged.pdf"
        
        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)
        
        writer = PyPDF2.PdfWriter()
        
        for file_path in file_paths:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    writer.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"Successfully merged {len(file_paths)} files into {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error merging PDFs: {e}")
        return None

async def handle_merge_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF merging request."""
    try:
        await update.message.reply_text("🔄 Merging PDFs...")

        # For now, return a placeholder response
        await update.message.reply_text(
            "⚠️ PDF merging is under maintenance.\n"
            "Please try again later or contact support."
        )

        logger.info(f"PDF merging requested by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in PDF merging: {e}")
        await update.message.reply_text("❌ Error merging files. Please try again.")
