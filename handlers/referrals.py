# handlers/referrals.py
import logging
import secrets
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
from database.db import add_referral_code, get_referral_stats, increment_referral_count, get_top_referrers

logger = logging.getLogger(__name__)

# Default referral premium days
REFERRAL_PREMIUM_DAYS = 7

async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral options."""
    await show_referrals(update, context)

async def show_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        stats = get_referral_stats(user_id)
        referral_code = await generate_referral_code(user_id)
        referral_link = f"https://t.me/{context.bot.username}?start={referral_code}"
        top_referrers = get_top_referrers(limit=5)
        leaderboard = "\n".join(f"{i+1}. @{r['username']}: {r['referral_count']} referrals" for i, r in enumerate(top_referrers))
        message = (
            f"👥 **Refer & Earn Free Pro Access!**\n\n"
            f"📌 **Your Code:** `{referral_code}`\n"
            f"🔗 **Share Link:** {referral_link}\n\n"
            f"👤 **Your Referrals:** {stats['referral_count']}\n"
            f"🎁 **Pro Days Earned:** {stats['premium_days_earned']}\n\n"
            f"💡 Invite friends for {REFERRAL_PREMIUM_DAYS} days of Pro access – free!\n\n"
            f"🏆 **Top Referrers:**\n{leaderboard}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
        for attempt in range(3):
            try:
                await update.message.reply_text(
                    message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
                )
                break
            except RetryAfter as e:
                logger.warning(f"Rate limit hit in show_referrals: {e}")
                await asyncio.sleep(e.retry_after)
    except Exception as e:
        logger.error(f"Error in show_referrals: {e}")
        await update.message.reply_text("❌ Error fetching referral stats. Try again.")

async def generate_referral_code(user_id: int) -> str:
    try:
        code = secrets.token_hex(4)
        add_referral_code(user_id, code)
        return code
    except Exception as e:
        logger.error(f"Error generating referral code for user {user_id}: {e}")
        return "ERROR"

async def get_referral_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    try:
        code = await generate_referral_code(user_id)
        return f"https://t.me/{context.bot.username}?start={code}"
    except Exception as e:
        logger.error(f"Error generating referral link for user {user_id}: {e}")
        return "ERROR"