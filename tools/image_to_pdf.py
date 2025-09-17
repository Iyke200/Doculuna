# tools/image_to_pdf.py - Production Image to PDF Converter
import logging
import os
import shutil
import asyncio
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from PIL import Image
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
from database.db import get_user_by_id, add_usage_log
from utils.watermark import add_pdf_watermark
from utils.usage_tracker import increment_usage

logger = logging.getLogger(__name__)

async def handle_image_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Convert image to PDF document."""
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
            await update.callback_query.edit_message_text("❌ No file found. Please upload an image first.")
            return

        file_size = file_obj.file_size or 0
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
        input_path = f"data/temp/image_{user_id}_{unique_id}.jpg"
        output_path = f"data/temp/pdf_{user_id}_{unique_id}.pdf"
        
        os.makedirs("data/temp", exist_ok=True)
        await file.download_to_drive(input_path)

        # Convert image to PDF
        image = Image.open(input_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Get image dimensions
        img_width, img_height = image.size
        
        # Create PDF with A4 size
        c = canvas.Canvas(output_path, pagesize=A4)
        page_width, page_height = A4
        
        # Calculate scaling to fit image on page
        scale_x = (page_width - 100) / img_width  # 50px margin on each side
        scale_y = (page_height - 100) / img_height  # 50px margin top/bottom
        scale = min(scale_x, scale_y)  # Use smaller scale to fit entirely
        
        # Calculate centered position
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        x = (page_width - scaled_width) / 2
        y = (page_height - scaled_height) / 2
        
        # Draw image
        c.drawImage(input_path, x, y, width=scaled_width, height=scaled_height)
        c.save()

        # Add watermark for free users
        if not is_premium:
            add_pdf_watermark(output_path)

        # Send the converted file
        with open(output_path, "rb") as f:
            caption = "✅ **Image converted to PDF!**\n\n"
            if not is_premium:
                caption += "Upgrade to Pro for watermark-free PDFs!"
            else:
                caption += "Premium quality - no watermarks!"
                
            for attempt in range(3):
                try:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename="converted.pdf",
                        caption=caption
                    )
                    add_usage_log(user_id, "image_to_pdf", True)
                    # Increment usage count for daily limits
                    try:
                        await increment_usage(user_id, "image_to_pdf")
                    except Exception as e:
                        logger.warning(f"Usage increment failed: {e}")
                    break
                except RetryAfter as e:
                    logger.warning(f"Rate limit hit in handle_image_to_pdf: {e}")
                    await asyncio.sleep(e.retry_after)

        # Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
            
        await update.callback_query.answer("✅ Conversion completed!")

    except Exception as e:
        logger.error(f"Error in handle_image_to_pdf: {e}")
        add_usage_log(user_id if 'user_id' in locals() else 0, "image_to_pdf", False)
        await update.callback_query.edit_message_text("❌ Conversion failed. Please try again.")
        await update.callback_query.answer()