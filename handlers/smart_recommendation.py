# smart_recommendation.py
"""Smart recommendation module for DocuLuna.

Analyzes user history to provide personalized recommendations and rewards
users for following them.
"""

import random
from typing import List, Dict
from messages import RECOMMENDATION_MESSAGES
from history import get_recent_history
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class SmartRecommendation:
    """Class for generating smart recommendations based on user history."""

    def __init__(self, gamification: "GamificationEngine"):  # Forward ref
        self.gamification = gamification

    async def analyze_and_suggest(self, user_id: int) -> str:
        """Analyze user history and suggest a recommendation."""
        try:
            history: List[Dict[str, Any]] = await get_recent_history(user_id, limit=20)
            if len(history) < 3:
                return random.choice(RECOMMENDATION_MESSAGES[:5])

            ops = [h['operation_type'] for h in history]
            types = [h['file_type'] for h in history]
            durations = [h['duration'] for h in history]

            # Improved logic with filters
            if sum(d > 30 for d in durations) > 3:
                msgs = [msg for msg in RECOMMENDATION_MESSAGES if 'compress' in msg.lower()]
                if msgs:
                    return random.choice(msgs)
            if 'ocr' not in ops and any(t in ['jpg', 'png', 'tiff'] for t in types):
                msgs = [msg for msg in RECOMMENDATION_MESSAGES if 'ocr' in msg.lower()]
                if msgs:
                    return random.choice(msgs)
            if len(history) > 15 and 'clean_history' not in ops:
                msgs = [msg for msg in RECOMMENDATION_MESSAGES if 'clean' in msg.lower()]
                if msgs:
                    return random.choice(msgs)
            if ops.count('convert') > 5:
                msgs = [msg for msg in RECOMMENDATION_MESSAGES if 'merge' in msg.lower() or 'bulk' in msg.lower()]
                if msgs:
                    return random.choice(msgs)

            return random.choice(RECOMMENDATION_MESSAGES)
        except Exception as e:
            logger.error(f"Error analyzing recommendation for user {user_id}: {e}")
            return random.choice(RECOMMENDATION_MESSAGES)

    async def reward_followed_recommendation(self, user_id: int) -> None:
        """Reward user for following a recommendation."""
        try:
            await self.gamification.add_xp(user_id, 75)
            await self.gamification._unlock_achievement(user_id, "Smart Worker")
            logger.info(f"Rewarded Smart Worker for user {user_id}")
        except Exception as e:
            logger.error(f"Error rewarding recommendation for user {user_id}: {e}")
