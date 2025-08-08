
import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from telegram import Bot
from telegram.error import TelegramError
from config import Config
from database.db import get_all_users, get_user

logger = logging.getLogger(__name__)

class NotificationSystem:
    """Advanced notification system with templates and scheduling"""
    
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
        self.templates = self._load_templates()
        self.notification_queue = []
        self.scheduled_notifications = {}
        
    def _load_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load notification templates"""
        return {
            "welcome_new_user": {
                "title": "🎉 Welcome to DocuLuna!",
                "message": """
Welcome, {user_name}! 🚀

You've just joined thousands of users who trust DocuLuna for their document processing needs.

🎁 **Your Free Account Includes:**
• {free_limit} daily tool uses
• All essential document tools
• Fast processing speeds
• Community support

💡 **Quick Tip:** Upload any document to get started instantly!

Ready to process your first file? 👇
""",
                "buttons": [
                    {"text": "🛠️ Start Processing", "callback": "tools_menu"},
                    {"text": "📚 Learn More", "callback": "quick_start_guide"}
                ]
            },
            
            "usage_limit_warning": {
                "title": "⚠️ Usage Limit Approaching",
                "message": """
Hi {user_name},

You've used {used_count} out of {total_limit} daily free uses.

🔥 **Remaining:** {remaining} uses today
⏰ **Resets:** In {reset_time} hours

💎 **Want unlimited access?** Upgrade to DocuLuna Pro!

✨ **Pro Benefits:**
• Unlimited tool usage
• Priority processing
• Advanced features
• Premium support
""",
                "buttons": [
                    {"text": "💎 Upgrade Now", "callback": "upgrade_menu"},
                    {"text": "👥 Invite Friends", "callback": "referral_menu"}
                ]
            },
            
            "premium_expired": {
                "title": "💎 Premium Subscription Expired",
                "message": """
Hi {user_name},

Your DocuLuna Pro subscription has expired.

😢 **What you'll miss:**
• Unlimited tool usage
• Priority processing queue
• Advanced features
• Premium support

🔄 **Good news:** You can renew anytime to restore all benefits!

Your account reverts to our generous free plan with {free_limit} daily uses.
""",
                "buttons": [
                    {"text": "💎 Renew Premium", "callback": "upgrade_menu"},
                    {"text": "📊 View Plans", "callback": "pricing_plans"}
                ]
            },
            
            "maintenance_notice": {
                "title": "🔧 Scheduled Maintenance",
                "message": """
📢 **System Maintenance Notice**

We'll be performing scheduled maintenance on:
📅 **Date:** {maintenance_date}
⏰ **Time:** {maintenance_time}
⏱️ **Duration:** Approximately {duration} minutes

During this time, DocuLuna will be temporarily unavailable.

🚀 **What's Coming:**
• Improved processing speeds
• Enhanced security
• New features
• Bug fixes

Thank you for your patience! 🙏
""",
                "buttons": [
                    {"text": "📅 Add to Calendar", "callback": "add_calendar"},
                    {"text": "🔔 Remind Me", "callback": "set_reminder"}
                ]
            },
            
            "new_feature_announcement": {
                "title": "🚀 New Feature Available!",
                "message": """
🎉 **Exciting Update!**

We've just released: **{feature_name}**

✨ **What's New:**
{feature_description}

🎯 **Benefits:**
{feature_benefits}

💡 **How to Use:**
{usage_instructions}

Try it now and let us know what you think!
""",
                "buttons": [
                    {"text": "🚀 Try Now", "callback": "tools_menu"},
                    {"text": "📖 Learn More", "callback": "feature_guide"}
                ]
            },
            
            "admin_alert": {
                "title": "🚨 Admin Alert",
                "message": """
⚠️ **System Alert**

**Type:** {alert_type}
**Severity:** {severity}
**Time:** {timestamp}

**Details:**
{alert_details}

