# utils/watermark.py
"""
DocuLuna Watermark Utility

Professional watermarking for images and PDFs with text/logo overlay.
Supports transparency, positioning, scaling, rotation, and batch processing.

Usage:
    from utils import watermark_utils
    
    # Initialize
    watermark_manager = watermark_utils.WatermarkManager()
    
    # Text watermark
    watermarked_image = await watermark_manager.add_text_watermark(
        image_path, text="Confidential", position='bottom-right'
    )
    
    # Logo watermark
    watermarked_pdf = await watermark_manager.add_logo_watermark(
        pdf_path, logo_path, opacity=0.3
    )
    
    # Batch processing
    results = await watermark_manager.batch_watermark(documents, config)
"""

import logging
import io
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import fitz  # PyMuPDF for PDF handling
import base64
from io import BytesIO

# Local imports
from ..error_handler import ErrorHandler, ErrorContext  # type: ignore
from ..stats import stats_tracker  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class WatermarkConfig:
    """Watermark configuration."""
    text: Optional[str] = None
    logo_path: Optional[Union[str, Path]] = None
    logo_data: Optional[bytes] = None
    position: str = "center"  # top-left, top-center, top-right, center, bottom-left, bottom-right
    opacity: float = 0.5  # 0.0-1.0
    font_size: int = 48
    font_color: Tuple[int, int, int] = (255, 255, 255)  # RGB white
    font_family: str = "arial"  # Font family name
    rotation: int = 45  # Degrees
    scale: float = 0.5  # Scale relative to image size
    padding: int = 20  # Padding from edges
    repeat: bool = False  # Repeat watermark across document
    page_range: Optional[List[int]] = None  # Specific pages for PDFs

class WatermarkType(Enum):
    """Types of watermarks supported."""
    TEXT = "text"
    LOGO = "logo"
    BOTH = "both"

class WatermarkError(Exception):
    """Custom exception for watermark operations."""
    pass

