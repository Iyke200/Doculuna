# Pricing for premium subscriptions (in Naira) - PRODUCTION PRICING
WEEKLY_PREMIUM_PRICE = 1000  # Weekly plan
MONTHLY_PREMIUM_PRICE = 2500  # Monthly plan

# Payment details (Manual)
MANUAL_PAYMENT_DETAILS = {
    "opay": {
        "account": "9057203030",
        "bank": "OPay",
        "name": "Ebere Nwankwo"
    },
    "palmpay": {
        "account": "9057203030",
        "bank": "PalmPay",
        "name": "Ebere Nwankwo"
    },
    "usdt_trc20": {
        "address": "T...", # Add real address here
        "network": "TRC20"
    }
}

# Telegram Bot Token - SECURITY: No default token for production
import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Usage limits for freemium model
FREE_USAGE_LIMIT = 3
PREMIUM_USAGE_LIMIT = 999999
REFERRAL_BONUS = 1

# Database configuration
DB_PATH = "database/doculuna.db"
DATABASE_URL = "database/doculuna.db"

# Admin configuration
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv("ADMIN_USER_IDS", "").split(",") if id.strip()]

# Premium plans configuration
PREMIUM_PLANS = {
    "weekly": {
        "price": WEEKLY_PREMIUM_PRICE,
        "duration_days": 7,
        "name": "Weekly Pro",
        "description": "Perfect for quick projects"
    },
    "monthly": {
        "price": MONTHLY_PREMIUM_PRICE,
        "duration_days": 30,
        "name": "Monthly Pro", 
        "description": "Best value for regular users"
    },
}

# Directories
TEMP_DIR = "data/temp"
PAYMENTS_DIR = "payments"
BACKUPS_DIR = "backups"
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".gif"]
