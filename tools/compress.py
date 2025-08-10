import logging
import os
import zipfile
from PIL import Image
import PyPDF2
from telegram import Update
from telegram.ext import ContextTypes
from utils.usage_tracker import increment_usage
from utils.premium_utils import is_premium

logger = logging.getLogger(__name__)


async def handle_compress_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF compression request."""
    try:
        await update.message.reply_text("🔄 Compressing PDF...")

        # For now, return a placeholder response
        await update.message.reply_text(
            "⚠️ PDF compression is under maintenance.\n"
            "Please try again later or contact support."
        )

        logger.info(f"PDF compression requested by user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Error in PDF compression: {e}")
        await update.message.reply_text("❌ Error compressing file. Please try again.")


async def compress_file(file_path, output_path=None, compression_quality=85):
    """Compress various file types."""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()

        if not output_path:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = f"temp/{base_name}_compressed{file_ext}"

        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)

        if file_ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            # Compress image
            with Image.open(file_path) as img:
                img.save(output_path, optimize=True, quality=compression_quality)

        elif file_ext == ".pdf":
            # Compress PDF (basic compression)
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                writer = PyPDF2.PdfWriter()

                for page in reader.pages:
                    writer.add_page(page)

                with open(output_path, "wb") as output_file:
                    writer.write(output_file)

        else:
            # Generic compression using ZIP
            zip_path = f"{output_path}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
            output_path = zip_path

        logger.info(f"Successfully compressed {file_path} to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error compressing file: {e}")
        return None


async def handle_compress_document(update, context):
    """Handle document compression from Telegram."""
    try:
        from telegram import InputFile

        # Download the file
        file = await update.message.document.get_file()
        file_path = f"temp/{update.message.document.file_name}"

        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)

        await file.download_to_drive(file_path)

        # Compress the file
        compressed_path = await compress_file(file_path)

        if compressed_path:
            with open(compressed_path, "rb") as compressed_file:
                await update.message.reply_document(
                    document=InputFile(
                        compressed_file, filename=os.path.basename(compressed_path)
                    ),
                    caption="🗜 Your compressed file is ready!",
                )

            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(compressed_path):
                os.remove(compressed_path)
        else:
            await update.message.reply_text("❌ Failed to compress the file.")

    except Exception as e:
        logger.error(f"Error handling document compression: {e}")
        await update.message.reply_text("❌ Error processing file for compression.")
