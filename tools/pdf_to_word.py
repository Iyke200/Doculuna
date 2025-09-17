‎# tools/pdf_to_word.py
‎import logging
‎import os
‎import shutil
‎from telegram import Update
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎from PyPDF2 import PdfReader
‎from docx import Document
‎from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
‎from database.db import get_user_by_id, add_usage_log
‎
‎logger = logging.getLogger(__name__)
‎
‎async def handle_pdf_to_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        stat = shutil.disk_usage("data")
‎        if stat.free < 50 * 1024 * 1024:
‎            logger.error("Low storage, cannot process file")
‎            await update.callback_query.edit_message_text("❌ Server storage full. Try again later.")
‎            return
‎        user_id = update.effective_user.id
‎        user = get_user_by_id(user_id)
‎        if not user:
‎            await update.callback_query.edit_message_text("❌ Register with /start first.")
‎            return
‎        is_premium = user[2]
‎        document = context.user_data.get("last_file")
‎        if not document or not document.file_name.lower().endswith('.pdf'):
‎            await update.callback_query.edit_message_text("❌ Upload a PDF first.")
‎            return
‎        file_size = document.file_size
‎        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
‎        if file_size > max_file_size:
‎            await update.callback_query.edit_message_text(f"❌ File too large. Max: {max_file_size / 1024 / 1024} MB. Go Pro for 50 MB files!")
‎            return
‎        file = await context.bot.get_file(document.file_id)
‎        input_path = f"data/temp/pdf_{user_id}.pdf"
‎        output_path = f"data/temp/word_{user_id}.docx"
‎        os.makedirs("data/temp", exist_ok=True)
‎        await file.download_to_drive(input_path)
‎        reader = PdfReader(input_path)
‎        doc = Document()
‎        for page in reader.pages:
‎            doc.add_paragraph(page.extract_text() or "")
‎        doc.save(output_path)
‎        with open(output_path, "rb") as f:
‎            for attempt in range(3):
‎                try:
‎                    await context.bot.send_document(
‎                        chat_id=update.effective_chat.id,
‎                        document=f,
‎                        filename="converted.docx",
‎                        caption="✅ Your PDF is now a Word doc – edit your WAEC results easily! Go Pro for unlimited conversions."
‎                    )
‎                    add_usage_log(user_id, "pdf_to_word", True)
‎                    break
‎                except RetryAfter as e:
‎                    logger.warning(f"Rate limit hit in handle_pdf_to_word: {e}")
‎                    await asyncio.sleep(e.retry_after)
‎        os.remove(input_path)
‎        os.remove(output_path)
‎        await update.callback_query.answer()
‎    except Exception as e:
‎        logger.error(f"Error in handle_pdf_to_word: {e}")
‎        add_usage_log(user_id, "pdf_to_word", False)
‎        await update.callback_query.edit_message_text("❌ Conversion failed. Try again.")
