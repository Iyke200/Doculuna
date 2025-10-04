#!/usr/bin/env python3
"""
DocuLuna - Document Compression Utility
Tool 1: Compress Document (PDF, DOCX, TXT)
Production-ready implementation with CLI and API support.
"""

import argparse
import os
import io
import sys
import tempfile
import zipfile
import zlib
import logging
from pathlib import Path
from typing import Optional, Tuple
try:
    from PIL import Image
    from pikepdf import Pdf, Name, PdfImage, PdfError
except ImportError as e:
    print(f"❌ Dependency error: {e}. Please install required packages (e.g., 'pip install Pillow pikepdf').")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('doculuna.log')
    ]
)
logger = logging.getLogger(__name__)

class CompressionLevel:
    """Compression level constants and mapping."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    
    QUALITY_MAP = {
        LOW: 95,    # Minimal quality loss
        MEDIUM: 85, # Balanced quality/size
        HIGH: 60    # Maximum compression
    }
    
    ZIP_COMPRESS_MAP = {
        LOW: 6,
        MEDIUM: 9,
        HIGH: 9
    }

class FileValidator:
    """File validation and sanitization."""
    
    @staticmethod
    def validate_input_file(file_path: str, max_size: int) -> str:
        """
        Validate input file exists, is not a directory, and sanitize path.
        
        Args:
            file_path: Input file path
            max_size: Maximum allowed file size in bytes
            
        Returns:
            Normalized file path
            
        Raises:
            ValueError: If file is invalid
        """
        if not file_path or not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("File path must be a non-empty string")
        
        # Normalize path to prevent traversal attacks
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        
        if not os.path.isfile(normalized_path):
            raise ValueError(f"Input '{file_path}' is not a valid file")
        
        # Check file size
        file_size = os.path.getsize(normalized_path)
        if file_size > max_size:
            raise ValueError(f"File size exceeds {max_size/(1024**3):.1f}GB limit")
        
        # Check for null bytes in chunks
        try:
            with open(normalized_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    if b'\x00' in chunk:
                        raise ValueError("File contains null bytes - potential security issue")
        except (PermissionError, OSError) as e:
            logger.warning(f"Unable to read file for null byte check: {e}")
            raise ValueError(f"Cannot validate file due to read error: {str(e)}")
        
        logger.info(f"Validated input file: {normalized_path} ({file_size:,} bytes)")
        return normalized_path
    
    @staticmethod
    def validate_output_path(output_path: str, input_path: str, overwrite: bool = False) -> str:
        """
        Validate output path and check overwrite permissions.
        
        Args:
            output_path: Output file path
            input_path: Input file path (to validate extension)
            overwrite: Whether to allow overwriting existing files
            
        Returns:
            Normalized output path
            
        Raises:
            ValueError: If output path is invalid or overwrite not permitted
        """
        if not output_path or not isinstance(output_path, str) or not output_path.strip():
            raise ValueError("Output path must be a non-empty string")
        
        normalized_path = os.path.normpath(os.path.abspath(output_path))
        input_ext = FileValidator.get_file_extension(input_path)
        output_ext = FileValidator.get_file_extension(normalized_path)
        
        if input_ext != output_ext:
            raise ValueError(f"Output file extension ({output_ext}) must match input ({input_ext})")
        
        if os.path.exists(normalized_path) and not overwrite:
            raise ValueError(f"Output file '{output_path}' already exists. Use --force to overwrite.")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(normalized_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        return normalized_path
    
    @staticmethod
    def get_file_extension(file_path: str) -> str:
        """Get lowercase file extension."""
        return Path(file_path).suffix.lower()

class PDFCompressor:
    """PDF compression utility."""
    
    @staticmethod
    def compress_pdf(input_path: str, output_path: str, level: str) -> Tuple[int, int]:
        """
        Compress PDF file with specified compression level.
        
        Args:
            input_path: Input PDF file path
            output_path: Output PDF file path
            level: Compression level ('low', 'medium', 'high')
            
        Returns:
            Tuple of (original_size, compressed_size) in bytes
            
        Raises:
            ValueError: If PDF is invalid or unsupported
        """
        try:
            original_size = os.path.getsize(input_path)
            logger.info(f"Starting PDF compression: {input_path}")
            
            with Pdf.open(input_path) as pdf:
                quality = CompressionLevel.QUALITY_MAP[level]
                compress_images = level != CompressionLevel.LOW
                
                # Process images for compression (medium/high levels)
                if compress_images:
                    logger.debug("Processing images for compression")
                    for page_num, page in enumerate(pdf.pages, 1):
                        if '/Resources' in page:
                            resources = page['/Resources']
                            if '/XObject' in resources:
                                xobjects = resources['/XObject']
                                for name, xobj in xobjects.items():
                                    if xobj.Type == Name('/XObject') and xobj.Subtype == Name('/Image'):
                                        PDFCompressor._compress_pdf_image(xobj, quality, level)
                
                # Apply PDF optimization
                optimization_flags = {
                    CompressionLevel.LOW: {'compress_streams': True},
                    CompressionLevel.MEDIUM: {'compress_streams': True, 'object_streams': 'generate'},
                    CompressionLevel.HIGH: {'compress_streams': True, 'object_streams': 'generate', 'linearize': True}
                }
                
                pdf.save(
                    output_path,
                    **optimization_flags[level],
                    fix_metadata=False,
                    normalize_content=True
                )
                
            compressed_size = os.path.getsize(output_path)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
            
            logger.info(f"PDF compression complete: {original_size:,} → {compressed_size:,} bytes "
                       f"({compression_ratio:.1f}% reduction)")
            
            return original_size, compressed_size
            
        except PdfError as e:
            logger.error(f"PDF parsing error: {e}")
            raise ValueError(f"Invalid PDF file: {str(e)}")
        except Exception as e:
            logger.error(f"PDF compression error: {e}")
            raise ValueError(f"PDF compression failed: {str(e)}")
    
    @staticmethod
    def _compress_pdf_image(image_obj: PdfImage, quality: int, level: str):
        """Compress individual PDF image."""
        try:
            # Extract image as PIL Image
            pil_image = image_obj.as_pil_image()
            
            # Determine output format and compression settings
            img_buffer = io.BytesIO()
            is_jpeg = image_obj.filter == Name('/DCTDecode')
            
            if is_jpeg:
                # JPEG compression
                pil_image.save(
                    img_buffer,
                    format='JPEG',
                    quality=quality,
                    optimize=True,
                    progressive=True
                )
                image_data = img_buffer.getvalue()
                image_obj.replace(image_data, filter=Name('/DCTDecode'))
            else:
                # PNG or other format compression
                compress_level = 9 if level == CompressionLevel.HIGH else 6
                pil_image.save(
                    img_buffer,
                    format='PNG',
                    optimize=True,
                    compress_level=compress_level
                )
                image_obj.replace(img_buffer.getvalue(), filter=Name('/FlateDecode'))
                
        except Exception as e:
            logger.warning(f"Skipping image compression due to error: {e}")

class DOCXCompressor:
    """DOCX compression utility."""
    
    @staticmethod
    def compress_docx(input_path: str, output_path: str, level: str) -> Tuple[int, int]:
        """
        Compress DOCX file by optimizing images and re-archiving.
        
        Args:
            input_path: Input DOCX file path
            output_path: Output DOCX file path
            level: Compression level ('low', 'medium', 'high')
            
        Returns:
            Tuple of (original_size, compressed_size) in bytes
            
        Raises:
            ValueError: If DOCX is invalid
        """
        try:
            if not zipfile.is_zipfile(input_path):
                raise ValueError("Input is not a valid DOCX file")
            
            original_size = os.path.getsize(input_path)
            logger.info(f"Starting DOCX compression: {input_path}")
            
            quality = CompressionLevel.QUALITY_MAP[level]
            zip_compress_level = CompressionLevel.ZIP_COMPRESS_MAP[level]
            optimize_images = level != CompressionLevel.LOW
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract DOCX contents
                with zipfile.ZipFile(input_path, 'r') as zin:
                    zin.extractall(temp_dir)
                
                # Optimize images if needed
                if optimize_images:
                    DOCXCompressor._optimize_docx_images(
                        os.path.join(temp_dir, 'word', 'media'),
                        quality,
                        level
                    )
                
                # Re-archive with maximum compression
                DOCXCompressor._rearchive_docx(temp_dir, output_path, zip_compress_level)
            
            compressed_size = os.path.getsize(output_path)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
            
            logger.info(f"DOCX compression complete: {original_size:,} → {compressed_size:,} bytes "
                       f"({compression_ratio:.1f}% reduction)")
            
            return original_size, compressed_size
            
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid DOCX file: {e}")
            raise ValueError("Input is not a valid DOCX file")
        except Exception as e:
            logger.error(f"DOCX compression error: {e}")
            raise ValueError(f"DOCX compression failed: {str(e)}")
    
    @staticmethod
    def _optimize_docx_images(media_dir: str, quality: int, level: str):
        """Optimize images in DOCX media folder."""
        if not os.path.exists(media_dir):
            return
        
        for filename in os.listdir(media_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                img_path = os.path.join(media_dir, filename)
                try:
                    with Image.open(img_path) as img:
                        img_buffer = io.BytesIO()
                        original_format = img.format if img.format else 'PNG'
                        
                        # Preserve original format where possible
                        if filename.lower().endswith(('.jpg', '.jpeg')):
                            img.save(img_buffer, format='JPEG', quality=quality, optimize=True)
                        else:
                            compress_level = 9 if level == CompressionLevel.HIGH else 6
                            save_format = original_format if original_format in ('PNG', 'GIF') else 'PNG'
                            img.save(img_buffer, format=save_format, optimize=True, compress_level=compress_level)
                            if save_format != original_format:
                                logger.warning(f"Converted {filename} from {original_format} to {save_format}")
                        
                        # Write optimized image back
                        img_buffer.seek(0)
                        with open(img_path, 'wb') as f:
                            f.write(img_buffer.getvalue())
                        
                        logger.debug(f"Optimized image: {filename}")
                        
                except Exception as e:
                    logger.warning(f"Failed to optimize image {filename}: {e}")
    
    @staticmethod
    def _rearchive_docx(source_dir: str, output_path: str, compress_level: int):
        """Re-archive DOCX with specified compression level."""
        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=compress_level) as zout:
            for root, dirs, files in os.walk(source_dir):
                # Skip system files
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    if file.startswith('.'):
                        continue
                    
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, source_dir)
                    
                    try:
                        zout.write(full_path, arcname)
                    except Exception as e:
                        logger.warning(f"Skipping file {file} during archiving: {e}")

class TXTCompressor:
    """Text file compression utility."""
    
    @staticmethod
    def compress_txt(input_path: str, output_path: str, level: str) -> Tuple[int, int]:
        """
        Compress TXT file by cleaning whitespace and normalizing content.
        
        Args:
            input_path: Input TXT file path
            output_path: Output TXT file path
            level: Compression level ('low', 'medium', 'high')
            
        Returns:
            Tuple of (original_size, compressed_size) in bytes
        """
        original_size = os.path.getsize(input_path)
        logger.info(f"Starting TXT compression: {input_path}")
        
        try:
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as fin:
                content = fin.read()
            
            original_ends_with_nl = content.endswith('\n')
            
            # Apply compression based on level
            if level == CompressionLevel.LOW:
                processed_content = content
            elif level == CompressionLevel.MEDIUM:
                # Remove trailing whitespace, preserve line breaks
                processed_content = '\n'.join(line.rstrip() for line in content.splitlines())
                processed_content += '\n' if original_ends_with_nl else ''
            elif level == CompressionLevel.HIGH:
                # Aggressive whitespace normalization, remove empty lines
                lines = []
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped:
                        normalized = ' '.join(stripped.split())
                        lines.append(normalized)
                processed_content = '\n'.join(lines)
                processed_content += '\n' if original_ends_with_nl else ''
            else:
                raise ValueError(f"Invalid compression level: {level}")
            
            # Write compressed content
            with open(output_path, 'w', encoding='utf-8') as fout:
                fout.write(processed_content)
            
            compressed_size = os.path.getsize(output_path)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
            
            logger.info(f"TXT compression complete: {original_size:,} → {compressed_size:,} bytes "
                       f"({compression_ratio:.1f}% reduction)")
            
            return original_size, compressed_size
            
        except UnicodeDecodeError:
            logger.error("File is not valid UTF-8 text")
            raise ValueError("Input file is not valid UTF-8 text")
        except Exception as e:
            logger.error(f"TXT compression error: {e}")
            raise ValueError(f"TXT compression failed: {str(e)}")

class DocumentCompressor:
    """Main document compression orchestrator."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
    
    @staticmethod
    def compress_document(
        input_path: str,
        output_path: str,
        level: str = CompressionLevel.MEDIUM,
        force_overwrite: bool = False,
        max_size: int = 2 * 1024 * 1024 * 1024
    ) -> dict:
        """
        Main function to compress document based on file type.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            level: Compression level ('low', 'medium', 'high')
            force_overwrite: Allow overwriting existing output file
            max_size: Maximum allowed input file size in bytes
            
        Returns:
            Dictionary with compression results
            
        Raises:
            ValueError: For invalid inputs or unsupported formats
        """
        # Validate inputs
        input_path = FileValidator.validate_input_file(input_path, max_size)
        output_path = FileValidator.validate_output_path(output_path, input_path, force_overwrite)
        
        # Validate compression level
        if level not in CompressionLevel.QUALITY_MAP:
            raise ValueError(f"Invalid compression level: {level}. Choose from: {list(CompressionLevel.QUALITY_MAP.keys())}")
        
        # Get file extension
        extension = FileValidator.get_file_extension(input_path)
        if extension not in DocumentCompressor.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {extension}. "
                           f"Supported formats: {', '.join(DocumentCompressor.SUPPORTED_EXTENSIONS)}")
        
        logger.info(f"Compressing {extension} file with {level} compression")
        
        # Dispatch to appropriate compressor
        try:
            if extension == '.pdf':
                original_size, compressed_size = PDFCompressor.compress_pdf(input_path, output_path, level)
            elif extension == '.docx':
                original_size, compressed_size = DOCXCompressor.compress_docx(input_path, output_path, level)
            elif extension == '.txt':
                original_size, compressed_size = TXTCompressor.compress_txt(input_path, output_path, level)
            
            # Calculate results
            compression_ratio = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
            
            results = {
                'success': True,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': round(compression_ratio, 2),
                'level': level,
                'format': extension,
                'input_file': input_path,
                'output_file': output_path
            }
            
            logger.info(f"Compression successful: {compression_ratio:.1f}% reduction")
            return results
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            raise ValueError(f"Document compression failed: {str(e)}")

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DocuLuna Document Compressor - Production Tool 1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python doculuna.py compress input.pdf output.pdf --level=high --force --max-size=4
  python doculuna.py compress document.docx compressed.docx --level=medium
  python doculuna.py compress report.txt optimized.txt --level=low --verbose
        """
    )
    
    parser.add_argument('command', choices=['compress'], help="Command to execute")
    parser.add_argument('input', help="Input file path")
    parser.add_argument('output', help="Output file path")
    parser.add_argument(
        '--level',
        choices=list(CompressionLevel.QUALITY_MAP.keys()),
        default=CompressionLevel.MEDIUM,
        help="Compression level (default: medium)"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force overwrite of existing output file"
    )
    parser.add_argument(
        '--max-size',
        type=float,
        default=2.0,
        help="Maximum input file size in GB (default: 2.0)"
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Convert max_size from GB to bytes
    max_size_bytes = int(args.max_size * 1024 * 1024 * 1024)
    
    if args.command == 'compress':
        try:
            results = DocumentCompressor.compress_document(
                input_path=args.input,
                output_path=args.output,
                level=args.level,
                force_overwrite=args.force,
                max_size=max_size_bytes
            )
            
            # Print summary
            print(f"\n{'='*50}")
            print("DOCULUNA COMPRESSION SUMMARY")
            print(f"{'='*50}")
            print(f"Input:  {results['input_file']}")
            print(f"Output: {results['output_file']}")
            print(f"Format: {results['format'].upper()}")
            print(f"Level:  {results['level'].upper()}")
            print(f"Original size: {results['original_size']:,} bytes")
            print(f"Compressed size: {results['compressed_size']:,} bytes")
            print(f"Size reduction: {results['compression_ratio']:.1f}%")
            print(f"{'='*50}")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
