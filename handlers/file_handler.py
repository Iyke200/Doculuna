# file_handler.py - File handling with new UX
import logging
import os
from aiogram import Dispatcher, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.usage_tracker import check_usage_limit, increment_usage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_document(message: types.Message, state: FSMContext):
    """Handle file received."""
    user_id = message.from_user.id
    
    can_process = await check_usage_limit(user_id, message)
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
    
    can_process = await check_usage_limit(user_id, message)
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
        logger.error(f"Error in file operation: {e}", exc_info=True)
        await callback.message.edit_text(
            "⚠️ Oops! Something went wrong while processing your file.\n"
            "Please try again later or contact @DocuLunaSupport"
        )

async def convert_file(bot: Bot, file_id: str, file_name: str) -> str:
    """Placeholder for file conversion logic."""
    import tempfile
    return tempfile.mktemp(suffix=".pdf")

async def compress_file(bot: Bot, file_id: str, file_name: str) -> str:
    """Placeholder for file compression logic."""
    import tempfile
    return tempfile.mktemp(suffix=".pdf")

async def image_to_pdf(bot: Bot, file_id: str, file_name: str) -> str:
    """Placeholder for image to PDF logic."""
    import tempfile
    return tempfile.mktemp(suffix=".pdf")

def register_file_handlers(dp: Dispatcher):
    """Register file handlers."""
    dp.message.register(handle_document, lambda m: m.document is not None)
    dp.message.register(handle_photo, lambda m: m.photo is not None)
    dp.callback_query.register(handle_file_operation, lambda c: c.data in [
        "convert_file", "merge_pdfs", "split_pdf", "compress_file", 
        "compress_image", "image_to_pdf"
    ])
