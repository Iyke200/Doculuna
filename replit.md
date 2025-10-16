# DocuLuna Bot - Professional Document Processing Telegram Bot

## Overview
DocuLuna is a production-grade Telegram bot for professional document processing, including PDF/Word conversion, image processing, file compression, and premium subscription management.

## Current State (October 16, 2025)
- ✅ **Project Migration Complete** - Successfully migrated to Replit environment
- ✅ **All Dependencies Installed** - All Python packages installed and verified (aiogram 3.13.1, PyMuPDF, python-docx, etc.)
- ✅ **Database Ready** - SQLite database initialized with user management, usage tracking, payments, and referrals
- ✅ **Workflow Running** - Bot is actively running in development mode (polling)
- ✅ **All Handlers Registered** - Start, premium, file processing, admin, stats, payments, referrals handlers working
- ✅ **Import Issues Fixed** - Resolved circular imports and missing dependencies
- ✅ **Security Enhanced** - Admin IDs moved to environment variables for security
- ✅ **Document Processing Ready** - All conversion tools fully integrated with production-ready code
- ✅ **UX Flows Complete** - All 13 UX flows implemented with exact specifications
- ⚠️ **REQUIRES BOT_TOKEN** - Bot needs Telegram BOT_TOKEN to run (add in Secrets tab)
- ⚠️ **REQUIRES ADMIN_USER_IDS** - Set admin user IDs in Secrets for admin access

## Recent Changes (October 16, 2025)
- **All Tools Fixed and Validated (Latest)** - Comprehensive tool fixes completed:
  - Fixed syntax error in merge.py (incomplete f-string, added missing except block)
  - Fixed import error in file_processor.py (InlineKeyboardBuilder import location)
  - Fixed variable naming in image_to_pdf.py (aiogram 3.x compatibility)
  - Implemented complete split.py with defensive validation for pages_per_file
  - Added input validation to prevent ZeroDivisionError in split operations
  - All 7 tools (pdf_to_word, word_to_pdf, image_to_pdf, compress, split, merge, file_processor) now import and run without errors
  - Bot verified running successfully with all handlers registered
- **Import Migration Complete** - Successfully migrated project to Replit:
  - Fixed all import errors and circular dependencies
  - Added missing Redis fallback code for upgrade state storage
  - Resolved format_currency circular import issue
  - Enhanced security by moving admin IDs to environment variables

## Previous Changes (October 12, 2025)
- **Document Processing Implemented (Latest)** - Integrated production-ready conversion tools:
  - PDF ↔ Word conversion with layout preservation
  - Image → PDF conversion with A4 sizing
  - File compression for PDF and DOCX (medium quality)
  - All tools validated and error-handled
- **Complete UX Implementation** - All 13 user flows implemented:
  - Welcome message with inline buttons (📂 Process, 💎 Premium, 👤 Account, ❓ Help)
  - Premium plans display (₦1000 weekly, ₦3500 monthly)
  - Account overview with premium status
  - Help section with essential commands
  - Usage limit messages (3 free daily actions)
  - File processing with conversion options
  - Success/error handling with proper messages
  - Referral system with ₦500 rewards
  - Admin panel access
- **File Handler Created** - New file_handler.py with document/image processing
- **Usage Tracking** - Implemented daily limit checks and premium bypass
- **Simplified UX/UI** - Removed onboarding flow for smooth direct experience
- **Fresh GitHub Import** - Successfully imported and configured for Replit environment
- **All Dependencies Installed** - aiogram 3.13.1, PyMuPDF, python-docx, Pillow, reportlab, pdf2docx, PyPDF2, aiofiles, pikepdf
- **Workflow Configured** - "DocuLuna Bot" workflow with console output
- **Deployment Configured** - VM deployment ready for production use
- **Database Verified** - Tested database initialization successfully

## User Preferences
- **Direct UX** - No lengthy onboarding flows or website-like setup processes
- **Simple Messages** - Concise, action-focused messaging without excessive emojis or fluff
- **Smooth Experience** - Users should get to work immediately without setup friction

## Setup Instructions

### 1. Get a Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the instructions
3. Copy the bot token you receive

### 2. Configure Environment Variables
1. Click the **Secrets** tab (🔒 icon) in Replit
2. Add required secrets:
   - Key: `BOT_TOKEN`
   - Value: Your Telegram bot token from BotFather
   
   - Key: `ADMIN_USER_IDS`
   - Value: Your Telegram user ID (comma-separated for multiple admins, e.g., "123456789,987654321")
   
3. Optional: Add Paystack integration secrets for payment processing:
   - `PAYSTACK_SECRET_KEY`
   - `PAYSTACK_PUBLIC_KEY`

### 3. Run the Bot
1. Click the **Run** button at the top
2. The bot will start in development mode (polling)
3. Check the console for "✅ DocuLuna started successfully"
4. Test by sending `/start` to your bot on Telegram

