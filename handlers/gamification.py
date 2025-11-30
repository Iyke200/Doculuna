# gamification.py
"""Gamification engine for DocuLuna bot.

This module handles user progression, including XP, levels, ranks, streaks,
achievements, and moons (virtual currency). It uses aiosqlite for asynchronous
database operations and includes robust error handling and logging.
"""

import aiosqlite
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import random
import logging

from config import DB_PATH

logger = logging.getLogger(__name__)

# Message templates
LEVEL_UP_MESSAGES: List[str] = [
    "⚡ Boom! Level {level} → {rank} | +{moons} moons",
    "🌕 Your lunar glow intensifies! Welcome to Level {level}",
    "✨ Level {level} unlocked! You are now a {rank} | +{moons} moons reward!",
    "🌑 From new moon to {rank}! Level {level} achieved | {moons} moons gifted.",
    "🌓 Waxing strong! Level {level} → {rank} | {moons} moons added.",
    "🪐 Celestial leap! Level {level} as {rank} | {moons} moons orbit you.",
    "🌙 Overlord in sight? Level {level} unlocked! {rank} | +{moons} moons.",
    "🔥 Level up alert! {level} reached – {rank} status | Bonus: {moons} moons.",
    "⭐ Shining brighter! Level {level} as {rank} | Collect {moons} moons."
]

ACHIEVEMENT_MESSAGES: Dict[str, str] = {
    "First Document": "⭐ First step on the moon: 'First Document' badge earned!",
    "Speedster": "🚀 Blasting off with 'Speedster'! Quick as lunar light.",
    "Streak Lord": "🔥 On fire! 'Streak Lord' for unbreakable 7-day dedication.",
    "Scholar": "📚 Lunar library built: 'Scholar' achievement unlocked!",
    "Moon Collector": "🌙 Hoarding moons? 'Moon Collector' badge shines bright.",
    "Smart Worker": "🧠 Brainy moves: 'Smart Worker' badge unlocked — you followed Luna's wisdom!",
    "Document Master": "🛡️ Document Master unlocked! 50 conversions mastered.",
    "Lunar Legend": "🌌 Lunar Legend! Reached level 50 with style."
}

STREAK_MESSAGES: List[str] = [
    "🔥 You're on a {streak}-day streak! Luna is proud!",
    "✨ {streak} days strong! Keep the lunar momentum.",
    "🌓 Streak at {streak}! The moon bows to your consistency.",
    "🌕 Full power streak: {streak} days. Legendary!",
    "🌔 Waxing streak to {streak}! More moons await.",
    "🌒 Building momentum: {streak}-day streak unlocked!",
    "🪐 Orbital consistency: {streak} days in a row!"
]


