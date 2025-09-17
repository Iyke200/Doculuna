# tools/pdf_to_word.py - Production PDF to Word Converter
import logging
import os
import shutil
import asyncio
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from PyPDF2 import PdfReader
from docx import Document
from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
from database.db import get_user_by_id, add_usage_log
from utils.usage_tracker import increment_usage

logger = logging.getLogger(__name__)

async def handle_pdf_to_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert PDF to Word document."""
    try:
        # Check disk space
        stat = shutil.disk_usage("data")
        if stat.free < 50 * 1024 * 1024:
            logger.error("Low storage, cannot process file")
            await update.callback_query.edit_message_text("❌ Server storage full. Try again later.")
            return

        user_id = update.effective_user.id
        user = get_user_by_id(user_id)
        if not user:
            await update.callback_query.edit_message_text("❌ Register with /start first.")
            return

        is_premium = user[2] if len(user) > 2 else False

        # Get file from context
        file_obj = context.user_data.get("file_obj")
        if not file_obj:
            await update.callback_query.edit_message_text("❌ No file found. Please upload a PDF first.")
            return

        file_size = file_obj.file_size
        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
        
        if file_size > max_file_size:
            await update.callback_query.edit_message_text(
                f"❌ File too large! Max: {max_file_size / 1024 / 1024:.0f}MB. "
                f"Upgrade to Pro for {MAX_FILE_SIZE_PREMIUM / 1024 / 1024:.0f}MB files!"
            )
            return

        # Process the file
        file = await context.bot.get_file(file_obj.file_id)
        unique_id = uuid.uuid4().hex[:8]
        input_path = f"data/temp/pdf_{user_id}_{unique_id}.pdf"
        output_path = f"data/temp/word_{user_id}_{unique_id}.docx"
        
        os.makedirs("data/temp", exist_ok=True)
        await file.download_to_drive(input_path)

        # Convert PDF to Word
        reader = PdfReader(input_path)
        doc = Document()
        
        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    doc.add_paragraph(text)
            except Exception as e:
                logger.warning(f"Error extracting text from page {page_num}: {e}")
                doc.add_paragraph(f"[Page {page_num + 1}: Text extraction failed]")
        
        doc.save(output_path)

        # Send the converted file
        with open(output_path, "rb") as f:
            for attempt in range(3):
                try:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename="converted.docx",
                        caption="✅ **PDF converted to Word!**\n\nEdit your document easily now. Upgrade to Pro for unlimited conversions!"
                    )
                    add_usage_log(user_id, "pdf_to_word", True)
                    # Increment usage count for daily limits
                    try:
                        await increment_usage(user_id, "pdf_to_word")
                    except Exception as e:
                        logger.warning(f"Usage increment failed: {e}")
                    break
                except RetryAfter as e:
                    logger.warning(f"Rate limit hit in handle_pdf_to_word: {e}")
                    await asyncio.sleep(e.retry_after)

        # Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
            
        await update.callback_query.answer("✅ Conversion completed!")

    except Exception as e:
        logger.error(f"Error in handle_pdf_to_word: {e}")
        add_usage_log(user_id if 'user_id' in locals() else 0, "pdf_to_word", False)
        await update.callback_query.edit_message_text("❌ Conversion failed. Please try again.")
        await update.callback_query.answer()