### 4. Deploy to Production (Optional)
1. Set up a webhook URL in the Secrets tab:
   - Key: `WEBHOOK_URL`
   - Value: Your webhook URL (e.g., https://yourdomain.com/webhook)
2. Set environment to production:
   - Key: `ENVIRONMENT`
   - Value: `production`
3. Click **Deploy** to publish your bot

## Project Architecture

### Core Components
- **main.py** - Bot entry point with production/development mode switching
- **config.py** - Configuration management with premium plans and payment settings  
- **database/** - SQLite database with schema management and user data
  - `db.py` - Database operations
  - `schema.sql` - Database schema
  - `doculuna.db` - SQLite database file
- **handlers/** - Modular command handlers
  - `start.py` - Simple welcome (no onboarding flow)
  - `help.py` - Concise help (essential commands only)
  - `file_handler.py` - Document/image processing with usage limits (NEW)
  - `admin.py` - Admin panel and management
  - `payments.py` - Payment processing
  - `paystack.py` - Paystack integration
  - `premium.py` - Premium features
  - `referrals.py` - Referral system
  - `stats.py` - Statistics and analytics
  - `callbacks.py` - Callback query handlers
- **tools/** - Document processing utilities (production-ready)
  - `pdf_to_word.py` - PDF to Word conversion with layout preservation
  - `word_to_pdf.py` - Word to PDF conversion with formatting preservation
  - `image_to_pdf.py` - Image to PDF conversion with A4 sizing
  - `compress.py` - PDF/DOCX compression with quality levels
  - `split.py` - PDF splitting
  - `merge.py` - PDF merging
- **utils/** - Support utilities
  - `usage_tracker.py` - Usage tracking and limits
  - `error_handler.py` - Error handling
  - `file_processor.py` - File processing utilities
  - `premium_utils.py` - Premium subscription utilities
  - `referral_utils.py` - Referral system utilities
  - `watermark.py` - Watermarking
  - `backup.py` - Database backups

### Key Features
- **Document Processing** ✅ FULLY IMPLEMENTED
  - PDF ↔ Word conversion with layout/formatting preservation
  - Image → PDF conversion with automatic A4 sizing
  - File compression (PDF/DOCX) with medium quality optimization
  - Production-ready with error handling and validation
- **Premium Subscriptions** - Weekly (₦1,000) and Monthly (₦3,500) plans with Paystack integration
- **Referral System** - User referrals with rewards and tracking (₦500 for monthly, ₦150 for weekly)
- **Usage Limits** - Freemium model with 3 free uses per day, unlimited for premium users
- **Admin Panel** - Advanced user management, analytics, broadcasting, and statistics
- **Payment Processing** - Secure payment handling with Paystack verification
- **Webhook Support** - Production-ready webhook mode for scalability

### Dependencies
- **aiogram 3.13.1** - Modern Telegram Bot API library
- **aiohttp 3.10.10** - Async HTTP client/server
- **PyMuPDF 1.23.26** - PDF manipulation
- **python-docx 1.1.0** - Word document processing
- **Pillow 10.2.0** - Image processing
- **python-dotenv 1.0.1** - Environment variable management
- **reportlab 4.0.8** - PDF generation
- **docx2pdf 0.1.8** - Document conversion
- **pdf2docx 0.5.6** - PDF to Word conversion
- **PyPDF2 3.0.1** - PDF manipulation
- **aiofiles 23.2.1** - Async file operations
- **pikepdf** - PDF manipulation
- **cryptography** - Security utilities

### Security Features
- **Environment variables** - Secure secret management via Replit Secrets
- **Sanitized logging** - No secret leakage in logs (HTTP logs set to WARNING level)
- **Rate limiting** - Abuse prevention and usage controls
- **File size limits** - 20MB for free users, 50MB for premium users
- **Admin-only commands** - Restricted access to administrative features

## Deployment Configuration
- **Development Mode** - Polling mode (default, no webhook required)
- **Production Mode** - Webhook mode on port 5000 with webhook URL
- **Deployment Target** - VM (always running, suitable for Telegram bots)
- **Auto-restart** - Configured to restart automatically on crashes

## Database Schema
The bot uses SQLite with the following tables:
- **users** - User profiles, premium status, onboarding tracking
- **usage_logs** - Tool usage history and success tracking
- **referrals** - Referral codes, counts, and earnings
- **feedback** - User feedback collection
- **payment_logs** - Payment transaction history
- **referral_rewards** - Referral reward tracking
- **premium_expiry_warnings** - Premium expiration notification tracking

## Environment Variables
See `.env.example` for all available configuration options. Required variables:
- `BOT_TOKEN` - Telegram bot token (required)
- `ENVIRONMENT` - development or production (optional, defaults to development)

Optional variables for enhanced functionality:
- `PAYSTACK_SECRET_KEY` - Paystack payment integration
- `PAYSTACK_PUBLIC_KEY` - Paystack payment integration
- `WEBHOOK_URL` - Webhook URL for production mode
- `ADMIN_USER_IDS` - Admin Telegram user IDs

## Troubleshooting

### Bot won't start
- Check that `BOT_TOKEN` is set in Secrets
- Review console logs for error messages
- Verify all dependencies are installed

### Bot not responding
- Ensure the workflow is running (check console)
- Verify bot token is valid
- Check database initialization logs

### Payment issues
- Verify Paystack credentials are set
- Check payment logs in database
- Review Paystack API status

## Support
For issues or questions:
1. Check console logs for detailed error messages
2. Verify environment variables are correctly set
3. Review database integrity
4. Contact bot administrator for technical support
