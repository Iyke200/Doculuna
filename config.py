import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8129574913:AAFTvBu_d4R4WDDTAYSJUxUwPhWgdozlbH4")

# Usage limits for freemium model
FREE_USAGE_LIMIT = 3  # Number of free uses per day
PREMIUM_USAGE_LIMIT = 999999  # Unlimited
REFERRAL_BONUS = 1  # Extra uses per successful referral

# Pricing for premium subscriptions (in Naira)
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

# Premium plans configuration
PREMIUM_PLANS = {
    "daily": {"price": DAILY_PREMIUM_PRICE, "duration_days": 1, "name": "Daily Plan"},
    "3month": {
        "price": THREE_MONTH_PREMIUM_PRICE,
        "duration_days": 90,
        "name": "3-Month Plan",
    },
    "lifetime": {
        "price": LIFETIME_PREMIUM_PRICE,
        "duration_days": 36500,  # 100 years
        "name": "Lifetime Plan",
    },
}

# Admin configuration
ADMIN_USER_IDS = [6857550239]  # Admin user IDs
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

# Business analytics
ANALYTICS_ENABLED = True
BACKUP_INTERVAL_HOURS = 6

# Marketing settings
REFERRAL_REWARD_USES = 1
WELCOME_SERIES_ENABLED = True
RETENTION_CAMPAIGN_ENABLED = True

# Security settings
MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT_HOURS = 24

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
TEMP_DIR = "data/temp"
PAYMENTS_DIR = "payments"
BACKUPS_DIR = "backups"

# File Configuration
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".gif"]
