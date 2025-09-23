# referrals.py (Updated with Enhanced Reward Logic)
import logging
import secrets
import string
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import bold as hbold, code as hcode
from dotenv import load_dotenv

# Assuming Redis for referral storage (fallback to in-memory)
try:
    import redis
    import json
    redis_client = redis.Redis(host='localhost', port=6379, db=3, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict
    referral_store = defaultdict(dict)
    referral_usage = defaultdict(int)
    referral_rewards = defaultdict(list)
    REDIS_AVAILABLE = False

# Import from premium for reward validation
from premium import PremiumPlan, PremiumStatus, get_premium_data, activate_premium  # type: ignore
from payments import Transaction, PaymentStatus  # type: ignore

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - referrer_id=%(referrer_id)s - referral_code=%(referral_code)s - reward_amount=%(reward_amount)s - plan=%(plan)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ReferralRewardType(Enum):
    """Types of referral rewards."""
    PREMIUM_DAYS = "premium_days"  # Free premium days for new user
    CURRENCY = "currency"  # Naira credit for referrer

# Enhanced referral configuration
REFERRAL_CONFIG = {
    'code_length': 8,
    'max_codes_per_user': 1,
    'reward_new_referral': {
        'type': ReferralRewardType.PREMIUM_DAYS,
        'value': 3  # 3 free premium days for new referral
    },
    'reward_referrer_monthly': {
        'type': ReferralRewardType.CURRENCY,
        'value': 500  # ₦500 for monthly plan referral
    },
    'reward_referrer_weekly': {
        'type': ReferralRewardType.CURRENCY,
        'value': 150   # ₦150 for weekly plan referral
    },
    'reward_window_days': 60,  # 2 months window for premium subscription reward
    'code_expiry_days': 90,
    'max_referrals_per_code': 50,  # Increased for better tracking
    'min_user_level_for_referral': 'user'
}

def generate_unique_code(length: int = None) -> str:
    """Generate unique alphanumeric referral code."""
    length = length or REFERRAL_CONFIG['code_length']
    chars = string.ascii_uppercase + string.digits
    code = ''.join(secrets.choice(chars) for _ in range(length))
    
    # Ensure uniqueness (check against existing codes)
    while await code_exists(code):
        code = ''.join(secrets.choice(chars) for _ in range(length))
    
    return code

async def code_exists(code: str) -> bool:
    """Check if referral code already exists."""
    try:
        if REDIS_AVAILABLE:
            return redis_client.exists(f"referral:code:{code}")
        else:
            return any(key.startswith(f"referral:code:{code}") for key in referral_store.keys())
    except Exception:
        return False

async def create_referral_code(user_id: int, user_role: str = 'user') -> Optional[str]:
    """Create new referral code for user with validation."""
    try:
        # Validate user eligibility
        if user_role not in ['user', 'support', 'moderator', 'superadmin']:
            logger.warning("User ineligible for referral creation", extra={
                'user_id': user_id,
                'role': user_role
            })
            return None
        
        # Check if user already has a code
        existing_code = await get_user_referral_code(user_id)
        if existing_code:
            logger.info("User already has referral code", extra={
                'user_id': user_id,
                'existing_code': existing_code
            })
            return existing_code
        
        # Generate new code
        code = generate_unique_code()
        now = datetime.utcnow()
        expiry = now + timedelta(days=REFERRAL_CONFIG['code_expiry_days'])
        
        referral_data = {
            'code': code,
            'referrer_id': user_id,
            'created_at': now.isoformat(),
            'expires_at': expiry.isoformat(),
            'usage_count': 0,
            'premium_conversions': 0,  # Track premium subscribers
            'max_uses': REFERRAL_CONFIG['max_referrals_per_code'],
            'status': 'active',
            'reward_window_end': (now + timedelta(days=REFERRAL_CONFIG['reward_window_days'])).isoformat()
        }
        
        # Store referral code
        code_key = f"referral:code:{code}"
        user_key = f"referral:user:{user_id}"
        
        if REDIS_AVAILABLE:
            redis_client.setex(code_key, REFERRAL_CONFIG['code_expiry_days'] * 86400, json.dumps(referral_data))
            redis_client.setex(user_key, REFERRAL_CONFIG['code_expiry_days'] * 86400, code)
        else:
            referral_store[code_key] = referral_data
            referral_store[user_key] = code
        
        logger.info("Referral code created", extra={
            'user_id': user_id,
            'code': code,
            'reward_window_days': REFERRAL_CONFIG['reward_window_days'],
            'code_expiry_days': REFERRAL_CONFIG['code_expiry_days']
        })
        
        return code
        
    except Exception as e:
        logger.error("Failed to create referral code", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return None

async def get_user_referral_code(user_id: int) -> Optional[str]:
    """Get user's existing referral code."""
    try:
        user_key = f"referral:user:{user_id}"
        
        if REDIS_AVAILABLE:
            code = redis_client.get(user_key)
            if code:
                return code
        else:
            if user_key in referral_store:
                return referral_store[user_key]
        
        return None
        
    except Exception as e:
        logger.error("Failed to get user referral code", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return None

async def validate_referral_code(code: str) -> Dict[str, Any]:
    """Validate referral code and return referral data."""
    try:
        # Basic validation
        if not code or len(code) != REFERRAL_CONFIG['code_length']:
            return {'valid': False, 'error': 'Invalid code format'}
        
        code_key = f"referral:code:{code}"
        
        if REDIS_AVAILABLE:
            data = redis_client.get(code_key)
            if not data:
                return {'valid': False, 'error': 'Code not found'}
            referral_data = json.loads(data)
        else:
            if code_key not in referral_store:
                return {'valid': False, 'error': 'Code not found'}
            referral_data = referral_store[code_key]
        
        # Check expiry
        expiry = datetime.fromisoformat(referral_data['expires_at'])
        if datetime.utcnow() > expiry:
            referral_data['status'] = 'expired'
            if REDIS_AVAILABLE:
                redis_client.delete(code_key)
            else:
                del referral_store[code_key]
            return {'valid': False, 'error': 'Code expired'}
        
        # Check if reward window is still open
        reward_window_end = datetime.fromisoformat(referral_data['reward_window_end'])
        if datetime.utcnow() > reward_window_end:
            referral_data['status'] = 'reward_window_closed'
            return {'valid': False, 'error': 'Referral reward period has ended (2 months)'}
        
        # Check usage limit
        if referral_data['usage_count'] >= referral_data['max_uses']:
            referral_data['status'] = 'max_uses_reached'
            if REDIS_AVAILABLE:
                redis_client.delete(code_key)
            else:
                del referral_store[code_key]
            return {'valid': False, 'error': 'Code usage limit reached'}
        
        return {
            'valid': True,
            'referrer_id': referral_data['referrer_id'],
            'code': code,
            'usage_count': referral_data['usage_count'],
            'premium_conversions': referral_data.get('premium_conversions', 0),
            'max_uses': referral_data['max_uses'],
            'expires_at': referral_data['expires_at'],
            'reward_window_end': referral_data['reward_window_end']
        }
        
    except Exception as e:
        logger.error("Failed to validate referral code", exc_info=True, extra={
            'code': code,
            'error': str(e)
        })
        return {'valid': False, 'error': 'Validation error'}

async def process_referral(user_id: int, code: str, user_role: str = 'new_user') -> Dict[str, Any]:
    """Process referral and assign initial rewards (new user bonus)."""
    try:
        # Validate code
        validation = await validate_referral_code(code)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error'],
                'referrer_id': None,
                'new_user_reward': None,
                'referrer_reward': None
            }
        
        referrer_id = validation['referrer_id']
        
        # Prevent self-referral
        if referrer_id == user_id:
            return {
                'success': False,
                'error': 'Cannot use your own referral code',
                'referrer_id': referrer_id
            }
        
        # Check if user already used a referral
        if await user_has_used_referral(user_id):
            return {
                'success': False,
                'error': 'You have already used a referral code',
                'referrer_id': referrer_id
            }
        
        # Mark user as referred and store referral relationship
        await mark_user_as_referred(user_id, referrer_id, code)
        
        # Assign initial new user reward (3 free premium days)
        new_user_reward = await assign_new_user_reward(user_id, validation)
        
        # Update usage count (only for tracking, not reward)
        await increment_code_usage(code)
        
        logger.info("Initial referral processed successfully", extra={
            'user_id': user_id,
            'referrer_id': referrer_id,
            'code': code,
            'new_user_reward': new_user_reward
        })
        
        return {
            'success': True,
            'referrer_id': referrer_id,
            'code': code,
            'new_user_reward': new_user_reward,
            'referrer_reward': None  # Premium conversion rewards handled separately
        }
        
    except Exception as e:
        logger.error("Referral processing failed", exc_info=True, extra={
            'user_id': user_id,
            'code': code,
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Processing error',
            'referrer_id': None
        }

async def process_premium_conversion_reward(user_id: int, transaction: Transaction, plan: PremiumPlan) -> Dict[str, Any]:
    """
    Process referral reward when referred user makes first premium purchase.
    This is called from premium.py after successful activation.
    """
    try:
        # Check if user was referred
        referral_info = await get_user_referral_info(user_id)
        if not referral_info:
            return {
                'success': False,
                'error': 'User not referred by anyone',
                'referrer_id': None,
                'reward_amount': 0
            }
        
        referrer_id = referral_info['referrer_id']
        code = referral_info['code']
        referred_at = datetime.fromisoformat(referral_info['referred_at'])
        
        # Check if within 2-month reward window
        reward_window_end = referred_at + timedelta(days=REFERRAL_CONFIG['reward_window_days'])
        if datetime.utcnow() > reward_window_end:
            logger.info("Referral reward window expired", extra={
                'user_id': user_id,
                'referrer_id': referrer_id,
                'code': code,
                'days_since_referral': (datetime.utcnow() - referred_at).days
            })
            return {
                'success': False,
                'error': 'Referral reward period expired (2 months)',
                'referrer_id': referrer_id,
                'reward_amount': 0
            }
        
        # Check if user already converted to premium via this referral
        if await user_has_converted_via_referral(user_id, referrer_id):
            logger.info("User already converted via this referral", extra={
                'user_id': user_id,
                'referrer_id': referrer_id,
                'code': code
            })
            return {
                'success': False,
                'error': 'Already rewarded for this user',
                'referrer_id': referrer_id,
                'reward_amount': 0
            }
        
        # Validate transaction
        if transaction.status != PaymentStatus.SUCCESS:
            return {
                'success': False,
                'error': 'Transaction not successful',
                'referrer_id': referrer_id,
                'reward_amount': 0
            }
        
        # Determine reward amount based on plan
        if plan == PremiumPlan.MONTHLY:
            reward_amount = REFERRAL_CONFIG['reward_referrer_monthly']['value']  # ₦500
        elif plan == PremiumPlan.WEEKLY:
            reward_amount = REFERRAL_CONFIG['reward_referrer_weekly']['value']   # ₦150
        else:
            return {
                'success': False,
                'error': 'Unsupported plan type',
                'referrer_id': referrer_id,
                'reward_amount': 0
            }
        
        # Assign reward to referrer
        reward_result = await assign_referrer_conversion_reward(referrer_id, user_id, reward_amount, plan)
        
        if reward_result['success']:
            # Mark as converted
            await mark_user_as_converted(user_id, referrer_id, transaction.transaction_id, plan)
            
            # Update referral code stats
            await increment_premium_conversion(code)
            
            logger.info("Premium conversion reward processed", extra={
                'user_id': user_id,
                'referrer_id': referrer_id,
                'code': code,
                'plan': plan.value['id'],
                'reward_amount': reward_amount,
                'transaction_id': transaction.transaction_id
            })
            
            return {
                'success': True,
                'referrer_id': referrer_id,
                'code': code,
                'plan': plan.value['id'],
                'reward_amount': reward_amount,
                'reward_result': reward_result
            }
        else:
            return {
                'success': False,
                'error': 'Failed to assign reward',
                'referrer_id': referrer_id,
                'reward_amount': reward_amount
            }
            
    except Exception as e:
        logger.error("Premium conversion reward processing failed", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Processing error',
            'referrer_id': None,
            'reward_amount': 0
        }

async def get_user_referral_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Get referral information for a user."""
    try:
        user_key = f"user:referral_used:{user_id}"
        
        if REDIS_AVAILABLE:
            data = redis_client.get(user_key)
            if data:
                return json.loads(data)
        else:
            if user_key in referral_usage:
                return referral_usage[user_key]
        
        return None
        
    except Exception as e:
        logger.error("Failed to get user referral info", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return None

async def user_has_used_referral(user_id: int) -> bool:
    """Check if user has already used a referral."""
    try:
        user_key = f"user:referral_used:{user_id}"
        
        if REDIS_AVAILABLE:
            return bool(redis_client.exists(user_key))
        else:
            return bool(referral_usage.get(user_key))
            
    except Exception as e:
        logger.error("Failed to check referral usage", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return False

async def user_has_converted_via_referral(user_id: int, referrer_id: int) -> bool:
    """Check if user has already converted to premium via specific referral."""
    try:
        conversion_key = f"user:conversion:{user_id}:{referrer_id}"
        
        if REDIS_AVAILABLE:
            return bool(redis_client.exists(conversion_key))
        else:
            return bool(referral_rewards.get(conversion_key))
            
    except Exception as e:
        logger.error("Failed to check conversion status", exc_info=True, extra={
            'user_id': user_id,
            'referrer_id': referrer_id,
            'error': str(e)
        })
        return False

async def mark_user_as_referred(user_id: int, referrer_id: int, code: str) -> None:
    """Mark user as having used a referral."""
    try:
        user_key = f"user:referral_used:{user_id}"
        referral_record = {
            'user_id': user_id,
            'referrer_id': referrer_id,
            'code': code,
            'referred_at': datetime.utcnow().isoformat(),
            'has_converted': False,
            'conversion_date': None
        }
        
        if REDIS_AVAILABLE:
            redis_client.setex(user_key, 365 * 86400, json.dumps(referral_record))  # 1 year
        else:
            referral_usage[user_key] = referral_record
            
    except Exception as e:
        logger.error("Failed to mark user as referred", exc_info=True, extra={
            'user_id': user_id,
            'referrer_id': referrer_id,
            'error': str(e)
        })

async def mark_user_as_converted(user_id: int, referrer_id: int, transaction_id: str, plan: PremiumPlan) -> None:
    """Mark user as having converted to premium via referral."""
    try:
        conversion_key = f"user:conversion:{user_id}:{referrer_id}"
        user_referral_key = f"user:referral_used:{user_id}"
        
        conversion_record = {
            'user_id': user_id,
            'referrer_id': referrer_id,
            'transaction_id': transaction_id,
            'plan': plan.value['id'],
            'conversion_date': datetime.utcnow().isoformat(),
            'reward_amount': REFERRAL_CONFIG['reward_referrer_monthly']['value'] if plan == PremiumPlan.MONTHLY else REFERRAL_CONFIG['reward_referrer_weekly']['value']
        }
        
        if REDIS_AVAILABLE:
            # Mark as converted
            redis_client.setex(conversion_key, 365 * 86400, json.dumps(conversion_record))
            
            # Update referral record
            pipe = redis_client.pipeline()
            pipe.multi()
            pipe.hset(user_referral_key, 'has_converted', 'true')
            pipe.hset(user_referral_key, 'conversion_date', datetime.utcnow().isoformat())
            pipe.hset(user_referral_key, 'conversion_plan', plan.value['id'])
            pipe.hset(user_referral_key, 'conversion_transaction', transaction_id)
            pipe.execute()
        else:
            referral_usage[conversion_key] = conversion_record
            if user_referral_key in referral_usage:
                referral_usage[user_referral_key].update({
                    'has_converted': True,
                    'conversion_date': datetime.utcnow().isoformat(),
                    'conversion_plan': plan.value['id'],
                    'conversion_transaction': transaction_id
                })
            
    except Exception as e:
        logger.error("Failed to mark user as converted", exc_info=True, extra={
            'user_id': user_id,
            'referrer_id': referrer_id,
            'error': str(e)
        })

async def increment_code_usage(code: str) -> None:
    """Increment referral code usage count."""
    try:
        code_key = f"referral:code:{code}"
        
        if REDIS_AVAILABLE:
            pipe = redis_client.pipeline()
            pipe.multi()
            pipe.hincrby(code_key, 'usage_count', 1)
            pipe.execute()
        else:
            if code_key in referral_store:
                referral_store[code_key]['usage_count'] += 1
                
    except Exception as e:
        logger.error("Failed to increment code usage", exc_info=True, extra={
            'code': code,
            'error': str(e)
        })

async def increment_premium_conversion(code: str) -> None:
    """Increment premium conversion count for referral code."""
    try:
        code_key = f"referral:code:{code}"
        
        if REDIS_AVAILABLE:
            pipe = redis_client.pipeline()
            pipe.multi()
            pipe.hincrby(code_key, 'premium_conversions', 1)
            pipe.execute()
        else:
            if code_key in referral_store:
                referral_store[code_key]['premium_conversions'] = referral_store[code_key].get('premium_conversions', 0) + 1
                
    except Exception as e:
        logger.error("Failed to increment premium conversion", exc_info=True, extra={
            'code': code,
            'error': str(e)
        })

async def assign_new_user_reward(user_id: int, validation: Dict[str, Any]) -> Dict[str, Any]:
    """Assign initial reward to new referral user (3 free premium days)."""
    try:
        reward_config = REFERRAL_CONFIG['reward_new_referral']
        reward_type = reward_config['type']
        reward_value = reward_config['value']
        
        if reward_type == ReferralRewardType.PREMIUM_DAYS:
            # Create mock transaction for reward
            mock_transaction = Transaction(
                transaction_id=f"reward_{user_id}_{int(time.time())}",
                user_id=user_id,
                amount=0.0,  # Free reward
                currency="NGN",
                gateway="referral_reward",
                status=PaymentStatus.SUCCESS,
                metadata={
                    'reward_type': 'referral_signup',
                    'referral_code': validation['code'],
                    'referrer_id': validation['referrer_id']
                },
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Grant 3 days of weekly premium equivalent
            success = await activate_premium(user_id, mock_transaction, PremiumPlan.WEEKLY)
            
            if success:
                premium_data = await get_premium_data(user_id)
                expiry = datetime.fromisoformat(premium_data['expiry'])
                actual_days = max(0, (expiry - datetime.utcnow()).days)
                
                return {
                    'type': 'premium_days',
                    'value': min(actual_days, reward_value),
                    'description': f"{reward_value} free premium days activated",
                    'success': success,
                    'referral_bonus': True
                }
            else:
                return {
                    'type': 'premium_days',
                    'value': 0,
                    'description': 'Failed to activate free premium days',
                    'success': False,
                    'referral_bonus': True
                }
                
        return {
            'type': reward_type,
            'value': reward_value,
            'success': False,
            'description': 'Unsupported reward type',
            'referral_bonus': True
        }
        
    except Exception as e:
        logger.error("Failed to assign new user reward", exc_info=True, extra={
            'user_id': user_id,
            'reward_type': reward_config['type'],
            'error': str(e)
        })
        return {
            'type': reward_config['type'],
            'value': 0,
            'success': False,
            'description': 'Reward assignment failed',
            'referral_bonus': True
        }

async def assign_referrer_conversion_reward(referrer_id: int, new_user_id: int, reward_amount: float, plan: PremiumPlan) -> Dict[str, Any]:
    """Assign conversion reward to referrer when referred user subscribes to premium."""
    try:
        # Add currency reward to referrer
        success = await add_user_currency_credit(referrer_id, reward_amount, f"premium_conversion_{plan.value['id']}")
        
        plan_name = plan.value['name']
        reward_description = f"₦{reward_amount} earned for {plan_name.lower()} subscription"
        
        return {
            'type': 'currency',
            'value': reward_amount,
            'currency': 'NGN',
            'description': reward_description,
            'new_user_id': new_user_id,
            'plan': plan.value['id'],
            'success': success
        }
        
    except Exception as e:
        logger.error("Failed to assign referrer conversion reward", exc_info=True, extra={
            'referrer_id': referrer_id,
            'new_user_id': new_user_id,
            'reward_amount': reward_amount,
            'plan': plan.value['id'],
            'error': str(e)
        })
        return {
            'type': 'currency',
            'value': reward_amount,
            'success': False,
            'description': 'Reward assignment failed',
            'new_user_id': new_user_id,
            'plan': plan.value['id']
        }

async def add_user_currency_credit(user_id: int, amount: float, source: str = "referral_reward") -> bool:
    """Add currency credit to user with source tracking."""
    try:
        credit_key = f"user:credit:{user_id}"
        timestamp = datetime.utcnow().isoformat()
        
        credit_record = {
            'user_id': user_id,
            'amount': amount,
            'currency': 'NGN',
            'source': source,
            'credited_at': timestamp,
            'status': 'active'
        }
        
        if REDIS_AVAILABLE:
            # Use transaction for atomicity
            pipe = redis_client.pipeline()
            pipe.multi()
            pipe.hincrbyfloat(credit_key, 'balance', amount)
            pipe.lpush(f"credit_history:{user_id}", json.dumps(credit_record))
            pipe.ltrim(f"credit_history:{user_id}", 0, 99)  # Keep last 100
            pipe.execute()
            
            # Log the transaction
            logger.info("Currency credit added", extra={
                'user_id': user_id,
                'amount': amount,
                'source': source,
                'new_balance': await get_user_credit_balance(user_id)
            })
            
            return True
        else:
            # In-memory tracking
            if credit_key not in referral_store:
                referral_store[credit_key] = {'balance': 0.0}
            referral_store[credit_key]['balance'] += amount
            
            logger.info("Currency credit added (in-memory)", extra={
                'user_id': user_id,
                'amount': amount,
                'source': source,
                'new_balance': referral_store[credit_key]['balance']
            })
            
            return True
            
    except Exception as e:
        logger.error("Failed to add currency credit", exc_info=True, extra={
            'user_id': user_id,
            'amount': amount,
            'source': source,
            'error': str(e)
        })
        return False

async def get_user_credit_balance(user_id: int) -> float:
    """Get user's current credit balance."""
    try:
        credit_key = f"user:credit:{user_id}"
        
        if REDIS_AVAILABLE:
            balance = redis_client.hget(credit_key, 'balance')
            return float(balance) if balance else 0.0
        else:
            credit_data = referral_store.get(credit_key, {'balance': 0.0})
            return float(credit_data['balance'])
            
    except Exception as e:
        logger.error("Failed to get credit balance", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return 0.0

async def get_referral_stats(user_id: int) -> Dict[str, Any]:
    """Get comprehensive referral statistics for user."""
    try:
        code = await get_user_referral_code(user_id)
        if not code:
            return {
                'code': None,
                'usage_count': 0,
                'premium_conversions': 0,
                'total_monthly_rewards': 0,
                'total_weekly_rewards': 0,
                'total_rewarded': 0.0,
                'successful_referrals': 0,
                'conversion_rate': 0.0
            }
        
        code_key = f"referral:code:{code}"
        
        if REDIS_AVAILABLE:
            data = redis_client.get(code_key)
            if not data:
                return {
                    'code': code,
                    'usage_count': 0,
                    'premium_conversions': 0,
                    'total_monthly_rewards': 0,
                    'total_weekly_rewards': 0,
                    'total_rewarded': 0.0,
                    'successful_referrals': 0,
                    'conversion_rate': 0.0
                }
            referral_data = json.loads(data)
            usage_count = referral_data.get('usage_count', 0)
            premium_conversions = referral_data.get('premium_conversions', 0)
        else:
            if code_key not in referral_store:
                return {
                    'code': code,
                    'usage_count': 0,
                    'premium_conversions': 0,
                    'total_monthly_rewards': 0,
                    'total_weekly_rewards': 0,
                    'total_rewarded': 0.0,
                    'successful_referrals': 0,
                    'conversion_rate': 0.0
                }
            referral_data = referral_store[code_key]
            usage_count = referral_data.get('usage_count', 0)
            premium_conversions = referral_data.get('premium_conversions', 0)
        
        # Calculate rewards
        monthly_rewards = premium_conversions * REFERRAL_CONFIG['reward_referrer_monthly']['value']  # Assuming all monthly for simplicity
        weekly_rewards = 0  # Track separately in production
        total_rewarded = monthly_rewards + weekly_rewards
        
        conversion_rate = (premium_conversions / usage_count * 100) if usage_count > 0 else 0
        
        return {
            'code': code,
            'usage_count': usage_count,
            'premium_conversions': premium_conversions,
            'total_monthly_rewards': monthly_rewards,
            'total_weekly_rewards': weekly_rewards,
            'total_rewarded': total_rewarded,
            'successful_referrals': premium_conversions,
            'conversion_rate': round(conversion_rate, 1),
            'max_uses': referral_data.get('max_uses', REFERRAL_CONFIG['max_referrals_per_code']),
            'expires_at': referral_data.get('expires_at'),
            'reward_window_end': referral_data.get('reward_window_end')
        }
        
    except Exception as e:
        logger.error("Failed to get referral stats", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return {
            'code': None,
            'usage_count': 0,
            'premium_conversions': 0,
            'total_monthly_rewards': 0,
            'total_weekly_rewards': 0,
            'total_rewarded': 0.0,
            'successful_referrals': 0,
            'conversion_rate': 0.0
        }

async def cleanup_expired_referrals() -> int:
    """Clean up expired referral codes and closed reward windows."""
    try:
        now = datetime.utcnow()
        expired_count = 0
        window_closed_count = 0
        
        if REDIS_AVAILABLE:
            pattern = "referral:code:*"
            keys = redis_client.keys(pattern)
            
            for key in keys:
                data = redis_client.get(key)
                if data:
                    referral_data = json.loads(data)
                    
                    # Check code expiry
                    code_expiry = datetime.fromisoformat(referral_data['expires_at'])
                    if now > code_expiry:
                        # Also remove user mapping
                        user_key = f"referral:user:{referral_data['referrer_id']}"
                        redis_client.delete(key, user_key)
                        expired_count += 1
                        continue
                    
                    # Check reward window closure (keep code active but mark window closed)
                    window_end = datetime.fromisoformat(referral_data['reward_window_end'])
                    if now > window_end:
                        pipe = redis_client.pipeline()
                        pipe.multi()
                        pipe.hset(key, 'status', 'reward_window_closed')
                        pipe.hset(key, 'reward_window_end', referral_data['reward_window_end'])
                        pipe.execute()
                        window_closed_count += 1
        else:
            # In-memory cleanup
            expired_keys = []
            window_closed_keys = []
            
            for key, data in list(referral_store.items()):
                if key.startswith('referral:code:') and isinstance(data, dict):
                    code_expiry = datetime.fromisoformat(data['expires_at'])
                    window_end = datetime.fromisoformat(data['reward_window_end'])
                    
                    if now > code_expiry:
                        expired_keys.append(key)
                        # Remove user mapping
                        user_key = f"referral:user:{data['referrer_id']}"
                        if user_key in referral_store:
                            del referral_store[user_key]
                    elif now > window_end:
                        data['status'] = 'reward_window_closed'
                        window_closed_keys.append(key)
            
            for key in expired_keys:
                del referral_store[key]
                expired_count += 1
            
            window_closed_count = len(window_closed_keys)
        
        logger.info("Referral cleanup completed", extra={
            'expired_codes': expired_count,
            'window_closed': window_closed_count
        })
        
        return expired_count + window_closed_count
        
    except Exception as e:
        logger.error("Failed to cleanup expired referrals", exc_info=True, extra={
            'error': str(e)
        })
        return 0

async def refer_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /refer command to generate/share referral code."""
    user_id = message.from_user.id
    
    try:
        # Get user role (from db.py)
        from db import get_user_role  # type: ignore
        user_role = get_user_role(user_id)
        
        # Create or retrieve referral code
        code = await create_referral_code(user_id, user_role)
        if not code:
            await message.reply(
                "❌ *Referral Error*\n\n"
                "Unable to generate referral code. Please try again later.",
                parse_mode='Markdown'
            )
            return
        
        # Get comprehensive referral stats
        stats = await get_referral_stats(user_id)
        
        # Generate referral link
        bot_username = "your_bot_username"  # Replace with actual bot username
        referral_link = f"https://t.me/{bot_username}?start=ref_{code}"
        
        # Format expiry dates
        code_expiry = datetime.fromisoformat(stats['expires_at']) if stats['expires_at'] else None
        window_end = datetime.fromisoformat(stats['reward_window_end']) if stats['reward_window_end'] else None
        
        code_expiry_text = f"Code expires: {code_expiry.strftime('%Y-%m-%d')}" if code_expiry else "No expiry"
        window_text = f"Rewards available until: {window_end.strftime('%Y-%m-%d')}" if window_end else "No reward window"
        
        response = (
            f"🔗 *Your Referral Code:*\n\n"
            f"📝 *Code:* `{code}`\n"
            f"🔗 *Share Link:* {hcode(referral_link)}\n\n"
            f"📊 *Your Stats:*\n"
            f"• Total referrals: {stats['usage_count']}\n"
            f"• Premium conversions: {stats['premium_conversions']}\n"
            f"• Conversion rate: {stats['conversion_rate']}%\n"
            f"• Total earned: {format_currency(stats['total_rewarded'])}\n\n"
            f"⏰ *Timeline:*\n"
            f"• {code_expiry_text}\n"
            f"• {window_text}\n\n"
            f"💎 *Earning Structure:*\n"
            f"• *Monthly referrals:* {format_currency(REFERRAL_CONFIG['reward_referrer_monthly']['value'])} each\n"
            f"• *Weekly referrals:* {format_currency(REFERRAL_CONFIG['reward_referrer_weekly']['value'])} each\n"
            f"• *New users get:* {REFERRAL_CONFIG['reward_new_referral']['value']} free premium days\n\n"
            f"👥 *Share your link above to start earning!*"
        )
        
        await message.reply(response, parse_mode='Markdown', disable_web_page_preview=True)
        
        logger.info("Enhanced referral stats shared", extra={
            'user_id': user_id,
            'code': code,
            'usage_count': stats['usage_count'],
            'premium_conversions': stats['premium_conversions'],
            'total_earned': stats['total_rewarded']
        })
        
    except Exception as e:
        logger.error("Referral command error", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        await message.reply(
            "❌ *Error*\n\n"
            "Failed to generate referral link. Please try again.",
            parse_mode='Markdown'
        )

async def referral_start_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /start ref_XXXXX deep linking for referrals."""
    user_id = message.from_user.id
    
    # Parse referral code from start command
    text = message.text or ""
    if text.startswith('/start ref_'):
        code = text[11:].strip().upper()  # Extract code after 'ref_'
        
        if len(code) != REFERRAL_CONFIG['code_length']:
            await message.reply(
                "❌ *Invalid Referral*\n\n"
                "The referral code format is incorrect.\n"
                "Use `/start` to begin normally or ask your friend for a valid code.",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Process referral
            from db import get_user_role  # type: ignore
            user_role = get_user_role(user_id) or 'new_user'
            
            result = await process_referral(user_id, code, user_role)
            
            if result['success']:
                referrer_id = result['referrer_id']
                
                # Enhanced welcome message
                welcome_msg = (
                    f"🎉 *Welcome to DocuLuna!*\n\n"
                    f"✨ *Thanks for joining via referral!*\n\n"
                    f"🎁 *Your Welcome Rewards:*\n"
                )
                
                if result['new_user_reward']:
                    reward = result['new_user_reward']
                    if reward['type'] == 'premium_days' and reward['success']:
                        welcome_msg += f"• ✅ {reward['description']}\n"
                    else:
                        welcome_msg += f"• ⚠️ {reward['description']}\n"
                
                welcome_msg += f"\n👤 *Referred by:* User {referrer_id}\n"
                welcome_msg += f"💎 *They'll earn* when you upgrade to premium!\n\n"
                welcome_msg += f"🚀 *Quick Start:*\n"
                welcome_msg += f"• `/help` - Explore commands\n"
                welcome_msg += f"• `/premium` - View plans (₦1,000/week or ₦3,500/month)\n"
                welcome_msg += f"• `/upgrade` - Get premium now\n\n"
                welcome_msg += f"💡 *Tip:* Upgrade within 60 days to maximize referral rewards!"
                
                await message.reply(welcome_msg, parse_mode='Markdown')
                
                # Notify referrer with enhanced message
                try:
                    await message.bot.send_message(
                        referrer_id,
                        f"🎉 *New Referral Alert!*\n\n"
                        f"👤 *User {user_id}* joined using your code `{code}`!\n\n"
                        f"💎 *Next Step:* When they upgrade to premium within 60 days:\n"
                        f"• *Monthly plan* → You earn ₦500\n"
                        f"• *Weekly plan* → You earn ₦150\n\n"
                        f"📊 *Your Stats:*\n"
                        f"• Total referrals: {result.get('stats', {}).get('usage_count', 1)}\n"
                        f"• Awaiting conversion: 1\n\n"
                        f"💰 *Check earnings:* `/refer`",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.warning("Failed to notify referrer", exc_info=True, extra={
                        'referrer_id': referrer_id,
                        'new_user_id': user_id,
                        'error': str(e)
                    })
                
            else:
                error_msg = (
                    f"❌ *Referral Issue*\n\n"
                    f"*{result['error']}*\n\n"
                    f"💡 *No worries!* You can still join and upgrade to premium.\n"
                    f"Use `/start` to begin normally."
                )
                await message.reply(error_msg, parse_mode='Markdown')
                
        except Exception as e:
            logger.error("Referral start handler error", exc_info=True, extra={
                'user_id': user_id,
                'code': code,
                'error': str(e)
            })
            await message.reply(
                "❌ *Welcome Error*\n\n"
                "Something went wrong processing your referral.\n"
                "Use `/start` to begin your DocuLuna journey!",
                parse_mode='Markdown'
            )
    else:
        # Regular start command with referral mention
        await message.reply(
            "🎉 *Welcome to DocuLuna!*\n\n"
            "🚀 *AI-powered document processing*\n\n"
            f"✨ *Get started:*\n"
            f"• `/help` - See all commands\n"
            f"• `/premium` - Upgrade (₦1,000/week • ₦3,500/month)\n"
            f"• `/refer` - Earn by inviting friends\n\n"
            f"💎 *Pro Tip:* Join with a friend's referral code for 3 *FREE* premium days!\n"
            f"Or ask someone: `/refer` to get their code.\n\n"
            f"🎯 *Ready?* Try `/upgrade` for premium features!",
            parse_mode='Markdown'
        )

def format_currency(amount: float) -> str:
    """Format Naira amount."""
    return f"₦{amount:,.0f}"

def register_referral_handlers(dp: Dispatcher) -> None:
    """Register all referral handlers."""
    dp.register_message_handler(refer_command_handler, Command("refer"))
    
    # Override start handler to handle referral deep links
    dp.register_message_handler(
        referral_start_handler,
        lambda message: message.text and message.text.startswith('/start'),
        state="*"
    )

# Admin utility commands
async def admin_referral_report(message: types.Message) -> None:
    """Admin command to get comprehensive referral report."""
    user_id = message.from_user.id
    
    # Admin authorization
    from admin import get_user_role  # type: ignore
    role = get_user_role(user_id)
    
    if role not in ['moderator', 'superadmin']:
        await message.reply("❌ Admin privileges required.")
        return
    
    try:
        if REDIS_AVAILABLE:
            # Get all active referral codes
            pattern = "referral:code:*"
            all_codes = redis_client.keys(pattern)
            total_codes = len(all_codes)
            
            # Get stats summary
            total_usage = 0
            total_conversions = 0
            total_rewarded = 0.0
            
            for key in all_codes:
                data = redis_client.get(key)
                if data:
                    referral_data = json.loads(data)
                    total_usage += referral_data.get('usage_count', 0)
                    total_conversions += referral_data.get('premium_conversions', 0)
                    total_rewarded += (referral_data.get('premium_conversions', 0) * 
                                     (REFERRAL_CONFIG['reward_referrer_monthly']['value'] * 0.7 +  # 70% monthly assumption
                                      REFERRAL_CONFIG['reward_referrer_weekly']['value'] * 0.3))  # 30% weekly assumption
            
            avg_conversion_rate = (total_conversions / total_usage * 100) if total_usage > 0 else 0
        else:
            # In-memory stats
            total_codes = sum(1 for key in referral_store.keys() if key.startswith('referral:code:'))
            total_usage = sum(data.get('usage_count', 0) for data in referral_store.values() 
                            if isinstance(data, dict) and 'usage_count' in data)
            total_conversions = sum(data.get('premium_conversions', 0) for data in referral_store.values() 
                                  if isinstance(data, dict) and 'premium_conversions' in data)
            total_rewarded = total_conversions * (REFERRAL_CONFIG['reward_referrer_monthly']['value'] * 0.7 + 
                                                REFERRAL_CONFIG['reward_referrer_weekly']['value'] * 0.3)
            avg_conversion_rate = (total_conversions / total_usage * 100) if total_usage > 0 else 0
        
        report = (
            f"📊 *Referral System Report*\n\n"
            f"🔢 *Active Codes:* {total_codes}\n"
            f"👥 *Total Referrals:* {total_usage}\n"
            f"💎 *Premium Conversions:* {total_conversions}\n"
            f"📈 *Conversion Rate:* {avg_conversion_rate:.1f}%\n"
            f"💰 *Total Rewards Paid:* {format_currency(total_rewarded)}\n\n"
            f"🎯 *Reward Structure:*\n"
            f"• Monthly conversion: {format_currency(REFERRAL_CONFIG['reward_referrer_monthly']['value'])}\n"
            f"• Weekly conversion: {format_currency(REFERRAL_CONFIG['reward_referrer_weekly']['value'])}\n"
            f"• New user bonus: {REFERRAL_CONFIG['reward_new_referral']['value']} premium days\n\n"
            f"⏰ *Time Windows:*\n"
            f"• Reward window: {REFERRAL_CONFIG['reward_window_days']} days\n"
            f"• Code expiry: {REFERRAL_CONFIG['code_expiry_days']} days"
        )
        
        await message.reply(report, parse_mode='Markdown')
        
        logger.info("Admin referral report generated", extra={
            'admin_id': user_id,
            'total_codes': total_codes,
            'total_conversions': total_conversions,
            'total_rewarded': total_rewarded
        })
        
    except Exception as e:
        logger.error("Admin referral report failed", exc_info=True, extra={
            'admin_id': user_id,
            'error': str(e)
        })
        await message.reply("❌ Failed to generate report. Please try again.")

def register_admin_referral_handlers(dp: Dispatcher) -> None:
    """Register admin referral management handlers."""
    from admin import admin_only
    dp.register_message_handler(
        admin_referral_report,
        admin_only(min_role='moderator'),
        commands=['referral_report']
    )
    
    # Keep cleanup command
    dp.register_message_handler(
        lambda m: admin_cleanup_referrals(m),
        admin_only(min_role='moderator'),
        commands=['cleanup_referrals']
    )

# Export functions for integration with premium.py
__all__ = [
    'process_premium_conversion_reward', 'get_user_referral_info',
    'user_has_converted_via_referral', 'register_referral_handlers',
    'register_admin_referral_handlers', 'get_referral_stats',
    'REFERRAL_CONFIG', 'format_currency'
    ]
