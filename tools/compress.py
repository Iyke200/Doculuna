
import logging
import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import fitz  # PyMuPDF
from database.db import get_user, add_usage
from utils.usage_tracker import check_usage_limit, increment_usage

logger = logging.getLogger(__name__)

async def handle_compress_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compress PDF files."""
    try:
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        if not user:
            await update.message.reply_text("❌ Please start the bot first with /start")
            return
        
        # Check usage limits for free users
        if not user['is_premium'] and not await check_usage_limit(user_id):
            await update.message.reply_text(
                "⚠️ **Daily limit reached!**\n\n"
                "Free users can process 3 documents per day.\n"
                "Upgrade to premium for unlimited access!\n\n"
                "Use /upgrade to see premium plans."
            )
            return
        
        if not update.message.document:
            await update.message.reply_text("📄 Please send a PDF file to compress.")
            return
        
        document = update.message.document
        if not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("❌ Please send a PDF file only.")
            return
        
        await update.message.reply_text("🔄 Compressing your PDF... Please wait.")
        
        # Download file
        file = await context.bot.get_file(document.file_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.pdf")
            output_path = os.path.join(temp_dir, "compressed.pdf")
            
            await file.download_to_drive(input_path)
            
            # Compress PDF
            success = await compress_pdf_file(input_path, output_path, user['is_premium'])
            
            if success:
                # Send compressed file
                with open(output_path, 'rb') as compressed_file:
                    filename = f"compressed_{document.file_name}"
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=compressed_file,
                        filename=filename,
                        caption="✅ **PDF Compressed Successfully!**" + ("" if user['is_premium'] else "\n\n🔓 Upgrade to premium for watermark-free files!")
                    )
                
                # Log usage
                add_usage(user_id, "compress_pdf", document.file_size)
                if not user['is_premium']:
                    await increment_usage(user_id)
                
                logger.info(f"PDF compressed successfully for user {user_id}")
            else:
                await update.message.reply_text("❌ Failed to compress PDF. Please try again.")
    
    except Exception as e:
        logger.error(f"Error compressing PDF for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred while compressing. Please try again.")

async def compress_pdf_file(input_path, output_path, is_premium=False):
    """Compress PDF file using PyMuPDF."""
    try:
        # Open the PDF
        pdf_document = fitz.open(input_path)
        
        # Create a new PDF with compression
        compressed_pdf = fitz.open()
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # Get page as pixmap with lower resolution for compression
            mat = fitz.Matrix(0.7, 0.7)  # 70% of original size
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to image and compress
            img_data = pix.tobytes("jpeg", jpg_quality=80)
            
            # Create new page and insert compressed image
            new_page = compressed_pdf.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(page.rect, stream=img_data)
            
            # Add watermark for free users
            if not is_premium:
                watermark_text = "DocuLuna - Upgrade for watermark-free files"
                new_page.insert_text(
                    (50, 50),
                    watermark_text,
                    fontsize=12,
                    color=(0.7, 0.7, 0.7),
                    overlay=True
                )
        
        # Save compressed PDF
        compressed_pdf.save(output_path)
        compressed_pdf.close()
        pdf_document.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error in PDF compression: {e}")
        return False
