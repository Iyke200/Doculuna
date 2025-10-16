#!/usr/bin/env python3
"""
DocuLuna - PDF Merging Utility
Tool 4: Merge PDF (Multiple PDFs → Single PDF)
Production-ready implementation with CLI and API support.
"""

import argparse
import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from pikepdf import Pdf, PdfError

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

class MergeValidator:
    """PDF validation utilities for merging."""
    
    @staticmethod
    def validate_pdf_file(file_path: str) -> str:
        """
        Validate PDF file exists and is readable.
        
        Args:
            file_path: Input PDF file path
            
        Returns:
            Normalized file path
            
        Raises:
            ValueError: If PDF is invalid
        """
        if not file_path or not isinstance(file_path, str):
            raise ValueError("File path must be a non-empty string")
        
        # Normalize path to prevent traversal attacks
        normalized_path = os.path.normpath(os.path.abspath(file_path))
        
        if not os.path.isfile(normalized_path):
            raise ValueError(f"Input '{file_path}' is not a valid file")
        
        # Check file size (prevent resource abuse)
        file_size = os.path.getsize(normalized_path)
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit per file
            raise ValueError("File size exceeds 2GB limit")
        
        # Validate PDF structure
        try:
            with Pdf.open(normalized_path) as pdf:
                page_count = len(pdf.pages)
                if page_count == 0:
                    raise ValueError("PDF contains no pages")
                logger.debug(f"Validated PDF: {normalized_path} ({page_count} pages, {file_size} bytes)")
        except PdfError as e:
            logger.error(f"PDF validation error: {e}")
            raise ValueError(f"Invalid PDF file: {str(e)}")
        
        return normalized_path
    
    @staticmethod
    def validate_input_files(input_paths: List[str]) -> List[str]:
        """
        Validate multiple input PDF files.
        
        Args:
            input_paths: List of input PDF paths
            
        Returns:
            List of normalized paths
            
        Raises:
            ValueError: If any file is invalid or fewer than 2 files
        """
        if len(input_paths) < 2:
            raise ValueError("At least two input PDF files are required for merging")
        
        normalized_paths = []
        total_size = 0
        for path in input_paths:
            norm_path = MergeValidator.validate_pdf_file(path)
            normalized_paths.append(norm_path)
            total_size += os.path.getsize(norm_path)
        
        if total_size > 4 * 1024 * 1024 * 1024:  # 4GB total limit
            raise ValueError("Total input size exceeds 4GB limit")
        
        return normalized_paths
    
    @staticmethod
    def validate_output_path(output_path: str, overwrite: bool = False) -> str:
        """
        Validate output PDF path and check overwrite permissions.
        
        Args:
            output_path: Output file path
            overwrite: Whether to allow overwriting existing files
            
        Returns:
            Normalized output path
            
        Raises:
            ValueError: If output path is invalid or overwrite not permitted
        """
        normalized_path = os.path.normpath(os.path.abspath(output_path))
        
        if os.path.exists(normalized_path) and not overwrite:
            raise ValueError(f"Output file '{output_path}' already exists. Use --force to overwrite.")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(normalized_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        return normalized_path
    
    @staticmethod
    def analyze_pdf_content(pdf_path: str) -> Dict:
        """
        Analyze PDF content for validation.
        
        Returns:
            Dictionary with page count, image count, etc.
        """
        try:
            with Pdf.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                image_count = 0
                annotation_count = 0
                
                for page in pdf.pages:
                    # Count images
                    if '/Resources' in page:
                        resources = page['/Resources']
                        if '/XObject' in resources:
                            for xobj in resources['/XObject'].values():
                                if xobj.get('/Subtype') == '/Image':
                                    image_count += 1
                    
                    # Count annotations
                    if '/Annots' in page:
                        annotation_count += len(page['/Annots'])
                
                return {
                    'page_count': page_count,
                    'image_count': image_count,
                    'annotation_count': annotation_count,
                    'has_bookmarks': bool(pdf.Root.get('/Outlines', None))
                }
        except Exception as e:
            logger.warning(f"Could not fully analyze PDF: {e}")
            return {'page_count': 0, 'image_count': 0, 'annotation_count': 0, 'has_bookmarks': False}

class PDFMerger:
    """PDF merging utility."""
    
    @staticmethod
    def merge_pdfs(
        input_paths: List[str], 
        output_path: str,
        preserve_bookmarks: bool = True,
        optimize: bool = False
    ) -> Dict:
        """
        Merge multiple PDFs into a single PDF.
        
        Args:
            input_paths: List of input PDF file paths
            output_path: Output PDF file path
            preserve_bookmarks: Preserve bookmarks from input PDFs
            optimize: Optimize the output PDF (stream compression)
            
        Returns:
            Dictionary with merge results and validation metrics
            
        Raises:
            ValueError: If merging fails
        """
        try:
            logger.info(f"Starting PDF merge: {len(input_paths)} files")
            
            # Validate inputs
            input_paths = MergeValidator.validate_input_files(input_paths)
            output_path = MergeValidator.validate_output_path(output_path)
            
            # Analyze input PDFs
            input_analyses = []
            total_input_pages = 0
            total_input_images = 0
            total_input_annotations = 0
            has_any_bookmarks = False
            
            for path in input_paths:
                analysis = MergeValidator.analyze_pdf_content(path)
                input_analyses.append(analysis)
                total_input_pages += analysis['page_count']
                total_input_images += analysis['image_count']
                total_input_annotations += analysis['annotation_count']
                has_any_bookmarks = has_any_bookmarks or analysis['has_bookmarks']
            
            logger.info(f"Input analysis: {total_input_pages} total pages, "
                       f"{total_input_images} images, {total_input_annotations} annotations")
            
            # Perform merge
            output_pdf = Pdf.new()
            
            for idx, input_path in enumerate(input_paths):
                with Pdf.open(input_path) as input_pdf:
                    # Append pages
                    output_pdf.pages.extend(input_pdf.pages)
                    
                    # Preserve bookmarks if enabled
                    if preserve_bookmarks and input_pdf.Root.get('/Outlines'):
                        # Simple bookmark preservation - offset by previous pages
                        if idx == 0:
                            if '/Outlines' in input_pdf.Root:
                                output_pdf.Root['/Outlines'] = input_pdf.Root['/Outlines']
                        else:
                            # TODO: Implement bookmark offsetting for multiple files
                            logger.warning("Advanced bookmark merging not implemented; using first file's bookmarks only")
            
            # Apply optimization if enabled
            save_kwargs = {}
            if optimize:
                save_kwargs = {
                    'compress_streams': True,
                    'object_streams': 'generate',
                    'linearize': True
                }
            
            output_pdf.save(output_path, **save_kwargs)
            
            # Analyze output PDF
            output_analysis = MergeValidator.analyze_pdf_content(output_path)
            
            # Validate merge
            validation_metrics = PDFMerger._validate_merge(
                total_input_pages, total_input_images, total_input_annotations,
                has_any_bookmarks, output_analysis
            )
            
            # File size analysis
            input_sizes = [os.path.getsize(p) for p in input_paths]
            total_input_size = sum(input_sizes)
            output_size = os.path.getsize(output_path)
            size_efficiency = (output_size / total_input_size) * 100 if total_input_size > 0 else 0
            
            results = {
                'success': True,
                'total_input_size': total_input_size,
                'output_size': output_size,
                'size_efficiency_percent': round(size_efficiency, 2),
                'input_analyses': input_analyses,
                'output_analysis': output_analysis,
                'validation': validation_metrics,
                'input_files': input_paths,
                'output_file': output_path,
                'merge_options': {
                    'preserve_bookmarks': preserve_bookmarks,
                    'optimize': optimize
                }
            }
            
            logger.info(f"Merge complete: {total_input_size:,} → {output_size:,} bytes "
                       f"({size_efficiency:.1f}% efficiency)")
