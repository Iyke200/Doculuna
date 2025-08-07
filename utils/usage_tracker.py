
import json
import os
from datetime import datetime, date
from database.db import get_user
import logging

logger = logging.getLogger(__name__)
USAGE_FILE = "data/usage.json"

def load_usage_data():
    """Load usage data from JSON file."""
    try:
        if os.path.exists(USAGE_FILE):
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading usage data: {e}")
        return {}

def save_usage_data(data):
    """Save usage data to JSON file."""
    try:
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving usage data: {e}")

async def check_usage_limit(user_id):
    """Check if user can use tools (premium users always can)."""
    try:
        # Get user from database
        user = get_user(user_id)
        if not user:
            return False
        
        # Premium users have unlimited access
        if user['is_premium']:
            return True
        
        # Check daily uses from database
        return user['daily_uses'] > 0
        
    except Exception as e:
        logger.error(f"Error checking usage limit for user {user_id}: {e}")
        return False

async def increment_usage(user_id):
    """Increment user's usage count."""
    try:
        # Get user from database
        user = get_user(user_id)
        if not user:
            return False
        
        # Don't count for premium users
        if user['is_premium']:
            return True
        
        # Database handles the decrement automatically via add_usage
        return True
        
    except Exception as e:
        logger.error(f"Error incrementing usage for user {user_id}: {e}")
        return False

def get_usage_stats(user_id):
    """Get user's usage statistics from database."""
    try:
        user = get_user(user_id)
        if not user:
            return {"count": 0, "remaining": 0}
        
        if user['is_premium']:
            return {"count": 0, "remaining": "Unlimited"}
        
        remaining = user['daily_uses']
        used = 3 - remaining
        
        return {"count": used, "remaining": remaining}
        
    except Exception as e:
        logger.error(f"Error getting usage stats for user {user_id}: {e}")
        return {"count": 0, "remaining": 0}

def add_watermark_to_file(file_path, is_premium=False):
    """Add watermark to files for free users."""
    if is_premium:
        return True
    
    try:
        import fitz  # PyMuPDF
        
        if file_path.lower().endswith('.pdf'):
            # Add watermark to PDF
            pdf_document = fitz.open(file_path)
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Add watermark text
                watermark_text = "DocuLuna Free - Upgrade for watermark-free files"
                page.insert_text(
                    (50, 50),
                    watermark_text,
                    fontsize=10,
                    color=(0.8, 0.8, 0.8),
                    overlay=True
                )
                
                # Add watermark at bottom
                page.insert_text(
                    (50, page.rect.height - 30),
                    "Get premium at t.me/DocuLunaBot",
                    fontsize=8,
                    color=(0.7, 0.7, 0.7),
                    overlay=True
                )
            
            pdf_document.save(file_path)
            pdf_document.close()
            
        return True
        
    except Exception as e:
        logger.error(f"Error adding watermark: {e}")
        return False
