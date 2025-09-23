# start.py
import logging
import json
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import bold as hbold, code as hcode, link as hlink
from dotenv import load_dotenv

# Assuming Redis for user session storage (fallback to in-memory)
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=4, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict
    user_preferences = defaultdict(dict)
    user_onboarding = defaultdict(dict)
    REDIS_AVAILABLE = False

# Import from other modules
from database.db import get_user_data, create_user, update_user_data  # type: ignore
from handlers.referrals import process_referral, REFERRAL_CONFIG  # type: ignore
from handlers.premium import get_premium_data, PremiumStatus  # type: ignore
from handlers.help import HelpCategory  # type: ignore

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s - is_new=%(is_new)s - preferences=%(preferences)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class OnboardingStep(Enum):
    """Onboarding workflow steps."""
    WELCOME = "welcome"
    LANGUAGE = "language"
    PREFERENCES = "preferences"
    FEATURES = "features"
    COMPLETE = "complete"

# Default user preferences
DEFAULT_PREFERENCES = {
    'language': 'en',
    'theme': 'light',
    'notifications': True,
    'document_format': 'auto',
    'ai_level': 'standard',
    'region': 'global',
    'timezone': 'UTC',
    'welcome_shown': False,
    'onboarding_complete': False
}

# Supported languages
SUPPORTED_LANGUAGES = {
    'en': {'code': 'en', 'name': 'English', 'flag': '🇺🇸'},
    'es': {'code': 'es', 'name': 'Español', 'flag': '🇪🇸'},
    'fr': {'code': 'fr', 'name': 'Français', 'flag': '🇫🇷'},
    'pt': {'code': 'pt', 'name': 'Português', 'flag': '🇧🇷'},
    'de': {'code': 'de', 'name': 'Deutsch', 'flag': '🇩🇪'},
    'it': {'code': 'it', 'name': 'Italiano', 'flag': '🇮🇹'},
    'ru': {'code': 'ru', 'name': 'Русский', 'flag': '🇷🇺'},
    'zh': {'code': 'zh', 'name': '中文', 'flag': '🇨🇳'},
    'ja': {'code': 'ja', 'name': '日本語', 'flag': '🇯🇵'},
    'ko': {'code': 'ko', 'name': '한국어', 'flag': '🇰🇷'}
}

