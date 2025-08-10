import logging
import os
import time
import traceback
import sys
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import NetworkError, Forbidden
from config import BOT_TOKEN

# Ensure required directories exist
os.makedirs("data/temp", exist_ok=True)
os.makedirs("payments", exist_ok=True)
os.makedirs("backups", exist_ok=True)
os.makedirs("analytics", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/doculuna.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def import_handlers():
    """Import handlers with error handling."""
    try:
        from database.db import init_db, get_all_users, get_pending_payments
        from handlers.start import start
        from handlers.referrals import referrals
        from handlers.premium import premium_status
        from handlers.upgrade import upgrade, handle_payment_submission
        from handlers.help import help_command
        from handlers.admin import admin_panel
        from handlers.callbacks import handle_callback_query
        from utils.error_handler import error_handler, log_error
        from utils.usage_tracker import check_usage_limit, increment_usage
        from utils.file_processor import process_file
        from config import ADMIN_USER_IDS

        return {
            'init_db': init_db,
            'start': start,
            'referrals': referrals,
            'premium_status': premium_status,
            'upgrade': upgrade,
            'handle_payment_submission': handle_payment_submission,
            'help_command': help_command,
            'admin_panel': admin_panel,
            'handle_callback_query': handle_callback_query,
            'process_file': process_file,
            'ADMIN_USER_IDS': ADMIN_USER_IDS
        }
    except Exception as e:
        logger.error(f"Error importing handlers: {e}")
        raise

async def error_callback(update, context):
    """Global error handler for the bot."""
    try:
        logger.error(f"Update {update} caused error {context.error}")

        if isinstance(context.error, NetworkError):
            return

        if isinstance(context.error, Forbidden):
            return

        if update and update.effective_chat:
            try:
                await update.effective_chat.send_message(
                    "❌ An unexpected error occurred. Please try again later."
                )
            except:
                pass

    except Exception as e:
        logger.error(f"Error in error handler: {e}")

def start_bot_clean():
    """Start the bot with clean initialization."""
    logger.info("🚀 Starting DocuLuna Bot...")

    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN not found")
        raise ValueError("BOT_TOKEN is required")
    logger.info("✓ Bot token found")

    # Import handlers
    handlers = import_handlers()

    # Initialize database
    logger.info("Initializing database...")
    handlers['init_db']()
    logger.info("✓ Database initialized")

    # Create Application
    logger.info("Creating Telegram application...")
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("✓ Application created")

    # Add global error handler
    app.add_error_handler(error_callback)

    # Register command handlers
    logger.info("Registering handlers...")
    app.add_handler(CommandHandler("start", handlers['start']))
    app.add_handler(CommandHandler("referral", handlers['referrals']))
    app.add_handler(CommandHandler("premium", handlers['premium_status']))
    app.add_handler(CommandHandler("upgrade", handlers['upgrade']))
    app.add_handler(CommandHandler("help", handlers['help_command']))
    app.add_handler(CommandHandler("admin", handlers['admin_panel']))

    # Import and add additional handlers with error handling
    try:
        from handlers.stats import stats_command
        app.add_handler(CommandHandler("stats", stats_command))

        from handlers.admin import grant_premium_command, revoke_premium_command, broadcast_message, force_upgrade_command
        app.add_handler(CommandHandler("grant_premium", grant_premium_command))
        app.add_handler(CommandHandler("revoke_premium", revoke_premium_command))
        app.add_handler(CommandHandler("force_upgrade", force_upgrade_command))
    except ImportError as e:
        logger.warning(f"Some admin commands not available: {e}")

    # Register callback query handler
    app.add_handler(CallbackQueryHandler(handlers['handle_callback_query']))

    # Register message handlers for file processing
    app.add_handler(MessageHandler(
        filters.Document.ALL & ~filters.COMMAND,
        handlers['process_file']
    ))
    app.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND,
        handlers['process_file']
    ))

    logger.info("✓ All handlers registered")

    # Start bot
    logger.info("Starting bot polling...")
    print("🤖 DocuLuna Bot is now running!")
    print("✓ Database initialized")
    print("✓ Handlers registered")
    print("✓ Polling started")

    logger.info("✅ DocuLuna started successfully")

    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting DocuLuna...")
        start_bot_clean()
    except KeyboardInterrupt:
        logging.info("🛑 Stopped by user.")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"❌ DocuLuna failed to start: {e}")
        sys.exit(1)