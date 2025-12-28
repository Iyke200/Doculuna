# image_to_pdf_batch.py - Batch image to PDF conversion
import os
import tempfile
import asyncio
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import logging

logger = logging.getLogger(__name__)

async def batch_convert_images(bot, bulk_files, user_id=None):
    """Convert multiple images into a single PDF."""
    try:
        output_path = tempfile.mktemp(suffix="_batch.pdf")
        c = canvas.Canvas(output_path, pagesize=A4)
        page_width, page_height = A4
        
        for file_info in bulk_files:
            file_id = file_info['file_id']
            file_name = file_info['file_name']
            
            # Download image
            file = await bot.get_file(file_id)
            input_path = tempfile.mktemp(suffix=".jpg")
            await bot.download_file(file.file_path, input_path)
            
            try:
                image = Image.open(input_path)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                img_width, img_height = image.size
                scale = min(page_width / img_width, page_height / img_height) * 0.9
                x = (page_width - img_width * scale) / 2
                y = (page_height - img_height * scale) / 2
                
                c.drawImage(input_path, x, y, img_width * scale, img_height * scale)
                c.showPage()
            finally:
                if os.path.exists(input_path):
                    os.remove(input_path)
        
        c.save()
        
        # Add watermark for free users
        if user_id:
            from database.db import get_user_data
            user_data = await get_user_data(user_id)
            is_premium = user_data.get('is_premium', False) if user_data else False
            if not is_premium:
                from handlers.file_handler import add_watermark_to_pdf
                await add_watermark_to_pdf(output_path)
        
        return output_path
    except Exception as e:
        logger.error(f"Batch conversion error: {e}", exc_info=True)
        return None
