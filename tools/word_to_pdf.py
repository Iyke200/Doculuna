‎# tools/word_to_pdf.py
‎import logging
‎import os
‎import shutil
‎from telegram import Update
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎from docx import Document
‎from reportlab.lib.pagesizes import letter
‎from reportlab.pdfgen import canvas
‎from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
‎from database.db import get_user_by_id, add_usage_log
‎from utils.watermark import add_pdf_watermark
‎
‎logger = logging.getLogger(__name__)
‎
‎async def handle_word_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
‎        if not document or not document.file_name.lower().endswith(('.doc', '.docx')):
‎            await update.callback_query.edit_message_text("❌ Upload a Word document first.")
‎            return
‎        file_size = document.file_size
‎        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
‎        if file_size > max_file_size:
‎            await update.callback_query.edit_message_text(f"❌ File too large. Max: {max_file_size / 1024 / 1024} MB. Go Pro for 50 MB files!")
‎            return
‎        file = await context.bot.get_file(document.file_id)
‎        input_path = f"data/temp/word_{user_id}.docx"
‎        output_path = f"data/temp/pdf_{user_id}.pdf"
‎        os.makedirs("data/temp", exist_ok=True)
‎        await file.download_to_drive(input_path)
‎        doc = Document(input_path)
‎        c = canvas.Canvas(output_path, pagesize=letter)
‎        y = 700
‎        for para in doc.paragraphs:
‎            c.drawString(100, y, para.text[:100])
‎            y -= 20
‎            if y < 50:
‎                c.showPage()
‎                y = 700
‎        c.save()
‎        if not is_premium:
‎            add_pdf_watermark(output_path)
‎        with open(output_path, "rb") as f:
‎            for attempt in range(3):
‎                try:
‎                    await context.bot.send_document(
‎                        chat_id=update.effective_chat.id,
‎                        document=f,
‎                        filename="converted.pdf",
‎                        caption="✅ Your Word doc is now a PDF – perfect for NYSC! Go Pro for watermark-free outputs."
‎                    )
‎                    add_usage_log(user_id, "word_to_pdf", True)
‎                    break
‎                except RetryAfter as e:
‎                    logger.warning(f"Rate limit hit in handle_word_to_pdf: {e}")
‎                    await asyncio.sleep(e.retry_after)
‎        os.remove(input_path)
‎        os.remove(output_path)
‎        await update.callback_query.answer()
‎    except Exception as e:
‎        logger.error(f"Error in handle_word_to_pdf: {e}")
‎        add_usage_log(user_id, "word_to_pdf", False)
‎        await update.callback_query.edit_message_text("❌ Conversion failed. Try again.")
‎
