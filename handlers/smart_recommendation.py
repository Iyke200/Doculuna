# smart_recommendation.py
"""Smart recommendation module for DocuLuna.

Analyzes user history to provide personalized recommendations and rewards
users for following them.
"""

import random
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import logging
from datetime import datetime

if TYPE_CHECKING:
    from handlers.gamification import GamificationEngine

logger = logging.getLogger(__name__)

# Recommendation messages with categories
RECOMMENDATION_MESSAGES: Dict[str, List[str]] = {
    "compress": [
        "🌙 Tip: Your files seem large. Try compressing them to save space!",
        "⚡ Pro tip: Compress PDFs before sharing — faster uploads!",
        "✨ Suggestion: Use compression for files over 5MB.",
    ],
    "ocr": [
        "🌓 Recommend: Use OCR on scanned documents for searchable text.",
        "📷 Smart move: Convert those scanned images to editable text!",
        "✨ Tip: OCR can extract text from your image files.",
    ],
    "clean": [
        "🌔 Pro tip: Clean old history weekly to keep things tidy.",
        "🧹 Housekeeping: Your history is getting long. Consider cleaning it!",
        "✨ Suggestion: Remove old files to stay organized.",
    ],
    "merge": [
        "🪐 Idea: Merge related PDFs into one master document!",
        "📚 Scholar hint: Combine similar documents for easier management.",
        "✨ Tip: Multiple small PDFs? Try merging them!",
    ],
    "split": [
        "✂️ Suggestion: Split large PDFs into chapters for mobile reading.",
        "📄 Smart move: Extract specific pages using the split feature.",
        "✨ Tip: Split that big document for easier sharing!",
    ],
    "general": [
        "🌙 Following tips earns XP and the Smart Worker badge!",
        "⭐ Sanitize filenames — remove special characters for safety.",
        "🧠 Quick win: Use bulk operations for multiple files.",
        "🌕 Smart move: Add timestamps to filenames for version control.",
        "🚀 Boost your productivity with keyboard shortcuts!",
        "✨ Regular users get bonus XP for consistency!",
    ]
}


class SmartRecommendation:
    """Class for generating smart recommendations based on user history."""

    def __init__(self, gamification: Optional["GamificationEngine"] = None):
        self.gamification = gamification
        self._last_recommendations: Dict[int, str] = {}

    def set_gamification(self, gamification: "GamificationEngine") -> None:
        """Set the gamification engine (for late binding)."""
        self.gamification = gamification

    async def analyze_and_suggest(
        self, 
        user_id: int, 
        history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze user history and generate a personalized recommendation."""
        try:
            # Get history if not provided
            if history is None:
                from handlers.history import get_recent_history
                history = await get_recent_history(user_id, limit=20)
            
            # For new users or empty history
            if len(history) < 3:
                recommendation = random.choice(RECOMMENDATION_MESSAGES["general"])
                return {
                    "message": recommendation,
                    "category": "general",
                    "confidence": 0.5,
                    "reason": "Welcome tip for new users"
                }
            
            # Analyze patterns
            ops = [h.get('operation_type', '') for h in history]
            types = [h.get('file_type', '') for h in history]
            durations = [h.get('duration', 0) for h in history]
            
            recommendation = None
            category = "general"
            confidence = 0.7
            reason = ""
            
            # Check for slow processing (might need compression)
            slow_count = sum(1 for d in durations if d and d > 30)
            if slow_count > 3:
                recommendation = random.choice(RECOMMENDATION_MESSAGES["compress"])
                category = "compress"
                confidence = 0.9
                reason = f"{slow_count} slow operations detected"
            
            # Check for image files without OCR usage
            elif any(t in ['jpg', 'jpeg', 'png', 'tiff', 'bmp'] for t in types) and 'ocr' not in ops:
                recommendation = random.choice(RECOMMENDATION_MESSAGES["ocr"])
                category = "ocr"
                confidence = 0.85
                reason = "Image files detected, OCR not used"
            
            # Check for long history
            elif len(history) > 15 and 'clean_history' not in ops:
                recommendation = random.choice(RECOMMENDATION_MESSAGES["clean"])
                category = "clean"
                confidence = 0.8
                reason = f"History has {len(history)}+ entries"
            
            # Check for many convert operations (suggest merge)
            elif ops.count('convert') > 5:
                recommendation = random.choice(RECOMMENDATION_MESSAGES["merge"])
                category = "merge"
                confidence = 0.75
                reason = "Multiple conversions detected"
            
            # Check for large file processing (suggest split)
            elif any(h.get('file_size', 0) > 10_000_000 for h in history):
                recommendation = random.choice(RECOMMENDATION_MESSAGES["split"])
                category = "split"
                confidence = 0.7
                reason = "Large files detected"
            
            # Default to general recommendation
            if not recommendation:
                # Avoid repeating the last recommendation
                last = self._last_recommendations.get(user_id)
                options = [m for m in RECOMMENDATION_MESSAGES["general"] if m != last]
                recommendation = random.choice(options) if options else random.choice(RECOMMENDATION_MESSAGES["general"])
                reason = "General productivity tip"
            
            # Store last recommendation to avoid repetition
            self._last_recommendations[user_id] = recommendation
            
            return {
                "message": recommendation,
                "category": category,
                "confidence": confidence,
                "reason": reason
            }
            
        except Exception as e:
            logger.error(f"Error analyzing recommendation for user {user_id}: {e}")
            return {
                "message": random.choice(RECOMMENDATION_MESSAGES["general"]),
                "category": "general",
                "confidence": 0.5,
                "reason": "Fallback recommendation"
            }

    async def reward_followed_recommendation(self, user_id: int, category: str = None) -> Dict[str, Any]:
        """Reward user for following a recommendation."""
        result = {"xp_gained": 0, "achievement_unlocked": None}
        
        try:
            if self.gamification:
                # Add bonus XP for following recommendations
                xp_result = await self.gamification.add_xp(user_id, 75)
                result["xp_gained"] = 75
                result["leveled_up"] = xp_result.get("leveled_up", False)
                
                # Try to unlock Smart Worker achievement
                unlocked = await self.gamification._unlock_achievement(user_id, "Smart Worker")
                if unlocked:
                    result["achievement_unlocked"] = "Smart Worker"
                    logger.info(f"Smart Worker achievement unlocked for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error rewarding recommendation for user {user_id}: {e}")
        
        return result

    async def get_category_tips(self, category: str) -> List[str]:
        """Get all tips for a specific category."""
        return RECOMMENDATION_MESSAGES.get(category, RECOMMENDATION_MESSAGES["general"])


# Global instance
smart_recommendation = SmartRecommendation()
