import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from database.db import get_all_users, update_premium_status, get_pending_payments
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

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback queries."""
    try:
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        if user_id not in ADMIN_IDS:
            await query.edit_message_text("❌ Access denied.")
            return

        if data == "admin_stats":
            await show_bot_stats(query, context)
        elif data == "admin_users":
            await show_users_list(query, context)
        elif data == "admin_payments":
            await show_payments_list(query, context)
        elif data == "admin_broadcast":
            await start_broadcast(query, context)
        elif data == "admin_test":
            await show_test_features(query, context)
        elif data == "admin_force_upgrade":
            await force_upgrade_user(query, context)
        elif data == "admin_approve_payment":
            # This callback should ideally lead to a prompt for payment ID or list pending payments
            # For now, let's redirect to the payment management view which shows pending payments
            await show_payments_list(query, context)
        elif data == "admin_reject_payment":
            # Similar to approve, this should lead to a prompt or list
            await show_payments_list(query, context)
        elif data == "admin_panel":
            # Re-render the admin panel
            await admin_panel(Update(query.message, context.bot), context) # Construct a fake update to call admin_panel
        else:
            await query.answer("🚧 Feature under development.", show_alert=True)

    except Exception as e:
        logger.error(f"Error handling admin callback: {e}")
        if query and query.message:
            await query.edit_message_text("❌ Admin error occurred.")
        else:
            logger.error(f"Could not edit message for admin callback error: {e}")


async def show_bot_stats(query, context):
    """Show bot statistics."""
    try:
        users = get_all_users()
        total_users = len(users)
        premium_users = len([u for u in users if u.get('is_premium')])

        message = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"💎 Premium Users: {premium_users}\n"
            f"🆓 Free Users: {total_users - premium_users}\n\n"
            f"📈 Premium Rate: {(premium_users/total_users*100):.1f}% if total_users > 0 else 0.0%"
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

async def show_users_list(query, context):
    """Show users list."""
    try:
        users = get_all_users()

        if not users:
            message = "👥 **Users List**\n\nNo users found."
        else:
            message = f"👥 **Users List** ({len(users)} users)\n\n"
            for i, user in enumerate(users[:10]):  # Show first 10 users
                status = "💎" if user.get('is_premium') else "🆓"
                name = user.get('first_name', 'Unknown')
                username = f"@{user.get('username', 'N/A')}" if user.get('username') else "N/A"
                message += f"{status} {name} ({username}) - ID: {user['user_id']}\n"

            if len(users) > 10:
                message += f"\n... and {len(users) - 10} more users"

        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing users list: {e}")

async def show_payments_list(query, context):
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
        logger.error(f"Error showing payments list: {e}")

async def start_broadcast(query, context):
    """Start broadcast message process."""
    try:
        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📤 **Broadcast Message**\n\n"
            "Send your message and it will be broadcast to all users.\n"
            "Format: `/broadcast Your message here`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")

async def show_test_features(query, context):
    """Show test features for admin."""
    try:
        keyboard = [
            [InlineKeyboardButton("🔍 Test Database", callback_data="admin_test_db")],
            [InlineKeyboardButton("📤 Test Broadcast", callback_data="admin_test_broadcast")],
            [InlineKeyboardButton("💾 Test Backup", callback_data="admin_test_backup")],
            [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🧪 **Test Features**\n\n"
            "Available test options:\n\n"
            "• Test database connectivity\n"
            "• Test broadcast system\n"
            "• Test backup functionality",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing test features: {e}")

async def force_upgrade_user(query, context):
    """Force upgrade a user."""
    try:
        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "⚙️ **Force Upgrade User**\n\n"
            "Force upgrade a user to premium.\n"
            "Format: `/force_upgrade USER_ID DAYS`\n\n"
            "Example: `/force_upgrade 123456789 30`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error in force upgrade: {e}")

async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium to a user via command."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if len(context.args) != 2:
            await update.message.reply_text(
                "Usage: `/grant_premium USER_ID DAYS`\n"
                "Example: `/grant_premium 123456789 30`"
            )
            return

        target_user_id = int(context.args[0])
        days = int(context.args[1])

        expires_at = (datetime.now() + timedelta(days=days)).isoformat()

        if update_premium_status(target_user_id, True, expires_at):
            await update.message.reply_text(
                f"✅ Premium granted to user {target_user_id} for {days} days."
            )
        else:
            await update.message.reply_text("❌ Failed to grant premium.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days value.")
    except Exception as e:
        logger.error(f"Error granting premium: {e}")
        await update.message.reply_text("❌ Error granting premium.")

async def revoke_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoke premium from a user via command."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if len(context.args) != 1:
            await update.message.reply_text(
                "Usage: `/revoke_premium USER_ID`\n"
                "Example: `/revoke_premium 123456789`"
            )
            return

        target_user_id = int(context.args[0])

        if update_premium_status(target_user_id, False, None):
            await update.message.reply_text(
                f"✅ Premium revoked from user {target_user_id}."
            )
        else:
            await update.message.reply_text("❌ Failed to revoke premium.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
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
            await update.message.reply_text("Usage: `/broadcast Your message here`")
            return

        message = " ".join(context.args)
        users = get_all_users()

        sent_count = 0
        failed_count = 0

        for user in users:
            try:
                await context.bot.send_message(user['user_id'], message)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")

        await update.message.reply_text(
            f"📤 Broadcast completed!\n"
            f"✅ Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}"
        )

    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        await update.message.reply_text("❌ Error broadcasting message.")

async def force_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force upgrade a user via command."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return

        if len(context.args) != 2:
            await update.message.reply_text(
                "Usage: `/force_upgrade USER_ID DAYS`\n"
                "Example: `/force_upgrade 123456789 30`"
            )
            return

        target_user_id = int(context.args[0])
        days = int(context.args[1])

        expires_at = (datetime.now() + timedelta(days=days)).isoformat()

        if update_premium_status(target_user_id, True, expires_at):
            await update.message.reply_text(
                f"✅ Force upgrade completed for user {target_user_id} for {days} days."
            )
        else:
            await update.message.reply_text("❌ Failed to force upgrade.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days value.")
    except Exception as e:
        logger.error(f"Error force upgrading: {e}")
        await update.message.reply_text("❌ Error force upgrading.")