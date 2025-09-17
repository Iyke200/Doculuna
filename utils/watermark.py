# utils/watermark.py - Professional Watermarking System
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

def add_pdf_watermark(pdf_path: str):
    """Add watermark to PDF file for free users."""
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Add subtle watermark
            watermark_text = "DocuLuna Free - Upgrade for watermark-free files"
            
            # Add watermark at top
            page.insert_text(
                (50, 50),
                watermark_text,
                fontsize=10,
                color=(0.7, 0.7, 0.7),  # Light gray
                overlay=False,
            )
            
            # Add footer watermark
            page.insert_text(
                (50, page.rect.height - 30),
                "Get premium at DocuLuna Bot",
                fontsize=8,
                color=(0.8, 0.8, 0.8),  # Even lighter
                overlay=False,
            )
        
        doc.save(pdf_path)
        doc.close()
        logger.info(f"Watermark added to {pdf_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding watermark to {pdf_path}: {e}")
        return False