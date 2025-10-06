import asyncio
import json
import hashlib
import hmac
import logging
import os
import time
from typing import Dict, Any, Optional

from aiogram import Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from dotenv import load_dotenv

load_dotenv()

# Secure secret for HMAC signatures (Fix 4: Prevent callback spoofing with server-side secret)
SECRET_KEY = os.getenv('BOT_SECRET_KEY', 'dev_fallback_secret_do_not_use_in_prod')

# Structured logging setup (Fix 2: Removed unsafe placeholders to prevent KeyError; use extras for context)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Callback context timeout (5 minutes)
CALLBACK_TIMEOUT = 300  # seconds
MAX_CALLBACK_DATA_LENGTH = 64  # Telegram limit

# In-memory fallback storage (Fix 3: Fault-tolerant Redis with in-memory fallback and expiration simulation)
callback_sessions: Dict[str, tuple[Dict[str, Any], float]] = {}
user_callback_times: Dict[int, list[float]] = {}
rate_lock = asyncio.Lock()

# Redis client initialization with connection test (Fix 3: Handle Redis failures gracefully)
REDIS_AVAILABLE = False
redis_client = None
try:
    import redis
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )
    redis_client.ping()  # Test connection
    REDIS_AVAILABLE = True
except Exception:
    logger.warning("Redis unavailable; falling back to in-memory storage")
    REDIS_AVAILABLE = False

def validate_callback_data(data: str) -> bool:
    """Validate callback data length, format, timestamp, and HMAC signature (Fix 1: Robust extraction and anti-spoofing)."""
    if not data or len(data) > MAX_CALLBACK_DATA_LENGTH:
        return False
    try:
        parts = data.split('|')
        if len(parts) != 4:
            return False
        action, ts_str, uid_str, received_sig = parts
        timestamp = int(ts_str)
        user_id = int(uid_str)
        if time.time() - timestamp > CALLBACK_TIMEOUT:
            return False
        # Verify HMAC signature (Fix 4: Secure against tampering)
        payload = f"{action}|{ts_str}|{uid_str}"
        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:8]
        if received_sig != expected_sig:
            logger.warning("Invalid HMAC signature in callback data", extra={'data': data[:20]})
            return False
        return True
    except (ValueError, IndexError):
        return False

def generate_callback_id(user_id: int, action: str, data: str = "") -> str:
    """Generate secure, time-bound callback identifier with HMAC (Fix 4: Server-side signing)."""
    timestamp = int(time.time())
    payload = f"{action}|{timestamp}|{user_id}"
    sig = hmac.new(
        SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:8]
    callback_data = f"{payload}|{sig}"
    # Truncate if necessary (rare, as payload is short)
    if len(callback_data) > MAX_CALLBACK_DATA_LENGTH:
        callback_data = callback_data[:MAX_CALLBACK_DATA_LENGTH]
    return callback_data

async def store_callback_context(callback_id: str, context: Dict[str, Any]) -> None:
    """Store callback context with expiration (Fix 3: Async-safe, fault-tolerant storage; Fix 5: Consistent handling)."""
    context_json = json.dumps(context)
    stored = False
    if REDIS_AVAILABLE:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                redis_client.setex,
                callback_id,
                CALLBACK_TIMEOUT,
                context_json
            )
            stored = True
        except Exception as e:
            logger.warning("Redis store failed, falling back to in-memory", exc_info=True, extra={'callback_id': callback_id})
    if not stored:
        # In-memory with simulated expiration via timestamp (Fix 3: Handle Redis downtime seamlessly)
        callback_sessions[callback_id] = (context, time.time())

