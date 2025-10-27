import os
import logging
from pathlib import Path
try:
    import fitz
except ImportError:
    fitz = None

try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    Document = None

logger = logging.getLogger(__name__)

def add_pdf_watermark(pdf_path: str, watermark_text: str = "Processed with DocuLuna - Upgrade for Watermark-Free"):
    """Add watermark to PDF file for free users."""
    if not fitz:
        logger.warning("PyMuPDF not available, skipping PDF watermark")
        return
    
    try:
        doc = fitz.open(pdf_path)
        
        for page in doc:
            text_rect = page.rect
            watermark_rect = fitz.Rect(
                text_rect.width * 0.1,
                text_rect.height * 0.95,
                text_rect.width * 0.9,
                text_rect.height * 0.98
            )
            
            page.insert_textbox(
                watermark_rect,
                watermark_text,
                fontsize=8,
                color=(0.7, 0.7, 0.7),
                align=fitz.TEXT_ALIGN_CENTER
            )
        
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        logger.info(f"Added watermark to PDF: {pdf_path}")
        
    except Exception as e:
        logger.error(f"Error adding PDF watermark: {e}", exc_info=True)

def add_docx_watermark(docx_path: str, watermark_text: str = "Processed with DocuLuna - Upgrade for Watermark-Free"):
    """Add watermark to DOCX file for free users."""
    if not Document:
        logger.warning("python-docx not available, skipping DOCX watermark")
        return
    
    try:
        doc = Document(docx_path)
        
        section = doc.sections[0]
        footer = section.footer
        
        if footer.paragraphs:
            paragraph = footer.paragraphs[0]
        else:
            paragraph = footer.add_paragraph()
        
        paragraph.text = watermark_text
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        run = paragraph.runs[0]
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(128, 128, 128)
        run.font.italic = True
        
        doc.save(docx_path)
        logger.info(f"Added watermark to DOCX: {docx_path}")
        
    except Exception as e:
        logger.error(f"Error adding DOCX watermark: {e}", exc_info=True)
