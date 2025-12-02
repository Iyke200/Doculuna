# DocuLuna Bot - Professional Document Processing Telegram Bot

## Overview
DocuLuna is a production-grade Telegram bot designed for professional document processing. Its core purpose is to provide a comprehensive suite of tools for PDF/Word conversion, image processing, and file compression within the Telegram messaging platform. The project aims to offer a seamless and efficient user experience for handling various document-related tasks, supported by a freemium model with premium subscriptions and a referral system.

## User Preferences
- **Direct UX** - No lengthy onboarding flows or website-like setup processes
- **Simple Messages** - Concise, action-focused messaging without excessive emojis or fluff
- **Smooth Experience** - Users should get to work immediately without setup friction

## Recent Changes (December 2, 2025) - UI/UX Specification Implementation
- **Complete Production UI/UX Specification Deployed:**
  - ✅ **Error Handling Templates:** 6 context-aware error templates (corrupted, unsupported, oversized, password-protected, timeout, quota) with clear explanations, solutions, and action buttons
  - ✅ **Success Message Templates:** Operation-specific success messages with metrics (time, size, file details) + gamification rewards display + next-action suggestions
  - ✅ **Tool-Specific Instructions:** Pre-operation guidance for each tool (PDF↔Word, Image→PDF, Merge, Split, Compress) explaining limits, timing, quality assurance
  - ✅ **Feature Suggestion System:** Smart "What's next?" prompts after each operation with context-appropriate next actions (compress, split, share, retry)
  - ✅ **Enhanced Profile Display:** Redesigned `/profile` command with visual progress bars, rank display, achievement showcase, and streamlined formatting
  - ✅ **Menu & Navigation Updates:** Consistent use of WELCOME_MSG, improved button layouts (2×3 grids), persistent Wallet access, shortened button text with arrow notation
  - ✅ **Next-Action Buttons:** Context-aware buttons after operations (Convert→Compress/Again, Compress→Share/Done, Split→Again/Back, Merge→Compress/Done)
  - ✅ **Smart Microcopy:** All messages maintain lunar-themed personality with action-focused tone, emoji optimization, and professional formatting
  - ✅ **Tool Instructions Module:** New `handlers/tool_instructions.py` with utility functions for showing instructions, formatting file sizes, and getting operation names
  - ✅ **Specification Document:** Complete 600+ line UI/UX specification in `DOCULUNA_UIUX_SPECIFICATION.md` with 9 implementation sections

## Recent Changes (December 1, 2025)
- **Complete Gamification System Integration:** Fully initialized and integrated gamification engine with real-time updates:
  - ✅ **XP & Leveling System:** Users earn XP from operations (convert: 50 XP, compress: 40 XP, merge: 60 XP, split: 55 XP, OCR: 65 XP, image_to_pdf: 45 XP). Levels calculated from total XP with square root progression formula: level = sqrt(xp/100) + 1
  - ✅ **Lunar Ranks System:** 8 progressive ranks from "🌑 New Moon" to "🌙 Luna Overlord" based on level thresholds (4, 9, 19, 34, 49, 69, 99)
  - ✅ **Moons Virtual Currency:** Earned on level-ups (5x level amount), resets, and streak bonuses. Can be collected and displayed in profiles/leaderboard
  - ✅ **Streak Tracking:** Daily activity streaks with 7-day milestone unlocking "Streak Lord" achievement. 20 bonus moons awarded on 7-day streaks
  - ✅ **Achievement System:** 8 achievements (First Document, Speedster, Streak Lord, Scholar, Moon Collector, Smart Worker, Document Master, Lunar Legend) with automatic unlock triggers
  - ✅ **Smart Recommendation Engine:** Analyzes user history patterns and generates personalized tips with confidence levels (0.5-0.9). Categories: compress, OCR, clean, merge, split, general. Recommending Smart Worker achievement +75 XP bonus
  - ✅ **Operation History Logging:** All operations automatically logged with filename, type, duration, status, file size, timestamp for analytics and recommendations
  - ✅ **Profile & Leaderboard Commands:** `/profile` shows rank, level, XP, moons, streaks, badges, achievements. `/recommend` provides personalized tips. `/history` displays recent operations with statistics
  - ✅ **Real-Time Integration:** XP/moons/streaks update immediately on each operation. Gamification linked in main.py init_db flow. Achievements check on level-ups and history milestones
  - ✅ **File Naming & Versioning:** Filename sanitization removes invalid characters, versioning prevents collisions with format: `{clean_base}_{operation}_{timestamp}_v{count}{ext}`
  - ✅ **First-Time & Empty DB Handling:** New users auto-initialized at level 1, 0 XP, 0 moons. Empty DB recommendations default to general tips. All queries gracefully handle missing data
  - ✅ **Asynchronous Architecture:** All gamification operations use aiosqlite for non-blocking async DB access. Executor runs bot with full async integration via aiogram polling
  - ✅ **Error Handling:** Comprehensive try-catch blocks in all modules. Database initialization auto-creates tables. Fallback messages for errors. All operations log to doculuna.log

