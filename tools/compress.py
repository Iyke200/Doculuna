
import logging
import os
import zipfile
from PIL import Image
import PyPDF2

logger = logging.getLogger(__name__)

async def compress_file(file_path, output_path=None, compression_quality=85):
    """Compress various file types."""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if not output_path:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = f"temp/{base_name}_compressed{file_ext}"
        
        # Ensure temp directory exists
        os.makedirs("temp", exist_ok=True)
        
        if file_ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            # Compress image
            with Image.open(file_path) as img:
                img.save(output_path, optimize=True, quality=compression_quality)
        
        elif file_ext == '.pdf':
            # Compress PDF (basic compression)
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                writer = PyPDF2.PdfWriter()
                
                for page in reader.pages:
                    writer.add_page(page)
                
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
        
        else:
            # Generic compression using ZIP
            zip_path = f"{output_path}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, os.path.basename(file_path))
            output_path = zip_path
        
        logger.info(f"Successfully compressed {file_path} to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error compressing file: {e}")
        return None
