import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

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

# File size limits (in MB)
MAX_FILE_SIZE = 50
MAX_PREMIUM_FILE_SIZE = 100

# Daily usage limits
FREE_DAILY_LIMIT = 3
PREMIUM_DAILY_LIMIT = -1  # Unlimited

# Referral Configuration
REFERRAL_BONUS_DAYS = 1