class UserOnboarding:
    """User onboarding state management."""
    
    def __init__(self):
        self.active_states: Dict[int, Dict[str, Any]] = {}
    
    async def start_onboarding(self, user_id: int, language: str = 'en') -> None:
        """Start onboarding flow for new user."""
        try:
            onboarding_key = f"onboarding:{user_id}"
            
            onboarding_data = {
                'user_id': user_id,
                'step': OnboardingStep.WELCOME.value,
                'language': language,
                'started_at': datetime.utcnow().isoformat(),
                'completed': False,
                'progress': 0,
                'preferences': DEFAULT_PREFERENCES.copy()
            }
            
            if REDIS_AVAILABLE:
                redis_client.setex(onboarding_key, 7 * 86400, json.dumps(onboarding_data))  # 7 days
            else:
                user_onboarding[onboarding_key] = onboarding_data
            
            self.active_states[user_id] = onboarding_data
            
            logger.info("Onboarding started", extra={
                'user_id': user_id,
                'language': language
            })
            
        except Exception as e:
            logger.error("Failed to start onboarding", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
    
    async def get_onboarding_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get current onboarding state."""
        try:
            onboarding_key = f"onboarding:{user_id}"
            
            if user_id in self.active_states:
                return self.active_states[user_id]
            
            if REDIS_AVAILABLE:
                data = redis_client.get(onboarding_key)
                if data:
                    state = json.loads(data)
                    self.active_states[user_id] = state
                    return state
            else:
                if onboarding_key in user_onboarding:
                    state = user_onboarding[onboarding_key]
                    self.active_states[user_id] = state
                    return state
            
            return None
            
        except Exception as e:
            logger.error("Failed to get onboarding state", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
            return None
    
    async def update_onboarding_step(self, user_id: int, step: str, data: Dict[str, Any] = None) -> None:
        """Update onboarding step and progress."""
        try:
            state = await self.get_onboarding_state(user_id)
            if not state:
                return
            
            state['step'] = step
            state['progress'] = self._calculate_progress(step)
            
            if data:
                state['preferences'].update(data)
            
            # Mark as complete if final step
            if step == OnboardingStep.COMPLETE.value:
                state['completed'] = True
                state['completed_at'] = datetime.utcnow().isoformat()
                await self.complete_onboarding(user_id, state['preferences'])
            
            onboarding_key = f"onboarding:{user_id}"
            
            if REDIS_AVAILABLE:
                redis_client.setex(onboarding_key, 7 * 86400, json.dumps(state))
            else:
                user_onboarding[onboarding_key] = state
            
            self.active_states[user_id] = state
            
            logger.info("Onboarding step updated", extra={
                'user_id': user_id,
                'step': step,
                'progress': state['progress']
            })
            
        except Exception as e:
            logger.error("Failed to update onboarding step", exc_info=True, extra={
                'user_id': user_id,
                'step': step,
                'error': str(e)
            })
    
    def _calculate_progress(self, step: str) -> int:
        """Calculate onboarding progress percentage."""
        steps = {
            OnboardingStep.WELCOME.value: 0,
            OnboardingStep.LANGUAGE.value: 25,
            OnboardingStep.PREFERENCES.value: 75,
            OnboardingStep.FEATURES.value: 90,
            OnboardingStep.COMPLETE.value: 100
        }
        return steps.get(step, 0)
    
    async def complete_onboarding(self, user_id: int, preferences: Dict[str, Any]) -> None:
        """Complete onboarding and save preferences."""
        try:
            # Save preferences to user data
            update_user_data(user_id, {
                'preferences': preferences,
                'onboarding_complete': True,
                'onboarding_date': datetime.utcnow().isoformat(),
                'language': preferences['language'],
                'timezone': preferences.get('timezone', 'UTC')
            })
            
            # Clean up onboarding state
            onboarding_key = f"onboarding:{user_id}"
            if REDIS_AVAILABLE:
                redis_client.delete(onboarding_key)
            else:
                if onboarding_key in user_onboarding:
                    del user_onboarding[onboarding_key]
            
            if user_id in self.active_states:
                del self.active_states[user_id]
            
            logger.info("Onboarding completed", extra={
                'user_id': user_id,
                'language': preferences['language'],
                'preferences': json.dumps({k: v for k, v in preferences.items() if k != 'welcome_shown'})
            })
            
        except Exception as e:
            logger.error("Failed to complete onboarding", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })

# Global onboarding manager
onboarding_manager = UserOnboarding()

def is_new_user(user_id: int) -> bool:
    """Check if user is new (no existing data)."""
    try:
        user_data = get_user_data(user_id)
        return not user_data or user_data.get('created_at') is None
    except Exception as e:
        logger.error("Failed to check user status", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return True

async def get_user_preferences(user_id: int) -> Dict[str, Any]:
    """Get user preferences with defaults."""
    try:
        user_data = get_user_data(user_id)
        preferences = user_data.get('preferences', {})
        
        # Merge with defaults
        final_prefs = DEFAULT_PREFERENCES.copy()
        final_prefs.update(preferences)
        
        # Ensure required fields
        final_prefs.setdefault('welcome_shown', False)
        final_prefs.setdefault('onboarding_complete', False)
        
        return final_prefs
        
    except Exception as e:
        logger.error("Failed to get user preferences", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return DEFAULT_PREFERENCES.copy()

async def create_user_record(user_id: int, username: str = None, first_name: str = None, 
                           last_name: str = None, language_code: str = 'en') -> None:
    """Create initial user record."""
    try:
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'language_code': language_code,
            'created_at': datetime.utcnow().isoformat(),
            'last_active': datetime.utcnow().isoformat(),
            'preferences': DEFAULT_PREFERENCES.copy(),
            'onboarding_complete': False,
            'total_interactions': 0,
            'premium_status': PremiumStatus.EXPIRED.value,
            'referral_used': False
        }
        
        create_user(user_data)
        
        # Initialize empty preferences in storage
        await store_user_preferences(user_id, DEFAULT_PREFERENCES)
        
        logger.info("User record created", extra={
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'language': language_code
        })
        
    except Exception as e:
        logger.error("Failed to create user record", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })

async def store_user_preferences(user_id: int, preferences: Dict[str, Any]) -> None:
    """Store user preferences."""
    try:
        pref_key = f"preferences:{user_id}"
        
        # Merge with defaults
        full_prefs = DEFAULT_PREFERENCES.copy()
        full_prefs.update(preferences)
        
        if REDIS_AVAILABLE:
            redis_client.setex(pref_key, 30 * 86400, json.dumps(full_prefs))  # 30 days
        else:
            user_preferences[pref_key] = full_prefs
        
        # Update database
        update_user_data(user_id, {'preferences': full_prefs})
        
    except Exception as e:
        logger.error("Failed to store preferences", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })

async def get_welcome_message(user_id: int, is_new: bool, preferences: Dict[str, Any], 
                           referral_result: Dict[str, Any] = None) -> str:
    """Generate personalized welcome message."""
    lang = preferences.get('language', 'en')
    lang_data = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES['en'])
    
    if is_new:
        # New user welcome
        welcome_text = (
            f"🌟 *Welcome to DocuLuna, {preferences.get('first_name', 'new user')}!* 🌟\n\n"
            f"✨ *Discover the power of AI document processing*\n\n"
            f"📚 *What you'll love:*\n"
        )
        
        features = [
            "🔍 Instant document analysis",
            "⚡ Lightning-fast processing", 
            "🧠 Smart AI insights",
            "🔒 Privacy first, always",
            "📱 Works on any device"
        ]
        
        for feature in features:
            welcome_text += f"• {feature}\n"
        
        welcome_text += f"\n🎯 *Quick Start:*\n"
        welcome_text += f"• `/help` - Explore all features\n"
        welcome_text += f"• `/premium` - Unlock unlimited access (₦1,000/week • ₦3,500/month)\n"
        welcome_text += f"• `/upgrade` - Get started with premium\n\n"
        
        if referral_result and referral_result.get('success'):
            # Add referral bonus info
            reward = referral_result.get('new_user_reward')
            if reward and reward.get('success'):
                welcome_text += f"🎁 *Special:* You received {reward['description']}!\n\n"
        
        welcome_text += f"💎 *Ready to begin?* Reply with your first document or use `/help`"
        
    else:
        # Returning user welcome
        last_active = preferences.get('last_active', '')
        if last_active:
            try:
                last_date = datetime.fromisoformat(last_active)
                days_away = (datetime.utcnow() - last_date).days
                if days_away == 0:
                    greeting = "👋 *Welcome back!*"
                elif days_away == 1:
                    greeting = "👋 *Welcome back! Missed you yesterday.*"
                else:
                    greeting = f"👋 *Welcome back! It's been {days_away} days.*"
            except:
                greeting = "👋 *Welcome back!*"
        else:
            greeting = "👋 *Welcome back!*"
        
        # Check premium status
        premium_data = await get_premium_data(user_id)
        premium_status = premium_data.get('status', PremiumStatus.EXPIRED.value)
        
        welcome_text = f"{greeting}\n\n"
        
        if premium_status == PremiumStatus.ACTIVE:
            expiry = datetime.fromisoformat(premium_data['expiry'])
            days_left = max(0, (expiry - datetime.utcnow()).days)
            plan_name = next((p.value['name'] for p in PremiumPlan if p.value['id'] == premium_data.get('plan')), 'Premium')
            
            welcome_text += f"🎖 *Premium Active* - {plan_name}\n"
            welcome_text += f"⏰ *Expires in:* {days_left} days\n\n"
        else:
            welcome_text += f"💎 *Upgrade to premium* for unlimited features!\n\n"
        
        welcome_text += f"🚀 *What's new:*\n"
        welcome_text += f"• Enhanced AI analysis\n"
        welcome_text += f"• Faster processing\n"
        welcome_text += f"• New referral program\n\n"
        
        welcome_text += f"📋 *Recent actions:*\n"
        welcome_text += f"• `/help` - Full command list\n"
        welcome_text += f"• `/premium` - Manage subscription\n"
        welcome_text += f"• `/refer` - Earn rewards\n\n"
        
        welcome_text += f"💬 *Upload a document* or type `/help` to continue!"
    
    return welcome_text

async def show_language_selection(message: types.Message, state: FSMContext) -> None:
    """Show language selection inline keyboard."""
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Add language buttons
        for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
            btn_text = f"{lang_info['flag']} {lang_info['name']}"
            callback_data = f"lang_{lang_code}"
            button = types.InlineKeyboardButton(btn_text, callback_data=callback_data)
            keyboard.add(button)
        
        # Skip button
        skip_btn = types.InlineKeyboardButton("⏭ Skip", callback_data="lang_skip")
        keyboard.add(skip_btn)
        
        response = (
            f"🌐 *Choose Your Language*\n\n"
            f"Select your preferred language for the best experience:\n\n"
            f"💡 *Tip:* You can change this anytime in settings."
        )
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Failed to show language selection", exc_info=True, extra={
            'user_id': message.from_user.id,
            'error': str(e)
        })
        await message.reply("Language selection temporarily unavailable. Continuing in English.")

async def show_preferences_selection(message: types.Message, state: FSMContext, 
                                   language: str = 'en') -> None:
    """Show preferences selection with inline keyboard."""
    try:
        # Get current preferences
        preferences = await get_user_preferences(message.from_user.id)
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Notification preference
        notif_text = "🔔 On" if preferences.get('notifications', True) else "🔕 Off"
        notif_callback = "pref_notifications_on" if not preferences.get('notifications', True) else "pref_notifications_off"
        notif_btn = types.InlineKeyboardButton(f"Notifications: {notif_text}", callback_data=notif_callback)
        keyboard.row(notif_btn)
        
        # AI level preference
        ai_levels = {
            'basic': '🐣 Basic',
            'standard': '🧠 Standard', 
            'advanced': '🚀 Advanced'
        }
        current_ai = preferences.get('ai_level', 'standard')
        ai_text = ai_levels.get(current_ai, '🧠 Standard')
        ai_callback = f"pref_ai_{'basic' if current_ai != 'basic' else 'standard' if current_ai != 'standard' else 'advanced'}"
        ai_btn = types.InlineKeyboardButton(f"AI Level: {ai_text}", callback_data=ai_callback)
        keyboard.row(ai_btn)
        
        # Theme preference
        theme_text = "☀️ Light" if preferences.get('theme', 'light') == 'light' else "🌙 Dark"
        theme_callback = "pref_theme_dark" if preferences.get('theme', 'light') == 'light' else "pref_theme_light"
        theme_btn = types.InlineKeyboardButton(f"Theme: {theme_text}", callback_data=theme_callback)
        keyboard.row(theme_btn)
        
        # Document format preference
        format_options = {
            'auto': '🔄 Auto-detect',
            'pdf': '📄 PDF only',
            'doc': '📝 Word docs',
            'images': '🖼️ Images'
        }
        current_format = preferences.get('document_format', 'auto')
        format_text = format_options.get(current_format, '🔄 Auto-detect')
        format_callback = f"pref_format_{next(k for k, v in format_options.items() if k != current_format)}"
        format_btn = types.InlineKeyboardButton(f"Documents: {format_text}", callback_data=format_callback)
        keyboard.row(format_btn)
        
        # Complete button
        complete_btn = types.InlineKeyboardButton("✅ All Set!", callback_data="onboarding_complete")
        keyboard.add(complete_btn)
        
        response = (
            f"⚙️ *Customize Your Experience*\n\n"
            f"Adjust your preferences:\n\n"
            f"💡 *You can change these anytime with* `/settings`"
        )
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Failed to show preferences selection", exc_info=True, extra={
            'user_id': message.from_user.id,
            'language': language,
            'error': str(e)
        })
        await message.reply("Preferences setup temporarily unavailable. Continuing with defaults.")

async def show_feature_tour(message: types.Message, state: FSMContext, 
                          language: str = 'en') -> None:
    """Show feature tour with quick action buttons."""
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Feature tour buttons
        features = [
            ("📄 Document Upload", "tour_documents"),
            ("🧠 AI Analysis", "tour_ai"), 
            ("💎 Premium Plans", "tour_premium"),
            ("👥 Refer & Earn", "tour_referrals"),
            ("⚙️ Settings", "tour_settings")
        ]
        
        for feature_text, callback_data in features:
            button = types.InlineKeyboardButton(feature_text, callback_data=callback_data)
            keyboard.add(button)
        
        # Quick actions
        quick_actions = [
            ("🚀 Try Premium", "quick_upgrade"),
            ("📖 See Commands", "quick_help"),
            ("👋 Skip Tour", "tour_skip")
        ]
        
        for action_text, callback_data in quick_actions:
            button = types.InlineKeyboardButton(action_text, callback_data=callback_data)
            keyboard.add(button)
        
        response = (
            f"🎉 *Feature Tour*\n\n"
            f"Discover what's possible with DocuLuna:\n\n"
            f"✨ *Tap any feature below* to learn more and get started!\n\n"
            f"💡 *Pro tip:* You can always revisit with `/help`"
        )
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Failed to show feature tour", exc_info=True, extra={
            'user_id': message.from_user.id,
            'language': language,
            'error': str(e)
        })
        await message.reply("Feature tour temporarily unavailable. Use `/help` to explore!")

async def start_command_handler(message: types.Message, state: FSMContext) -> None:
    """Main /start command handler with new/returning user detection."""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    language_code = message.from_user.language_code or 'en'
    
    try:
        # Step 1: Check if user exists
        user_data = get_user_data(user_id)
        is_new = not user_data
        
        # Step 2: Create user record if new
        if is_new:
            await create_user_record(user_id, username, first_name, last_name, language_code)
            logger.info("New user detected", extra={'user_id': user_id, 'username': username})
        else:
            # Update last active
            update_user_data(user_id, {'last_active': datetime.utcnow().isoformat()})
            logger.info("Returning user detected", extra={'user_id': user_id, 'days_since_last': 'calculated'})
        
        # Step 3: Check onboarding status
        preferences = await get_user_preferences(user_id)
        onboarding_complete = preferences.get('onboarding_complete', False)
        welcome_shown = preferences.get('welcome_shown', False)
        
        # Step 4: Handle referral from deep link
        referral_result = None
        text = message.text or ""
        if text.startswith('/start ref_'):
            code = text[11:].strip().upper()
            if len(code) == REFERRAL_CONFIG['code_length']:
                from database.db import get_user_role  # type: ignore
                user_role = get_user_role(user_id) or 'new_user'
                referral_result = await process_referral(user_id, code, user_role)
                logger.info("Referral processed in start", extra={
                    'user_id': user_id,
                    'code': code,
                    'success': referral_result.get('success', False)
                })
        
        # Step 5: Determine flow
        if is_new:
            # New user: Start onboarding
            await onboarding_manager.start_onboarding(user_id, language_code)
            await show_welcome_screen(message, state)
            
        elif not onboarding_complete and not welcome_shown:
            # Incomplete onboarding
            current_step = (await onboarding_manager.get_onboarding_state(user_id))['step'] if await onboarding_manager.get_onboarding_state(user_id) else OnboardingStep.WELCOME.value
            await handle_onboarding_step(message, state, current_step)
            
        else:
            # Returning user: Show welcome
            welcome_text = await get_welcome_message(user_id, False, preferences, referral_result)
            
            # Mark welcome as shown
            if not welcome_shown:
                preferences['welcome_shown'] = True
                await store_user_preferences(user_id, preferences)
            
            # Add quick action buttons for returning users
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            actions = [
                ("📄 Upload Document", "quick_upload"),
                ("💎 Upgrade Premium", "quick_upgrade"),
                ("📊 My Stats", "quick_stats"),
                ("👥 Refer Friends", "quick_refer")
            ]
            
            for action_text, callback_data in actions:
                button = types.InlineKeyboardButton(action_text, callback_data=callback_data)
                keyboard.add(button)
            
            await message.reply(welcome_text, parse_mode='Markdown', reply_markup=keyboard)
            
            logger.info("Returning user welcome shown", extra={
                'user_id': user_id,
                'premium_active': preferences.get('premium_status') == PremiumStatus.ACTIVE.value
            })
        
    except Exception as e:
        logger.error("Start command handler error", exc_info=True, extra={
            'user_id': user_id,
            'is_new': is_new,
            'error': str(e)
        })
        # Fallback welcome
        fallback_text = (
            f"👋 *Hi there!*\n\n"
            f"Welcome to DocuLuna - your AI document assistant.\n\n"
            f"🚀 *Get started:*\n"
            f"• `/help` - All commands\n"
            f"• `/premium` - Upgrade\n"
            f"• Upload a document to begin\n\n"
            f"Something went wrong - try `/help` for assistance!"
        )
        await message.reply(fallback_text, parse_mode='Markdown')

async def show_welcome_screen(message: types.Message, state: FSMContext) -> None:
    """Show initial welcome screen for new users."""
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "friend"
    
    try:
        # Get language preference
        lang_code = message.from_user.language_code or 'en'
        lang_data = SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES['en'])
        
        welcome_text = (
            f"🎉 *Welcome to DocuLuna, {first_name}!* 🎉\n\n"
            f"✨ *AI-Powered Document Magic*\n\n"
            f"Transform how you work with documents:\n\n"
            f"🔍 *Instant Analysis* - Upload & get insights\n"
            f"⚡ *Lightning Fast* - Process in seconds\n"
            f"🧠 *Smart AI* - Understands context\n"
            f"🔒 *Private & Secure* - Your data stays yours\n\n"
            f"🌟 *Ready to begin your journey?*\n\n"
            f"👇 *Let's set up your preferences first!*"
        )
        
        # Create simple continue button
        keyboard = types.InlineKeyboardMarkup()
        continue_btn = types.InlineKeyboardButton("🚀 Let's Go!", callback_data="welcome_continue")
        keyboard.add(continue_btn)
        
        await message.reply(welcome_text, parse_mode='Markdown', reply_markup=keyboard)
        
        # Start onboarding
        await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.WELCOME.value)
        
        logger.info("New user welcome screen shown", extra={
            'user_id': user_id,
            'first_name': first_name,
            'language': lang_code
        })
        
    except Exception as e:
        logger.error("Failed to show welcome screen", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        await message.reply(
            f"Welcome, {first_name}! Let's get started with `/help`",
            parse_mode='Markdown'
        )

async def handle_onboarding_step(message: types.Message, state: FSMContext, step: str) -> None:
    """Handle specific onboarding step."""
    user_id = message.from_user.id
    
    try:
        if step == OnboardingStep.WELCOME.value:
            await show_language_selection(message, state)
            await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.LANGUAGE.value)
            
        elif step == OnboardingStep.LANGUAGE.value:
            await show_preferences_selection(message, state)
            await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.PREFERENCES.value)
            
        elif step == OnboardingStep.PREFERENCES.value:
            await show_feature_tour(message, state)
            await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.FEATURES.value)
            
        elif step == OnboardingStep.FEATURES.value:
            # Complete onboarding
            preferences = await get_user_preferences(user_id)
            await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.COMPLETE.value, preferences)
            
            # Show completion message
            completion_text = (
                f"🎉 *All Set Up!*\n\n"
                f"✨ *Your DocuLuna journey begins now!*\n\n"
                f"🚀 *Quick recap:*\n"
                f"• Language: {SUPPORTED_LANGUAGES[preferences['language']]['name']}\n"
                f"• Notifications: {'🔔 On' if preferences['notifications'] else '🔕 Off'}\n"
                f"• AI Level: {'🚀 Advanced' if preferences['ai_level'] == 'advanced' else '🧠 Standard'}\n\n"
                f"💎 *Ready to try?*\n"
                f"• Upload a document 📄\n"
                f"• Or use `/help` for commands\n"
                f"• Check `/premium` for unlimited access"
            )
            
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            try_btn = types.InlineKeyboardButton("📄 Try Document", callback_data="start_try_document")
            premium_btn = types.InlineKeyboardButton("💎 Get Premium", callback_data="start_upgrade")
            help_btn = types.InlineKeyboardButton("📖 Help", callback_data="start_help")
            
            keyboard.add(try_btn, premium_btn)
            keyboard.add(help_btn)
            
            await message.reply(completion_text, parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        logger.error("Failed to handle onboarding step", exc_info=True, extra={
            'user_id': user_id,
            'step': step,
            'error': str(e)
        })
        await message.reply("Setup complete! Use `/help` to get started.")

# Callback handlers for onboarding
async def handle_onboarding_callbacks(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle onboarding callback queries."""
    user_id = callback.from_user.id
    data = callback.data
    
    try:
        current_state = await onboarding_manager.get_onboarding_state(user_id)
        if not current_state:
            await callback.answer("Onboarding session expired. Use /start to begin again.")
            return
        
        if data.startswith('lang_'):
            # Language selection
            lang_code = data[5:]  # Remove 'lang_' prefix
            if lang_code == 'skip':
                lang_code = 'en'
            
            if lang_code in SUPPORTED_LANGUAGES:
                lang_info = SUPPORTED_LANGUAGES[lang_code]
                preferences = current_state['preferences']
                preferences['language'] = lang_code
                
                await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.LANGUAGE.value, {'language': lang_code})
                
                # Update message
                lang_text = f"✅ *Language Set*\n\n{lang_info['flag']} {lang_info['name']} selected!\n\nNext: Preferences ➡️"
                keyboard = types.InlineKeyboardMarkup()
                continue_btn = types.InlineKeyboardButton("⚙️ Preferences", callback_data="lang_continue")
                keyboard.add(continue_btn)
                
                await callback.message.edit_text(lang_text, parse_mode='Markdown', reply_markup=keyboard)
                await callback.answer(f"Language set to {lang_info['name']}")
            else:
                await callback.answer("Invalid language selection.")
                
        elif data == 'lang_continue':
            await show_preferences_selection(callback.message, state, current_state['language'])
            await callback.answer()
            
        elif data.startswith('pref_'):
            # Preference updates
            current_prefs = current_state['preferences']
            
            if data == 'pref_notifications_on':
                current_prefs['notifications'] = True
                await callback.answer("🔔 Notifications enabled")
            elif data == 'pref_notifications_off':
                current_prefs['notifications'] = False
                await callback.answer("🔕 Notifications disabled")
                
            elif data.startswith('pref_ai_'):
                new_ai = data[7:]  # Remove 'pref_ai_' prefix
                current_prefs['ai_level'] = new_ai
                ai_levels = {'basic': '🐣 Basic', 'standard': '🧠 Standard', 'advanced': '🚀 Advanced'}
                await callback.answer(f"AI level set to {ai_levels[new_ai]}")
                
            elif data.startswith('pref_theme_'):
                new_theme = data[10:]  # Remove 'pref_theme_' prefix
                current_prefs['theme'] = new_theme
                theme_text = "☀️ Light" if new_theme == 'light' else "🌙 Dark"
                await callback.answer(f"Theme set to {theme_text}")
                
            elif data.startswith('pref_format_'):
                new_format = data[10:]  # Remove 'pref_format_' prefix
                current_prefs['document_format'] = new_format
                formats = {'auto': '🔄 Auto', 'pdf': '📄 PDF', 'doc': '📝 Docs', 'images': '🖼️ Images'}
                await callback.answer(f"Document format: {formats[new_format]}")
                
            elif data == 'onboarding_complete':
                # Skip to completion
                await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.COMPLETE.value, current_prefs)
                await handle_onboarding_step(callback.message, state, OnboardingStep.COMPLETE.value)
                await callback.answer("Setup complete! 🎉")
                
            # Refresh preferences screen
            await show_preferences_selection(callback.message, state, current_state['language'])
            
        elif data.startswith('tour_'):
            # Feature tour callbacks
            tour_info = {
                'tour_documents': (
                    "📄 *Document Upload*\n\n"
                    "Simply send any document and get instant AI analysis!\n\n"
                    "📋 *Supported:*\n"
                    "• PDF, DOC, DOCX\n"
                    "• Images (JPG, PNG)\n"
                    "• Text files\n\n"
                    "⚡ *Pro tip:* Premium users get unlimited uploads!"
                ),
                'tour_ai': (
                    "🧠 *AI Analysis*\n\n"
                    "Our AI understands your documents:\n\n"
                    "🔍 *Extracts:* Key points, summaries, entities\n"
                    "📊 *Analyzes:* Structure, sentiment, insights\n"
                    "💡 *Suggests:* Actions, improvements, next steps\n\n"
                    "🎯 *Try it:* Upload a document now!"
                ),
                'tour_premium': (
                    "💎 *Premium Plans*\n\n"
                    "Unlock unlimited power:\n\n"
                    f"⚡ *Weekly:* {hcode('₦1,000')} - 7 days\n"
                    f"🚀 *Monthly:* {hcode('₦3,500')} - 30 days (save 17%!)\n\n"
                    "✨ *Includes:*\n"
                    "• Unlimited documents\n"
                    "• Advanced AI features\n"
                    "• Priority processing\n"
                    "• Ad-free experience\n\n"
                    f"💳 *Get started:* `/upgrade`"
                ),
                'tour_referrals': (
                    "👥 *Refer & Earn*\n\n"
                    "Invite friends, earn rewards:\n\n"
                    "🎁 *You get:*\n"
                    f"• ₦500 per *monthly* referral\n"
                    f"• ₦150 per *weekly* referral\n\n"
                    "🎁 *They get:*\n"
                    "• 3 free premium days\n\n"
                    "🔗 *Share:* `/refer` to get your link\n"
                    "⏰ *Window:* 60 days from signup"
                ),
                'tour_settings': (
                    "⚙️ *Settings*\n\n"
                    "Personalize your experience anytime:\n\n"
                    "🌐 *Language & Region*\n"
                    "🔔 *Notifications*\n"
                    "🎨 *Theme preferences*\n"
                    "🤖 *AI processing level*\n\n"
                    "🔧 *Access:* `/settings` command\n"
                    "💾 *Saved automatically*"
                )
            }
            
            if data in tour_info:
                tour_text = tour_info[data]
                keyboard = types.InlineKeyboardMarkup()
                back_btn = types.InlineKeyboardButton("⬅️ Back to Tour", callback_data="tour_back")
                done_btn = types.InlineKeyboardButton("✅ Done!", callback_data="tour_complete")
                keyboard.add(back_btn, done_btn)
                
                await callback.message.edit_text(tour_text, parse_mode='Markdown', reply_markup=keyboard)
                await callback.answer()
            elif data == 'tour_back':
                await show_feature_tour(callback.message, state)
                await callback.answer()
            elif data == 'tour_complete':
                preferences = await get_user_preferences(user_id)
                await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.COMPLETE.value, preferences)
                await handle_onboarding_step(callback.message, state, OnboardingStep.COMPLETE.value)
                await callback.answer("Tour complete! 🎉")
            elif data == 'tour_skip':
                preferences = await get_user_preferences(user_id)
                await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.COMPLETE.value, preferences)
                await handle_onboarding_step(callback.message, state, OnboardingStep.COMPLETE.value)
                await callback.answer("Skipped tour - you're all set!")
                
        elif data.startswith('quick_'):
            # Quick action callbacks
            if data == 'quick_upgrade':
                # Trigger upgrade flow
                from premium import purchase_premium_handler
                upgrade_msg = types.Message(
                    message_id=callback.message.message_id,
                    from_user=callback.from_user,
                    date=datetime.now(),
                    chat=callback.message.chat,
                    text="/upgrade"
                )
                await purchase_premium_handler(upgrade_msg, state)
                await callback.answer("Starting upgrade...")
                
            elif data == 'quick_help':
                from help import help_command_handler
                help_msg = types.Message(
                    message_id=callback.message.message_id,
                    from_user=callback.from_user,
                    date=datetime.now(),
                    chat=callback.message.chat,
                    text="/help"
                )
                await help_command_handler(help_msg)
                await callback.answer("Showing help...")
                
            elif data == 'quick_refer':
                from referrals import refer_command_handler
                refer_msg = types.Message(
                    message_id=callback.message.message_id,
                    from_user=callback.from_user,
                    date=datetime.now(),
                    chat=callback.message.chat,
                    text="/refer"
                )
                await refer_command_handler(refer_msg, state)
                await callback.answer("Get your referral link...")
                
            elif data == 'quick_stats':
                # Show user stats
                preferences = await get_user_preferences(user_id)
                premium_data = await get_premium_data(user_id)
                
                stats_text = f"📊 *Your Stats*\n\n"
                stats_text += f"👤 *Account:* {preferences.get('first_name', 'User')} #{user_id}\n"
                
                if premium_data['status'] == PremiumStatus.ACTIVE:
                    expiry = datetime.fromisoformat(premium_data['expiry'])
                    days_left = max(0, (expiry - datetime.utcnow()).days)
                    stats_text += f"🎖 *Premium:* Active ({days_left} days left)\n"
                else:
                    stats_text += f"💎 *Premium:* Free tier\n"
                
                stats_text += f"🌐 *Language:* {SUPPORTED_LANGUAGES[preferences['language']]['name']}\n"
                stats_text += f"🔔 *Notifications:* {'On' if preferences['notifications'] else 'Off'}\n"
                
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                upgrade_btn = types.InlineKeyboardButton("💎 Upgrade", callback_data="quick_upgrade")
                settings_btn = types.InlineKeyboardButton("⚙️ Settings", callback_data="quick_settings")
                keyboard.add(upgrade_btn, settings_btn)
                
                await callback.message.edit_text(stats_text, parse_mode='Markdown', reply_markup=keyboard)
                await callback.answer()
                
            elif data == 'quick_upload':
                await callback.message.edit_text(
                    "📄 *Upload Document*\n\n"
                    "Simply send any document file and I'll analyze it instantly!\n\n"
                    "📋 *Supported formats:*\n"
                    "• PDF files\n"
                    "• Word documents (.doc, .docx)\n"
                    "• Images (.jpg, .png)\n"
                    "• Text files (.txt)\n\n"
                    "⚡ *Pro tip:* Premium users get unlimited uploads and advanced analysis!",
                    parse_mode='Markdown'
                )
                await callback.answer("Upload ready!")
                
        elif data == 'welcome_continue':
            # Continue from welcome screen
            await show_language_selection(callback.message, state)
            await onboarding_manager.update_onboarding_step(user_id, OnboardingStep.LANGUAGE.value)
            await callback.answer("Starting setup...")
            
        elif data in ['start_try_document', 'start_upgrade', 'start_help']:
            # Completion quick actions
            if data == 'start_try_document':
                await callback.message.edit_text(
                    "📄 *Ready to try?*\n\n"
                    "Just send me any document and I'll show you the magic!\n\n"
                    "💡 *No document handy?* Try `/help` or `/premium` to explore more.",
                    parse_mode='Markdown'
                )
            elif data == 'start_upgrade':
                from premium import purchase_premium_handler
                upgrade_msg = types.Message(
                    message_id=callback.message.message_id,
                    from_user=callback.from_user,
                    date=datetime.now(),
                    chat=callback.message.chat,
                    text="/upgrade"
                )
                await purchase_premium_handler(upgrade_msg, state)
            elif data == 'start_help':
                from help import help_command_handler
                help_msg = types.Message(
                    message_id=callback.message.message_id,
                    from_user=callback.from_user,
                    date=datetime.now(),
                    chat=callback.message.chat,
                    text="/help"
                )
                await help_command_handler(help_msg)
            
            await callback.answer()
            
    except Exception as e:
        logger.error("Onboarding callback handler error", exc_info=True, extra={
            'user_id': user_id,
            'callback_data': data,
            'error': str(e)
        })
        await callback.answer("Something went wrong. Use /start to try again.")

