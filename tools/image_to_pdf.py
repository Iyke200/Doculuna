# tools/image_to_pdf.py - Production Image to PDF Converter
import logging
import os
import shutil
import asyncio
import uuid
from aiogram import types
from aiogram.fsm.context import FSMContext
from PIL import Image
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from config import MAX_FILE_SIZE_FREE, MAX_FILE_SIZE_PREMIUM
from database.db import get_user_data, update_user_data
from utils.watermark import WatermarkManager, WatermarkConfig
from utils.usage_tracker import increment_usage
from io import BytesIO

logger = logging.getLogger(__name__)
watermark_manager = WatermarkManager()
WATERMARK_TEXT = "Processed with DocuLuna - Upgrade for Watermark-Free"

async def handle_image_to_pdf(message: types.Message, state: FSMContext = None):
    """Convert image to PDF document."""
    try:
        # Check disk space
        stat = shutil.disk_usage("data")
        if stat.free < 50 * 1024 * 1024:
            logger.error("Low storage, cannot process file")
            await message.reply("❌ Server storage full. Try again later.")
            return

        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        if not user_data:
            await message.reply("❌ Register with /start first.")
            return

        is_premium = user_data.get('is_premium', False) if user_data else False

        # Get file from message
        file_obj = message.photo[-1] if message.photo else message.document
        if not file_obj:
            await message.reply("❌ No image found. Please upload an image first.")
            return

        file_size = file_obj.file_size or 0
        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
        
        if file_size > max_file_size:
            await message.reply(
                f"❌ File too large! Max: {max_file_size / 1024 / 1024:.0f}MB. "
                f"Upgrade to Pro for {MAX_FILE_SIZE_PREMIUM / 1024 / 1024:.0f}MB files!"
            )
            return

        # Process the file
        bot = message.bot
        file = await bot.get_file(file_obj.file_id)
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
            try:
                with open(output_path, 'rb') as f:
                    pdf_data = f.read()
                
                config = WatermarkConfig(
                    text=WATERMARK_TEXT,
                    position="bottom-center",
                    opacity=0.3,
                    font_size=36,
                    rotation=0
                )
                
                watermarked_data = await watermark_manager.add_text_watermark(
                    BytesIO(pdf_data),
                    WATERMARK_TEXT,
                    config,
                    output_format="pdf"
                )
                
                with open(output_path, 'wb') as f:
                    f.write(watermarked_data)
                
                logger.info(f"Added watermark to PDF for free user {user_id}")
            except Exception as e:
                logger.error(f"Error adding watermark: {e}")

        # Send the converted file
        with open(output_path, "rb") as pdf_file:
            caption = "✅ **Image converted to PDF!**\n\n"
            if not is_premium:
                caption += "Upgrade to Pro for watermark-free PDFs!"
            else:
                caption += "Premium quality - no watermarks!"
                
            await bot.send_document(
                chat_id=message.chat.id,
                document=types.FSInputFile(output_path, filename="converted.pdf"),
                caption=caption
            )
            
            # Increment usage count for daily limits
            try:
                await increment_usage(user_id)
            except Exception as e:
                logger.warning(f"Usage increment failed: {e}")

        # Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
            
        await message.reply("✅ Conversion completed!")

    except Exception as e:
        logger.error(f"Error in handle_image_to_pdf: {e}")
        await message.reply("❌ Conversion failed. Please try again.")