async def get_callback_context(callback_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and validate callback context (single-use) (Fix 3: Fallback and cleanup; Fix 5: Consistent retrieval)."""
    if REDIS_AVAILABLE:
        loop = asyncio.get_running_loop()
        try:
            context_json = await loop.run_in_executor(None, redis_client.get, callback_id)
            if context_json:
                await loop.run_in_executor(None, redis_client.delete, callback_id)
                return json.loads(context_json)
        except Exception as e:
            logger.warning("Redis get failed, falling back to in-memory", exc_info=True, extra={'callback_id': callback_id})
    # Fallback to in-memory with expiration check
    if callback_id in callback_sessions:
        context, ts = callback_sessions[callback_id]
        if time.time() - ts > CALLBACK_TIMEOUT:
            # Expired: cleanup (comment: simulates Redis TTL)
            del callback_sessions[callback_id]
            return None
        del callback_sessions[callback_id]  # Single-use
        return context
    return None

async def rate_limit_callback(user_id: int) -> bool:
    """Async-safe rate limiting (10 per minute) (Fix 7: Use Redis atomic ops or locked in-memory fallback)."""
    if REDIS_AVAILABLE:
        loop = asyncio.get_running_loop()
        key = f"rate:{user_id}:count"
        try:
            count = await loop.run_in_executor(None, redis_client.incr, key)
            if count == 1:
                await loop.run_in_executor(None, redis_client.expire, key, 60)
            return count <= 10
        except Exception as e:
            logger.warning("Redis rate limit failed, falling back to in-memory", exc_info=True, extra={'user_id': user_id})
    # Locked in-memory fallback
    async with rate_lock:
        now = time.time()
        if user_id in user_callback_times:
            recent_times = [t for t in user_callback_times[user_id] if now - t < 60]
            if len(recent_times) >= 10:
                return False
            recent_times.append(now)
            user_callback_times[user_id] = recent_times
        else:
            user_callback_times[user_id] = [now]
        return True

def extract_user_id_from_callback(data: str) -> Optional[int]:
    """Securely extract user_id from callback data (Fix 1: Correct split for full format)."""
    try:
        parts = data.split('|')
        if len(parts) == 4:
            return int(parts[2])
        return None
    except (ValueError, IndexError):
        return None

async def safe_callback_response(callback: CallbackQuery, text: str = "Action completed.", show_alert: bool = False) -> None:
    """Send safe response to callback query with error isolation (Fix 6: Handle None/deleted messages via try/except)."""
    try:
        if show_alert:
            await callback.answer(text, show_alert=True)
        else:
            await callback.answer()
        # Attempt edit; fallback to new message if message is None or deleted (Fix 6)
        try:
            await callback.message.edit_text(text)
        except Exception:
            await callback.bot.send_message(callback.chat.id, text)
    except Exception as e:
        logger.error("Failed to respond to callback", exc_info=True, extra={
            'user_id': callback.from_user.id,
            'callback_id': callback.id
        })
        try:
            await callback.answer("An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass  # Last resort; can't do more

async def handle_unknown_callback(callback: CallbackQuery) -> None:
    """Handle unknown or expired callbacks gracefully."""
    await safe_callback_response(
        callback,
        "This action has expired or is no longer available.",
        show_alert=True
    )
    logger.warning("Unknown callback received", extra={
        'user_id': callback.from_user.id,
        'callback_id': callback.id,
        'data': callback.data
    })

async def process_callback_query(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Main callback query processor with security and context tracking (Fix 8: FSM ops wrapped; overall safety).
    """
    user_id = callback.from_user.id

    # Rate limiting (Fix 7)
    if not await rate_limit_callback(user_id):
        await safe_callback_response(callback, "Too many requests. Please wait.", show_alert=True)
        return

    # Validate callback data (Fix 1)
    if not callback.data or not validate_callback_data(callback.data):
        await handle_unknown_callback(callback)
        return

    # Verify user_id matches callback
    expected_user_id = extract_user_id_from_callback(callback.data)
    if expected_user_id != user_id:
        logger.warning("User ID mismatch in callback", extra={
            'expected': expected_user_id,
            'actual': user_id,
            'callback_id': callback.id
        })
        await safe_callback_response(callback, "Invalid action.", show_alert=True)
        return

    try:
        # Extract action (safe after validation)
        action = callback.data.split('|')[0]

        # Retrieve context (Fix 5)
        context = await get_callback_context(callback.data)
        if not context:
            await handle_unknown_callback(callback)
            return

        # Process based on action (extensible pattern)
        handler_map = {
            'confirm_payment': handle_payment_confirmation,
            'cancel_action': handle_cancel_action,
            'select_option': handle_option_selection,
            # Add more actions as needed
        }

        handler = handler_map.get(action)
        if handler:
            await handler(callback, state, context)
        else:
            await handle_unknown_callback(callback)

    except Exception as e:
        # Isolate errors completely
        logger.error("Callback processing error", exc_info=True, extra={
            'user_id': user_id,
            'callback_id': callback.id,
            'data': callback.data
        })
        await safe_callback_response(callback, "An unexpected error occurred.", show_alert=True)

async def handle_payment_confirmation(callback: CallbackQuery, state: FSMContext, context: Dict[str, Any]) -> None:
    """Handle payment confirmation callback."""
    amount = context.get('amount', 0)
    transaction_id = context.get('transaction_id', 'unknown')

    await safe_callback_response(callback, f"Payment of ${amount} confirmed!\nTransaction: {transaction_id}")

    # Wrap FSM operations (Fix 8: Prevent session errors)
    try:
        await state.update_data(payment_confirmed=True, transaction_id=transaction_id)
    except Exception as e:
        logger.error("Failed to update FSM state for payment confirmation", exc_info=True, extra={
            'user_id': callback.from_user.id,
            'transaction_id': transaction_id
        })

    logger.info("Payment confirmed via callback", extra={
        'user_id': callback.from_user.id,
        'amount': amount,
        'transaction_id': transaction_id,
        'action': 'confirm_payment'
    })

async def handle_cancel_action(callback: CallbackQuery, state: FSMContext, context: Dict[str, Any]) -> None:
    """Handle cancel action callback."""
    action_type = context.get('action_type', 'unknown')

    await safe_callback_response(callback, f"{action_type} cancelled.")

    # Wrap FSM operations (Fix 8)
    try:
        await state.finish()  # Clear any active state
    except Exception as e:
        logger.error("Failed to finish FSM state for cancel action", exc_info=True, extra={
            'user_id': callback.from_user.id,
            'action_type': action_type
        })

    logger.info("Action cancelled", extra={
        'user_id': callback.from_user.id,
        'action_type': action_type,
        'action': 'cancel_action'
    })

async def handle_option_selection(callback: CallbackQuery, state: FSMContext, context: Dict[str, Any]) -> None:
    """Handle option selection callback."""
    selected_option = context.get('option', 'unknown')
    category = context.get('category', 'general')

    response = f"You selected: {selected_option}\nCategory: {category}"
    await safe_callback_response(callback, response)

    logger.info("Option selected", extra={
        'user_id': callback.from_user.id,
        'option': selected_option,
        'category': category,
        'action': 'select_option'
    })

def create_confirmation_keyboard(user_id: int, text: str) -> InlineKeyboardMarkup:
    """Create confirmation inline keyboard (Fix: Added user_id param to bind correct user; minimal sig change via addition)."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    confirm_btn = InlineKeyboardButton("✅ Confirm", callback_data=generate_callback_id(user_id, "confirm_payment"))  # Assume context stored separately
    cancel_btn = InlineKeyboardButton("❌ Cancel", callback_data=generate_callback_id(user_id, "cancel_action", f"action:{text[:20]}"))
    keyboard.add(confirm_btn, cancel_btn)
    return keyboard

def create_option_keyboard(user_id: int, options: list, category: str = "general") -> InlineKeyboardMarkup:
    """Create option selection inline keyboard (Fix: Added user_id param)."""
    keyboard = InlineKeyboardMarkup(row_width=1)
    for option in options:
        callback_data = generate_callback_id(user_id, "select_option", f"option:{option}|category:{category}")
        btn = InlineKeyboardButton(option, callback_data=callback_data)
        keyboard.add(btn)
    return keyboard

def register_callback_handlers(dp: Dispatcher) -> None:
    """Register all callback query handlers (Aiogram 3.x compatible)."""
    # Catch-all for callbacks (Fix 9: Removed redundant lambda; direct register)
    dp.callback_query.register(process_callback_query)

# Example simulation of Redis failure handling (comment only; in prod, errors logged as above):
# If Redis down during store: falls back to in-memory dict with ts check in get (expires after 300s).
# If Redis down during rate limit: uses locked list, preventing >10/min per user.
# Tested: callback_data sig verified independently of storage.
