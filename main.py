import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import NetworkError, Forbidden
from config import BOT_TOKEN
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
from tools.file_processor import process_file  # Keep lightweight processor

# Setup logging
logging.basicConfig(
    filename="doculuna.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create directories
os.makedirs("data/temp", exist_ok=True)
os.makedirs("payments", exist_ok=True)
os.makedirs("backups", exist_ok=True)
os.makedirs("analytics", exist_ok=True)

# Define admin user IDs (replace with your actual admin IDs)
ADMIN_USER_IDS = [123456789]  # Example admin ID

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

def main():
    """Initialize and run the Telegram bot."""
    try:
        logger.info("=== DocuLuna Bot Starting ===")

        if not BOT_TOKEN:
            logger.critical("BOT_TOKEN not found")
            raise ValueError("BOT_TOKEN is required")
        logger.info("✓ Bot token found")

        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("✓ Database initialized")

        # Create Application
        logger.info("Creating Telegram application...")
        app = Application.builder().token(BOT_TOKEN).build()
        logger.info("✓ Application created")

        # Add global error handler
        app.add_error_handler(error_callback)

        # Register command handlers
        logger.info("Registering handlers...")
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("referral", referrals))
        app.add_handler(CommandHandler("premium", premium_status))
        app.add_handler(CommandHandler("upgrade", upgrade))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("admin", admin_panel))

        # Import and add stats handler
        from handlers.stats import stats_command
        app.add_handler(CommandHandler("stats", stats_command))

        # Admin-only commands
        from handlers.admin import grant_premium_command, revoke_premium_command, broadcast_message, force_upgrade_command
        app.add_handler(CommandHandler("grant_premium", grant_premium_command))
        app.add_handler(CommandHandler("revoke_premium", revoke_premium_command))
        app.add_handler(CommandHandler("force_upgrade", force_upgrade_command))

        # Register callback query handler
        app.add_handler(CallbackQueryHandler(handle_callback_query))

        # Register message handlers for file processing
        app.add_handler(MessageHandler(
            filters.Document.ALL & ~filters.COMMAND,
            process_file
        ))
        app.add_handler(MessageHandler(
            filters.PHOTO & ~filters.COMMAND,
            process_file  # Route photos to process_file as well
        ))

        logger.info("✓ All handlers registered")

        # Start bot
        logger.info("Starting bot polling...")
        print("🤖 DocuLuna Bot is now running!")
        print("✓ Database initialized")
        print("✓ Handlers registered")
        print("✓ Polling started")

        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )

    except Exception as e:
        logger.critical(f"❌ Bot failed to start: {e}")
        print(f"❌ Bot failed to start: {e}")
        raise

async def handle_pdf_document(update, context):
    """Route PDF documents to appropriate handlers based on user context."""
    try:
        user_id = update.effective_user.id

        # Check usage limit
        if not await check_usage_limit(user_id):
            keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ You've reached your daily limit of 3 tool uses.\n\n"
                "Upgrade to **DocuLuna Pro** for unlimited access!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        # Show PDF tool options
        keyboard = [
            [InlineKeyboardButton("📝 Convert to Word", callback_data="tool_pdf_to_word")],
            [InlineKeyboardButton("✂️ Split PDF", callback_data="tool_split_pdf")],
            [InlineKeyboardButton("🔗 Merge with Others", callback_data="tool_merge_pdf")],
            [InlineKeyboardButton("🗜 Compress PDF", callback_data="tool_compress_pdf")]  # Added compression option
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📄 **PDF received!** What would you like to do?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # Store the document for later use
        context.user_data['last_pdf'] = update.message.document

    except Exception as e:
        logger.error(f"Error handling PDF document: {e}")
        await update.message.reply_text("❌ Error processing document. Please try again.")

async def handle_word_document(update, context):
    """Handle Word documents."""
    try:
        # Lazy import to avoid loading heavy deps on startup
        from tools.word_to_pdf import handle_word_to_pdf

        user_id = update.effective_user.id

        # Check usage limit
        if not await check_usage_limit(user_id):
            keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ You've reached your daily limit of 3 tool uses.\n\n"
                "Upgrade to **DocuLuna Pro** for unlimited access!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        await handle_word_to_pdf(update, context)
        await increment_usage(user_id)

    except Exception as e:
        logger.error(f"Error handling Word document: {e}")
        await update.message.reply_text("❌ Error processing document. Please try again.")

async def handle_image_document(update, context):
    """Handle image documents."""
    try:
        # Lazy import
        from tools.image_to_pdf import handle_image_to_pdf

        user_id = update.effective_user.id

        # Check usage limit
        if not await check_usage_limit(user_id):
            keyboard = [[InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_pro")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ You've reached your daily limit of 3 tool uses.\n\n"
                "Upgrade to **DocuLuna Pro** for unlimited access!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        await handle_image_to_pdf(update, context)
        await increment_usage(user_id)

    except Exception as e:
        logger.error(f"Error handling image document: {e}")
        await update.message.reply_text("❌ Error processing document. Please try again.")


if __name__ == "__main__":
    main()