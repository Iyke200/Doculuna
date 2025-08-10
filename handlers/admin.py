import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from database.db import (
    get_all_users,
    update_premium_status,
    get_pending_payments,
    approve_payment,
    reject_payment,
)
from config import ADMIN_IDS, ADMIN_USER_IDS

logger = logging.getLogger(__name__)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel with management options."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text(
                "❌ Access denied. Admin privileges required."
            )
            return

        # Get stats
        all_users = get_all_users()
        total_users = len(all_users)
        premium_users = len([u for u in all_users if u.get('is_premium', False)])
        pending_payments = get_pending_payments()

        keyboard = [
            [InlineKeyboardButton("👥 User Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("💳 Pending Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("💎 Grant Premium", callback_data="admin_grant")],
            [InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        admin_message = (
            "🔧 **Admin Panel**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Users: {total_users}\n"
            f"• Premium Users: {premium_users}\n"
            f"• Pending Payments: {len(pending_payments)}\n\n"
            "Choose an option:"
        )

        await update.message.reply_text(
            admin_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        logger.info(f"Admin panel accessed by user {user_id}")

    except Exception as e:
        logger.error(f"Error in admin panel: {e}")
        await update.message.reply_text("❌ Error loading admin panel.")


async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium to a user."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: /grant_premium <user_id> <days>\n"
                "Example: /grant_premium 123456789 30"
            )
            return

        target_user_id = int(context.args[0])
        days = int(context.args[1])

        expires_at = datetime.now() + timedelta(days=days)
        update_premium_status(target_user_id, True, expires_at)

        await update.message.reply_text(
            f"✅ Premium granted to user {target_user_id} for {days} days."
        )

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

        if len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /revoke_premium <user_id>\n"
                "Example: /revoke_premium 123456789"
            )
            return

        target_user_id = int(context.args[0])
        update_premium_status(target_user_id, False, None)

        await update.message.reply_text(
            f"✅ Premium revoked from user {target_user_id}."
        )

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
            await update.message.reply_text(
                "Usage: /broadcast <message>\n"
                "Example: /broadcast Hello everyone!"
            )
            return

        message = " ".join(context.args)
        users = get_all_users()
        success_count = 0

        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **Broadcast Message:**\n\n{message}",
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception:
                continue

        await update.message.reply_text(
            f"✅ Broadcast sent to {success_count}/{len(users)} users."
        )

    except Exception as e:
        logger.error(f"Error broadcasting: {e}")
        await update.message.reply_text("❌ Error sending broadcast.")


async def force_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force upgrade a user to premium."""
    try:
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /force_upgrade <user_id>\n"
                "Example: /force_upgrade 123456789"
            )
            return

        target_user_id = int(context.args[0])
        expires_at = datetime.now() + timedelta(days=36500)  # Lifetime
        update_premium_status(target_user_id, True, expires_at)

        await update.message.reply_text(
            f"✅ User {target_user_id} force upgraded to lifetime premium."
        )

    except Exception as e:
        logger.error(f"Error force upgrading: {e}")
        await update.message.reply_text("❌ Error force upgrading user.")

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback queries."""
    try:
        query = update.callback_query
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            await query.answer("❌ Access denied.", show_alert=True)
            return

        callback_data = query.data

        if callback_data == "admin_stats":
            all_users = get_all_users()
            premium_users = len([u for u in all_users if u.get('is_premium', False)])
            pending_payments_count = len(get_pending_payments())

            message = (
                f"📊 **Bot Statistics**\n\n"
                f"👥 Total Users: {len(all_users)}\n"
                f"💎 Premium Users: {premium_users}\n"
                f"💰 Pending Payments: {pending_payments_count}\n"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif callback_data == "admin_payments":
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
                [InlineKeyboardButton("✅ Approve", callback_data="admin_approve_payment")],
                [InlineKeyboardButton("❌ Reject", callback_data="admin_reject_payment")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif callback_data == "admin_grant":
            await query.edit_message_text(
                "Use the command `/grant_premium <user_id> <days>` to grant premium.\n"
                "Example: `/grant_premium 123456789 30`"
            )

        elif callback_data == "admin_analytics":
            await query.edit_message_text("Analytics feature is coming soon!")

        elif callback_data == "admin_broadcast":
            await query.edit_message_text(
                "Use the command `/broadcast <message>` to send a broadcast.\n"
                "Example: `/broadcast Hello everyone!`"
            )

        elif callback_data == "admin_panel":
            await admin_panel(update, context) # Re-display admin panel

        else:
            await query.edit_message_text("🔧 **Admin Panel**\n\nSelect an option from the menu.")

        await query.answer() # Acknowledge the callback

    except Exception as e:
        logger.error(f"Error in admin callback: {e}")
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)