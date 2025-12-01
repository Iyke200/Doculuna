# file_naming.py
"""File naming utilities for DocuLuna.

Provides functions for sanitizing and generating unique, versioned file names.
"""

import re
from datetime import datetime
import aiosqlite
import os
from typing import Optional, Tuple
import logging

from config import DB_PATH

logger = logging.getLogger(__name__)

# Characters that are invalid in filenames across different OS
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r'\s+')
CONSECUTIVE_UNDERSCORES = re.compile(r'_+')


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitize a filename by removing invalid characters and normalizing.
    
    Args:
        name: The original filename
        max_length: Maximum length for the filename (default 200)
    
    Returns:
        A sanitized filename safe for all operating systems
    """
    if not name:
        return "untitled_document"
    
    # Remove invalid characters
    name = INVALID_CHARS.sub('_', name)
    
    # Normalize whitespace to underscores
    name = WHITESPACE.sub('_', name.strip())
    
    # Remove consecutive underscores
    name = CONSECUTIVE_UNDERSCORES.sub('_', name)
    
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    # Truncate to max length
    if len(name) > max_length:
        # Try to preserve the extension
        base, ext = os.path.splitext(name)
        if ext and len(ext) <= 10:
            name = base[:max_length - len(ext)] + ext
        else:
            name = name[:max_length]
    
    return name or "untitled_document"


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext else '.pdf'


def generate_output_filename(
    operation: str, 
    original: str, 
    output_ext: str = None
) -> str:
    """
    Generate a clean output filename based on operation and original filename.
    
    Args:
        operation: The operation type (convert, compress, merge, etc.)
        original: The original filename
        output_ext: The output extension (if different from original)
    
    Returns:
        A clean, descriptive output filename
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Get clean base name without extension
    base = os.path.splitext(original)[0]
    clean_base = sanitize_filename(base, max_length=100)
    
    # Determine output extension
    if output_ext:
        ext = output_ext if output_ext.startswith('.') else f'.{output_ext}'
    else:
        ext = get_file_extension(original)
    
    # Operation-specific prefixes
    operation_prefixes = {
        'convert': 'converted',
        'compress': 'compressed',
        'merge': 'merged',
        'split': 'split',
        'ocr': 'ocr',
        'watermark': 'watermarked',
        'image_to_pdf': 'img2pdf'
    }
    
    prefix = operation_prefixes.get(operation.lower(), operation.lower())
    
    return f"{clean_base}_{prefix}_{timestamp}{ext}"


async def generate_smart_name(
    operation: str, 
    user_id: int, 
    original: str, 
    db_path: Optional[str] = None
) -> str:
    """
    Generate a unique, versioned filename based on operation and history.
    Checks for filename collisions and adds version numbers.
    
    Args:
        operation: The operation type
        user_id: The user ID
        original: The original filename
        db_path: Path to the database
    
    Returns:
        A unique, versioned filename
    """
    db_path = db_path or DB_PATH
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Get clean base name
        base_name = os.path.splitext(original)[0]
        clean_base = sanitize_filename(base_name, max_length=100)
        ext = get_file_extension(original)
        
        # Create candidate filename
        candidate = f"{clean_base}_{operation}_{timestamp}"
        
        # Check for existing files with similar names in history
        async with aiosqlite.connect(db_path) as db:
            # Initialize history table if needed
            await db.execute('''
                CREATE TABLE IF NOT EXISTS operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT,
                    operation_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    duration REAL DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    file_size INTEGER DEFAULT 0,
                    output_filename TEXT
                )
            ''')
            
            async with db.execute(
                '''SELECT COUNT(*) FROM operation_history 
                   WHERE user_id = ? AND output_filename LIKE ?''',
                (user_id, f"{candidate}%")
            ) as cursor:
                count = (await cursor.fetchone())[0]
        
        # Add version suffix if there are conflicts
        version = f"_v{count + 1}" if count > 0 else ""
        
        return f"{candidate}{version}{ext}"
        
    except aiosqlite.Error as e:
        logger.error(f"Error generating filename for user {user_id}: {e}")
        # Fallback to simple timestamped name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        clean = sanitize_filename(original, max_length=100)
        return f"{clean}_{timestamp}{get_file_extension(original)}"


def validate_filename(filename: str) -> tuple[bool, str]:
    """
    Validate a filename and return any issues found.
    
    Args:
        filename: The filename to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename:
        return False, "Filename cannot be empty"
    
    if len(filename) > 255:
        return False, "Filename is too long (max 255 characters)"
    
    if INVALID_CHARS.search(filename):
        return False, "Filename contains invalid characters"
    
    # Check for reserved names (Windows)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', 
                'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    base = os.path.splitext(filename)[0].upper()
    if base in reserved:
        return False, f"'{filename}' is a reserved filename"
    
    return True, ""
