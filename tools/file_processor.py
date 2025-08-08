import logging
import asyncio
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, File
from telegram.ext import ContextTypes
from database.db import get_user, log_usage
from utils.usage_tracker import check_usage_limit, increment_usage
from config import Config

logger = logging.getLogger(__name__)

class AdvancedFileProcessor:
    """Advanced file processor with progress tracking and optimization"""
    
    def __init__(self):
        self.processing_queue = {}
        self.batch_processing = {}
        self.progress_tracking = {}
        
    def get_file_type(self, file_name: str) -> str:
        """Determine file type with enhanced detection"""
        file_name = file_name.lower()
        
        if file_name.endswith('.pdf'):
            return 'pdf'
        elif file_name.endswith(('.doc', '.docx')):
            return 'word'
        elif file_name.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff')):
            return 'image'
        elif file_name.endswith(('.txt', '.rtf')):
            return 'text'
        elif file_name.endswith(('.ppt', '.pptx')):
            return 'presentation'
        elif file_name.endswith(('.xls', '.xlsx')):
            return 'spreadsheet'
        else:
            return 'unknown'
    
    def get_file_icon(self, file_type: str) -> str:
        """Get appropriate icon for file type"""
        icons = {
            'pdf': '📄',
            'word': '📝',
            'image': '🖼️',
            'text': '📃',
            'presentation': '📊',
            'spreadsheet': '📈',
            'unknown': '📁'
        }
        return icons.get(file_type, '📁')
    
    async def create_progress_message(self, update: Update, operation: str) -> str:
        """Create a progress tracking message"""
        progress_id = f"{update.effective_user.id}_{int(time.time())}"
        
        progress_text = f"""
🔄 **Processing Your File**

**Operation**: {operation}
**Status**: Starting...
**Progress**: ░░░░░░░░░░ 0%

⏱️ Estimated time: Calculating...
🕒 Started: {datetime.now().strftime('%H:%M:%S')}

Please wait while we process your file...
"""
        
        message = await update.message.reply_text(progress_text, parse_mode='Markdown')
        
        self.progress_tracking[progress_id] = {
            'message': message,
            'start_time': time.time(),
            'operation': operation,
            'status': 'processing'
        }
        
        return progress_id
    
    async def update_progress(self, progress_id: str, progress: int, status: str = None):
        """Update progress bar and status"""
        if progress_id not in self.progress_tracking:
            return
            
        tracking = self.progress_tracking[progress_id]
        elapsed = time.time() - tracking['start_time']
        
        # Create progress bar
        filled = '█' * (progress // 10)
        empty = '░' * (10 - (progress // 10))
        progress_bar = f"{filled}{empty}"
        
        # Calculate ETA
        if progress > 0:
            eta = (elapsed / progress) * (100 - progress)
            eta_text = f"{eta:.0f}s" if eta < 60 else f"{eta//60:.0f}m {eta%60:.0f}s"
        else:
            eta_text = "Calculating..."
        
        updated_text = f"""
🔄 **Processing Your File**

**Operation**: {tracking['operation']}
**Status**: {status or 'Processing...'}
**Progress**: {progress_bar} {progress}%

⏱️ ETA: {eta_text}
🕒 Elapsed: {elapsed:.0f}s

Please wait while we process your file...
"""
        
        try:
            await tracking['message'].edit_text(updated_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
    
    async def complete_progress(self, progress_id: str, success: bool = True, result_message: str = None):
        """Complete progress tracking"""
        if progress_id not in self.progress_tracking:
            return
            
        tracking = self.progress_tracking[progress_id]
        elapsed = time.time() - tracking['start_time']
        
        if success:
            status_icon = "✅"
            status_text = "Completed Successfully!"
        else:
            status_icon = "❌"
            status_text = "Processing Failed"
        
        final_text = f"""
{status_icon} **File Processing Complete**

**Operation**: {tracking['operation']}
**Status**: {status_text}
**Time Taken**: {elapsed:.1f} seconds

{result_message or ''}
"""
        
        try:
            await tracking['message'].edit_text(final_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error completing progress: {e}")
        
        # Clean up
        del self.progress_tracking[progress_id]
    
    async def validate_file(self, file: File, file_type: str) -> Tuple[bool, str]:
        """Validate file with comprehensive checks"""
        try:
            # Check file size
            if file.file_size > Config.MAX_FILE_SIZE:
                size_mb = file.file_size / (1024 * 1024)
                max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
                return False, f"File too large ({size_mb:.1f}MB). Maximum allowed: {max_mb:.0f}MB"
            
            # Check file type
            if file_type == 'unknown':
                return False, "Unsupported file type. Please upload PDF, Word, or image files."
            
            # Check file name
            if not file.file_path or len(file.file_path) > 255:
                return False, "Invalid file name or path too long."
            
            return True, "File validation successful"
            
        except Exception as e:
            logger.error(f"Error validating file: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def get_file_info(self, file: File, file_type: str) -> Dict[str, Any]:
        """Get comprehensive file information"""
        try:
            size_mb = round(file.file_size / (1024 * 1024), 2)
            size_kb = round(file.file_size / 1024, 1)
            
            return {
                'name': file.file_path.split('/')[-1] if file.file_path else 'Unknown',
                'type': file_type,
                'size_bytes': file.file_size,
                'size_mb': size_mb,
                'size_kb': size_kb,
                'size_display': f"{size_mb} MB" if size_mb >= 1 else f"{size_kb} KB",
                'icon': self.get_file_icon(file_type),
                'mime_type': getattr(file, 'mime_type', 'unknown'),
                'upload_time': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {'error': str(e)}
    
    async def show_enhanced_tools_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_info: Dict[str, Any] = None):
        """Show enhanced tools menu with file information"""
        try:
            file_type = file_info.get('type') if file_info else 'unknown'
            
            # Base text
            menu_text = "🛠️ **DocuLuna Advanced Tools**\n\n"
            
            if file_info:
                menu_text += f"""📁 **File Information**
{file_info['icon']} **Name**: {file_info['name']}
📊 **Size**: {file_info['size_display']}
🏷️ **Type**: {file_info['type'].title()}

"""
            
            menu_text += "**Choose a tool category:**"
            
            # Dynamic keyboard based on file type
            keyboard = []
            
            if file_type == 'pdf':
                keyboard.extend([
                    [InlineKeyboardButton("📝 PDF to Word", callback_data="tool_pdf_to_word")],
                    [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
                    [InlineKeyboardButton("🔗 Merge PDFs", callback_data="tool_merge_pdf")],
                    [InlineKeyboardButton("🗜️ Compress PDF", callback_data="tool_compress_pdf")]
                ])
            elif file_type == 'word':
                keyboard.extend([
                    [InlineKeyboardButton("📄 Word to PDF", callback_data="tool_word_to_pdf")],
                    [InlineKeyboardButton("🗜️ Compress Document", callback_data="tool_compress_doc")]
                ])
            elif file_type == 'image':
                keyboard.extend([
                    [InlineKeyboardButton("📄 Image to PDF", callback_data="tool_image_to_pdf")],
                    [InlineKeyboardButton("🔗 Merge Images", callback_data="tool_merge_images")],
                    [InlineKeyboardButton("🗜️ Compress Image", callback_data="tool_compress_image")]
                ])
            else:
                keyboard.extend([
                    [InlineKeyboardButton("📄 PDF Tools", callback_data="menu_pdf_tools")],
                    [InlineKeyboardButton("📝 Word Tools", callback_data="menu_word_tools")],
                    [InlineKeyboardButton("🖼️ Image Tools", callback_data="menu_image_tools")]
                ])
            
            # Add universal options
            keyboard.extend([
                [InlineKeyboardButton("🔄 Batch Processing", callback_data="menu_batch_processing")],
                [InlineKeyboardButton("📊 File Analysis", callback_data="menu_file_analysis")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    menu_text, 
                    reply_markup=reply_markup, 
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    menu_text, 
                    reply_markup=reply_markup, 
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error showing tools menu: {e}")
            error_msg = "❌ Error loading tools menu."
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
    
    async def process_file_advanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Advanced file processing with enhanced features"""
        try:
            user_id = update.effective_user.id
            user = get_user(user_id)
            
            if not user:
                await update.message.reply_text(
                    "❌ Please start the bot first with /start",
                    parse_mode='Markdown'
                )
                return
            
            # Get file
            if update.message.document:
                file = update.message.document
                file_obj = await file.get_file()
            elif update.message.photo:
                file = update.message.photo[-1]  # Get highest resolution
                file_obj = await file.get_file()
            else:
                await update.message.reply_text("❌ No file detected. Please send a document or image.")
                return
            
            # Determine file type
            file_name = getattr(file, 'file_name', 'image.jpg')
            file_type = self.get_file_type(file_name)
            
            # Validate file
            is_valid, validation_message = await self.validate_file(file_obj, file_type)
            if not is_valid:
                await update.message.reply_text(f"❌ {validation_message}")
                return
            
            # Check usage limits
            if not await check_usage_limit(user_id):
                keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ **Usage Limit Reached**\n\n"
                    "You've reached your daily limit of free tool uses.\n\n"
                    "💎 **Upgrade to DocuLuna Pro** for:\n"
                    "• Unlimited tool usage\n"
                    "• Priority processing\n"
                    "• Advanced features\n"
                    "• 24/7 support",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
            
            # Get file information
            file_info = await self.get_file_info(file_obj, file_type)
            
            # Store file for processing
            context.user_data['last_file'] = file
            context.user_data['last_file_info'] = file_info
            context.user_data['last_file_object'] = file_obj
            
            # Show enhanced tools menu
            await self.show_enhanced_tools_menu(update, context, file_info)
            
            # Log file upload
            await log_usage(user_id, f"file_upload_{file_type}")
            
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            await update.message.reply_text(
                "❌ **Processing Error**\n\n"
                "Sorry, there was an error processing your file. Please try again.\n\n"
                f"Error details: {str(e)[:100]}...",
                parse_mode='Markdown'
            )

# Global file processor instance
file_processor = AdvancedFileProcessor()

# Main function exports
async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main tools menu"""
    await file_processor.show_enhanced_tools_menu(update, context)

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uploaded files with advanced features"""
    await file_processor.process_file_advanced(update, context)

# Utility functions for other modules
def get_file_type(file_name: str) -> str:
    """Determine file type - utility function"""
    return file_processor.get_file_type(file_name)

async def create_progress_tracker(update: Update, operation: str) -> str:
    """Create progress tracker - utility function"""
    return await file_processor.create_progress_message(update, operation)

async def update_progress_tracker(progress_id: str, progress: int, status: str = None):
    """Update progress tracker - utility function"""
    await file_processor.update_progress(progress_id, progress, status)

async def complete_progress_tracker(progress_id: str, success: bool = True, result_message: str = None):
    """Complete progress tracker - utility function"""
    await file_processor.complete_progress(progress_id, success, result_message)