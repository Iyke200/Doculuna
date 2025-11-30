# gamification.py
"""Gamification engine for DocuLuna bot.

This module handles user progression, including XP, levels, ranks, streaks,
achievements, and moons (virtual currency). It uses aiosqlite for asynchronous
database operations and includes robust error handling and logging.
"""

import aiosqlite
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from messages import LEVEL_UP_MESSAGES, ACHIEVEMENT_MESSAGES, STREAK_MESSAGES
import random
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class GamificationEngine:
    """Core class for managing gamification features."""

    def __init__(self, db_path: str = "doculuna.db"):
        self.db_path = db_path
        self.rank_thresholds: List[Tuple[int, str]] = [
            (4, '🌑 New Moon'),
            (9, '🌒 Crescent Seeker'),
            (19, '🌓 Half-Moon Adept'),
            (34, '🌔 Lunar Scholar'),
            (49, '🌕 Full Moon Pro'),
            (69, '🪐 Orbital Master'),
            (99, '✨ Celestial Elite'),
            (float('inf'), '🌙 Luna Overlord')  # Use inf for the last rank
        ]

    async def init_db(self) -> None:
        """Initialize the database tables if they don't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        rank TEXT DEFAULT '🌑 New Moon',
                        streak INTEGER DEFAULT 0,
                        last_activity TEXT,
                        moons INTEGER DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
                    
                    CREATE TABLE IF NOT EXISTS achievements (
                        user_id INTEGER,
                        achievement TEXT,
                        unlocked_at TEXT,
                        PRIMARY KEY (user_id, achievement)
                    );
                    CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id);
                ''')
                await db.commit()
            logger.info("Database initialized successfully.")
        except aiosqlite.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    async def ensure_user(self, user_id: int) -> None:
        """Ensure a user exists in the database."""
        await self.init_db()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR IGNORE INTO users (user_id) VALUES (?)',
                    (user_id,)
                )
                await db.commit()
        except aiosqlite.Error as e:
            logger.error(f"Error ensuring user {user_id}: {e}")

    async def add_xp(self, user_id: int, amount: int = 50) -> Dict[str, Any]:
        """Add XP to a user and handle level ups."""
        await self.ensure_user(user_id)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT xp, level, moons FROM users WHERE user_id = ?', (user_id,)) as cursor:
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
                    'UPDATE users SET xp = ?, level = ?, rank = ?, moons = ? WHERE user_id = ?',
                    (new_xp, new_level, rank, moons, user_id)
                )
                await db.commit()

            return {
                "leveled_up": leveled_up,
                "new_level": new_level,
                "new_rank": rank,
                "moons_reward": moons_reward,
                "messages": messages
            }
        except aiosqlite.Error as e:
            logger.error(f"Error adding XP for user {user_id}: {e}")
            return {}

    async def update_streak(self, user_id: int) -> Dict[str, Any]:
        """Update user's streak based on activity."""
        await self.ensure_user(user_id)
        today = datetime.now().date()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT streak, last_activity FROM users WHERE user_id = ?', (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    streak, last_str = row or (0, None)
                    last_date = datetime.fromisoformat(last_str).date() if last_str else None

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
                    'UPDATE users SET streak = ?, last_activity = ? WHERE user_id = ?',
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
            return {}

    async def reward_moons(self, user_id: int, amount: int) -> None:
        """Reward moons to a user."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('UPDATE users SET moons = moons + ? WHERE user_id = ?', (amount, user_id))
                await db.commit()
            total_moons = await self.get_moons(user_id)
            if total_moons >= 100:
                await self._unlock_achievement(user_id, "Moon Collector")
        except aiosqlite.Error as e:
            logger.error(f"Error rewarding moons for user {user_id}: {e}")

    async def get_moons(self, user_id: int) -> int:
        """Get the number of moons for a user."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT moons FROM users WHERE user_id = ?', (user_id,)) as cursor:
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
            return True
        except aiosqlite.Error as e:
            logger.error(f"Error unlocking achievement {achievement} for user {user_id}: {e}")
            return False

    async def _check_achievements(self, user_id: int, new_level: int) -> None:
        """Check and unlock level-based achievements."""
        achievements = []
        if new_level >= 2:
            achievements.append("First Document")
        if new_level >= 5:
            achievements.append("Speedster")
        if new_level >= 20:
            achievements.append("Scholar")
        if new_level >= 50:
            achievements.append("Lunar Legend")

        for ach in achievements:
            unlocked = await self._unlock_achievement(user_id, ach)
            if unlocked:
                logger.info(f"Unlocked {ach} for user {user_id}")

        # Check history-based achievements
        from history import get_recent_history  # Deferred import to avoid circular deps
        history = await get_recent_history(user_id, limit=1000)
        if len(history) >= 50:
            unlocked = await self._unlock_achievement(user_id, "Document Master")
            if unlocked:
                logger.info(f"Unlocked Document Master for user {user_id}")

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Retrieve user's gamification profile."""
        await self.init_db()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    return {}
                async with db.execute('SELECT achievement FROM achievements WHERE user_id = ?', (user_id,)) as cursor:
                    badges = [r[0] for r in await cursor.fetchall()]
            return {
                "xp": row[1], "level": row[2], "rank": row[3],
                "streak": row[4], "moons": row[6], "badges": badges
            }
        except aiosqlite.Error as e:
            logger.error(f"Error getting profile for user {user_id}: {e}")
            return {}

    def _calculate_level(self, xp: int) -> int:
        """Calculate level from XP."""
        return int(math.sqrt(max(0, xp) / 100)) + 1

    def _get_rank(self, level: int) -> str:
        """Get rank based on level."""
        for max_level, rank in self.rank_thresholds:
            if level <= max_level:
                return rank
        return '🌙 Luna Overlord'
