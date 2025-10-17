#!/usr/bin/env python3
"""DocuLuna - PDF Splitting Utility"""

import argparse
import os
import logging
from typing import Dict
from pikepdf import Pdf, PdfError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFSplitter:
    @staticmethod
    def split_pdf(input_path: str, output_dir: str, pages_per_file: int = 1, prefix: str = "split") -> Dict:
        """Split PDF into multiple files."""
        # Validate pages_per_file first (before any operations)
        if not isinstance(pages_per_file, int) or pages_per_file < 1:
            raise ValueError(f"pages_per_file must be a positive integer, got: {pages_per_file}")
        
        if not os.path.isfile(input_path):
            raise ValueError(f"Input file not found: {input_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        output_files = []
        
        try:
            with Pdf.open(input_path) as pdf:
                total_pages = len(pdf.pages)
                num_files = (total_pages + pages_per_file - 1) // pages_per_file
                
                for file_num in range(num_files):
                    output_pdf = Pdf.new()
                    start_page = file_num * pages_per_file
                    end_page = min(start_page + pages_per_file, total_pages)
                    
                    for page_num in range(start_page, end_page):
                        output_pdf.pages.append(pdf.pages[page_num])
                    
                    output_filename = f"{prefix}_{file_num + 1:03d}.pdf"
                    output_path = os.path.join(output_dir, output_filename)
                    output_pdf.save(output_path)
                    output_files.append(output_path)
            
            return {
                'success': True,
                'total_pages': total_pages,
                'output_files': output_files,
                'num_files': len(output_files)
            }
        except PdfError as e:
            logger.error(f"PDF error: {e}")
            raise ValueError(f"Invalid PDF file: {str(e)}")

async def handle_split_pdf_callback(callback, state=None):
    """Handle Split PDF callback from menu."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    try:
        text = (
            "✂️ PDF Splitter\n\n"
            "Please send me a PDF file and I'll help you split it into separate pages or sections.\n\n"
            "✅ Split by pages\n"
            "✅ Custom page ranges\n"
            "✅ Multiple output files\n\n"
            "Just upload your PDF file now 👇"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Back to Tools", callback_data="process_document")
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in Split PDF callback: {e}")
        await callback.answer("Error", show_alert=True)

def register_split_pdf(dp):
    """Register Split PDF handler."""
    dp.callback_query.register(handle_split_pdf_callback, lambda c: c.data == "split_pdf")

def main():
    parser = argparse.ArgumentParser(description='DocuLuna PDF Splitter')
    parser.add_argument('input', help='Input PDF file')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--pages-per-file', '-p', type=int, default=1)
    parser.add_argument('--prefix', default='split')
    args = parser.parse_args()
    
    try:
        results = PDFSplitter.split_pdf(args.input, args.output_dir, args.pages_per_file, args.prefix)
        print(f"✅ Created {results['num_files']} files")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
