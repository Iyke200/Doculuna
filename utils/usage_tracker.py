
import json
import os
from datetime import datetime, date
from utils.premium_utils import is_premium

USAGE_FILE = "data/usage.json"

def load_usage_data():
    """Load usage data from JSON file."""
    try:
        if os.path.exists(USAGE_FILE):
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception:
        return {}

def save_usage_data(data):
    """Save usage data to JSON file."""
    try:
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

async def check_usage_limit(user_id):
    """Check if user can use tools (premium users always can)."""
    try:
        # Premium users have unlimited access
        if is_premium(user_id):
            return True
        
        usage_data = load_usage_data()
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        if user_id_str not in usage_data:
            usage_data[user_id_str] = {"date": today, "count": 0}
            save_usage_data(usage_data)
            return True
        
        user_usage = usage_data[user_id_str]
        
        # Reset count if it's a new day
        if user_usage.get("date") != today:
            user_usage["date"] = today
            user_usage["count"] = 0
            save_usage_data(usage_data)
            return True
        
        # Check if under limit
        return user_usage.get("count", 0) < 3
        
    except Exception:
        return True  # Allow on error

async def increment_usage(user_id):
    """Increment user's usage count."""
    try:
        # Don't count for premium users
        if is_premium(user_id):
            return
        
        usage_data = load_usage_data()
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        if user_id_str not in usage_data:
            usage_data[user_id_str] = {"date": today, "count": 1}
        else:
            user_usage = usage_data[user_id_str]
            if user_usage.get("date") != today:
                user_usage["date"] = today
                user_usage["count"] = 1
            else:
                user_usage["count"] = user_usage.get("count", 0) + 1
        
        save_usage_data(usage_data)
        
    except Exception:
        pass

def get_usage_stats(user_id):
    """Get user's usage statistics."""
    try:
        usage_data = load_usage_data()
        user_id_str = str(user_id)
        today = date.today().isoformat()
        
        if user_id_str not in usage_data:
            return {"count": 0, "remaining": 3}
        
        user_usage = usage_data[user_id_str]
        
        if user_usage.get("date") != today:
            return {"count": 0, "remaining": 3}
        
        count = user_usage.get("count", 0)
        return {"count": count, "remaining": max(0, 3 - count)}
        
    except Exception:
        return {"count": 0, "remaining": 3}
