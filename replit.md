# DocuLuna Bot - Professional Document Processing Telegram Bot

## Overview
DocuLuna is a production-grade Telegram bot designed for professional document processing. Its core purpose is to provide a comprehensive suite of tools for PDF/Word conversion, image processing, and file compression within the Telegram messaging platform. The project aims to offer a seamless and efficient user experience for handling various document-related tasks, supported by a freemium model with premium subscriptions and a referral system.

## User Preferences
- **Direct UX** - No lengthy onboarding flows or website-like setup processes
- **Simple Messages** - Concise, action-focused messaging without excessive emojis or fluff
- **Smooth Experience** - Users should get to work immediately without setup friction

## Recent Changes (October 30, 2025)
- **Main Menu Wallet Access:** Added "🏦 Wallet" button to /start menu for easy access to wallet features
- **Referral Link Fix:** Fixed "username not found" error by implementing dynamic bot.get_me() instead of hardcoded username
- **Watermark Enhancement:** Enabled watermarking for image-to-PDF conversions for free users
- **Feature Verification:** All wallet, referral, withdrawal, and leaderboard features tested and confirmed operational

## Previous Changes (October 28, 2025)
- **Complete Wallet System:** Implemented comprehensive wallet management with balance tracking, total earnings display, and referral code generation (format: DOCU{user_id}).
- **Referral Tracking System:** New users using referral links are automatically tracked; referrers earn ₦150 for weekly plans and ₦350 for monthly plans when referred users purchase premium.
- **Withdrawal Flow with FSM:** Multi-step withdrawal process collecting amount, account name, bank name, and account number with ₦2,000 minimum threshold and validation.
- **Admin Withdrawal Management:** Admins receive instant notifications for withdrawal requests with inline approve/reject buttons; approval deducts from wallet, rejection keeps balance intact.
- **Referral Statistics:** Users can view complete referral stats including total referrals, completed/pending status, total earned, and shareable referral link.
- **Weekly Leaderboard:** Dynamic leaderboard showing top 10 referrers by total earnings to encourage engagement.
- **Withdrawal History:** Users can view their past withdrawal requests with status indicators (pending, approved, rejected).
- **Database Schema Updates:** Added `wallets`, `referral_relationships` tables with proper foreign keys and constraints preventing duplicate referrals.
- **Pricing Corrections:** Fixed premium plan pricing to ₦1,000 (weekly) and ₦3,500 (monthly) with corresponding referral rewards.
- **Integration Points:** Referral rewards automatically credited in `activate_premium()` function; start handler tracks referrals from /start commands.
- **Watermark System:** Integrated comprehensive watermarking for all free user document operations (PDF/Word conversion, Image to PDF, PDF/DOCX compression) using utils/watermark.py with bottom-center text placement, gray color, and low opacity.
- **Bot Status:** All wallet, referral, withdrawal, and watermark features tested and running successfully with proper error handling and security controls.

## System Architecture

### Core Design Principles
The bot is built with a focus on modularity, scalability, and ease of use. It employs an asynchronous programming model using `aiogram` for efficient handling of Telegram API interactions. A key design decision was to integrate all document processing capabilities directly within Telegram, avoiding external websites or complex setups. The architecture supports both polling (development) and webhook (production) modes for deployment flexibility.

### UI/UX Decisions
The user interface is designed to be direct and functional. Key UX flows include:
- A clear welcome message with inline buttons for core functionalities (Process, Premium, Account, Help).
- Concise premium plan displays and account overviews.
- Direct file processing with clear conversion options.
- User-friendly rate limiting with reminders and upgrade prompts.
- Specific error messages for better user guidance.

### Technical Implementation & Feature Specifications
- **Document Processing:** Full support for PDF ↔ Word conversion (preserving layout), Image → PDF conversion (A4 sizing), and file compression for PDF/DOCX (medium quality). All tools include robust error handling and validation.
- **Freemium Model:** Users receive 3 free daily uses, with unlimited access provided to premium subscribers. Free users receive watermarked documents; premium users receive clean files.
- **Watermarking:** Comprehensive watermark system using utils/watermark.py applied to all free user operations (PDF/Word conversion, Image to PDF, PDF/DOCX compression). Watermark text: "Processed with DocuLuna - Upgrade for Watermark-Free" placed at bottom-center with gray color and low opacity.
- **Premium Subscriptions:** Offers weekly (₦1,000) and monthly (₦3,500) plans, integrated with payment gateways.
- **Wallet System:** Each user has a digital wallet tracking balance and total earnings from referrals with transaction history.
- **Referral System:** Automated referral tracking with unique codes (DOCU{user_id}); rewards credited on successful premium purchases (₦350 for monthly, ₦150 for weekly).
- **Withdrawal System:** Users can request withdrawals (minimum ₦2,000) with multi-step FSM collecting bank details; admin approval/rejection flow with automated notifications.
- **Leaderboard:** Weekly ranking of top 10 referrers by earnings to gamify the referral system.
- **Admin Panel:** Provides user management, analytics, broadcasting capabilities, withdrawal management, and statistics for administrators.
- **Database:** Uses SQLite with tables for users, wallets, referral_relationships, withdrawal_requests, usage logs, payment history, and feedback.
- **Security:** Incorporates environment variables for sensitive data (BOT_TOKEN, ADMIN_USER_IDS), sanitized logging, rate limiting, file size restrictions, admin-only access controls, and UNIQUE constraints preventing duplicate referrals.

### System Design Choices
- **Modular Handlers:** Command and callback handlers are organized into separate files (`start.py`, `file_handler.py`, `admin.py`, etc.) for maintainability.
- **Dedicated Tool Utilities:** Document processing logic is encapsulated in a `tools/` directory (e.g., `pdf_to_word.py`, `compress.py`), promoting reusability and clear separation of concerns.
- **Configuration Management:** `config.py` centralizes premium plans and payment settings.
- **Asynchronous Operations:** Leverages `aiogram` and `aiofiles` for non-blocking I/O, improving bot responsiveness.
- **Automatic Migrations:** Database schema updates are handled automatically to accommodate new features like usage tracking and referral systems.

## External Dependencies

- **Telegram Bot API:** Interacted with via `aiogram` (version 3.13.1).
- **SQLite:** Used as the primary database, accessed asynchronously via `aiosqlite`.
- **Paystack:** Integrated for secure payment processing using `PAYSTACK_SECRET_KEY` and `PAYSTACK_PUBLIC_KEY`.
- **PyMuPDF (fitz):** For high-performance PDF manipulation.
- **python-docx:** For processing Word documents.
- **Pillow:** For image processing tasks.
- **python-dotenv:** For managing environment variables.
- **reportlab:** For PDF generation.
- **docx2pdf & pdf2docx:** For robust Word to PDF and PDF to Word conversions.
- **PyPDF2 & pikepdf:** Additional libraries for PDF manipulation.
- **aiohttp:** For asynchronous HTTP requests, often used internally by `aiogram` and other libraries.
- **cryptography:** For security-related utilities.
- **psutil:** For system monitoring (e.g., resource usage).