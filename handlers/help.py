‎# handlers/help.py
‎import logging
‎from telegram import Update
‎from telegram.ext import ContextTypes
‎from telegram.error import RetryAfter
‎
‎logger = logging.getLogger(__name__)
‎
‎async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
‎    try:
‎        message = (
‎            "📄 **DocuLuna Help – Your Document Assistant!**\n\n"
‎            "Convert WAEC results, NYSC docs, or CVs with ease!\n\n"
‎            "🔹 **Commands**:\n"
‎            "/start - Get started\n"
‎            "/help - View this guide\n"
‎            "/premium - Explore Pro plans (1,000 NGN/week, 3,500 NGN/month)\n"
‎            "/referrals - Earn free Pro days\n"
‎            "/stats - Check your usage\n"
‎            "/upgrade - Go Pro for watermark-free outputs\n\n"
‎            "🔹 **How to Use**:\nUpload a PDF, Word, or image to convert or create a CV!"
‎        )
‎        for attempt in range(3):
‎            try:
‎                await update.message.reply_text(message, parse_mode="Markdown")
‎                break
‎            except RetryAfter as e:
‎                logger.warning(f"Rate limit hit in help_command: {e}")
‎                await asyncio.sleep(e.retry_after)
‎    except Exception as e:
‎        logger.error(f"Error in help_command: {e}")
‎        await update.message.reply_text("❌ Error showing help. Try again.")
