
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from utils.usage_tracker import increment_usage, check_usage_limit
from utils.premium_utils import is_premium
import io

logger = logging.getLogger(__name__)

async def handle_image_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Image to PDF conversion."""
    input_file = None
    output_file = None

    try:
        user_id = update.effective_user.id

        # Check usage limit
        if not await check_usage_limit(user_id):
            keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ You've reached your daily limit of 3 tool uses.\n\n"
                "Upgrade to **DocuLuna Pro** for unlimited access!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        await update.message.reply_text("🔄 Converting image to PDF...")

        # Get the image (either as document or photo)
        if update.message.document:
            document = update.message.document
            file = await context.bot.get_file(document.file_id)
            filename = document.file_name
        elif update.message.photo:
            # Get the largest photo size
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            filename = f"image_{photo.file_id}.jpg"
        else:
            await update.message.reply_text("❌ No image found. Please send an image file.")
            return

        # Create temp directory
        os.makedirs("data/temp", exist_ok=True)

        # Download input file
        input_file = f"data/temp/image_input_{user_id}_{file.file_id}"
        await file.download_to_drive(input_file)

        # Convert to PDF
        output_file = f"data/temp/image_output_{user_id}_{file.file_id}.pdf"

        # Open and process the image
        image = Image.open(input_file)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Create PDF
        c = canvas.Canvas(output_file, pagesize=letter)
        width, height = letter

        # Calculate image dimensions to fit the page
        img_width, img_height = image.size
        aspect_ratio = img_height / img_width

        # Scale image to fit page while maintaining aspect ratio
        if aspect_ratio > (height / width):
            # Image is tall, scale by height
            new_height = height - 100  # Leave some margin
            new_width = new_height / aspect_ratio
        else:
            # Image is wide, scale by width
            new_width = width - 100  # Leave some margin
            new_height = new_width * aspect_ratio

        # Center the image
        x = (width - new_width) / 2
        y = (height - new_height) / 2

        # Draw the image
        c.drawImage(ImageReader(image), x, y, width=new_width, height=new_height)
        c.save()

        # Add watermark for free users
        if not is_premium(user_id):
            add_pdf_watermark(output_file)

        # Send the converted file
        with open(output_file, 'rb') as pdf_file:
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            caption = "✅ **Image to PDF conversion complete!**"
            if not is_premium(user_id):
                caption += "\n\n💎 *Upgrade to Pro to remove watermark*"
                
            await update.message.reply_document(
                document=pdf_file,
                filename=f"{base_name}.pdf",
                caption=caption,
                parse_mode='Markdown'
            )

        # Increment usage
        await increment_usage(user_id)
        logger.info(f"Image to PDF conversion successful for user {user_id}")

    except Exception as e:
        logger.error(f"Error in Image to PDF conversion: {e}")
        await update.message.reply_text(
            "❌ Error converting image to PDF. Please ensure you sent a valid image file."
        )
    finally:
        # Clean up files
        try:
            if input_file and os.path.exists(input_file):
                os.remove(input_file)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
        except Exception as e:
            logger.error(f"Error cleaning up files: {e}")

def add_pdf_watermark(file_path):
    """Add DocuLuna watermark to PDF."""
    try:
        # Create watermark
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFont("Helvetica", 40)
        can.setFillAlpha(0.1)
        can.drawString(100, 400, "DocuLuna")
        can.setFont("Helvetica", 12)
        can.drawString(100, 50, "Generated by DocuLuna - Upgrade to Pro to remove watermark")
        can.save()

        # Move to the beginning of the StringIO buffer
        packet.seek(0)
        watermark = PdfReader(packet)

        # Read the existing PDF
        existing_pdf = PdfReader(file_path)
        output = PdfWriter()

        # Add watermark to each page
        for page in existing_pdf.pages:
            page.merge_page(watermark.pages[0])
            output.add_page(page)

        # Write the result
        with open(file_path, "wb") as output_stream:
            output.write(output_stream)

    except Exception as e:
        logger.error(f"Error adding watermark to PDF: {e}")
