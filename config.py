import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management with validation"""
    
    # Core Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8129574913:AAFTvBu_d4R4WDDTAYSJUxUwPhWgdozlbH4")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = ENVIRONMENT == "development"
    
    # Database Configuration
    DB_PATH = "database/doculuna.db"
    DATABASE_URL = "database/doculuna.db"
    
    # Usage Limits and Premium Features
    FREE_USAGE_LIMIT = 3
    PREMIUM_USAGE_LIMIT = 999999  # Unlimited
    REFERRAL_BONUS = 1  # Extra uses per successful referral
    REFERRAL_REWARD_USES = 1
    
    # Premium Pricing (Nigerian Naira)
    DAILY_PREMIUM_PRICE = 3500
    THREE_MONTH_PREMIUM_PRICE = 9000
    LIFETIME_PREMIUM_PRICE = 25000
    
    # Payment Configuration
    PAYMENT_ACCOUNT = "9057203030"
    PAYMENT_BANK = "Moniepoint"
    PAYMENT_NAME = "Ebere Nwankwo"
    PAYMENT_VERIFICATION_API = os.getenv("PAYMENT_VERIFICATION_API", "")
    
    # Admin Configuration
    ADMIN_USER_IDS = [6857550239]  # Main admin
    
    # File Processing Configuration
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_MERGE_FILES = 10
    MAX_CONCURRENT_PROCESSES = 5
    PROCESSING_TIMEOUT = 300  # 5 minutes
    ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.gif', '.bmp']
    
    # Rate Limiting and Security
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW = 60  # seconds
    MAX_DAILY_REQUESTS = 50
    MAX_LOGIN_ATTEMPTS = 5
    SESSION_TIMEOUT_HOURS = 24
    
    # Directories
    TEMP_DIR = "data/temp"
    PAYMENTS_DIR = "payments"
    BACKUPS_DIR = "backups"
    ANALYTICS_DIR = "analytics"
    LOGS_DIR = "logs"
    
    # Logging Configuration
    LOG_FILE = "doculuna.log"
    LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
    
    # Feature Flags
    ENABLE_PREMIUM_FEATURES = True
    ENABLE_ANALYTICS = True
    ENABLE_NOTIFICATIONS = True
    ANALYTICS_ENABLED = True
    WELCOME_SERIES_ENABLED = True
    RETENTION_CAMPAIGN_ENABLED = True
    
    # Business Configuration
    BACKUP_INTERVAL_HOURS = 6
    
    # Webhook Configuration (for production)
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PORT = int(os.getenv("PORT", 5000))
    
    # Advanced Admin Features
    ENABLE_ADVANCED_ANALYTICS = True
    ENABLE_REAL_TIME_MONITORING = True
    ENABLE_AUDIT_LOGS = True
    ENABLE_BACKUP_AUTOMATION = True
    ENABLE_SECURITY_MONITORING = True
    
    # UI/UX Configuration
    ENABLE_DARK_MODE = True
    ENABLE_ANIMATIONS = True
    ENABLE_TOOLTIPS = True
    ENABLE_PROGRESS_BARS = True
    
    # Notification Settings
    NOTIFICATION_CHANNELS = ["telegram", "email"]
    ALERT_THRESHOLDS = {
        "error_rate": 0.05,  # 5% error rate
        "response_time": 5000,  # 5 seconds
        "disk_usage": 0.85,  # 85% disk usage
        "memory_usage": 0.90  # 90% memory usage
    }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration settings"""
        try:
            if not cls.BOT_TOKEN:
                logger.error("BOT_TOKEN is required")
                return False
            
            if not cls.ADMIN_USER_IDS:
                logger.error("At least one admin user ID is required")
                return False
            
            # Create required directories
            for dir_path in [cls.TEMP_DIR, cls.PAYMENTS_DIR, cls.BACKUPS_DIR, 
                           cls.ANALYTICS_DIR, cls.LOGS_DIR]:
                os.makedirs(dir_path, exist_ok=True)
            
            logger.info("Configuration validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    @classmethod
    def get_admin_config(cls) -> Dict[str, Any]:
        """Get admin-specific configuration"""
        return {
            "admin_ids": cls.ADMIN_USER_IDS,
            "features": {
                "advanced_analytics": cls.ENABLE_ADVANCED_ANALYTICS,
                "real_time_monitoring": cls.ENABLE_REAL_TIME_MONITORING,
                "audit_logs": cls.ENABLE_AUDIT_LOGS,
                "backup_automation": cls.ENABLE_BACKUP_AUTOMATION,
                "security_monitoring": cls.ENABLE_SECURITY_MONITORING
            },
            "thresholds": cls.ALERT_THRESHOLDS
        }

# Legacy exports for backward compatibility
BOT_TOKEN = Config.BOT_TOKEN
FREE_USAGE_LIMIT = Config.FREE_USAGE_LIMIT
REFERRAL_BONUS = Config.REFERRAL_BONUS
DAILY_PREMIUM_PRICE = Config.DAILY_PREMIUM_PRICE
THREE_MONTH_PREMIUM_PRICE = Config.THREE_MONTH_PREMIUM_PRICE
LIFETIME_PREMIUM_PRICE = Config.LIFETIME_PREMIUM_PRICE
PAYMENT_ACCOUNT = Config.PAYMENT_ACCOUNT
PAYMENT_BANK = Config.PAYMENT_BANK
PAYMENT_NAME = Config.PAYMENT_NAME
ADMIN_USER_IDS = Config.ADMIN_USER_IDS
MAX_FILE_SIZE = Config.MAX_FILE_SIZE
TEMP_DIR = Config.TEMP_DIR
DATABASE_URL = Config.DATABASE_URL
DB_PATH = Config.DB_PATH

# Validate configuration on import
if not Config.validate():
    raise RuntimeError("Invalid configuration detected")