**Metrics:**
{system_metrics}

**Action Required:** {action_required}
""",
                "buttons": [
                    {"text": "🔧 Admin Panel", "callback": "admin_panel"},
                    {"text": "📊 System Status", "callback": "system_status"}
                ]
            },
            
            "payment_reminder": {
                "title": "💰 Payment Verification Needed",
                "message": """
Hi {user_name},

We received your payment screenshot for {plan_type}.

⏳ **Status:** Under Review
💰 **Amount:** ₦{amount:,}
📅 **Submitted:** {submission_date}

Our team typically processes payments within 24 hours.

📸 **Having issues?** Make sure your screenshot clearly shows:
• Transaction amount
• Date and time
• Our account details
• Reference number
""",
                "buttons": [
                    {"text": "📞 Contact Support", "callback": "contact_support"},
                    {"text": "📋 Resubmit", "callback": "resubmit_payment"}
                ]
            }
        }
    
    async def send_notification(self, user_id: int, template_name: str, variables: Dict[str, Any] = None, immediate: bool = True) -> bool:
        """Send notification using template"""
        try:
            if template_name not in self.templates:
                logger.error(f"Template {template_name} not found")
                return False
            
            template = self.templates[template_name]
            variables = variables or {}
            
            # Format message
            message = template["message"].format(**variables)
            
            # Create inline keyboard if buttons exist
            reply_markup = None
            if "buttons" in template:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = []
                for button in template["buttons"]:
                    keyboard.append([InlineKeyboardButton(
                        button["text"], 
                        callback_data=button["callback"]
                    )])
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            if immediate:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                # Add to queue for batch processing
                self.notification_queue.append({
                    'user_id': user_id,
                    'message': message,
                    'reply_markup': reply_markup,
                    'timestamp': datetime.now()
                })
            
            logger.info(f"Notification {template_name} sent to user {user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending notification to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
            return False
    
    async def broadcast_notification(self, template_name: str, variables: Dict[str, Any] = None, user_filter: str = "all") -> Dict[str, int]:
        """Broadcast notification to multiple users"""
        try:
            users = get_all_users()
            
            # Filter users based on criteria
            if user_filter == "premium":
                users = [u for u in users if u.get('is_premium')]
            elif user_filter == "free":
                users = [u for u in users if not u.get('is_premium')]
            elif user_filter == "active":
                # Users active in last 7 days
                week_ago = datetime.now() - timedelta(days=7)
                users = [u for u in users if u.get('last_usage', '') > week_ago.isoformat()]
            
            results = {
                'total': len(users),
                'sent': 0,
                'failed': 0
            }
            
            # Send notifications in batches to avoid rate limits
            batch_size = 30  # Telegram rate limit considerations
            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]
                
                for user in batch:
                    success = await self.send_notification(
                        user['user_id'], 
                        template_name, 
                        variables, 
                        immediate=False
                    )
                    
                    if success:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                
                # Process queue
                await self._process_notification_queue()
                
                # Wait between batches
                if i + batch_size < len(users):
                    await asyncio.sleep(1)
            
            logger.info(f"Broadcast complete: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error broadcasting notification: {e}")
            return {'error': str(e)}
    
    async def _process_notification_queue(self):
        """Process queued notifications"""
        try:
            while self.notification_queue:
                notification = self.notification_queue.pop(0)
                
                await self.bot.send_message(
                    chat_id=notification['user_id'],
                    text=notification['message'],
                    reply_markup=notification['reply_markup'],
                    parse_mode='Markdown'
                )
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")
    
    async def schedule_notification(self, user_id: int, template_name: str, variables: Dict[str, Any], send_time: datetime) -> str:
        """Schedule notification for future delivery"""
        try:
            notification_id = f"{user_id}_{int(send_time.timestamp())}"
            
            self.scheduled_notifications[notification_id] = {
                'user_id': user_id,
                'template_name': template_name,
                'variables': variables,
                'send_time': send_time,
                'status': 'scheduled'
            }
            
            logger.info(f"Notification scheduled: {notification_id} for {send_time}")
            return notification_id
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return None
    
    async def send_admin_alert(self, alert_type: str, details: Dict[str, Any]):
        """Send alert to all admin users"""
        try:
            admin_ids = Config.ADMIN_USER_IDS
            
            variables = {
                'alert_type': alert_type,
                'severity': details.get('severity', 'Medium'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'alert_details': details.get('details', 'No details provided'),
                'system_metrics': details.get('metrics', 'N/A'),
                'action_required': details.get('action', 'Review and take appropriate action')
            }
            
            for admin_id in admin_ids:
                await self.send_notification(admin_id, "admin_alert", variables)
            
            logger.info(f"Admin alert sent: {alert_type}")
            
        except Exception as e:
            logger.error(f"Error sending admin alert: {e}")
    
    async def check_and_send_scheduled(self):
        """Check and send scheduled notifications"""
        try:
            current_time = datetime.now()
            
            for notification_id, notification in list(self.scheduled_notifications.items()):
                if notification['send_time'] <= current_time and notification['status'] == 'scheduled':
                    success = await self.send_notification(
                        notification['user_id'],
                        notification['template_name'],
                        notification['variables']
                    )
                    
                    if success:
                        notification['status'] = 'sent'
                        logger.info(f"Scheduled notification sent: {notification_id}")
                    else:
                        notification['status'] = 'failed'
                        logger.error(f"Failed to send scheduled notification: {notification_id}")
            
            # Clean up old notifications
            self._cleanup_old_notifications()
            
        except Exception as e:
            logger.error(f"Error checking scheduled notifications: {e}")
    
    def _cleanup_old_notifications(self):
        """Remove old completed notifications"""
        try:
            week_ago = datetime.now() - timedelta(days=7)
            
            to_remove = []
            for notification_id, notification in self.scheduled_notifications.items():
                if notification['send_time'] < week_ago and notification['status'] in ['sent', 'failed']:
                    to_remove.append(notification_id)
            
            for notification_id in to_remove:
                del self.scheduled_notifications[notification_id]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old notifications")
                
        except Exception as e:
            logger.error(f"Error cleaning up notifications: {e}")

# Global notification system instance
notification_system = NotificationSystem(Config.BOT_TOKEN)

# Utility functions for easy access
async def send_welcome_notification(user_id: int, user_name: str):
    """Send welcome notification to new user"""
    variables = {
        'user_name': user_name,
        'free_limit': Config.FREE_USAGE_LIMIT
    }
    return await notification_system.send_notification(user_id, "welcome_new_user", variables)

async def send_usage_warning(user_id: int, user_name: str, used_count: int):
    """Send usage limit warning"""
    variables = {
        'user_name': user_name,
        'used_count': used_count,
        'total_limit': Config.FREE_USAGE_LIMIT,
        'remaining': Config.FREE_USAGE_LIMIT - used_count,
        'reset_time': 24  # Hours until reset
    }
    return await notification_system.send_notification(user_id, "usage_limit_warning", variables)

async def send_admin_system_alert(alert_type: str, details: Dict[str, Any]):
    """Send system alert to admins"""
    return await notification_system.send_admin_alert(alert_type, details)

async def broadcast_maintenance_notice(maintenance_date: str, maintenance_time: str, duration: int):
    """Broadcast maintenance notice to all users"""
    variables = {
        'maintenance_date': maintenance_date,
        'maintenance_time': maintenance_time,
        'duration': duration
    }
    return await notification_system.broadcast_notification("maintenance_notice", variables)

# Background task to check scheduled notifications
async def notification_scheduler():
    """Background task to process scheduled notifications"""
    while True:
        try:
            await notification_system.check_and_send_scheduled()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in notification scheduler: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error
