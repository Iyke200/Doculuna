#!/usr/bin/env python3
"""DocuLuna - Text to PDF Utility"""

import argparse
import os
import logging
from typing import Dict
from fpdf import FPDF

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TextToPDF:
    @staticmethod
    def text_to_pdf(input_text: str, output_path: str, font: str = 'helvetica', font_size: int = 12) -> Dict:
        """
        Convert text to a PDF file.
        
        Args:
            input_text: The text content to convert to PDF.
            output_path: The path to save the output PDF.
            font: The font to use (e.g., 'helvetica', 'courier'). For Unicode support, provide a .ttf font path via add_font.
            font_size: The font size.
        
        Returns:
            Dictionary with conversion results.
        
        Raises:
            ValueError: If conversion fails.
        """
        if not input_text:
            raise ValueError("Input text cannot be empty")
        
        if font_size <= 0:
            raise ValueError("Font size must be positive")
        
        # Validate output path
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        if os.path.exists(output_path):
            logger.warning(f"Overwriting existing file: {output_path}")
        
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15.0)
            
            # Handle font setting with fallback for invalid fonts
            try:
                pdf.set_font(font, size=font_size)
            except Exception as font_error:
                logger.warning(f"Invalid font '{font}': {font_error}. Falling back to 'helvetica'.")
                pdf.set_font('helvetica', size=font_size)
            
            # For better Unicode support, optionally add a TrueType font (commented; user must provide .ttf)
            # Example: Download DejaVuSans.ttf and uncomment:
            # pdf.add_font('DejaVu', '', 'path/to/DejaVuSans.ttf', uni=True)
            # pdf.set_font('DejaVu', size=font_size)
            
            # Use multi_cell for text wrapping; handles basic Unicode if using uni=True font
            pdf.multi_cell(0, 10, input_text)
            
            pdf.output(output_path)
            
            output_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'output_file': output_path,
                'output_size': output_size,
                'page_count': pdf.page_no()
            }
        except Exception as e:
            logger.error(f"Text to PDF conversion failed: {e}")
            raise ValueError(f"Conversion failed: {str(e)}")

async def handle_text_to_pdf_callback(callback, state=None):
    """Handle Text to PDF callback from menu."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    try:
        text = (
            "📄 Text to PDF Converter\n\n"
            "Send me some text, and I'll convert it into a PDF document.\n\n"
            "✅ Simple formatting\n"
            "✅ Custom fonts\n"
            "✅ Quick conversion\n\n"
            "Type or paste your text now 👇\n\n"
            "Note: For text with special characters, ensure to use a Unicode-compatible font."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back to Tools", callback_data="process_document")
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in Text to PDF callback: {e}")
        await callback.answer("Error", show_alert=True)

def register_text_to_pdf(dp):
    """Register Text to PDF handler."""
    dp.callback_query.register(handle_text_to_pdf_callback, lambda c: c.data == "text_to_pdf")

def main():
    parser = argparse.ArgumentParser(
        description='DocuLuna Text to PDF Converter\n'
                    'Note: For multiline text, quote the input or use --file for a text file.'
    )
    parser.add_argument('input_text', help='Input text (or path to text file if --file)')
    parser.add_argument('output', help='Output PDF file')
    parser.add_argument('--font', default='helvetica', help='Font to use')
    parser.add_argument('--font-size', type=int, default=12, help='Font size')
    parser.add_argument('--file', action='store_true', help='Treat input_text as file path')
    args = parser.parse_args()
    
    try:
        if args.file:
            if not os.path.isfile(args.input_text):
                raise ValueError(f"Input file not found: {args.input_text}")
            with open(args.input_text, 'r', encoding='utf-8') as f:
                input_text = f.read()
        else:
            input_text = args.input_text
        
        results = TextToPDF.text_to_pdf(input_text, args.output, args.font, args.font_size)
        print(f"✅ Created PDF: {results['output_file']} ({results['output_size']} bytes)")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
