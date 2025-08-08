import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_IDS = [int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()]
ADMIN_IDS = ADMIN_USER_IDS  # Alias for compatibility

# Database Configuration
DB_PATH = "database/doculuna.db"

# Payment Configuration
PAYMENT_METHODS = {
    "bkash": {
        "number": "+8801700000000",
        "account_type": "Personal"
    },
    "nagad": {
        "number": "+8801700000000", 
        "account_type": "Personal"
    }
}

# Premium Plans
PREMIUM_PLANS = {
    "daily": {"price": 20, "days": 1},
    "3month": {"price": 300, "days": 90},
    "lifetime": {"price": 1000, "days": None}
}

# Usage Limits
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "3"))
PREMIUM_DAILY_LIMIT = int(os.getenv("PREMIUM_DAILY_LIMIT", "1000"))

# File Size Limits (in MB)
MAX_FILE_SIZE_FREE = int(os.getenv("MAX_FILE_SIZE_FREE", "10"))
MAX_FILE_SIZE_PREMIUM = int(os.getenv("MAX_FILE_SIZE_PREMIUM", "100"))

# Referral Configuration
REFERRAL_BONUS_DAYS = 1