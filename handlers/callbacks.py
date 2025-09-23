# callbacks.py
import logging
import time
import json
import hashlib
from typing import Callable, Awaitable, Dict, Any, Optional
from datetime import datetime, timedelta

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from dotenv import load_dotenv

# Assuming Redis for production session storage (fallback to in-memory for testing)
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict
    session_store = defaultdict(dict)
    REDIS_AVAILABLE = False

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - callback_id=%(callback_id)s - action=%(action)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Callback context timeout (5 minutes)
CALLBACK_TIMEOUT = 300  # seconds
MAX_CALLBACK_DATA_LENGTH = 64  # Telegram limit

# In-memory callback tracking (Redis in production)
callback_sessions: Dict[str, Dict[str, Any]] = {}
user_callback_times: dict[int, list[float]] = {}

def validate_callback_data(data: str) -> bool:
    """Validate callback data length and basic format."""
    if not data or len(data) > MAX_CALLBACK_DATA_LENGTH:
        return False
    try:
        # Basic structure: action|timestamp|user_id|data_hash
        parts = data.split('|', 3)
        if len(parts) < 3:
            return False
        timestamp = int(parts[1])
        user_id = int(parts[2])
        if time.time() - timestamp > CALLBACK_TIMEOUT:
            return False
        return True
    except (ValueError, IndexError):
        return False

def generate_callback_id(user_id: int, action: str, data: str = "") -> str:
    """Generate secure, time-bound callback identifier."""
    timestamp = int(time.time())
    data_hash = hashlib.sha256(f"{user_id}{action}{data}{timestamp}".encode()).hexdigest()[:8]
    callback_data = f"{action}|{timestamp}|{user_id}|{data_hash}"
    
    # Truncate if necessary
    if len(callback_data) > MAX_CALLBACK_DATA_LENGTH:
        callback_data = callback_data[:MAX_CALLBACK_DATA_LENGTH]
    
    return callback_data

def store_callback_context(callback_id: str, context: Dict[str, Any]) -> None:
    """Store callback context with expiration."""
    if REDIS_AVAILABLE:
        redis_client.setex(callback_id, CALLBACK_TIMEOUT, json.dumps(context))
    else:
        callback_sessions[callback_id] = context

def get_callback_context(callback_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and validate callback context."""
    if REDIS_AVAILABLE:
        context_json = redis_client.get(callback_id)
        if not context_json:
            return None
        redis_client.delete(callback_id)  # Single-use
        return json.loads(context_json)
    else:
        if callback_id not in callback_sessions:
            return None
        context = callback_sessions.pop(callback_id)
        return context

def rate_limit_callback(user_id: int) -> bool:
    """Rate limit callback queries (10 per minute)."""
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
    """Securely extract user_id from callback data."""
    try:
        parts = data.split('|', 2)
        if len(parts) < 3:
            return None
        return int(parts[2])
    except (ValueError, IndexError):
        return None

async def safe_callback_response(callback: CallbackQuery, text: str = "Action completed.", show_alert: bool = False) -> None:
    """Send safe response to callback query with error isolation."""
    try:
        if show_alert:
            await callback.answer(text, show_alert=True)
        else:
            await callback.answer()
            await callback.message.edit_text(text) if callback.message else await callback.message.reply(text)
    except Exception as e:
        logger.error("Failed to respond to callback", exc_info=True, extra={'user_id': callback.from_user.id, 'callback_id': callback.id})
        try:
            await callback.answer("An error occurred. Please try again.", show_alert=True)
        except:
            pass

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
    Main callback query processor with security and context tracking.
    """
    user_id = callback.from_user.id
    
    # Rate limiting
    if not rate_limit_callback(user_id):
        await safe_callback_response(callback, "Too many requests. Please wait.", show_alert=True)
        return
    
    # Validate callback data
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
        # Extract action
        action = callback.data.split('|')[0]
        
        # Retrieve context
        context = get_callback_context(callback.data)
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
    
    # Store state in FSM if needed
    await state.update_data(payment_confirmed=True, transaction_id=transaction_id)
    
    logger.info("Payment confirmed via callback", extra={
        'user_id': callback.from_user.id, 
        'amount': amount, 
        'transaction_id': transaction_id
    })

async def handle_cancel_action(callback: CallbackQuery, state: FSMContext, context: Dict[str, Any]) -> None:
    """Handle cancel action callback."""
    action_type = context.get('action_type', 'unknown')
    
    await safe_callback_response(callback, f"{action_type} cancelled.")
    await state.finish()  # Clear any active state
    
    logger.info("Action cancelled", extra={
        'user_id': callback.from_user.id, 
        'action_type': action_type
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
        'category': category
    })

def create_confirmation_keyboard(text: str, callback_data: str) -> types.InlineKeyboardMarkup:
    """Create confirmation inline keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    confirm_btn = types.InlineKeyboardButton("✅ Confirm", callback_data=callback_data)
    cancel_btn = types.InlineKeyboardButton("❌ Cancel", callback_data=generate_callback_id(
        0, "cancel_action", f"action:{text[:20]}"
    ))
    keyboard.add(confirm_btn, cancel_btn)
    return keyboard

def create_option_keyboard(options: list, category: str = "general") -> types.InlineKeyboardMarkup:
    """Create option selection inline keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for option in options:
        callback_data = generate_callback_id(0, "select_option", f"option:{option}|category:{category}")
        btn = types.InlineKeyboardButton(option, callback_data=callback_data)
        keyboard.add(btn)
    return keyboard

def register_callback_handlers(dp: Dispatcher) -> None:
    """Register all callback query handlers."""
    # aiogram 3.x syntax
    dp.callback_query.register(
        process_callback_query, 
        lambda c: True  # Catch all callback queries
    )