class WatermarkManager:
    """
    Professional watermarking system for images and PDFs.
    
    Features:
        - Text and logo watermarking with transparency
        - Multiple positioning options (9 positions)
        - Rotation, scaling, and opacity control
        - Font customization and color options
        - Batch processing for multiple files
        - PDF multi-page support with selective page ranges
        - Image format preservation
    
    Args:
        default_config: Default watermark configuration
        max_image_size_mb: Maximum image size for processing
        supported_formats: Supported input/output formats
        error_handler: Error handler instance
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        'font_family': 'arial',
        'font_size': 48,
        'font_color': (255, 255, 255),  # White
        'opacity': 0.3,
        'rotation': 45,
        'scale': 0.3,
        'padding': 50,
        'repeat': False,
        'quality': 95  # JPEG quality
    }
    
    # Supported formats
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp'}
    SUPPORTED_PDF_FORMATS = {'.pdf'}
    OUTPUT_FORMATS = {'.png', '.jpg', '.pdf'}
    
    # Position mapping for 9-grid layout
    POSITIONS = {
        'top-left': (0.1, 0.1),
        'top-center': (0.5, 0.1),
        'top-right': (0.9, 0.1),
        'center-left': (0.1, 0.5),
        'center': (0.5, 0.5),
        'center-right': (0.9, 0.5),
        'bottom-left': (0.1, 0.9),
        'bottom-center': (0.5, 0.9),
        'bottom-right': (0.9, 0.9)
    }
    
    def __init__(
        self,
        default_config: Optional[Dict[str, Any]] = None,
        max_image_size_mb: int = 50,
        error_handler: Optional[ErrorHandler] = None
    ):
        self.default_config = default_config or self.DEFAULT_CONFIG.copy()
        self.max_image_size = max_image_size_mb * 1024 * 1024
        self.error_handler = error_handler or ErrorHandler()
        
        # Font cache
        self._font_cache = {}
        
        # Supported formats validation
        self.supported_formats = self.SUPPORTED_IMAGE_FORMATS.union(self.SUPPORTED_PDF_FORMATS)
        
        logger.info("WatermarkManager initialized", extra={
            'max_size_mb': max_image_size_mb,
            'supported_formats': len(self.supported_formats),
            'default_position': self.default_config.get('position', 'center'),
            'default_opacity': self.default_config.get('opacity', 0.5)
        })
    
    async def add_text_watermark(
        self,
        file_path: Union[str, Path, bytes],
        text: str,
        config: Optional[WatermarkConfig] = None,
        output_format: str = '.png'
    ) -> bytes:
        """
        Add text watermark to image or PDF.
        
        Args:
            file_path: Input file path or bytes
            text: Watermark text
            config: Watermark configuration
            output_format: Output format (default: .png)
            
        Returns:
            Watermarked file as bytes
            
        Raises:
            WatermarkError: If processing fails
            ValueError: If invalid input format or configuration
        """
        start_time = time.time()
        request_id = f"wm_text_{int(time.time()*1000)}_{hash(text) % 10000:04d}"
        
        try:
            logger.info("Starting text watermark", extra={
                'request_id': request_id,
                'input_type': type(file_path).__name__,
                'text_length': len(text),
                'output_format': output_format
            })
            
            # Validate input
            input_data, input_type = await self._load_input(file_path)
            if not input_data:
                raise ValueError(f"Invalid input: {type(file_path)}")
            
            # Determine processing method
            if input_type in self.SUPPORTED_IMAGE_FORMATS:
                # Image processing
                watermarked = await self._add_text_to_image(
                    input_data,
                    text,
                    config or WatermarkConfig(text=text)
                )
            elif input_type == '.pdf':
                # PDF processing
                watermarked = await self._add_text_to_pdf(
                    input_data,
                    text,
                    config or WatermarkConfig(text=text)
                )
            else:
                raise ValueError(f"Unsupported format: {input_type}")
            
            # Validate output format
            if output_format not in self.OUTPUT_FORMATS:
                output_format = '.png'  # Default
            
            # Convert if needed
            if output_format != input_type:
                watermarked = await self._convert_format(watermarked, input_type, output_format)
            
            processing_time = time.time() - start_time
            
            logger.info("Text watermark completed", extra={
                'request_id': request_id,
                'input_type': input_type,
                'output_format': output_format,
                'input_size': len(input_data),
                'output_size': len(watermarked),
                'processing_time_s': round(processing_time, 3)
            })
            
            return watermarked
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Text watermark failed", exc_info=True, extra={
                'request_id': request_id,
                'input_type': getattr(file_path, 'suffix', type(file_path).__name__),
                'error': str(e),
                'processing_time_s': round(processing_time, 3)
            })
            
            # Use error handler if available
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(operation='add_text_watermark'),
                extra_data={
                    'input_type': input_type if 'input_type' in locals() else None,
                    'text_length': len(text),
                    'output_format': output_format
                }
            )
            
            raise WatermarkError(f"Text watermarking failed: {str(e)}")
    
    async def add_logo_watermark(
        self,
        file_path: Union[str, Path, bytes],
        logo_path: Union[str, Path, bytes],
        config: Optional[WatermarkConfig] = None,
        output_format: str = '.png'
    ) -> bytes:
        """
        Add logo watermark to image or PDF.
        
        Args:
            file_path: Input file path or bytes
            logo_path: Logo file path or bytes
            config: Watermark configuration
            output_format: Output format (default: .png)
            
        Returns:
            Watermarked file as bytes
        """
        start_time = time.time()
        request_id = f"wm_logo_{int(time.time()*1000)}_{hash(str(logo_path)) % 10000:04d}"
        
        try:
            logger.info("Starting logo watermark", extra={
                'request_id': request_id,
                'input_type': type(file_path).__name__,
                'logo_type': type(logo_path).__name__,
                'output_format': output_format
            })
            
            # Load logo
            logo_data = await self._load_logo(logo_path)
            if not logo_data:
                raise ValueError("Invalid logo file")
            
            # Load input file
            input_data, input_type = await self._load_input(file_path)
            if not input_data:
                raise ValueError(f"Invalid input file: {type(file_path)}")
            
            # Process based on type
            if input_type in self.SUPPORTED_IMAGE_FORMATS:
                watermarked = await self._add_logo_to_image(
                    input_data,
                    logo_data,
                    config or WatermarkConfig(logo_data=logo_data)
                )
            elif input_type == '.pdf':
                watermarked = await self._add_logo_to_pdf(
                    input_data,
                    logo_data,
                    config or WatermarkConfig(logo_data=logo_data)
                )
            else:
                raise ValueError(f"Unsupported format: {input_type}")
            
            # Convert format if needed
            if output_format != input_type:
                watermarked = await self._convert_format(watermarked, input_type, output_format)
            
            processing_time = time.time() - start_time
            
            logger.info("Logo watermark completed", extra={
                'request_id': request_id,
                'input_type': input_type,
                'output_format': output_format,
                'input_size': len(input_data),
                'logo_size': len(logo_data),
                'output_size': len(watermarked),
                'processing_time_s': round(processing_time, 3)
            })
            
            return watermarked
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Logo watermark failed", exc_info=True, extra={
                'request_id': request_id,
                'input_type': getattr(file_path, 'suffix', type(file_path).__name__),
                'logo_type': type(logo_path).__name__,
                'error': str(e),
                'processing_time_s': round(processing_time, 3)
            })
            
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(operation='add_logo_watermark'),
                extra_data={
                    'input_type': input_type if 'input_type' in locals() else None,
                    'logo_type': type(logo_path).__name__
                }
            )
            
            raise WatermarkError(f"Logo watermarking failed: {str(e)}")
    
    async def add_watermark(
        self,
        file_path: Union[str, Path, bytes],
        config: WatermarkConfig,
        watermark_type: WatermarkType = WatermarkType.BOTH,
        output_format: str = '.png'
    ) -> bytes:
        """
        Add combined text and logo watermark.
        
        Args:
            file_path: Input file
            config: Watermark configuration (text, logo, position, etc.)
            watermark_type: Type of watermark (text, logo, both)
            output_format: Output format
            
        Returns:
            Watermarked file bytes
        """
        start_time = time.time()
        request_id = f"wm_combined_{int(time.time()*1000)}_{hash(str(config)) % 10000:04d}"
        
        try:
            logger.info("Starting combined watermark", extra={
                'request_id': request_id,
                'input_type': type(file_path).__name__,
                'watermark_type': watermark_type.value,
                'has_text': bool(config.text),
                'has_logo': bool(config.logo_path or config.logo_data),
                'output_format': output_format
            })
            
            # Load input
            input_data, input_type = await self._load_input(file_path)
            if not input_data:
                raise ValueError("Invalid input file")
            
            # Process in stages
            watermarked = input_data
            
            if watermark_type in [WatermarkType.TEXT, WatermarkType.BOTH] and config.text:
                watermarked = await self.add_text_watermark(
                    BytesIO(watermarked),
                    config.text,
                    WatermarkConfig(**asdict(config)),
                    output_format
                )
            
            if watermark_type in [WatermarkType.LOGO, WatermarkType.BOTH] and (config.logo_path or config.logo_data):
                logo_data = config.logo_data or await self._load_logo(config.logo_path)
                if logo_data:
                    watermarked = await self.add_logo_watermark(
                        BytesIO(watermarked),
                        logo_data,
                        WatermarkConfig(**asdict(config)),
                        output_format
                    )
            
            processing_time = time.time() - start_time
            
            logger.info("Combined watermark completed", extra={
                'request_id': request_id,
                'input_type': input_type,
                'output_format': output_format,
                'input_size': len(input_data),
                'output_size': len(watermarked),
                'processing_time_s': round(processing_time, 3)
            })
            
            return watermarked
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Combined watermark failed", exc_info=True, extra={
                'request_id': request_id,
                'input_type': getattr(file_path, 'suffix', type(file_path).__name__),
                'watermark_type': watermark_type.value,
                'error': str(e),
                'processing_time_s': round(processing_time, 3)
            })
            
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(operation='add_combined_watermark'),
                extra_data={
                    'watermark_type': watermark_type.value,
                    'input_type': input_type if 'input_type' in locals() else None
                }
            )
            
            raise WatermarkError(f"Watermarking failed: {str(e)}")
    
    async def batch_watermark(
        self,
        files: List[Union[str, Path, Tuple[str, bytes]]],
        config: WatermarkConfig,
        watermark_type: WatermarkType = WatermarkType.TEXT,
        output_dir: Optional[Union[str, Path]] = None,
        parallel_limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Batch watermark multiple files with concurrency control.
        
        Args:
            files: List of file paths or (path, content) tuples
            config: Watermark configuration
            watermark_type: Watermark type
            output_dir: Output directory (default: same as input)
            parallel_limit: Maximum concurrent operations
            
        Returns:
            List of results with success/failure status
        """
        start_time = time.time()
        batch_id = f"wm_batch_{int(time.time()*1000)}_{len(files):03d}"
        
        try:
            logger.info("Starting batch watermark", extra={
                'batch_id': batch_id,
                'file_count': len(files),
                'watermark_type': watermark_type.value,
                'parallel_limit': parallel_limit,
                'output_dir': str(output_dir) if output_dir else 'input_dir'
            })
            
            # Validate files
            valid_files = []
            for i, file_item in enumerate(files):
                try:
                    if isinstance(file_item, (str, Path)):
                        file_path = Path(file_item)
                        if not file_path.exists():
                            logger.warning(f"File not found: {file_path}", extra={'batch_id': batch_id, 'index': i})
                            continue
                        
                        # Read file content
                        async with aiofiles.open(file_path, 'rb') as f:
                            content = await f.read()
                        
                        valid_files.append((str(file_path), content, file_path.suffix.lower()))
                        
                    elif isinstance(file_item, tuple) and len(file_item) == 2:
                        file_path, content = file_item
                        suffix = Path(file_path).suffix.lower() if file_path else '.bin'
                        valid_files.append((str(file_path), content, suffix))
                    
                    else:
                        logger.warning(f"Invalid file format at index {i}", extra={'batch_id': batch_id})
                        continue
                        
                except Exception as e:
                    logger.error(f"Failed to validate file {i}", extra={'error': str(e), 'batch_id': batch_id})
                    continue
            
            if not valid_files:
                raise ValueError("No valid files for processing")
            
            logger.debug("Batch files validated", extra={
                'batch_id': batch_id,
                'valid_count': len(valid_files),
                'original_count': len(files)
            })
            
            # Process files with semaphore for concurrency control
            semaphore = asyncio.Semaphore(parallel_limit)
            
            async def process_single_file(file_info):
                async with semaphore:
                    file_path, content, file_type = file_info
                    try:
                        # Check supported format
                        if file_type not in self.supported_formats:
                            return {
                                'file_path': file_path,
                                'success': False,
                                'error': f"Unsupported format: {file_type}",
                                'output_path': None,
                                'processing_time_s': 0
                            }
                        
                        start_time = time.time()
                        
                        # Process file
                        if file_type in self.SUPPORTED_IMAGE_FORMATS:
                            watermarked = await self.add_watermark(
                                BytesIO(content),
                                config,
                                watermark_type,
                                file_type  # Preserve original format
                            )
                        elif file_type == '.pdf':
                            watermarked = await self.add_watermark(
                                BytesIO(content),
                                config,
                                watermark_type,
                                '.pdf'
                            )
                        else:
                            watermarked = content
                        
                        processing_time = time.time() - start_time
                        
                        # Save output
                        output_path = None
                        if output_dir:
                            output_filename = Path(file_path).name
                            if watermark_type == WatermarkType.BOTH:
                                output_filename = output_filename.rsplit('.', 1)[0] + '_watermarked.' + file_type.lstrip('.')
                            output_path = Path(output_dir) / output_filename
                            async with aiofiles.open(output_path, 'wb') as f:
                                await f.write(watermarked)
                            
                            # Set secure permissions
                            os.chmod(str(output_path), 0o644)
                        
                        return {
                            'file_path': file_path,
                            'success': True,
                            'output_path': str(output_path) if output_path else None,
                            'input_size': len(content),
                            'output_size': len(watermarked),
                            'processing_time_s': round(processing_time, 3),
                            'format': file_type
                        }
                        
                    except Exception as e:
                        processing_time = time.time() - start_time
                        await self.error_handler.handle_error(
                            e,
                            context=ErrorContext(operation=f"batch_watermark_{file_path}"),
                            extra_data={'batch_id': batch_id, 'file_type': file_type}
                        )
                        
                        return {
                            'file_path': file_path,
                            'success': False,
                            'error': str(e),
                            'output_path': None,
                            'processing_time_s': round(processing_time, 3),
                            'format': file_type
                        }
            
            # Process all files
            tasks = [process_single_file(file_info) for file_info in valid_files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Batch processing exception", extra={
                        'batch_id': batch_id,
                        'error': str(result)
                    })
                    final_results.append({
                        'success': False,
                        'error': f"Processing error: {str(result)}",
                        'output_path': None
                    })
                else:
                    final_results.append(result)
            
            # Calculate batch statistics
            successful = sum(1 for r in final_results if r['success'])
            total_size_in = sum(r['input_size'] for r in final_results if r.get('input_size'))
            total_size_out = sum(r['output_size'] for r in final_results if r.get('output_size'))
            
            batch_time = time.time() - start_time
            
            logger.info("Batch watermark completed", extra={
                'batch_id': batch_id,
                'total_files': len(final_results),
                'successful': successful,
                'total_size_in_mb': round(total_size_in / (1024*1024), 2),
                'total_size_out_mb': round(total_size_out / (1024*1024), 2),
                'batch_time_s': round(batch_time, 3),
                'avg_time_per_file_s': round(batch_time / len(final_results), 3)
            })
            
            return final_results
            
        except Exception as e:
            batch_time = time.time() - start_time
            logger.error("Batch watermark failed", exc_info=True, extra={
                'batch_id': batch_id,
                'file_count': len(files),
                'error': str(e),
                'batch_time_s': round(batch_time, 3)
            })
            
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(operation='batch_watermark'),
                extra_data={
                    'batch_id': batch_id,
                    'file_count': len(files),
                    'parallel_limit': parallel_limit
                }
            )
            
            raise WatermarkError(f"Batch processing failed: {str(e)}")
    
    async def _load_input(self, file_input: Union[str, Path, bytes]) -> Tuple[bytes, str]:
        """Load and validate input file."""
        try:
            if isinstance(file_input, (str, Path)):
                file_path = Path(file_input)
                
                if not file_path.exists():
                    raise ValueError(f"File not found: {file_path}")
                
                if file_path.stat().st_size > self.max_image_size:
                    raise ValueError(f"File too large: {file_path.stat().st_size} bytes")
                
                async with aiofiles.open(file_path, 'rb') as f:
                    content = await f.read()
                
                file_type = file_path.suffix.lower()
                
            elif isinstance(file_input, bytes):
                content = file_input
                if len(content) > self.max_image_size:
                    raise ValueError(f"Input too large: {len(content)} bytes")
                file_type = '.bin'  # Unknown
                
            else:
                raise ValueError(f"Unsupported input type: {type(file_input)}")
            
            # Validate supported format
            if file_type not in self.supported_formats:
                raise ValueError(f"Unsupported format: {file_type}")
            
            return content, file_type
            
        except Exception as e:
            logger.error("Input loading failed", extra={'error': str(e)})
            raise ValueError(f"Failed to load input: {str(e)}")
    
    async def _load_logo(self, logo_input: Union[str, Path, bytes]) -> Optional[bytes]:
        """Load and validate logo image."""
        try:
            if isinstance(logo_input, (str, Path)):
                logo_path = Path(logo_input)
                if not logo_path.exists():
                    raise ValueError(f"Logo file not found: {logo_path}")
                
                async with aiofiles.open(logo_path, 'rb') as f:
                    logo_data = await f.read()
            else:
                logo_data = logo_input
            
            # Validate it's an image
            try:
                Image.open(BytesIO(logo_data))
            except Exception:
                raise ValueError("Invalid logo image format")
            
            return logo_data
            
        except Exception as e:
            logger.error("Logo loading failed", extra={'error': str(e)})
            return None
    
    async def _add_text_to_image(
        self,
        image_data: bytes,
        text: str,
        config: WatermarkConfig
    ) -> bytes:
        """Add text watermark to image."""
        try:
            # Load image
            image = Image.open(BytesIO(image_data)).convert('RGBA')
            draw = ImageDraw.Draw(image)
            
            # Get font
            font = await self._get_font(config)
            
            # Calculate text position
            position = self._calculate_position(image.size, config)
            
            # Draw text with transparency
            self._draw_transparent_text(draw, text, position, font, config)
            
            # Save with transparency
            output = BytesIO()
            image.save(output, 'PNG', optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error("Image text watermark failed", extra={'error': str(e)})
            raise WatermarkError(f"Image watermarking failed: {str(e)}")
    
    async def _add_text_to_pdf(
        self,
        pdf_data: bytes,
        text: str,
        config: WatermarkConfig
    ) -> bytes:
        """Add text watermark to PDF."""
        try:
            # Load PDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get page dimensions
                rect = page.rect
                point = self._calculate_pdf_position(rect, config)
                
                # Add text
                page.insert_text(
                    point,
                    text,
                    fontsize=config.font_size,
                    color=(1, 1, 1),  # White
                    overlay=True
                )
            
            # Save PDF
            output = BytesIO()
            doc.save(output)
            doc.close()
            
            return output.getvalue()
            
        except Exception as e:
            logger.error("PDF text watermark failed", extra={'error': str(e)})
            raise WatermarkError(f"PDF watermarking failed: {str(e)}")
    
    async def _add_logo_to_image(
        self,
        image_data: bytes,
        logo_data: bytes,
        config: WatermarkConfig
    ) -> bytes:
        """Add logo watermark to image."""
        try:
            # Load images
            base_image = Image.open(BytesIO(image_data)).convert('RGBA')
            logo_image = Image.open(BytesIO(logo_data)).convert('RGBA')
            
            # Resize logo
            logo_size = self._calculate_logo_size(base_image.size, config)
            logo_image = logo_image.resize(logo_size, Image.Resampling.LANCZOS)
            
            # Apply opacity
            logo_image = self._apply_opacity(logo_image, config.opacity)
            
            # Calculate position
            position = self._calculate_position(base_image.size, config)
            
            # Paste logo
            base_image.paste(logo_image, position, logo_image)
            
            # Save
            output = BytesIO()
            base_image.save(output, 'PNG', optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error("Image logo watermark failed", extra={'error': str(e)})
            raise WatermarkError(f"Logo watermarking failed: {str(e)}")
    
    async def _add_logo_to_pdf(
        self,
        pdf_data: bytes,
        logo_data: bytes,
        config: WatermarkConfig
    ) -> bytes:
        """Add logo watermark to PDF."""
        try:
            # Load PDF
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            
            # Load logo as image
            logo_image = Image.open(BytesIO(logo_data))
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                rect = page.rect
                
                # Calculate position
                point = self._calculate_pdf_position(rect, config)
                
                # Convert logo to PDF image
                logo_bytes = logo_image.tobytes()
                logo_img = fitz.ImageData(logo_bytes, logo_image.width, logo_image.height)
                
                # Insert image
                page.insert_image(
                    point,
                    pixmap=logo_img,
                    overlay=True
                )
            
            # Save
            output = BytesIO()
            doc.save(output)
            doc.close()
            
            return output.getvalue()
            
        except Exception as e:
            logger.error("PDF logo watermark failed", extra={'error': str(e)})
            raise WatermarkError(f"PDF logo watermarking failed: {str(e)}")
    
    async def _convert_format(self, content: bytes, source_format: str, 
                            target_format: str) -> bytes:
        """Convert between supported formats."""
        try:
            if source_format in self.SUPPORTED_IMAGE_FORMATS and target_format == '.pdf':
                return await self._image_to_pdf(content)
            elif source_format == '.pdf' and target_format in self.SUPPORTED_IMAGE_FORMATS:
                # Extract first page as image
                return await self._pdf_to_image(content, target_format)
            else:
                # Same format - return as-is
                return content
                
        except Exception as e:
            logger.error("Format conversion failed", extra={
                'source': source_format,
                'target': target_format,
                'error': str(e)
            })
            raise WatermarkError(f"Format conversion failed: {str(e)}")
    
    async def _image_to_pdf(self, image_data: bytes) -> bytes:
        """Convert image to PDF."""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from io import BytesIO
            
            image = Image.open(BytesIO(image_data))
            
            # Create PDF
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            width, height = A4
            
            # Calculate scaling
            img_width, img_height = image.size
            scale = min(width/img_width * 0.9, height/img_height * 0.9)
            img_width = img_width * scale
            img_height = img_height * scale
            
            # Center position
            x = (width - img_width) / 2
            y = (height - img_height) / 2
            
            # Add image
            can.drawImage(image, x, y, img_width, img_height)
            can.save()
            
            packet.seek(0)
            return packet.read()
            
        except Exception as e:
            logger.error("Image to PDF conversion failed", extra={'error': str(e)})
            raise WatermarkError(f"Conversion failed: {str(e)}")
    
    async def _pdf_to_image(self, pdf_data: bytes, image_format: str) -> bytes:
        """Convert first page of PDF to image."""
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            page = doc.load_page(0)
            
            # Convert to image
            mat = fitz.Matrix(2, 2)  # 2x zoom
            pix = page.get_pixmap(matrix=mat)
            
            # Save as specified format
            output = BytesIO()
            if image_format == '.png':
                pix.save(output, 'png')
            elif image_format == '.jpg':
                pix.save(output, 'jpeg', jpeg_quality=95)
            else:
                pix.save(output, 'png')  # Default
            
            doc.close()
            return output.getvalue()
            
        except Exception as e:
            logger.error("PDF to image conversion failed", extra={'error': str(e)})
            raise WatermarkError(f"Conversion failed: {str(e)}")
    
    async def _get_font(self, config: WatermarkConfig) -> ImageFont.FreeTypeFont:
        """Get font object with caching."""
        try:
            font_key = f"{config.font_family}_{config.font_size}"
            
            if font_key not in self._font_cache:
                # Try system fonts
                font_paths = [
                    f"/usr/share/fonts/truetype/{config.font_family}.ttf",
                    f"/System/Library/Fonts/{config.font_family}.ttf",
                    f"C:/Windows/Fonts/{config.font_family}.ttf"
                ]
                
                font_path = None
                for path in font_paths:
                    if Path(path).exists():
                        font_path = path
                        break
                
                # Fallback to default
                if not font_path:
                    try:
                        font_path = ImageFont.truetype("arial.ttf", config.font_size)
                    except OSError:
                        font = ImageFont.load_default()
                        self._font_cache[font_key] = font
                        return font
                
                self._font_cache[font_key] = ImageFont.truetype(font_path, config.font_size)
            
            return self._font_cache[font_key]
            
        except Exception as e:
            logger.warning("Font loading failed - using default", extra={'error': str(e)})
            return ImageFont.load_default()
    
    def _calculate_position(self, image_size: Tuple[int, int], config: WatermarkConfig) -> Tuple[float, float]:
        """Calculate watermark position."""
        try:
            width, height = image_size
            
            # Get position coordinates
            x_ratio, y_ratio = self.POSITIONS.get(config.position, self.POSITIONS['center'])
            
            # Calculate absolute position
            x = width * x_ratio
            y = height * y_ratio
            
            # Apply padding
            x = max(config.padding, x)
            y = max(config.padding, y)
            
            # Adjust for text/logo size (approximate)
            if config.text:
                # Estimate text bounding box
                x -= 100  # Approximate half-width
                y -= 50   # Approximate half-height
            
            return (x, y)
            
        except Exception as e:
            logger.error("Position calculation failed", extra={'error': str(e)})
            return (image_size[0] * 0.5, image_size[1] * 0.5)  # Center fallback
    
    def _calculate_pdf_position(self, rect: fitz.Rect, config: WatermarkConfig) -> Tuple[float, float]:
        """Calculate watermark position for PDF page."""
        try:
            width, height = rect.width, rect.height
            x_ratio, y_ratio = self.POSITIONS.get(config.position, self.POSITIONS['center'])
            
            x = width * x_ratio
            y = height * y_ratio
            
            # Apply padding
            x = max(config.padding, x)
            y = max(config.padding, y)
            
            return (x, y)
            
        except Exception as e:
            logger.error("PDF position calculation failed", extra={'error': str(e)})
            return (rect.width * 0.5, rect.height * 0.5)
    
    def _calculate_logo_size(self, image_size: Tuple[int, int], config: WatermarkConfig) -> Tuple[int, int]:
        """Calculate optimal logo size."""
        try:
            width, height = image_size
            max_width = width * config.scale
            max_height = height * config.scale
            
            # Preserve aspect ratio
            logo_width = min(max_width, logo_height * (max_width / max_height))
            logo_height = min(max_height, logo_height * (max_height / max_width))
            
            return (int(logo_width), int(logo_height))
            
        except Exception as e:
            logger.error("Logo size calculation failed", extra={'error': str(e)})
            return (100, 50)  # Default size
    
    def _apply_opacity(self, image: Image.Image, opacity: float) -> Image.Image:
        """Apply transparency to image."""
        try:
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Create transparent overlay
            alpha = image.split()[-1]
            alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
            image.putalpha(alpha)
            
            return image
            
        except Exception as e:
            logger.error("Opacity application failed", extra={'error': str(e)})
            return image
    
    def _draw_transparent_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: Tuple[float, float],
        font: ImageFont.ImageFont,
        config: WatermarkConfig
    ) -> None:
        """Draw text with transparency and styling."""
        try:
            # Calculate text size
            bbox = draw.textbbox(position, text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Create transparent background for better readability
            if config.font_color != (0, 0, 0):  # Not black
                # Draw semi-transparent black background
                bg_position = (position[0] - 5, position[1] - 5)
                bg_size = (text_width + 10, text_height + 10)
                overlay = Image.new('RGBA', bg_size, (0, 0, 0, 128))
                draw.bitmap(bg_position, overlay, (0, 0, 0, 128))
            
            # Draw rotated text
            if config.rotation != 0:
                # Create temporary image for rotation
                temp_image = Image.new('RGBA', (text_width + 20, text_height + 20), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_image)
                
                # Center text
                text_x = (text_width + 20 - text_width) / 2
                text_y = (text_height + 20 - text_height) / 2
                
                # Draw text
                temp_draw.text((text_x, text_y), text, fill=config.font_color, font=font)
                
                # Rotate
                rotated = temp_image.rotate(config.rotation, expand=True)
                
                # Paste to main image
                rot_bbox = rotated.getbbox()
                rot_width = rot_bbox[2] - rot_bbox[0]
                rot_height = rot_bbox[3] - rot_bbox[1]
                
                paste_x = position[0] - rot_width / 2
                paste_y = position[1] - rot_height / 2
                
                image.paste(rotated, (int(paste_x), int(paste_y)), rotated)
            else:
                # Draw directly
                draw.text(position, text, fill=config.font_color, font=font)
                
        except Exception as e:
            logger.error("Text drawing failed", extra={'error': str(e)})
            # Fallback: draw simple text
            draw.text(position, text, fill=(255, 255, 255), font=ImageFont.load_default())

# Global watermark manager
watermark_manager: Optional[WatermarkManager] = None

def initialize_watermark_manager(
    default_config: Optional[Dict[str, Any]] = None,
    error_handler_instance: Optional[ErrorHandler] = None
) -> WatermarkManager:
    """Initialize global watermark manager."""
    global watermark_manager
    
    if watermark_manager is None:
        watermark_manager = WatermarkManager(
            default_config=default_config,
            error_handler=error_handler_instance
        )
    
    return watermark_manager

# Convenience functions
async def add_text_watermark(file_input: Union[str, Path, bytes], text: str, **kwargs) -> bytes:
    """Convenience function for text watermark."""
    global watermark_manager
    if not watermark_manager:
        raise RuntimeError("Watermark manager not initialized")
    
    return await watermark_manager.add_text_watermark(file_input, text, **kwargs)

async def add_logo_watermark(file_input: Union[str, Path, bytes], logo_input: Union[str, Path, bytes], **kwargs) -> bytes:
    """Convenience function for logo watermark."""
    global watermark_manager
    if not watermark_manager:
        raise RuntimeError("Watermark manager not initialized")
    
    return await watermark_manager.add_logo_watermark(file_input, logo_input, **kwargs)

async def batch_watermark(files: List[Union[str, Path]], config: WatermarkConfig, **kwargs) -> List[Dict[str, Any]]:
    """Convenience function for batch watermarking."""
    global watermark_manager
    if not watermark_manager:
        raise RuntimeError("Watermark manager not initialized")
    
    return await watermark_manager.batch_watermark(files, config, **kwargs)
