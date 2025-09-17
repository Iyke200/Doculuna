# DocuLuna Bot - Professional Document Processing Telegram Bot

## Overview
DocuLuna is a production-grade Telegram bot for professional document processing, including PDF/Word conversion, image processing, file compression, and premium subscription management.

## Current State
- ✅ **RUNNING** - Bot is operational and connected to Telegram API
- ✅ **Database** - SQLite database initialized with user management, usage tracking, payments, and referrals  
- ✅ **Security** - Hardened logging, secret management, import validation
- ✅ **Production Ready** - Webhook support for deployment, polling for development

## Recent Changes (September 17, 2025)
- **Fixed critical import conflict** - Removed deprecated `telegram` package, using `python-telegram-bot==20.7`
- **Security hardening** - Prevented BOT_TOKEN leakage in HTTP logs
- **Added production deployment** - Webhook mode for production, polling for development
- **Database initialization** - Proper SQLite setup with schema management
- **Workflow configuration** - Background service running successfully

## User Preferences
- **Production Grade** - This is a real-life production project requiring professional standards
- **Advanced Admin Panel** - Comprehensive admin features for user management and analytics
- **All Tools Working** - Document conversion, compression, splitting, merging capabilities

## Project Architecture

### Core Components
- **main.py** - Bot entry point with production/development mode switching
- **config.py** - Configuration management with premium plans and payment settings  
- **database/** - SQLite database with schema management and user data
- **handlers/** - Modular command handlers (start, admin, payments, premium, etc.)
- **tools/** - Document processing utilities (PDF/Word conversion, compression, etc.)
- **utils/** - Support utilities (usage tracking, error handling, file processing)

### Key Features
- **Document Processing** - PDF↔Word conversion, image→PDF, file compression, splitting/merging
- **Premium Subscriptions** - Weekly/Monthly plans with Paystack integration
- **Referral System** - User referrals with rewards and tracking
- **Usage Limits** - Freemium model with daily usage tracking
- **Admin Panel** - Advanced user management, analytics, broadcasting
- **Payment Processing** - Secure payment handling with verification

### Dependencies
- **python-telegram-bot 20.7** - Modern Telegram Bot API
- **PyMuPDF, python-docx** - Document processing
- **Pillow, reportlab** - Image and PDF generation
- **SQLite** - Local database storage
- **aiofiles** - Async file handling

### Security Features
- **Environment variables** - Secure BOT_TOKEN management
- **Sanitized logging** - No secret leakage in logs
- **Import validation** - Runtime guards against package conflicts
- **Rate limiting** - Abuse prevention and usage controls

## Deployment Configuration
- **Development** - Polling mode on localhost
- **Production** - Webhook mode on 0.0.0.0:5000 with TLS
- **Background Service** - VM deployment target for persistent operation

## Next Steps
1. **Rotate BOT_TOKEN** - Security requirement after previous log exposure
2. **Production deployment** - Ready for live deployment with webhook support
3. **Feature testing** - Verify all document processing tools work correctly