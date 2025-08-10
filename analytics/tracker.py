import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Simple analytics tracker for bot usage."""

    def __init__(self):
        self.events = []

    def track_event(self, event_type, user_id, data=None):
        """Track an event."""
        try:
            event = {
                "timestamp": datetime.now(),
                "event_type": event_type,
                "user_id": user_id,
                "data": data or {},
            }
            self.events.append(event)
            logger.info(f"Event tracked: {event_type} for user {user_id}")
        except Exception as e:
            logger.error(f"Error tracking event: {e}")

    def get_stats(self):
        """Get basic statistics."""
        return {
            "total_events": len(self.events),
            "last_24h": len(
                [e for e in self.events if (datetime.now() - e["timestamp"]).days < 1]
            ),
        }