## System Architecture

### Core Design Principles
The bot is built with a focus on modularity, scalability, and ease of use. It employs an asynchronous programming model using `aiogram` for efficient handling of Telegram API interactions. A key design decision was to integrate all document processing capabilities directly within Telegram, avoiding external websites or complex setups. The architecture supports both polling (development) and webhook (production) modes for deployment flexibility.

### Deployment Modes
- **Development (Polling):** Uses long-polling for local development and testing on Replit
- **Production (Webhook):** Uses webhook mode for cloud deployment on Render with automatic webhook registration
- **Mode Detection:** Automatically switches based on `ENVIRONMENT` variable (production/development)
- **Health Monitoring:** Includes `/health` and `/` endpoints for platform health checks

### UI/UX Architecture
- **Error Routing:** Intelligent error detection routes to context-aware templates with solutions
- **Success Flow:** Operation → Metrics → Gamification → Smart Suggestions → Next Actions
- **Menu Navigation:** Persistent main menu with WELCOME_MSG + consistent button layouts
- **Profile Display:** Visual progress bars + lunar ranks + achievement showcase + activity tracking
- **Feature Discovery:** Smart recommendations surface tool usage patterns to maximize feature adoption

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
- **Message Templates:** Centralized message system in `utils/messages.py` with specification-compliant templates for errors, success, recommendations, and tool instructions.
- **Tool Instructions Module:** New `handlers/tool_instructions.py` provides reusable utilities for showing pre-operation guidance and formatting operation data.
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

## File Structure
```
/
├── main.py (Bot initialization & async dispatcher)
├── config.py (Plans, settings, constants)
├── handlers/
│   ├── start.py (Welcome + /start command)
│   ├── callbacks.py (Menu navigation & routing)
│   ├── file_handler.py (File processing + success/error messages)
│   ├── gamification.py (XP, levels, ranks, achievements)
│   ├── smart_recommendation.py (Personalized suggestions)
│   ├── profile_handlers.py (/profile, /recommend, /history)
│   ├── admin.py (Admin panel & controls)
│   ├── wallet.py (Balance & earnings management)
│   ├── referrals.py (Referral tracking & rewards)
│   ├── tool_instructions.py (Pre-op guidance utilities)
│   └── [...other handlers]
├── tools/
│   ├── pdf_to_word.py (PDF ↔ Word conversion)
│   ├── compress.py (File compression)
│   ├── image_to_pdf.py (Image conversion)
│   ├── merge_pdf.py (PDF merging)
│   ├── split_pdf.py (PDF splitting)
│   └── [...other tools]
├── utils/
│   ├── messages.py (Message templates & UI copy)
│   ├── watermark.py (Watermark generation)
│   └── [...other utilities]
├── database/
│   └── db.py (Database initialization & queries)
├── DOCULUNA_UIUX_SPECIFICATION.md (Complete UI/UX spec)
└── replit.md (This file)
```
