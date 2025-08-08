
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from database.db import get_all_users, update_premium_status, get_pending_payments, approve_payment, reject_payment
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel with management options."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return

        keyboard = [
            [InlineKeyboardButton("📊 View Bot Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 View Users", callback_data="admin_users")],
            [InlineKeyboardButton("💰 View Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("📤 Broadcast Message", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🧪 Test Features", callback_data="admin_test")],
            [InlineKeyboardButton("⚙️ Force Upgrade", callback_data="admin_force_upgrade")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "🔧 **Admin Panel**\n\n"
            "Welcome to the admin control center.\n"
            "Select an option below:"
        )

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Admin panel accessed by user {user_id}")

    except Exception as e:
        logger.error(f"Error in admin panel for user {user_id}: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def show_bot_stats(query, context):
    """Show bot statistics."""
    try:
        users = get_all_users()
        total_users = len(users)
        premium_users = len([u for u in users if u.get('is_premium', False)])
        
        message = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"💎 Premium Users: {premium_users}\n"
            f"🆓 Free Users: {total_users - premium_users}\n"
        )

        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing bot stats: {e}")

async def show_pending_payments(query, context):
    """Show pending payments."""
    try:
        payments = get_pending_payments()

        if not payments:
            message = "💰 **Pending Payments**\n\nNo pending payments found."
        else:
            message = f"💰 **Pending Payments** ({len(payments)} pending)\n\n"
            for payment in payments[:5]:  # Show first 5 payments
                message += (
                    f"ID: {payment['id']}\n"
                    f"User: {payment.get('first_name', 'Unknown')} ({payment['user_id']})\n"
                    f"Plan: {payment['plan_type']}\n"
                    f"Amount: ₦{payment['amount']}\n"
                    f"Date: {payment.get('created_at', 'N/A')[:10]}\n\n"
                )
            if len(payments) > 5:
                message += f"... and {len(payments) - 5} more pending payments."

        keyboard = [
            [InlineKeyboardButton("✅ Approve Payment", callback_data="admin_approve_payment")],
            [InlineKeyboardButton("❌ Reject Payment", callback_data="admin_reject_payment")],
            [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing pending payments: {e}")

async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium to a user via command."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /grant_premium <user_id> [days]")
            return

        target_user = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        
        if update_premium_status(target_user, True, expires_at):
            await update.message.reply_text(f"✅ Premium granted to user {target_user} for {days} days.")
        else:
            await update.message.reply_text("❌ Failed to grant premium.")

    except Exception as e:
        logger.error(f"Error granting premium: {e}")
        await update.message.reply_text("❌ Error granting premium.")

async def revoke_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoke premium from a user."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /revoke_premium <user_id>")
            return

        target_user = int(context.args[0])
        
        if update_premium_status(target_user, False):
            await update.message.reply_text(f"✅ Premium revoked from user {target_user}.")
        else:
            await update.message.reply_text("❌ Failed to revoke premium.")

    except Exception as e:
        logger.error(f"Error revoking premium: {e}")
        await update.message.reply_text("❌ Error revoking premium.")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return

        message = " ".join(context.args)
        users = get_all_users()
        
        sent = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(user['user_id'], message)
                sent += 1
            except:
                failed += 1

        await update.message.reply_text(f"📤 Broadcast complete!\nSent: {sent}\nFailed: {failed}")

    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        await update.message.reply_text("❌ Error broadcasting message.")

async def force_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force upgrade a user."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /force_upgrade <user_id> <plan_type>")
            return

        target_user = int(context.args[0])
        plan_type = context.args[1] if len(context.args) > 1 else "lifetime"
        
        if plan_type == "daily":
            expires_at = (datetime.now() + timedelta(days=1)).isoformat()
        elif plan_type == "3month":
            expires_at = (datetime.now() + timedelta(days=90)).isoformat()
        else:  # lifetime
            expires_at = None
        
        if update_premium_status(target_user, True, expires_at):
            await update.message.reply_text(f"✅ Force upgraded user {target_user} to {plan_type}.")
        else:
            await update.message.reply_text("❌ Failed to force upgrade.")

    except Exception as e:
        logger.error(f"Error force upgrading: {e}")
        await update.message.reply_text("❌ Error force upgrading user.")
