"""Tool instruction messages for DocuLuna file operations."""

from utils.messages import (
    TOOL_INSTRUCTION_PDF_WORD,
    TOOL_INSTRUCTION_WORD_PDF,
    TOOL_INSTRUCTION_IMAGE_PDF,
    TOOL_INSTRUCTION_MERGE,
    TOOL_INSTRUCTION_SPLIT,
    TOOL_INSTRUCTION_COMPRESS,
)
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def show_tool_instruction(message: Message, tool_name: str) -> None:
    """Show instruction for a specific tool before operation."""
    instructions = {
        "pdf_to_word": TOOL_INSTRUCTION_PDF_WORD,
        "word_to_pdf": TOOL_INSTRUCTION_WORD_PDF,
        "image_to_pdf": TOOL_INSTRUCTION_IMAGE_PDF,
        "merge_pdf": TOOL_INSTRUCTION_MERGE,
        "split_pdf": TOOL_INSTRUCTION_SPLIT,
        "compress_pdf": TOOL_INSTRUCTION_COMPRESS,
    }
    
    if tool_name in instructions:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        await message.answer(instructions[tool_name], reply_markup=builder.as_markup())


def get_operation_name(operation_type: str) -> str:
    """Get human-readable operation name."""
    names = {
        "pdf_to_word": "PDF to Word",
        "word_to_pdf": "Word to PDF",
        "image_to_pdf": "Image to PDF",
        "merge_pdf": "Merge PDFs",
        "split_pdf": "Split PDF",
        "compress_pdf": "Compress PDF",
    }
    return names.get(operation_type, operation_type)


def format_file_size(bytes_size: int) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"
