# admin.py
import logging
import time
import os
from typing import Callable, Awaitable

from aiogram import Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Assuming a separate db.py module handles database interactions (e.g., using SQLite or similar).
# For production, db.py would use thread-safe connections and proper error handling.
from database.db import get_user_role, ban_user, unban_user, get_all_users  # type: ignore

load_dotenv()

# Define role levels
ROLE_LEVELS = {
    'superadmin': 3,
    'moderator': 2,
    'support': 1,
    'user': 0
}

# In-memory rate limiting (requests per minute). For production scale, replace with Redis.
RATE_LIMIT = 5  # max commands per minute per admin
user_command_times: dict[int, list[float]] = {}

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def rate_limit_check(user_id: int) -> bool:
    """
    Simple in-memory rate limiter. Checks if user exceeded command limit in the last 60 seconds.
    """
    now = time.time()
    if user_id in user_command_times:
        recent_times = [t for t in user_command_times[user_id] if now - t < 60]
        if len(recent_times) >= RATE_LIMIT:
            return False
        recent_times.append(now)
        user_command_times[user_id] = recent_times
    else:
        user_command_times[user_id] = [now]
    return True

def admin_only(min_role: str = 'support') -> Callable:
    """
    Decorator for role-based access control with rate limiting.
    Authentication is based on Telegram user_id validated against DB roles.
    No separate token/session needed as Telegram handles session implicitly via user_id.
    """
    min_level = ROLE_LEVELS.get(min_role, 1)

    def decorator(handler: Callable[[types.Message], Awaitable[None]]) -> Callable:
        async def wrapper(message: types.Message) -> None:
            user_id = message.from_user.id
            role = get_user_role(user_id)
            role_level = ROLE_LEVELS.get(role, 0)
            if role_level < min_level:
                await message.reply("You are not authorized for this action.")
                return
            if not rate_limit_check(user_id):
                await message.reply("Rate limit exceeded. Please try again later.")
                return
            try:
                await handler(message)
            except Exception as e:
                # Isolate errors to prevent system crash
                logger.error("Error in admin handler", exc_info=True, extra={'user_id': user_id, 'action': handler.__name__})
                await message.reply("An error occurred. Please try again.")

        return wrapper
    return decorator

@admin_only(min_role='moderator')
async def ban_handler(message: types.Message) -> None:
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        user_id_to_ban = int(parts[1])  # Input validation: must be integer
        if user_id_to_ban <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.reply("Usage: /ban <user_id> (positive integer)")
        return

    ban_user(user_id_to_ban)
    logger.info("Admin banned user", extra={'user_id': message.from_user.id, 'action': 'ban', 'target_user': user_id_to_ban})
    await message.reply(f"User {user_id_to_ban} has been banned.")

@admin_only(min_role='moderator')
async def unban_handler(message: types.Message) -> None:
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        user_id_to_unban = int(parts[1])  # Input validation: must be integer
        if user_id_to_unban <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.reply("Usage: /unban <user_id> (positive integer)")
        return

    unban_user(user_id_to_unban)
    logger.info("Admin unbanned user", extra={'user_id': message.from_user.id, 'action': 'unban', 'target_user': user_id_to_unban})
    await message.reply(f"User {user_id_to_unban} has been unbanned.")

@admin_only(min_role='superadmin')
async def broadcast_handler(message: types.Message) -> None:
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.reply("Usage: /broadcast <message>")
        return

    users = get_all_users()
    sent_count = 0
    for user_id in users:
        try:
            await message.bot.send_message(user_id, text)
            sent_count += 1
        except Exception:
            # Isolate per-user errors
            logger.warning("Failed to send broadcast to user", extra={'user_id': user_id, 'action': 'broadcast'})

    logger.info("Admin broadcasted message", extra={'user_id': message.from_user.id, 'action': 'broadcast', 'sent_count': sent_count, 'message': text})
    await message.reply(f"Broadcast sent to {sent_count} users.")

def register_admin_handlers(dp: Dispatcher) -> None:
    """
    Register all admin handlers with the dispatcher.
    """
    dp.register_message_handler(ban_handler, Command("ban"))
    dp.register_message_handler(unban_handler, Command("unban"))
    dp.register_message_handler(broadcast_handler, Command("broadcast"))
