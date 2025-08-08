
import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)

async def convert_image_to_pdf(file_path, output_path=None):
    """Convert image to PDF."""
    try:
        if not output_path:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = f"temp/{base_name}.pdf"
        
        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)
        
        # Open and convert image
        image = Image.open(file_path)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save as PDF
        image.save(output_path, "PDF")
        
        logger.info(f"Successfully converted {file_path} to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error converting image to PDF: {e}")
        return None
