# ocr.py - Simplified OCR implementation for Fast Mode
import logging
import os
import tempfile
import asyncio
from PIL import Image
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

async def perform_ocr(bot, file_id, file_name, user_id=None):
    """
    Perform OCR on Image or PDF.
    Since tesseract is not available in nixpkgs, we'll provide a 
    placeholder implementation that informs the user about the engine status
    or uses basic text extraction for PDFs.
    """
    try:
        file = await bot.get_file(file_id)
        input_path = tempfile.mktemp(suffix=os.path.splitext(file_name)[1])
        await bot.download_file(file.file_path, input_path)
        
        extracted_text = ""
        
        if file_name.lower().endswith('.pdf'):
            doc = fitz.open(input_path)
            for page in doc:
                extracted_text += page.get_text() # type: ignore
            doc.close()
        else:
            # For images, we'd normally use pytesseract
            # Informing user about the limitation in this environment
            extracted_text = "[System Note: OCR Engine (Tesseract) is currently unavailable in this environment. Image text extraction is limited. For PDFs, standard text was extracted.]"
            
        if not extracted_text.strip():
            extracted_text = "No text could be extracted from this document."
            
        # Create a text file with results
        output_path = tempfile.mktemp(suffix=".txt")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"--- OCR Result for {file_name} ---\n\n")
            f.write(extracted_text)
            
        os.remove(input_path)
        return output_path
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return None
