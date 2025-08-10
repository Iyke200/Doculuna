import logging

logger = logging.getLogger(__name__)


class NotificationSystem:
    """Simple notification system."""

    def __init__(self):
        self.notifications = []

    async def send_notification(self, user_id, message, bot=None):
        """Send notification to user."""
        try:
            if bot:
                await bot.send_message(user_id, message)
            logger.info(f"Notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def schedule_notification(self, user_id, message, delay=0):
        """Schedule a notification (simplified)."""
        self.notifications.append(
            {"user_id": user_id, "message": message, "delay": delay}
        )


import logging

logger = logging.getLogger(__name__)


class NotificationSystem:
    """Simple notification system for bot events."""

    def __init__(self):
        self.notifications = []

    def send_notification(self, message, user_id=None):
        """Send a notification."""
        try:
            notification = {"message": message, "user_id": user_id, "timestamp": "now"}
            self.notifications.append(notification)
            logger.info(f"Notification sent: {message}")
        except Exception as e:
            logger.error(f"Notification failed: {e}")
