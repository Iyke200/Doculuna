# file_naming.py
"""File naming utilities for DocuLuna.

Provides functions for sanitizing and generating unique, versioned file names.
"""

import re
from datetime import datetime
import aiosqlite
import os
from typing import str
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def sanitize_filename(name: str) -> str:
    """Sanitize a filename by removing invalid characters and normalizing."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = name[:200]
    return name or "untitled_document"

async def generate_smart_name(operation: str, user_id: int, original: str, db_path: str) -> str:
    """Generate a unique, versioned filename based on operation and history."""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = f"{operation}_{timestamp}"
        clean = sanitize_filename(os.path.splitext(original)[0])
        candidate = f"{clean}_{base}"
        ext = os.path.splitext(original)[1] or '.pdf'
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                'SELECT COUNT(*) FROM history WHERE user_id = ? AND filename LIKE ?',
                (user_id, f"{candidate}%")
            ) as cursor:
                count = (await cursor.fetchone())[0]
        version = f"_v{count + 1}" if count > 0 else ""
        return f"{candidate}{version}{ext}"
    except aiosqlite.Error as e:
        logger.error(f"Error generating filename for user {user_id}: {e}")
        return f"{sanitize_filename(original)}_{timestamp}{ext}"