def register_start_handlers(dp: Dispatcher) -> None:
    """Register all start-related handlers."""
    # Main start command - aiogram 3.x syntax
    dp.message.register(start_command_handler, Command("start"))
    
    # Onboarding callbacks (extend existing callback handler)
    from handlers.callbacks import process_callback_query
    original_process = process_callback_query
    
    async def enhanced_callback_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
        """Enhanced callback handler that includes onboarding."""
        # Check if it's an onboarding callback
        if (callback.data and 
            (callback.data.startswith(('lang_', 'pref_', 'tour_', 'quick_', 'welcome_', 'start_')) or
             callback.data in ['onboarding_complete', 'tour_complete', 'tour_skip'])):

            await handle_onboarding_callbacks(callback, state)
            return
        
        # Otherwise, pass to original handler
        await original_process(callback, state)
    
    # Monkey patch the callback handler
    import handlers.callbacks as callbacks
    callbacks.process_callback_query = enhanced_callback_handler
    
    logger.info("Start handlers registered with onboarding integration")

__all__ = [
    'start_command_handler', 'register_start_handlers',
    'onboarding_manager', 'UserOnboarding',
    'is_new_user', 'get_user_preferences',
    'SUPPORTED_LANGUAGES', 'DEFAULT_PREFERENCES'
]
