import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8129574913:AAFTvBu_d4R4WDDTAYSJUxUwPhWgdozlbH4")

# Usage limits for freemium model
FREE_USAGE_LIMIT = 3  # Number of free uses per day
REFERRAL_BONUS = 1   # Extra uses per successful referral

# Pricing for premium subscriptions (in Naira)
DAILY_PREMIUM_PRICE = 3500
THREE_MONTH_PREMIUM_PRICE = 9000
LIFETIME_PREMIUM_PRICE = 25000

# Payment details
PAYMENT_ACCOUNT = "9057203030"
PAYMENT_BANK = "Moniepoint"
PAYMENT_NAME = "Ebere Nwankwo"

# Database configuration
DB_PATH = "database/doculuna.db"

# Logging configuration
LOG_FILE = "doculuna.log"
LOG_LEVEL = "DEBUG"

# Abuse prevention
MAX_DAILY_REQUESTS = 50  # Max requests per user per day
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size

# Admin configuration
ADMIN_USER_IDS = [6857550239]  # Admin user IDs

# Production settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"

# Rate limiting
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds

# File processing limits
MAX_CONCURRENT_PROCESSES = 5
PROCESSING_TIMEOUT = 300  # 5 minutes

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
TEMP_DIR = "temp"
PAYMENTS_DIR = "payments"
BACKUPS_DIR = "backups"

# File Size Limits (in bytes)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_MERGE_FILES = 10

# Usage Limits
FREE_USAGE_LIMIT = 3
REFERRAL_BONUS = 1

# Premium Pricing (Nigerian Naira)
DAILY_PREMIUM_PRICE = 3500
THREE_MONTH_PREMIUM_PRICE = 9000
LIFETIME_PREMIUM_PRICE = 25000

# Payment Details
PAYMENT_ACCOUNT = "9057203030"
PAYMENT_BANK = "Moniepoint"
PAYMENT_NAME = "Ebere Nwankwo"

# Admin Configuration
ADMIN_USER_IDS = [6857550239]  # Replace with actual admin user IDs
