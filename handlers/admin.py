import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (get_all_payments, get_all_users, update_premium_status, 
                        get_pending_payments, approve_payment_by_id, reject_payment_by_id)
from config import ADMIN_USER_IDS
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel with management options."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
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

        await update.message.reply_text(
            f"🔧 **Admin Panel**\n\n"
            f"Welcome, Admin! 👨‍💼\n\n"
            f"**Available Functions:**\n"
            f"💰 Payment Management - Review & approve payments\n"
            f"👥 User Management - View & manage users\n"
            f"📊 System Stats - Bot usage statistics\n"
            f"💎 Premium Control - Manage premium users\n"
            f"🔧 System Tools - Maintenance functions\n"
            f"📢 Broadcast - Send messages to all users\n\n"
            f"🕒 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing admin panel: {e}")
        await update.message.reply_text("❌ Error loading admin panel.")

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback queries."""
    try:
        query = update.callback_query
        data = query.data
        user_id = query.from_user.id

        if user_id not in ADMIN_USER_IDS:
            await query.edit_message_text("❌ Access denied.")
            return

        if data == "admin_payments":
            await show_payment_management(query, context)
        elif data == "admin_users":
            await show_user_management(query, context)
        elif data == "admin_stats":
            await show_system_stats(query, context)
        elif data == "admin_premium":
            await show_premium_control(query, context)
        elif data == "admin_system":
            await show_system_tools(query, context)
        elif data == "admin_broadcast":
            await show_broadcast_options(query, context)
        elif data.startswith("approve_"):
            payment_id = int(data.split("_")[1])
            await approve_payment(query, context, payment_id)
        elif data.startswith("reject_"):
            payment_id = int(data.split("_")[1])
            await reject_payment(query, context, payment_id)
        elif data == "admin_user_list":
            await show_user_list(query, context)
        elif data == "admin_premium_list":
            await show_premium_list(query, context)
        elif data == "admin_grant_premium":
            await start_grant_premium(query, context)
        elif data == "admin_revoke_premium":
            await start_revoke_premium(query, context)
        elif data == "admin_clean_temp":
            await clean_temp_files(query, context)
        elif data == "admin_view_logs":
            await view_system_logs(query, context)
        elif data == "admin_restart":
            await restart_bot(query, context)
        elif data == "admin_broadcast_all":
            await start_broadcast(query, context, "all")
        elif data == "admin_broadcast_premium":
            await start_broadcast(query, context, "premium")
        elif data == "admin_broadcast_free":
            await start_broadcast(query, context, "free")
        elif data == "admin_test":
            await show_test_features(query, context)
        elif data == "admin_force_upgrade":
            await show_force_upgrade(query, context)
        elif data == "admin_restart_confirm":
            await confirm_restart(query, context)
        elif data.startswith("confirm_broadcast_"):
            await execute_broadcast(query, context)
        elif data.startswith("force_upgrade_"):
            plan_type = data.split("_")[2]
            await start_force_upgrade(query, context, plan_type)
        elif data == "force_revoke_premium":
            await start_revoke_premium(query, context)
        elif data.startswith("confirm_upgrade_"):
            parts = data.split("_")
            target_user_id = int(parts[2])
            plan_type = parts[3]
            await execute_force_upgrade(query, context, target_user_id, plan_type)
        elif data.startswith("confirm_revoke_"):
            target_user_id = int(data.split("_")[2])
            await execute_revoke_premium(query, context, target_user_id)
        elif data == "admin_panel":
            # Simulate an update object for calling admin_panel
            fake_update = type('obj', (object,), {'message': type('obj', (object,), {'reply_text': query.edit_message_text}), 'effective_user': query.from_user})
            await admin_panel(fake_update, context)
        elif data == "admin_back": # Added for navigation consistency
            await admin_panel(query, context) # Assuming admin_panel needs query for context
        else:
            await query.answer("🚧 Feature under development.", show_alert=True)

    except Exception as e:
        logger.error(f"Error handling admin callback: {e}")
        # Use edit_message_text for callback queries
        if query and query.message:
            await query.edit_message_text("❌ Admin error occurred.")
        else:
            # If query or query.message is None, we might be in a different context
            # Log the error and potentially reply to message if available
            logger.error(f"Could not edit message for admin callback error: {e}")


async def show_payment_management(query, context):
    """Show payment management interface."""
    try:
        pending_payments = get_pending_payments()

        if not pending_payments:
            keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "💰 **Payment Management**\n\n"
                "✅ No pending payments to review.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        message = "💰 **Pending Payments**\n\n"
        keyboard = []

        for payment in pending_payments[:5]:  # Show first 5
            user_name = payment.get('first_name', 'Unknown')
            plan = payment['plan_type'].title()
            amount = payment['amount']

            message += f"👤 {user_name} - {plan} (₦{amount})\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve #{payment['id']}", callback_data=f"approve_{payment['id']}"),
                InlineKeyboardButton(f"❌ Reject #{payment['id']}", callback_data=f"reject_{payment['id']}"),
            ])

        keyboard.append([InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error showing payment management: {e}")

async def show_user_management(query, context):
    """Show user management interface."""
    try:
        all_users = get_all_users()
        total_users = len(all_users)
        premium_users = len([u for u in all_users if u.get('is_premium')])

        keyboard = [
            [InlineKeyboardButton("📋 User List", callback_data="admin_user_list")],
            [InlineKeyboardButton("💎 Premium Users", callback_data="admin_premium_list")],
            [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"👥 **User Management**\n\n"
            f"📊 **Statistics:**\n"
            f"Total Users: {total_users}\n"
            f"Premium Users: {premium_users}\n"
            f"Free Users: {total_users - premium_users}\n\n"
            f"Select an option:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing user management: {e}")

async def show_system_stats(query, context):
    """Show system statistics."""
    try:
        all_users = get_all_users()
        all_payments = get_all_payments()

        total_users = len(all_users)
        premium_users = len([u for u in all_users if u.get('is_premium')])
        total_payments = len(all_payments)
        approved_payments = len([p for p in all_payments if p.get('status') == 'approved'])

        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📊 **System Statistics**\n\n"
            f"👥 **Users:**\n"
            f"• Total: {total_users}\n"
            f"• Premium: {premium_users}\n"
            f"• Free: {total_users - premium_users}\n\n"
            f"💰 **Payments:**\n"
            f"• Total Submissions: {total_payments}\n"
            f"• Approved: {approved_payments}\n"
            f"• Success Rate: {(approved_payments/total_payments*100) if total_payments > 0 else 0:.1f}%\n\n"
            f"🕒 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing system stats: {e}")

async def show_premium_control(query, context):
    """Show premium control options."""
    keyboard = [
        [InlineKeyboardButton("🎁 Grant Premium", callback_data="admin_grant_premium")],
        [InlineKeyboardButton("🚫 Revoke Premium", callback_data="admin_revoke_premium")],
        [InlineKeyboardButton("📋 Premium Users", callback_data="admin_premium_list")],
        [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"💎 **Premium Control**\n\n"
        f"Manage premium subscriptions:\n\n"
        f"• Grant premium access\n"
        f"• Revoke premium access\n"
        f"• View premium users\n\n"
        f"Select an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_system_tools(query, context):
    """Show system maintenance tools."""
    keyboard = [
        [InlineKeyboardButton("🧹 Clean Temp Files", callback_data="admin_clean_temp")],
        [InlineKeyboardButton("📋 View Logs", callback_data="admin_view_logs")],
        [InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart")],
        [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🔧 **System Tools**\n\n"
        f"Maintenance and system functions:\n\n"
        f"• Clean temporary files\n"
        f"• View system logs\n"
        f"• Restart bot service\n\n"
        f"Select an option:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_broadcast_options(query, context):
    """Show broadcast message options."""
    keyboard = [
        [InlineKeyboardButton("📢 Send to All Users", callback_data="admin_broadcast_all")],
        [InlineKeyboardButton("💎 Send to Premium Only", callback_data="admin_broadcast_premium")],
        [InlineKeyboardButton("🆓 Send to Free Users", callback_data="admin_broadcast_free")],
        [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📢 **Broadcast Messages**\n\n"
        f"Send announcements to users:\n\n"
        f"• All registered users\n"
        f"• Premium subscribers only\n"
        f"• Free users only\n\n"
        f"Select target audience:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def approve_payment(query, context, payment_id):
    """Approve a payment."""
    try:
        success = approve_payment_by_id(payment_id)
        if success:
            await query.edit_message_text(f"✅ Payment #{payment_id} approved successfully!")
        else:
            await query.edit_message_text(f"❌ Failed to approve payment #{payment_id}")
    except Exception as e:
        logger.error(f"Error approving payment {payment_id}: {e}")
        await query.edit_message_text("❌ Error processing approval.")

async def reject_payment(query, context, payment_id):
    """Reject a payment."""
    try:
        success = reject_payment_by_id(payment_id)
        if success:
            await query.edit_message_text(f"❌ Payment #{payment_id} rejected.")
        else:
            await query.edit_message_text(f"❌ Failed to reject payment #{payment_id}")
    except Exception as e:
        logger.error(f"Error rejecting payment {payment_id}: {e}")
        await query.edit_message_text("❌ Error processing rejection.")

async def show_user_list(query, context):
    """Show list of all users."""
    try:
        all_users = get_all_users()

        if not all_users:
            keyboard = [[InlineKeyboardButton("🏠 Back to User Management", callback_data="admin_users")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "👥 **User List**\n\n❌ No users found.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        message = "👥 **User List** (Latest 10)\n\n"
        for i, user in enumerate(all_users[:10], 1):
            status = "💎" if user.get('is_premium') else "🆓"
            name = user.get('first_name', 'Unknown')
            message += f"{i}. {status} {name} (ID: {user['user_id']})\n"

        keyboard = [[InlineKeyboardButton("🏠 Back to User Management", callback_data="admin_users")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error showing user list: {e}")

async def show_premium_list(query, context):
    """Show list of premium users."""
    try:
        all_users = get_all_users()
        premium_users = [u for u in all_users if u.get('is_premium')]

        if not premium_users:
            keyboard = [[InlineKeyboardButton("🏠 Back to Premium Control", callback_data="admin_premium")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💎 **Premium Users**\n\n❌ No premium users found.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        message = "💎 **Premium Users**\n\n"
        for i, user in enumerate(premium_users[:10], 1):
            name = user.get('first_name', 'Unknown')
            expiry = user.get('premium_expiry', 'Unknown')
            message += f"{i}. {name} (ID: {user['user_id']})\n   Expires: {expiry}\n\n"

        keyboard = [[InlineKeyboardButton("🏠 Back to Premium Control", callback_data="admin_premium")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error showing premium list: {e}")

async def start_grant_premium(query, context):
    """Start premium granting process."""
    try:
        keyboard = [[InlineKeyboardButton("🏠 Back to Premium Control", callback_data="admin_premium")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🎁 **Grant Premium Access**\n\n"
            "Send the user ID followed by duration:\n"
            "Format: `/grant_premium USER_ID DAYS`\n\n"
            "Example: `/grant_premium 123456789 30`\n"
            "This grants 30 days of premium access.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting grant premium: {e}")

async def start_revoke_premium(query, context):
    """Start premium revoking process."""
    try:
        keyboard = [[InlineKeyboardButton("🏠 Back to Premium Control", callback_data="admin_premium")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🚫 **Revoke Premium Access**\n\n"
            "Send the user ID to revoke premium:\n"
            "Format: `/revoke_premium USER_ID`\n\n"
            "Example: `/revoke_premium 123456789`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting revoke premium: {e}")

async def clean_temp_files(query, context):
    """Clean temporary files."""
    try:
        import os
        import shutil

        temp_dir = "data/temp"
        files_removed = 0

        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        files_removed += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        files_removed += 1
                except Exception as e:
                    logger.error(f"Error removing {file_path}: {e}")

        keyboard = [[InlineKeyboardButton("🏠 Back to System Tools", callback_data="admin_system")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🧹 **Cleanup Complete**\n\n"
            f"✅ Removed {files_removed} temporary files/folders\n"
            f"📁 Cleaned directory: {temp_dir}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
        await query.edit_message_text("❌ Error cleaning temporary files.")

async def view_system_logs(query, context):
    """View recent system logs."""
    try:
        import os

        log_file = "doculuna.log"
        logs_content = "📋 **Recent System Logs**\n\n"

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-10:]  # Last 10 lines
                for line in recent_lines:
                    logs_content += f"`{line.strip()}`\n"
        else:
            logs_content += "❌ Log file not found."

        keyboard = [[InlineKeyboardButton("🏠 Back to System Tools", callback_data="admin_system")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Truncate if too long
        if len(logs_content) > 4000:
            logs_content = logs_content[:4000] + "..."

        await query.edit_message_text(logs_content, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error viewing logs: {e}")
        await query.edit_message_text("❌ Error reading system logs.")

async def restart_bot(query, context):
    """Restart bot confirmation."""
    try:
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Restart", callback_data="admin_restart_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_system")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🔄 **Bot Restart**\n\n"
            "⚠️ This will restart the bot service.\n"
            "All active sessions will be terminated.\n\n"
            "Are you sure you want to proceed?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error showing restart confirmation: {e}")

async def start_broadcast(query, context, target_type: str):
    """Start broadcast message process."""
    try:
        target_descriptions = {
            "all": "All Users",
            "premium": "Premium Users Only",
            "free": "Free Users Only"
        }

        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data['broadcast_target'] = target_type
        context.user_data['broadcast_step'] = 'waiting_message'

        await query.edit_message_text(
            f"📢 **Broadcast to {target_descriptions.get(target_type, 'Users')}**\n\n"
            f"Please send the message content you want to broadcast to {target_descriptions.get(target_type, 'users').lower()}.\n\n"
            f"After you send the message, you'll be asked to confirm before sending.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")

async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Show confirmation for broadcast message."""
    try:
        target_type = context.user_data.get('broadcast_target', 'all')
        target_descriptions = {
            "all": "All Users",
            "premium": "Premium Users Only", 
            "free": "Free Users Only"
        }
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Send", callback_data=f"confirm_broadcast_{target_type}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['broadcast_message'] = message_text
        context.user_data['broadcast_step'] = 'waiting_confirmation'

        await update.message.reply_text(
            f"📢 **Confirm Broadcast**\n\n"
            f"**Target:** {target_descriptions.get(target_type, 'Users')}\n"
            f"**Message:**\n{message_text}\n\n"
            f"✅ Send to all users?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error confirming broadcast: {e}")
        await update.message.reply_text("❌ Error preparing broadcast confirmation.")

