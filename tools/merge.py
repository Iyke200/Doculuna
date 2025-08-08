
import logging
import os
import PyPDF2

logger = logging.getLogger(__name__)

async def merge_pdfs(file_paths, output_path=None):
    """Merge multiple PDF files."""
    try:
        if not output_path:
            output_path = "temp/merged.pdf"
        
        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)
        
        writer = PyPDF2.PdfWriter()
        
        for file_path in file_paths:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    writer.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"Successfully merged {len(file_paths)} files into {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error merging PDFs: {e}")
        return None
