#!/usr/bin/env python3
"""DocuLuna - PDF Splitting Utility"""

import argparse
import os
import logging
from typing import Dict, Optional
from pikepdf import Pdf, PdfError, Outline, OutlineItem

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
                if total_pages == 0:
                    raise ValueError("PDF contains no pages")
                
                num_files = (total_pages + pages_per_file - 1) // pages_per_file
                
                for file_num in range(num_files):
                    output_pdf = Pdf.new()
                    
                    # Preserve metadata from original PDF
                    if hasattr(pdf, 'docinfo'):
                        output_pdf.docinfo = pdf.docinfo.copy()
                    if '/Metadata' in pdf.Root:
                        output_pdf.Root['/Metadata'] = output_pdf.copy_foreign(pdf.Root['/Metadata'])
                    
                    # Preserve AcroForm (forms) if present, to keep form fields functional
                    if '/AcroForm' in pdf.Root:
                        output_pdf.Root['/AcroForm'] = output_pdf.copy_foreign(pdf.Root['/AcroForm'])
                    
                    start_page = file_num * pages_per_file  # 0-based index
                    end_page = min(start_page + pages_per_file, total_pages)
                    
                    # Copy pages using copy_foreign to preserve resources (images, fonts, etc.)
                    for page_num in range(start_page, end_page):
                        copied_page = output_pdf.copy_foreign(pdf.pages[page_num])
                        output_pdf.pages.append(copied_page)
                    
                    # Preserve and adjust bookmarks (outlines) within the page range
                    if '/Outlines' in pdf.Root:
                        with Outline(output_pdf) as out_outline:
                            with Outline(pdf) as in_outline:
                                for item in in_outline.root:
                                    cloned_item = PDFSplitter._clone_outline_item(item, start_page, end_page, start_page)
                                    if cloned_item:
                                        out_outline.root.append(cloned_item)
                    
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
    
    @staticmethod
    def _clone_outline_item(item: OutlineItem, start_page: int, end_page: int, page_offset: int) -> Optional[OutlineItem]:
        """
        Recursively clone outline item if it or its children fall within the page range,
        adjusting page destinations accordingly.
        
        Args:
            item: The outline item to clone.
            start_page: Start of the page range (0-based).
            end_page: End of the page range (exclusive).
            page_offset: Offset to subtract from page destinations (start_page).
        
        Returns:
            Cloned OutlineItem if relevant, else None.
        """
        dest = item.destination
        dest_page = None
        if dest is not None:
            dest = list(dest)
            if len(dest) > 0 and isinstance(dest[0], int):
                dest_page = dest[0]
        
        # Skip if destination is outside range (but check children first)
        if dest_page is not None and not (start_page <= dest_page < end_page):
            dest = None  # Will check children
        
        cloned_item = OutlineItem(item.title)
        if dest is not None:
            dest[0] -= page_offset
            cloned_item.destination = dest
        if item.action is not None:
            cloned_item.action = item.action
        
        # Recursively clone children
        has_valid_children = False
        for child in item.children:
            cloned_child = PDFSplitter._clone_outline_item(child, start_page, end_page, page_offset)
            if cloned_child:
                cloned_item.children.append(cloned_child)
                has_valid_children = True
        
        # Return cloned item if it has a valid destination or valid children
        if dest is not None or has_valid_children:
            return cloned_item
        return None

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