async def show_test_features(query, context):
    """Show test features for admin."""
    keyboard = [
        [InlineKeyboardButton("🔍 Test Database", callback_data="admin_test_db")],
        [InlineKeyboardButton("📤 Test Broadcast", callback_data="admin_test_broadcast")],
        [InlineKeyboardButton("💾 Test Backup", callback_data="admin_test_backup")],
        [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🧪 **Test Features**\n\n"
        f"Available test options:\n\n"
        f"• Test database connectivity\n"
        f"• Test broadcast system\n"
        f"• Test backup functionality\n\n"
        f"Select a test to run:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_force_upgrade(query, context):
    """Show force upgrade interface."""
    keyboard = [
        [InlineKeyboardButton("🔓 Grant Daily Plan", callback_data="force_upgrade_daily")],
        [InlineKeyboardButton("📅 Grant 3-Month Plan", callback_data="force_upgrade_3month")],
        [InlineKeyboardButton("💎 Grant Lifetime Plan", callback_data="force_upgrade_lifetime")],
        [InlineKeyboardButton("❌ Revoke Premium", callback_data="force_revoke_premium")],
        [InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"⚙️ **Force Upgrade User**\n\n"
        f"Manually promote any user by ID to premium level:\n\n"
        f"🔓 **Daily Plan** - 24 hours access\n"
        f"📅 **3-Month Plan** - 90 days access\n"
        f"💎 **Lifetime Plan** - Permanent access\n\n"
        f"⚠️ This bypasses payment verification!\n\n"
        f"Select plan type to continue:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def force_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force upgrade a user to premium."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return

        if len(context.args) != 3:
            await update.message.reply_text(
                "❌ Invalid format.\nUsage: `/force_upgrade USER_ID PLAN_TYPE DAYS`\n"
                "Example: `/force_upgrade 123456789 lifetime 0`",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(context.args[0])
        plan_type = context.args[1].lower()
        days = int(context.args[2])

        if plan_type not in ['daily', '3month', 'lifetime']:
            await update.message.reply_text("❌ Invalid plan type. Use: daily, 3month, or lifetime")
            return

        if plan_type == 'lifetime':
            expiry_date = None
        else:
            expiry_date = (datetime.now() + timedelta(days=days)).isoformat()

        success = update_premium_status(target_user_id, True, expiry_date, plan_type)

        if success:
            await update.message.reply_text(
                f"✅ **Force upgrade successful!**\n"
                f"👤 User ID: {target_user_id}\n"
                f"💎 Plan: {plan_type.title()}\n"
                f"⏰ Duration: {'Lifetime' if plan_type == 'lifetime' else f'{days} days'}"
            )
        else:
            await update.message.reply_text("❌ Failed to upgrade user.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days value.")
    except Exception as e:
        logger.error(f"Error force upgrading user: {e}")
        await update.message.reply_text("❌ Error processing force upgrade.")


async def confirm_restart(query, context):
    """Confirm and execute bot restart."""
    try:
        await query.edit_message_text(
            "🔄 **Restarting Bot...**\n\n"
            "✅ Restart command executed\n"
            "⏳ Bot will be back online shortly\n\n"
            "Please wait a moment and try again."
        )

        # Note: In a production environment, you would implement
        # actual restart logic here (e.g., exit with restart code)
        import sys
        logger.info("Admin requested bot restart")
        # sys.exit(0)  # Uncomment for actual restart

    except Exception as e:
        logger.error(f"Error during restart: {e}")

def is_admin(user_id):
    """Check if user is an admin."""
    return user_id in ADMIN_USER_IDS

async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to grant premium access to a user."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return

        if len(context.args) != 2:
            await update.message.reply_text(
                "❌ Invalid format.\nUsage: `/grant_premium USER_ID DAYS`\n"
                "Example: `/grant_premium 123456789 30`",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(context.args[0])
        days = int(context.args[1])

        expiry_date = datetime.now() + timedelta(days=days)
        success = update_premium_status(target_user_id, True, expiry_date.isoformat())

        if success:
            await update.message.reply_text(
                f"✅ Premium access granted!\n"
                f"👤 User ID: {target_user_id}\n"
                f"⏰ Duration: {days} days\n"
                f"📅 Expires: {expiry_date.strftime('%Y-%m-%d')}"
            )
        else:
            await update.message.reply_text("❌ Failed to grant premium access.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days value.")
    except Exception as e:
        logger.error(f"Error granting premium: {e}")
        await update.message.reply_text("❌ Error granting premium access.")

async def revoke_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to revoke premium access from a user."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return

        if len(context.args) != 1:
            await update.message.reply_text(
                "❌ Invalid format.\nUsage: `/revoke_premium USER_ID`\n"
                "Example: `/revoke_premium 123456789`",
                parse_mode='Markdown'
            )
            return

        target_user_id = int(context.args[0])

        success = update_premium_status(target_user_id, False, None)

        if success:
            await update.message.reply_text(
                f"✅ Premium access revoked!\n"
                f"👤 User ID: {target_user_id}"
            )
        else:
            await update.message.reply_text("❌ Failed to revoke premium access.")

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
    except Exception as e:
        logger.error(f"Error revoking premium: {e}")
        await update.message.reply_text("❌ Error revoking premium access.")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast messages from admin."""
    try:
        user_id = update.effective_user.id

        if user_id not in ADMIN_USER_IDS:
            return

        # Check if admin is in broadcast mode
        broadcast_step = context.user_data.get('broadcast_step')
        if broadcast_step != 'waiting_message':
            return

        message_text = update.message.text
        if not message_text:
            await update.message.reply_text("❌ Please send a text message to broadcast.")
            return

        # Show confirmation
        await confirm_broadcast(update, context, message_text)

    except Exception as e:
        logger.error(f"Error handling broadcast message: {e}")
        await update.message.reply_text("❌ Error processing broadcast message.")

async def execute_broadcast(query, context):
    """Execute the confirmed broadcast."""
    try:
        broadcast_target = context.user_data.get('broadcast_target')
        message_text = context.user_data.get('broadcast_message')
        
        if not broadcast_target or not message_text:
            await query.edit_message_text("❌ Broadcast data not found.")
            return

        all_users = get_all_users()

        # Filter users based on target
        if broadcast_target == "premium":
            target_users = [u for u in all_users if u.get('is_premium')]
        elif broadcast_target == "free":
            target_users = [u for u in all_users if not u.get('is_premium')]
        else:  # all
            target_users = all_users

        await query.edit_message_text(f"📢 Starting broadcast to {len(target_users)} users...")

        sent_count = 0
        failed_count = 0

        for user in target_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **Announcement**\n\n{message_text}",
                    parse_mode='Markdown'
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")

        # Clear broadcast mode
        context.user_data.pop('broadcast_target', None)
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_step', None)

        await query.edit_message_text(
            f"✅ **Broadcast Complete**\n\n"
            f"📤 Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"🎯 Target: {broadcast_target.title()} users"
        )

        logger.info(f"Broadcast completed: {sent_count} sent, {failed_count} failed")

    except Exception as e:
        logger.error(f"Error executing broadcast: {e}")
        await query.edit_message_text("❌ Error sending broadcast.")

async def start_force_upgrade(query, context, plan_type):
    """Start force upgrade process."""
    try:
        plan_names = {
            "daily": "Daily Plan (24 hours)",
            "3month": "3-Month Plan (90 days)", 
            "lifetime": "Lifetime Plan (Permanent)"
        }
        
        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['force_upgrade_plan'] = plan_type
        context.user_data['admin_action'] = 'waiting_user_id_upgrade'

        await query.edit_message_text(
            f"⚙️ **Force Upgrade to {plan_names.get(plan_type, 'Premium')}**\n\n"
            f"Please send the User ID of the user you want to upgrade.\n\n"
            f"Example: `123456789`\n\n"
            f"⚠️ Make sure the User ID is correct before confirming!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting force upgrade: {e}")
        await query.edit_message_text("❌ Error starting force upgrade.")

async def start_revoke_premium(query, context):
    """Start revoke premium process."""
    try:
        keyboard = [[InlineKeyboardButton("🏠 Back to Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['admin_action'] = 'waiting_user_id_revoke'

        await query.edit_message_text(
            f"❌ **Revoke Premium Access**\n\n"
            f"Please send the User ID of the user whose premium access you want to revoke.\n\n"
            f"Example: `123456789`\n\n"
            f"⚠️ This will immediately remove their premium status!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting revoke premium: {e}")
        await query.edit_message_text("❌ Error starting revoke premium.")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin message inputs for various admin actions."""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_USER_IDS:
            return
        
        admin_action = context.user_data.get('admin_action')
        message_text = update.message.text
        
        if admin_action == 'waiting_user_id_upgrade':
            await handle_force_upgrade_user_id(update, context, message_text)
        elif admin_action == 'waiting_user_id_revoke':
            await handle_revoke_premium_user_id(update, context, message_text)
        elif context.user_data.get('broadcast_step') == 'waiting_message':
            await broadcast_message(update, context)
            
    except Exception as e:
        logger.error(f"Error handling admin message: {e}")

async def handle_force_upgrade_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_text: str):
    """Handle user ID input for force upgrade."""
    try:
        try:
            target_user_id = int(user_id_text.strip())
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID. Please send a valid numeric User ID.")
            return
        
        plan_type = context.user_data.get('force_upgrade_plan')
        if not plan_type:
            await update.message.reply_text("❌ Plan type not found. Please restart the process.")
            return
        
        # Check if user exists
        from database.db import get_user
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"❌ User with ID {target_user_id} not found.")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Upgrade", callback_data=f"confirm_upgrade_{target_user_id}_{plan_type}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        plan_names = {
            "daily": "Daily Plan (24 hours)",
            "3month": "3-Month Plan (90 days)",
            "lifetime": "Lifetime Plan (Permanent)"
        }
        
        user_name = user.get('first_name', 'Unknown')
        
        await update.message.reply_text(
            f"⚙️ **Confirm Force Upgrade**\n\n"
            f"**User:** {user_name} (ID: {target_user_id})\n"
            f"**Plan:** {plan_names.get(plan_type, 'Premium')}\n\n"
            f"⚠️ Confirm upgrade? This bypasses payment verification.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data.pop('admin_action', None)
        
    except Exception as e:
        logger.error(f"Error handling force upgrade user ID: {e}")
        await update.message.reply_text("❌ Error processing upgrade request.")

async def handle_revoke_premium_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_text: str):
    """Handle user ID input for revoking premium."""
    try:
        try:
            target_user_id = int(user_id_text.strip())
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID. Please send a valid numeric User ID.")
            return
        
        # Check if user exists and has premium
        from database.db import get_user
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"❌ User with ID {target_user_id} not found.")
            return
        
        if not user.get('is_premium'):
            await update.message.reply_text(f"❌ User {user.get('first_name', 'Unknown')} is not a premium user.")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Revoke", callback_data=f"confirm_revoke_{target_user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_name = user.get('first_name', 'Unknown')
        plan_type = user.get('premium_type', 'Premium')
        
        await update.message.reply_text(
            f"❌ **Confirm Revoke Premium**\n\n"
            f"**User:** {user_name} (ID: {target_user_id})\n"
            f"**Current Plan:** {plan_type.title()}\n\n"
            f"⚠️ Confirm revoke? This will immediately remove premium access.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data.pop('admin_action', None)
        
    except Exception as e:
        logger.error(f"Error handling revoke premium user ID: {e}")
        await update.message.reply_text("❌ Error processing revoke request.")

async def execute_force_upgrade(query, context, target_user_id: int, plan_type: str):
    """Execute the force upgrade."""
    try:
        from database.db import update_user_premium, get_user
        from datetime import datetime, timedelta
        
        user = get_user(target_user_id)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return
        
        # Calculate expiry based on plan type
        if plan_type == "lifetime":
            expires_at = None
        elif plan_type == "daily":
            expires_at = (datetime.now() + timedelta(days=1)).isoformat()
        elif plan_type == "3month":
            expires_at = (datetime.now() + timedelta(days=90)).isoformat()
        else:
            expires_at = None
        
        # Update user premium status
        update_user_premium(target_user_id, True, expires_at, plan_type)
        
        plan_names = {
            "daily": "Daily Plan (24 hours)",
            "3month": "3-Month Plan (90 days)",
            "lifetime": "Lifetime Plan (Permanent)"
        }
        
        user_name = user.get('first_name', 'Unknown')
        
        await query.edit_message_text(
            f"✅ **Force Upgrade Successful**\n\n"
            f"**User:** {user_name} (ID: {target_user_id})\n"
            f"**Plan:** {plan_names.get(plan_type, 'Premium')}\n"
            f"**Expires:** {expires_at if expires_at else 'Never'}\n\n"
            f"User has been upgraded successfully!",
            parse_mode='Markdown'
        )
        
        # Try to notify the user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Congratulations!**\n\n"
                f"You have been upgraded to **{plan_names.get(plan_type, 'Premium')}**!\n\n"
                f"Enjoy unlimited access to all DocuLuna features! 🚀",
                parse_mode='Markdown'
            )
            logger.info(f"Notified user {target_user_id} of force upgrade")
        except Exception as e:
            logger.warning(f"Could not notify user {target_user_id} of upgrade: {e}")
        
        logger.info(f"Force upgrade completed for user {target_user_id} to {plan_type}")
        
    except Exception as e:
        logger.error(f"Error executing force upgrade: {e}")
        await query.edit_message_text("❌ Error completing upgrade.")

async def execute_revoke_premium(query, context, target_user_id: int):
    """Execute the premium revoke."""
    try:
        from database.db import update_user_premium, get_user
        
        user = get_user(target_user_id)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return
        
        # Revoke premium status
        update_user_premium(target_user_id, False, None, None)
        
        user_name = user.get('first_name', 'Unknown')
        
        await query.edit_message_text(
            f"✅ **Premium Revoked Successfully**\n\n"
            f"**User:** {user_name} (ID: {target_user_id})\n\n"
            f"Premium access has been removed.",
            parse_mode='Markdown'
        )
        
        # Try to notify the user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"📢 **Premium Access Update**\n\n"
                f"Your premium access has been updated.\n\n"
                f"You can upgrade again anytime using /upgrade.",
                parse_mode='Markdown'
            )
            logger.info(f"Notified user {target_user_id} of premium revoke")
        except Exception as e:
            logger.warning(f"Could not notify user {target_user_id} of revoke: {e}")
        
        logger.info(f"Premium revoked for user {target_user_id}")
        
    except Exception as e:
        logger.error(f"Error revoking premium: {e}")
        await query.edit_message_text("❌ Error revoking premium.")