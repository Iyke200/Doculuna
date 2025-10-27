import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token - SECURITY: No default token for production
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Usage limits for freemium model
FREE_USAGE_LIMIT = 3  # Number of free uses per day
PREMIUM_USAGE_LIMIT = 999999  # Unlimited
REFERRAL_BONUS = 1  # Extra uses per successful referral

# Pricing for premium subscriptions (in Naira) - PRODUCTION PRICING
WEEKLY_PREMIUM_PRICE = 3500  # Weekly plan
MONTHLY_PREMIUM_PRICE = 1000  # Monthly plan

# Legacy pricing (deprecated)
DAILY_PREMIUM_PRICE = 3500
THREE_MONTH_PREMIUM_PRICE = 9000
LIFETIME_PREMIUM_PRICE = 25000

# Payment details
PAYMENT_ACCOUNT = "9057203030"
PAYMENT_BANK = "Moniepoint"
PAYMENT_NAME = "Ebere Nwankwo"

# Payment Methods (additional options)
PAYMENT_METHODS = {
    "upi": "your-upi-id@bank",
    "paytm": "9876543210",
    "gpay": "9876543210",
}

# Database configuration
DB_PATH = "database/doculuna.db"
DATABASE_URL = "database/doculuna.db"

# Logging configuration
LOG_FILE = "doculuna.log"
LOG_LEVEL = "DEBUG"

# Abuse prevention
MAX_DAILY_REQUESTS = 50  # Max requests per user per day
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size

# Premium plans configuration - PRODUCTION PLANS
PREMIUM_PLANS = {
    "weekly": {
        "price": WEEKLY_PREMIUM_PRICE,  # 3500 NGN
        "duration_days": 7,
        "name": "Weekly Pro",
        "description": "Perfect for quick projects"
    },
    "monthly": {
        "price": MONTHLY_PREMIUM_PRICE,  # 1000 NGN
        "duration_days": 30,
        "name": "Monthly Pro", 
        "description": "Best value for regular users"
    },
}

# Legacy plans (deprecated)
LEGACY_PLANS = {
    "daily": {"price": DAILY_PREMIUM_PRICE, "duration_days": 1, "name": "Daily Plan"},
    "3month": {
        "price": THREE_MONTH_PREMIUM_PRICE,
        "duration_days": 90,
        "name": "3-Month Plan",
    },
    "lifetime": {
        "price": LIFETIME_PREMIUM_PRICE,
        "duration_days": 36500,
        "name": "Lifetime Plan",
    },
}

# Admin configuration
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv("ADMIN_USER_IDS", "").split(",") if id.strip()]  # Admin user IDs from environment
ADMIN_IDS = ADMIN_USER_IDS  # Alias for compatibility

# Production settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"

# Rate limiting
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds

# File processing limits
MAX_CONCURRENT_PROCESSES = 5
PROCESSING_TIMEOUT = 300  # 5 minutes
MAX_MERGE_FILES = 10

# File size limits (in bytes)
MAX_FILE_SIZE_FREE = 20 * 1024 * 1024  # 20MB for free users
MAX_FILE_SIZE_PREMIUM = 50 * 1024 * 1024  # 50MB for premium users

# Business analytics
ANALYTICS_ENABLED = True
BACKUP_INTERVAL_HOURS = 6

# Marketing settings - PRODUCTION REFERRAL SYSTEM
REFERRAL_REWARD_USES = 1
REFERRAL_REWARDS = {
    "monthly": 500,  # 500 NGN for referring monthly premium user
    "weekly": 150,   # 150 NGN for referring weekly premium user
}
MINIMUM_WITHDRAWAL_AMOUNT = 2000  # Minimum amount for withdrawal in NGN
WELCOME_SERIES_ENABLED = True
RETENTION_CAMPAIGN_ENABLED = True

# Security settings
MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT_HOURS = 24

# Webhook settings (for production)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("PORT", 5000))

# External services - PAYSTACK INTEGRATION
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"
PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"

# Legacy
PAYMENT_VERIFICATION_API = os.getenv("PAYMENT_VERIFICATION_API", "")

# Feature flags
ENABLE_PREMIUM_FEATURES = True
ENABLE_ANALYTICS = True
ENABLE_NOTIFICATIONS = True

# Directories
TEMP_DIR = "data/temp"
PAYMENTS_DIR = "payments"
BACKUPS_DIR = "backups"

# File Configuration
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".gif"]

# Welcome message
WELCOME_MESSAGE = """
🌟 *Welcome to DocuLuna Bot!* 🌟

Your all-in-one document processing assistant. I can help you with:

📄 PDF to Word conversion
📝 Word to PDF conversion  
🖼️ Image to PDF conversion
📊 PDF merging and splitting
🗜️ File compression

Click the button below to get started!
"""
