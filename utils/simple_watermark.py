"""
Simple watermarking utility for DocuLuna free users.
Adds watermarks to PDF and DOCX files.
"""
import logging
import fitz  # PyMuPDF
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

WATERMARK_TEXT = "DocuLuna Free"

def add_pdf_watermark(pdf_path: str) -> str:
    """
    Add watermark to PDF file.
    
    Args:
        pdf_path: Path to input PDF file
        
    Returns:
        Path to watermarked PDF (same as input)
    """
    try:
        pdf_document = fitz.open(pdf_path)
        
        for page in pdf_document:
            text_rect = page.rect
            
            text = fitz.TextWriter(page.rect)
            text.fill_textbox(
                text_rect,
                WATERMARK_TEXT,
                fontsize=48,
                color=(0.8, 0.8, 0.8),
                align=fitz.TEXT_ALIGN_CENTER
            )
            
            text.write_text(page, opacity=0.3, rotate=45)
        
        pdf_document.save(pdf_path, incremental=True, encryption=False)
        pdf_document.close()
        
        logger.info(f"Added watermark to PDF: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"Failed to add PDF watermark: {e}")
        return pdf_path

def add_docx_watermark(docx_path: str) -> str:
    """
    Add watermark to DOCX file.
    
    Args:
        docx_path: Path to input DOCX file
        
    Returns:
        Path to watermarked DOCX (same as input)
    """
    try:
        doc = Document(docx_path)
        
        for section in doc.sections:
            header = section.header
            
            paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            paragraph.text = WATERMARK_TEXT
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            run = paragraph.runs[0] if paragraph.runs else paragraph.add_run(WATERMARK_TEXT)
            font = run.font
            font.size = Pt(48)
            font.color.rgb = RGBColor(200, 200, 200)
            font.bold = True
        
        doc.save(docx_path)
        
        logger.info(f"Added watermark to DOCX: {docx_path}")
        return docx_path
        
    except Exception as e:
        logger.error(f"Failed to add DOCX watermark: {e}")
        return docx_path
