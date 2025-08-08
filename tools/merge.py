import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.usage_tracker import increment_usage, check_usage_limit
from utils.premium_utils import is_premium
import io

logger = logging.getLogger(__name__)

async def handle_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF merge requests."""
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

        # Initialize merge session
        session_key = f"merge_files_{user_id}"
        if session_key not in context.bot_data:
            context.bot_data[session_key] = []

        # Get the PDF document
        document = update.message.document
        if not document or not document.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("❌ Please send a PDF file for merging.")
            return

        # Add file to merge session
        context.bot_data[session_key].append({
            'file_id': document.file_id,
            'file_name': document.file_name
        })

        files_count = len(context.bot_data[session_key])

        keyboard = [
            [InlineKeyboardButton(f"🔗 Merge {files_count} PDFs", callback_data=f"merge_now_{user_id}")],
            [InlineKeyboardButton("➕ Add More PDFs", callback_data=f"merge_add_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"merge_cancel_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📄 **PDF {files_count} added to merge queue**\n\n"
            f"Files ready: {files_count}\n"
            f"Send more PDFs or click 'Merge' to combine them.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error in merge handler: {e}")
        await update.message.reply_text("❌ Error processing PDF for merge.")

async def merge_pdfs(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """Merge multiple PDFs."""
    input_files = []
    output_file = None

    try:
        # Lazy imports
        from PyPDF2 import PdfMerger

        if user_id is None:
            user_id = update.effective_user.id

        session_key = f"merge_files_{user_id}"
        files_to_merge = context.bot_data.get(session_key, [])

        if len(files_to_merge) < 2:
            await update.message.reply_text("❌ Please add at least 2 PDF files to merge.")
            return

        await update.message.reply_text("🔄 Merging PDFs...")

        # Create temp directory
        os.makedirs("data/temp", exist_ok=True)

        # Download all files
        merger = PdfMerger()

        for i, file_info in enumerate(files_to_merge):
            file = await context.bot.get_file(file_info['file_id'])
            input_file = f"data/temp/merge_input_{user_id}_{i}.pdf"
            await file.download_to_drive(input_file)
            input_files.append(input_file)

            # Add to merger
            merger.append(input_file)

        # Create output file
        output_file = f"data/temp/merged_output_{user_id}.pdf"
        merger.write(output_file)
        merger.close()

        # Add watermark for free users
        if not is_premium(user_id):
            add_pdf_watermark(output_file)

        # Send the merged file
        with open(output_file, 'rb') as pdf_file:
            caption = f"✅ **{len(files_to_merge)} PDFs merged successfully!**"
            if not is_premium(user_id):
                caption += "\n\n💎 *Upgrade to Pro to remove watermark*"

            await update.message.reply_document(
                document=pdf_file,
                filename=f"merged_{len(files_to_merge)}_pdfs.pdf",
                caption=caption,
                parse_mode='Markdown'
            )

        # Clear session
        context.bot_data[session_key] = []

        # Increment usage
        await increment_usage(user_id)
        logger.info(f"PDF merge successful for user {user_id}")

    except Exception as e:
        logger.error(f"Error merging PDFs: {e}")
        await update.message.reply_text("❌ Error merging PDFs. Please try again.")
    finally:
        # Clean up files
        try:
            for input_file in input_files:
                if os.path.exists(input_file):
                    os.remove(input_file)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
        except Exception as e:
            logger.error(f"Error cleaning up merge files: {e}")

async def handle_merge_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF merge requests."""
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

        # Initialize merge session if not exists
        if 'merge_files' not in context.user_data:
            context.user_data['merge_files'] = []

        keyboard = [
            [InlineKeyboardButton("📄 Add PDF", callback_data="add_pdf_merge")],
            [InlineKeyboardButton("🔗 Merge All", callback_data="merge_all_pdfs")],
            [InlineKeyboardButton("🗑️ Clear All", callback_data="clear_merge_files")],
            [InlineKeyboardButton("⬅️ Back", callback_data="tools_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        files_count = len(context.user_data['merge_files'])
        message = (
            f"🔗 **PDF Merger**\n\n"
            f"📊 Files added: {files_count}\n\n"
            f"📄 **Add PDF** - Upload more PDF files\n"
            f"🔗 **Merge All** - Combine all uploaded PDFs\n"
            f"🗑️ **Clear All** - Remove all files\n\n"
            f"💡 Upload multiple PDF files, then click 'Merge All'"
        )

        await update.message.reply_text(
            message, reply_markup=reply_markup, parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error in handle_merge_pdf: {e}")
        await update.message.reply_text("❌ Error setting up PDF merger. Please try again.")

# Export the main function as well
__all__ = ['handle_merge', 'handle_merge_pdf', 'merge_pdfs']


def add_pdf_watermark(file_path):
    """Add DocuLuna watermark to PDF."""
    try:
        # Lazy imports
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from PyPDF2 import PdfReader, PdfWriter

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