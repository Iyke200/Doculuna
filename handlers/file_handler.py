# file_handler.py - File handling with new UX
import logging
import os
import tempfile
import asyncio
from aiogram import Dispatcher, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.usage_tracker import check_usage_limit, increment_usage
from tools.pdf_to_word import PDFToWordConverter
from tools.word_to_pdf import WordToPDFConverter
from tools.compress import PDFCompressor, DOCXCompressor, CompressionLevel
from tools.image_to_pdf import handle_image_to_pdf
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_document(message: types.Message, state: FSMContext):
    """Handle file received."""
    user_id = message.from_user.id
    
    can_process = await check_usage_limit(user_id)
    if not can_process:
        return
    
    try:
        file_received_text = (
            "📄 File received successfully!\n"
            "What would you like to do with it? 👇"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔁 Convert File", callback_data="convert_file")
        builder.button(text="📊 Merge PDFs", callback_data="merge_pdfs")
        builder.button(text="✂️ Split PDF", callback_data="split_pdf")
        builder.button(text="🗜️ Compress", callback_data="compress_file")
        builder.adjust(2, 2)
        
        await message.reply(file_received_text, reply_markup=builder.as_markup())
        
        await state.update_data(file_id=message.document.file_id if message.document else None)
        await state.update_data(file_name=message.document.file_name if message.document else "file")
        
    except Exception as e:
        logger.error(f"Error handling document: {e}", exc_info=True)
        await message.reply(
            "⚠️ Oops! Something went wrong while processing your file.\n"
            "Please try again later or contact @DocuLunaSupport"
        )

async def handle_photo(message: types.Message, state: FSMContext):
    """Handle image received."""
    user_id = message.from_user.id
    
    can_process = await check_usage_limit(user_id)
    if not can_process:
        return
    
    try:
        file_received_text = (
            "📄 Image received successfully!\n"
            "What would you like to do with it? 👇"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📄 Convert to PDF", callback_data="image_to_pdf")
        builder.button(text="🗜️ Compress", callback_data="compress_image")
        builder.adjust(2)
        
        await message.reply(file_received_text, reply_markup=builder.as_markup())
        
        photo = message.photo[-1]
        await state.update_data(file_id=photo.file_id)
        await state.update_data(file_name="image.jpg")
        
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await message.reply(
            "⚠️ Oops! Something went wrong while processing your file.\n"
            "Please try again later or contact @DocuLunaSupport"
        )

async def handle_file_operation(callback: types.CallbackQuery, state: FSMContext):
    """Handle file operation callbacks."""
    operation = callback.data
    user_id = callback.from_user.id
    
    try:
        processing_text = (
            "⚙️ Please wait a moment...\n"
            "Your document is being processed 🔄"
        )
        
        await callback.message.edit_text(processing_text)
        await callback.answer()
        
        user_data = await state.get_data()
        file_id = user_data.get('file_id')
        file_name = user_data.get('file_name', 'file')
        
        if operation == "convert_file":
            result_file_path = await convert_file(callback.bot, file_id, file_name)
        elif operation == "compress_file" or operation == "compress_image":
            result_file_path = await compress_file(callback.bot, file_id, file_name)
        elif operation == "image_to_pdf":
            result_file_path = await image_to_pdf(callback.bot, file_id, file_name)
        else:
            await callback.message.edit_text("Operation not yet implemented")
            return
        
        if result_file_path:
            success_text = (
                "✅ Done! Your document is ready 🎉\n"
                "Click below to download your file 👇"
            )
            
            with open(result_file_path, 'rb') as doc:
                doc_message = await callback.message.answer_document(doc)
            
            builder = InlineKeyboardBuilder()
            builder.button(text="⬇️ Download File", callback_data=f"download_{doc_message.message_id}")
            builder.button(text="💎 Upgrade for Unlimited Access", callback_data="go_premium")
            builder.adjust(2)
            
            await callback.message.edit_text(success_text, reply_markup=builder.as_markup())
            
            await increment_usage(user_id)
            
            try:
                os.remove(result_file_path)
            except:
                pass
        else:
            raise Exception("Processing failed")
        
    except Exception as e:
        logger.error(f"Error in file operation {operation}: {e}", exc_info=True)
        
        error_message = "⚠️ Processing failed.\n\n"
        
        if "size" in str(e).lower():
            error_message += "File is too large. Please use a smaller file."
        elif "format" in str(e).lower() or "unsupported" in str(e).lower():
            error_message += "Unsupported file format. Please check file type."
        elif "corrupt" in str(e).lower() or "invalid" in str(e).lower():
            error_message += "File appears to be corrupted or invalid."
        else:
            error_message += "An error occurred while processing your file."
        
        error_message += "\n\nIf the problem persists, contact @DocuLunaSupport"
        
        await callback.message.edit_text(error_message)

async def convert_file(bot: Bot, file_id: str, file_name: str) -> str:
    """Convert PDF to Word or Word to PDF based on file type."""
    try:
        file = await bot.get_file(file_id)
        input_path = tempfile.mktemp(suffix=os.path.splitext(file_name)[1])
        await file.download_to_drive(input_path)
        
        if file_name.lower().endswith('.pdf'):
            output_path = tempfile.mktemp(suffix=".docx")
            result = PDFToWordConverter.convert_pdf_to_docx(
                input_path, 
                output_path, 
                preserve_layout=True, 
                extract_images=True
            )
            logger.info(f"PDF to Word conversion: {result['success']}")
        elif file_name.lower().endswith(('.docx', '.doc')):
            output_path = tempfile.mktemp(suffix=".pdf")
            result = WordToPDFConverter.convert_docx_to_pdf(
                input_path, 
                output_path, 
                preserve_formatting=True, 
                high_quality=True
            )
            logger.info(f"Word to PDF conversion: {result['success']}")
        else:
            raise ValueError("Unsupported file type for conversion")
        
        try:
            os.remove(input_path)
        except:
            pass
            
        return output_path
    except Exception as e:
        logger.error(f"Conversion error: {e}", exc_info=True)
        raise

async def compress_file(bot: Bot, file_id: str, file_name: str) -> str:
    """Compress PDF or DOCX file."""
    try:
        file = await bot.get_file(file_id)
        input_path = tempfile.mktemp(suffix=os.path.splitext(file_name)[1])
        await file.download_to_drive(input_path)
        
        output_path = tempfile.mktemp(suffix=os.path.splitext(file_name)[1])
        
        if file_name.lower().endswith('.pdf'):
            original_size, compressed_size = PDFCompressor.compress_pdf(
                input_path, 
                output_path, 
                CompressionLevel.MEDIUM
            )
            logger.info(f"PDF compressed: {original_size} → {compressed_size} bytes")
        elif file_name.lower().endswith('.docx'):
            original_size, compressed_size = DOCXCompressor.compress_docx(
                input_path, 
                output_path, 
                CompressionLevel.MEDIUM
            )
            logger.info(f"DOCX compressed: {original_size} → {compressed_size} bytes")
        else:
            raise ValueError("Unsupported file type for compression")
        
        try:
            os.remove(input_path)
        except:
            pass
            
        return output_path
    except Exception as e:
        logger.error(f"Compression error: {e}", exc_info=True)
        raise

async def image_to_pdf(bot: Bot, file_id: str, file_name: str) -> str:
    """Convert image to PDF."""
    try:
        file = await bot.get_file(file_id)
        input_path = tempfile.mktemp(suffix=".jpg")
        await file.download_to_drive(input_path)
        
        output_path = tempfile.mktemp(suffix=".pdf")
        
        image = Image.open(input_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_width, img_height = image.size
        c = canvas.Canvas(output_path, pagesize=A4)
        page_width, page_height = A4
        
        scale = min(page_width / img_width, page_height / img_height) * 0.9
        x = (page_width - img_width * scale) / 2
        y = (page_height - img_height * scale) / 2
        
        c.drawImage(input_path, x, y, img_width * scale, img_height * scale)
        c.save()
        
        try:
            os.remove(input_path)
        except:
            pass
            
        logger.info(f"Image to PDF conversion complete: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Image to PDF error: {e}", exc_info=True)
        raise

def register_file_handlers(dp: Dispatcher):
    """Register file handlers."""
    dp.message.register(handle_document, lambda m: m.document is not None)
    dp.message.register(handle_photo, lambda m: m.photo is not None)
    dp.callback_query.register(handle_file_operation, lambda c: c.data in [
        "convert_file", "merge_pdfs", "split_pdf", "compress_file", 
        "compress_image", "image_to_pdf"
    ])