class GamificationEngine:
    """Core class for managing gamification features."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.rank_thresholds: List[Tuple[int, str]] = [
            (4, '🌑 New Moon'),
            (9, '🌒 Crescent Seeker'),
            (19, '🌓 Half-Moon Adept'),
            (34, '🌔 Lunar Scholar'),
            (49, '🌕 Full Moon Pro'),
            (69, '🪐 Orbital Master'),
            (99, '✨ Celestial Elite'),
            (float('inf'), '🌙 Luna Overlord')
        ]

    async def init_db(self) -> None:
        """Initialize the database tables if they don't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript('''
                    CREATE TABLE IF NOT EXISTS gamification_users (
                        user_id INTEGER PRIMARY KEY,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        rank TEXT DEFAULT '🌑 New Moon',
                        streak INTEGER DEFAULT 0,
                        last_activity TEXT,
                        moons INTEGER DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS idx_gamification_users_user_id ON gamification_users(user_id);
                    
                    CREATE TABLE IF NOT EXISTS achievements (
                        user_id INTEGER,
                        achievement TEXT,
                        unlocked_at TEXT,
                        PRIMARY KEY (user_id, achievement)
                    );
                    CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id);
                ''')
                await db.commit()
            logger.info("Gamification database initialized successfully.")
        except aiosqlite.Error as e:
            logger.error(f"Gamification database initialization error: {e}")
            raise

    async def ensure_user(self, user_id: int) -> None:
        """Ensure a user exists in the gamification database."""
        await self.init_db()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR IGNORE INTO gamification_users (user_id, last_activity) VALUES (?, ?)',
                    (user_id, datetime.now().isoformat())
                )
                await db.commit()
        except aiosqlite.Error as e:
            logger.error(f"Error ensuring gamification user {user_id}: {e}")

    async def add_xp(self, user_id: int, amount: int = 50) -> Dict[str, Any]:
        """Add XP to a user and handle level ups."""
        await self.ensure_user(user_id)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT xp, level, moons FROM gamification_users WHERE user_id = ?', 
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    xp, level, moons = row or (0, 1, 0)

                new_xp = max(0, xp + amount)
                new_level = self._calculate_level(new_xp)
                leveled_up = new_level > level

                rank = self._get_rank(new_level)
                moons_reward = 0
                messages: List[str] = []

                if leveled_up:
                    moons_reward = new_level * 5
                    moons += moons_reward
                    messages.append(random.choice(LEVEL_UP_MESSAGES).format(
                        level=new_level, rank=rank, moons=moons_reward
                    ))
                    await self._check_achievements(user_id, new_level=new_level)

                await db.execute(
                    'UPDATE gamification_users SET xp = ?, level = ?, rank = ?, moons = ? WHERE user_id = ?',
                    (new_xp, new_level, rank, moons, user_id)
                )
                await db.commit()

            return {
                "leveled_up": leveled_up,
                "new_level": new_level,
                "new_rank": rank,
                "moons_reward": moons_reward,
                "total_xp": new_xp,
                "messages": messages
            }
        except aiosqlite.Error as e:
            logger.error(f"Error adding XP for user {user_id}: {e}")
            return {"leveled_up": False, "messages": []}

    async def update_streak(self, user_id: int) -> Dict[str, Any]:
        """Update user's streak based on activity."""
        await self.ensure_user(user_id)
        today = datetime.now().date()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT streak, last_activity FROM gamification_users WHERE user_id = ?', 
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    streak, last_str = row or (0, None)
                    last_date = None
                    if last_str:
                        try:
                            last_date = datetime.fromisoformat(last_str).date()
                        except ValueError:
                            last_date = None

                if last_date == today:
                    return {"streak": streak, "increased": False, "message": None}

                if last_date == today - timedelta(days=1):
                    new_streak = streak + 1
                else:
                    new_streak = 1

                streak_message = None
                if new_streak > streak:
                    if new_streak % 7 == 0:
                        await self.reward_moons(user_id, 20)
                        await self._unlock_achievement(user_id, "Streak Lord")
                        streak_message = "🔥 7-DAY STREAK! +20 moons | Streak Lord unlocked!"
                    else:
                        streak_message = random.choice(STREAK_MESSAGES).format(streak=new_streak)

                await db.execute(
                    'UPDATE gamification_users SET streak = ?, last_activity = ? WHERE user_id = ?',
                    (new_streak, today.isoformat(), user_id)
                )
                await db.commit()

            return {
                "streak": new_streak,
                "increased": new_streak > streak,
                "message": streak_message
            }
        except aiosqlite.Error as e:
            logger.error(f"Error updating streak for user {user_id}: {e}")
            return {"streak": 0, "increased": False, "message": None}

    async def reward_moons(self, user_id: int, amount: int) -> None:
        """Reward moons to a user."""
        await self.ensure_user(user_id)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE gamification_users SET moons = moons + ? WHERE user_id = ?', 
                    (amount, user_id)
                )
                await db.commit()
            total_moons = await self.get_moons(user_id)
            if total_moons >= 100:
                await self._unlock_achievement(user_id, "Moon Collector")
        except aiosqlite.Error as e:
            logger.error(f"Error rewarding moons for user {user_id}: {e}")

    async def get_moons(self, user_id: int) -> int:
        """Get the number of moons for a user."""
        await self.ensure_user(user_id)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT moons FROM gamification_users WHERE user_id = ?', 
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except aiosqlite.Error as e:
            logger.error(f"Error getting moons for user {user_id}: {e}")
            return 0

    async def _unlock_achievement(self, user_id: int, achievement: str) -> bool:
        """Unlock an achievement if not already unlocked."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT 1 FROM achievements WHERE user_id = ? AND achievement = ?',
                    (user_id, achievement)
                ) as cursor:
                    if await cursor.fetchone():
                        return False
                await db.execute(
                    'INSERT INTO achievements (user_id, achievement, unlocked_at) VALUES (?, ?, ?)',
                    (user_id, achievement, datetime.now().isoformat())
                )
                await db.commit()
            logger.info(f"Achievement unlocked: {achievement} for user {user_id}")
            return True
        except aiosqlite.Error as e:
            logger.error(f"Error unlocking achievement {achievement} for user {user_id}: {e}")
            return False

    async def _check_achievements(self, user_id: int, new_level: int) -> List[str]:
        """Check and unlock level-based achievements. Returns list of unlocked achievements."""
        achievements_to_check = []
        unlocked = []
        
        if new_level >= 2:
            achievements_to_check.append("First Document")
        if new_level >= 5:
            achievements_to_check.append("Speedster")
        if new_level >= 20:
            achievements_to_check.append("Scholar")
        if new_level >= 50:
            achievements_to_check.append("Lunar Legend")

        for ach in achievements_to_check:
            if await self._unlock_achievement(user_id, ach):
                unlocked.append(ach)
                logger.info(f"Unlocked {ach} for user {user_id}")

        return unlocked

    async def check_history_achievements(self, user_id: int, history_count: int) -> List[str]:
        """Check history-based achievements."""
        unlocked = []
        if history_count >= 50:
            if await self._unlock_achievement(user_id, "Document Master"):
                unlocked.append("Document Master")
        return unlocked

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Retrieve user's gamification profile."""
        await self.ensure_user(user_id)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT user_id, xp, level, rank, streak, last_activity, moons FROM gamification_users WHERE user_id = ?', 
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return {
                        "xp": 0, "level": 1, "rank": "🌑 New Moon",
                        "streak": 0, "moons": 0, "badges": [],
                        "next_level_xp": 100
                    }
                    
                async with db.execute(
                    'SELECT achievement, unlocked_at FROM achievements WHERE user_id = ?', 
                    (user_id,)
                ) as cursor:
                    badges = [{"name": r[0], "unlocked_at": r[1]} for r in await cursor.fetchall()]
            
            current_level = row[2]
            next_level_xp = ((current_level) ** 2) * 100
            
            return {
                "xp": row[1], 
                "level": row[2], 
                "rank": row[3],
                "streak": row[4], 
                "last_activity": row[5],
                "moons": row[6], 
                "badges": badges,
                "next_level_xp": next_level_xp
            }
        except aiosqlite.Error as e:
            logger.error(f"Error getting profile for user {user_id}: {e}")
            return {
                "xp": 0, "level": 1, "rank": "🌑 New Moon",
                "streak": 0, "moons": 0, "badges": [],
                "next_level_xp": 100
            }

    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by XP."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT user_id, xp, level, rank, moons FROM gamification_users ORDER BY xp DESC LIMIT ?',
                    (limit,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {"user_id": r[0], "xp": r[1], "level": r[2], "rank": r[3], "moons": r[4]}
                        for r in rows
                    ]
        except aiosqlite.Error as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

    def _calculate_level(self, xp: int) -> int:
        """Calculate level from XP using square root progression."""
        return int(math.sqrt(max(0, xp) / 100)) + 1

    def _get_rank(self, level: int) -> str:
        """Get rank based on level."""
        for max_level, rank in self.rank_thresholds:
            if level <= max_level:
                return rank
        return '🌙 Luna Overlord'

    def get_achievement_message(self, achievement: str) -> str:
        """Get the message for an achievement."""
        return ACHIEVEMENT_MESSAGES.get(achievement, f"🏆 Achievement unlocked: {achievement}!")


# Global instance
gamification_engine = GamificationEngine()
