# DocuLuna Bot - Professional Document Processing Telegram Bot

## Overview
DocuLuna is a production-grade Telegram bot designed for professional document processing. Its core purpose is to provide a comprehensive suite of tools for PDF/Word conversion, image processing, and file compression within the Telegram messaging platform. The project aims to offer a seamless and efficient user experience for handling various document-related tasks, supported by a freemium model with premium subscriptions and a referral system.

## User Preferences
- **Direct UX** - No lengthy onboarding flows or website-like setup processes
- **Simple Messages** - Concise, action-focused messaging without excessive emojis or fluff
- **Smooth Experience** - Users should get to work immediately without setup friction

## Recent Changes (October 25, 2025)
- **Database Functions:** Added complete set of async database functions including `get_user_data`, `create_user`, `get_all_users`, `get_user_role`, `get_user_by_id`, `add_usage_log`, `get_usage_count`, `update_user_premium_status`, `get_pending_payments`, and `log_admin_action`.
- **Admin Functionality:** Verified and tested full admin system with role-based access control, user management, analytics dashboard, payment tracking, activity logs, system tools, and broadcasting capabilities.
- **Async/Await:** Fixed all async patterns throughout handlers to properly await database operations.
- **Database Migrations:** Added automatic migrations for `is_banned` and `role` columns in the users table.
- **Bot Status:** Successfully running in polling mode with all handlers registered and database initialized.

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
- **Freemium Model:** Users receive 3 free daily uses, with unlimited access provided to premium subscribers.
- **Premium Subscriptions:** Offers weekly (₦1,000) and monthly (₦3,500) plans, integrated with payment gateways.
- **Referral System:** Rewards users for successful referrals (₦500 for monthly, ₦150 for weekly).
- **Admin Panel:** Provides user management, analytics, broadcasting capabilities, and statistics for administrators.
- **Database:** Uses SQLite for persistent storage of user profiles, usage logs, referral data, payment history, and feedback.
- **Security:** Incorporates environment variables for sensitive data (BOT_TOKEN, ADMIN_USER_IDS), sanitized logging, rate limiting, and file size restrictions to prevent abuse.

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