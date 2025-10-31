# DocuLuna Bot 🌟

A professional Telegram bot for document processing, featuring PDF/Word conversion, image processing, file compression, and premium subscription management.

## Features ✨

### Document Processing
- 📄 **PDF to Word** - Convert PDF files to editable Word documents
- 📝 **Word to PDF** - Convert Word documents to PDF format
- 🖼️ **Image to PDF** - Convert images (JPG, PNG, GIF) to PDF
- 📊 **PDF Merging** - Combine multiple PDF files into one
- ✂️ **PDF Splitting** - Split PDF files into separate pages
- 🗜️ **File Compression** - Reduce file sizes while maintaining quality

### Premium Features
- 💎 **Weekly Premium** - ₦1,000 for 7 days of unlimited access
- 💎 **Monthly Premium** - ₦3,500 for 30 days of unlimited access
- 🎁 **Referral System** - Earn ₦500 for monthly referrals, ₦150 for weekly
- 📊 **Usage Tracking** - Monitor your document processing activity
- 🚀 **Priority Processing** - Faster processing for premium users

### Administration
- 📈 **Analytics Dashboard** - Track user engagement and revenue
- 👥 **User Management** - Manage user accounts and premium status
- 📢 **Broadcasting** - Send announcements to all users
- 💰 **Payment Tracking** - Monitor payment transactions and referrals
- 🔄 **Database Backups** - Automated backup system

## Quick Start 🚀

### Prerequisites
- A Telegram account
- Access to Telegram's @BotFather

### Setup on Replit

1. **Get Your Bot Token**
   - Open Telegram and find @BotFather
   - Send `/newbot` and follow the instructions
   - Save the bot token you receive

2. **Configure Secrets**
   - Click the **Secrets** tab (🔒 icon) in Replit
   - Add your bot token:
     - Key: `BOT_TOKEN`
     - Value: [Your bot token from BotFather]

3. **Run the Bot**
   - Click the **Run** button
   - Wait for "✅ DocuLuna started successfully" in the console
   - Open Telegram and find your bot
   - Send `/start` to begin!

## Usage 💡

### For Users
1. Start a chat with your bot on Telegram
2. Send `/start` to see available options
3. Upload documents for processing
4. Free users get 3 uses per day
5. Upgrade to premium for unlimited access

### For Admins
- Send `/admin` to access the admin panel
- View statistics with `/stats`
- Broadcast messages to all users
- Manage premium subscriptions
- Track payments and referrals

## Configuration ⚙️

### Environment Variables
All configuration is done through Replit Secrets. See `.env.example` for all available options.

**Required:**
- `BOT_TOKEN` - Your Telegram bot token

**Optional:**
- `ENVIRONMENT` - Set to `production` for webhook mode
- `WEBHOOK_URL` - Your webhook URL (for production)
- `PAYSTACK_SECRET_KEY` - Paystack payment integration
- `PAYSTACK_PUBLIC_KEY` - Paystack payment integration
- `ADMIN_USER_IDS` - Comma-separated Telegram user IDs for admins

### Deployment Modes

**Development Mode (Default)**
- Uses long polling to receive messages
- No webhook URL required
- Perfect for testing and development

**Production Mode**
- Uses webhooks for better performance
- Requires a webhook URL
- Set `ENVIRONMENT=production` in Secrets
- Set `WEBHOOK_URL` to your deployment URL

## Technology Stack 🛠️

- **Python 3.11** - Core programming language
- **aiogram 3.13.1** - Modern Telegram Bot API framework
- **SQLite** - Local database for user data and analytics
- **PyMuPDF** - PDF manipulation and processing
- **python-docx** - Word document processing
- **Pillow** - Image processing
- **Paystack** - Payment processing integration

## File Structure 📁

```
DocuLuna/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── database/
│   ├── db.py             # Database operations
│   ├── schema.sql        # Database schema
│   └── doculuna.db       # SQLite database
├── handlers/             # Command handlers
│   ├── start.py         # Welcome and onboarding
│   ├── admin.py         # Admin panel
│   ├── payments.py      # Payment processing
│   ├── premium.py       # Premium features
│   └── ...
├── tools/               # Document processing
│   ├── pdf_to_word.py
│   ├── word_to_pdf.py
│   ├── compress.py
│   └── ...
└── utils/              # Utilities
    ├── usage_tracker.py
    ├── error_handler.py
    └── ...
```

## Security 🔒

- Secure secret management via Replit Secrets
- No secrets exposed in logs or code
- Rate limiting to prevent abuse
- File size limits (20MB free, 50MB premium)
- Admin-only commands with user ID verification

## Support 📞

### Common Issues

**Bot won't start**
- Check that `BOT_TOKEN` is set in Secrets
- Review console logs for errors
- Verify the token is valid

**Bot not responding**
- Ensure the workflow is running
- Check the console for error messages
- Restart the bot using the Run button

**Payment issues**
- Verify Paystack credentials
- Check payment logs in admin panel
- Ensure account details are correct

### Getting Help
1. Check the console logs for detailed error messages
2. Review the `replit.md` file for technical documentation
3. Contact your system administrator

## License 📄

This is a proprietary project. All rights reserved.

## Credits 👏

Built with ❤️ using:
- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot API framework
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF processing
- [python-docx](https://github.com/python-openxml/python-docx) - Word processing
- [Paystack](https://paystack.com/) - Payment processing

---

**Ready to get started?** Click the Run button and send `/start` to your bot on Telegram! 🚀
