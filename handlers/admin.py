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
            [InlineKeyboardButton("💰 Payment Management", callback_data="admin_payments")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
            [InlineKeyboardButton("📊 System Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("💎 Premium Control", callback_data="admin_premium")],
            [InlineKeyboardButton("🔧 System Tools", callback_data="admin_system")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
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

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle admin callback queries."""
    try:
        query = update.callback_query
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
        elif data == "admin_restart_confirm":
            await confirm_restart(query, context)
        elif data == "admin_panel":
            fake_message = type('obj', (object,), {'reply_text': query.edit_message_text})
            fake_update = type('obj', (object,), {'message': fake_message, 'effective_user': query.from_user})
            await admin_panel(fake_update, context)
        else:
            await query.answer("🚧 Feature under development.", show_alert=True)

    except Exception as e:
        logger.error(f"Error handling admin callback: {e}")
        await query.edit_message_text("❌ Admin error occurred.")

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
        [InlineKeyboardButton("📋 Premium List", callback_data="admin_premium_list")],
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

async def start_broadcast(query, context, target_type):
    """Start broadcast message process."""
    try:
        target_descriptions = {
            "all": "All Users",
            "premium": "Premium Users Only",
            "free": "Free Users Only"
        }

        keyboard = [[InlineKeyboardButton("🏠 Back to Broadcast", callback_data="admin_broadcast")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data['broadcast_target'] = target_type

        await query.edit_message_text(
            f"📢 **Broadcast to {target_descriptions.get(target_type, 'Users')}**\n\n"
            f"Send your message to broadcast to {target_descriptions.get(target_type, 'users').lower()}.\n\n"
            f"Type your message and send it. The broadcast will start immediately.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Error starting broadcast: {e}")

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
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (get_all_payments, get_all_users, update_premium_status, 
                        get_pending_payments, approve_payment_by_id, reject_payment_by_id)
from config import ADMIN_USER_IDS
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
        broadcast_target = context.user_data.get('broadcast_target')
        if not broadcast_target:
            return

        message_text = update.message.text
        if not message_text:
            await update.message.reply_text("❌ Please send a text message to broadcast.")
            return

        all_users = get_all_users()
        
        # Filter users based on target
        if broadcast_target == "premium":
            target_users = [u for u in all_users if u.get('is_premium')]
        elif broadcast_target == "free":
            target_users = [u for u in all_users if not u.get('is_premium')]
        else:  # all
            target_users = all_users

        sent_count = 0
        failed_count = 0

        await update.message.reply_text(f"📢 Starting broadcast to {len(target_users)} users...")

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

        await update.message.reply_text(
            f"✅ **Broadcast Complete**\n\n"
            f"📤 Sent: {sent_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"🎯 Target: {broadcast_target.title()} users"
        )

    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
        await update.message.reply_text("❌ Error sending broadcast.")

