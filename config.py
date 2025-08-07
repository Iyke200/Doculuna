import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Webhook settings (for production)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("PORT", 5000))

# External services
PAYMENT_VERIFICATION_API = os.getenv("PAYMENT_VERIFICATION_API", "")

# Feature flags
ENABLE_PREMIUM_FEATURES = True
ENABLE_ANALYTICS = True
ENABLE_NOTIFICATIONS = True

# Directories
TEMP_DIR = "temp"
PAYMENTS_DIR = "payments"
BACKUPS_DIR = "backups"

# File Size Limits (in bytes)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_MERGE_FILES = 10

# Usage Limits
FREE_USAGE_LIMIT = 3
PREMIUM_USAGE_LIMIT = 999999  # Unlimited
REFERRAL_BONUS = 1

# Premium Pricing (Nigerian Naira)
DAILY_PREMIUM_PRICE = 3500
THREE_MONTH_PREMIUM_PRICE = 9000
LIFETIME_PREMIUM_PRICE = 25000

# Payment Details
PAYMENT_ACCOUNT = "9057203030"
PAYMENT_BANK = "Moniepoint"
PAYMENT_NAME = "Ebere Nwankwo"

# Payment Configuration
PAYMENT_METHODS = {
    "upi": "your-upi-id@bank",
    "paytm": "9876543210",
    "gpay": "9876543210"
}

# Admin Configuration
ADMIN_USER_IDS = [6857550239]  # Replace with actual admin user IDs