import logging
import os
import sys
import asyncio
from typing import Any

# aiogram 3.22 imports
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN

# Ensure required directories exist
os.makedirs("data/temp", exist_ok=True)
os.makedirs("payments", exist_ok=True)
os.makedirs("backups", exist_ok=True)
os.makedirs("analytics", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Setup logging with security hardening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/doculuna.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Prevent token leakage in HTTP logs (CRITICAL SECURITY FIX)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

# Global dispatcher
dp = Dispatcher(storage=MemoryStorage())

def import_handlers():
    """Import handlers with error handling."""
    try:
        from database.db import init_db, get_all_users, get_pending_payments
        from handlers.start import start_command_handler
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
            "init_db": init_db,
            "start": start_command_handler,
            "referrals": referrals,
            "premium_status": premium_status,
            "upgrade": upgrade,
            "handle_payment_submission": handle_payment_submission,
            "help_command": help_command,
            "admin_panel": admin_panel,
            "handle_callback_query": handle_callback_query,
            "process_file": process_file,
            "ADMIN_USER_IDS": ADMIN_USER_IDS,
        }
    except Exception as e:
        logger.error(f"Error importing handlers: {e}")
        raise

@dp.error()
async def error_callback(event: ErrorEvent) -> None:
    """Global error handler for the bot."""
    try:
        logger.error(f"Update {event.update} caused error {event.exception}")
        
        # Get the update information
        update = event.update
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.answer(
                    "❌ An unexpected error occurred. Please try again later."
                )
            except:
                pass
        elif update and hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.message.answer(
                    "❌ An unexpected error occurred. Please try again later."
                )
            except:
                pass

    except Exception as e:
        logger.error(f"Error in error handler: {e}")

def register_handlers():
    """Register all bot handlers with the dispatcher."""
    logger.info("Registering handlers...")
    
    # Import handlers
    handlers = import_handlers()
    
    # Register command handlers
    dp.message.register(handlers["start"], Command("start"))
    dp.message.register(handlers["referrals"], Command("referral"))
    dp.message.register(handlers["premium_status"], Command("premium"))
    dp.message.register(handlers["upgrade"], Command("upgrade"))
    dp.message.register(handlers["help_command"], Command("help"))
    dp.message.register(handlers["admin_panel"], Command("admin"))
    
    # Import and register additional handlers with error handling
    try:
        from handlers.stats import stats_command
        dp.message.register(stats_command, Command("stats"))

        from handlers.admin import (
            grant_premium_command,
            revoke_premium_command,
            broadcast_message,
            force_upgrade_command,
        )

        dp.message.register(grant_premium_command, Command("grant_premium"))
        dp.message.register(revoke_premium_command, Command("revoke_premium"))
        dp.message.register(force_upgrade_command, Command("force_upgrade"))
    except ImportError as e:
        logger.warning(f"Some admin commands not available: {e}")

    # Register callback query handler
    dp.callback_query.register(handlers["handle_callback_query"])

    # Register message handlers for file processing (documents and photos)
    dp.message.register(handlers["process_file"])

    logger.info("✓ All handlers registered")
    return handlers

async def start_bot_clean():
    """Start the bot with clean initialization."""
    logger.info("🚀 Starting DocuLuna Bot...")

    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN not found")
        raise ValueError("BOT_TOKEN is required")
    logger.info("✓ Bot token found")

    # Register handlers and get handler functions
    handlers = register_handlers()

    # Initialize database
    logger.info("Initializing database...")
    handlers["init_db"]()
    logger.info("✓ Database initialized")

    # Create Bot instance
    logger.info("Creating Telegram bot...")
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    logger.info("✓ Bot created")

    # Start bot
    logger.info("Starting bot polling...")
    print("🤖 DocuLuna Bot is now running!")
    print("✓ Database initialized")
    print("✓ Handlers registered")
    print("✓ Polling started")

    logger.info("✅ DocuLuna started successfully")

    # Production webhook mode vs development polling mode
    webhook_url = os.getenv("WEBHOOK_URL")
    if os.getenv("ENVIRONMENT") == "production" and webhook_url:
        port = int(os.getenv("PORT", 5000))
        logger.info(f"🌐 Starting webhook mode on port {port}")
        print(f"🌐 Webhook mode: {webhook_url}")
        
        # For webhook mode in aiogram 3.22
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        
        web.run_app(app, host="0.0.0.0", port=port)
    else:
        logger.info("🔄 Starting polling mode (development)")
        print("🔄 Polling mode (development)")
        
        # Start polling in aiogram 3.22 style
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

async def main():
    """Main entry point."""
    try:
        await start_bot_clean()
    except KeyboardInterrupt:
        logger.info("🛑 Stopped by user.")
    except Exception as e:
        logger.exception(f"❌ DocuLuna failed to start: {e}")
        raise

if __name__ == "__main__":
    try:
        logging.info("🚀 Starting DocuLuna...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Stopped by user.")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"❌ DocuLuna failed to start: {e}")
        sys.exit(1)