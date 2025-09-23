# premium.py (Updated with Naira Pricing)
import logging
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import bold as hbold, code as hcode
from dotenv import load_dotenv

# Assuming Redis for premium storage (fallback to in-memory)
try:
    import redis
    import json
    redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict
    premium_store = defaultdict(dict)
    REDIS_AVAILABLE = False

# Import from db.py for user data
from database.db import get_user_data, update_user_data  # type: ignore

# Import from payments for transaction handling
from handlers.payments import PaymentStatus, payment_orchestrator, Transaction

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s - status=%(status)s - plan=%(plan)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Premium plan configuration
class PremiumPlan(Enum):
    """Premium subscription plans."""
    WEEKLY = {
        'id': 'weekly',
        'name': 'Weekly',
        'duration_days': 7,
        'price_ngn': 1000,
        'description': 'Perfect for short-term access'
    }
    MONTHLY = {
        'id': 'monthly',
        'name': 'Monthly', 
        'duration_days': 30,
        'price_ngn': 3500,
        'description': 'Best value for regular use'
    }

# Calculate plan duration
def get_plan_duration(plan: PremiumPlan) -> timedelta:
    """Get duration for specific plan."""
    return timedelta(days=plan.value['duration_days'])

# Premium status constants
class PremiumStatus:
    """Premium subscription status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    CANCELLED = "cancelled"

# Premium features
PREMIUM_FEATURES = [
    "📄 Unlimited document processing",
    "🧠 Advanced AI analysis", 
    "⚡ Priority support",
    "🎨 Ad-free experience",
    "🔒 Secure cloud storage"
]

def is_premium_active(user_data: Dict[str, Any]) -> bool:
    """Check if user's premium is active."""
    expiry = user_data.get('premium_expiry')
    if not expiry:
        return False
    try:
        expiry_date = datetime.fromisoformat(expiry)
        return datetime.utcnow() < expiry_date
    except ValueError:
        return False

def calculate_expiry_date(start_date: datetime = None, plan: PremiumPlan = PremiumPlan.MONTHLY) -> str:
    """Calculate premium expiry date based on plan."""
    start = start_date or datetime.utcnow()
    duration = get_plan_duration(plan)
    expiry = start + duration
    return expiry.isoformat()

def format_currency(amount: float) -> str:
    """Format Naira amount with proper locale."""
    return f"₦{amount:,.0f}"

def get_premium_status_emoji(status: str) -> str:
    """Get emoji for premium status."""
    status_emojis = {
        PremiumStatus.ACTIVE: "🎖",
        PremiumStatus.EXPIRED: "⏰",
        PremiumStatus.PENDING: "⏳",
        PremiumStatus.CANCELLED: "❌"
    }
    return status_emojis.get(status, "❓")

async def get_premium_data(user_id: int) -> Dict[str, Any]:
    """Retrieve premium data for user."""
    premium_key = f"premium:{user_id}"
    
    try:
        if REDIS_AVAILABLE:
            data = redis_client.get(premium_key)
            if data:
                return json.loads(data)
            else:
                # Fallback to DB
                user_data = get_user_data(user_id)
                premium_data = {
                    'status': user_data.get('premium_status', PremiumStatus.EXPIRED),
                    'expiry': user_data.get('premium_expiry'),
                    'plan': user_data.get('premium_plan', PremiumPlan.MONTHLY.value['id']),
                    'subscription_id': user_data.get('subscription_id'),
                    'created_at': user_data.get('premium_created_at', datetime.utcnow().isoformat()),
                    'last_renewal': user_data.get('last_renewal')
                }
                await store_premium_data(user_id, premium_data)
                return premium_data
        else:
            if premium_key in premium_store:
                return premium_store[premium_key]
            else:
                user_data = get_user_data(user_id)
                premium_data = {
                    'status': user_data.get('premium_status', PremiumStatus.EXPIRED),
                    'expiry': user_data.get('premium_expiry'),
                    'plan': user_data.get('premium_plan', PremiumPlan.MONTHLY.value['id']),
                    'subscription_id': user_data.get('subscription_id'),
                    'created_at': user_data.get('premium_created_at', datetime.utcnow().isoformat()),
                    'last_renewal': user_data.get('last_renewal')
                }
                premium_store[premium_key] = premium_data
                return premium_data
    except Exception as e:
        logger.error("Error retrieving premium data", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        # Return default expired state
        return {'status': PremiumStatus.EXPIRED, 'plan': PremiumPlan.MONTHLY.value['id']}

async def store_premium_data(user_id: int, data: Dict[str, Any]) -> None:
    """Store premium data with validation."""
    try:
        premium_key = f"premium:{user_id}"
        
        # Validate data structure
        required_fields = ['status', 'plan']
        for field in required_fields:
            if field not in data:
                data[field] = PremiumStatus.EXPIRED if field == 'status' else PremiumPlan.MONTHLY.value['id']
        
        if REDIS_AVAILABLE:
            redis_client.setex(premium_key, 86400, json.dumps(data))  # 24h cache
        else:
            premium_store[premium_key] = data
        
        # Sync to persistent storage
        update_user_data(user_id, {
            'premium_status': data['status'],
            'premium_expiry': data.get('expiry'),
            'premium_plan': data['plan'],
            'subscription_id': data.get('subscription_id'),
            'premium_created_at': data.get('created_at'),
            'last_renewal': data.get('last_renewal')
        })
        
        logger.debug("Premium data stored", extra={
            'user_id': user_id,
            'status': data['status'],
            'plan': data['plan']
        })
        
    except Exception as e:
        logger.error("Error storing premium data", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })

async def activate_premium(user_id: int, transaction: Transaction, plan: PremiumPlan = PremiumPlan.MONTHLY) -> bool:
    """Activate premium subscription after successful purchase."""
    try:
        # Validate transaction
        if transaction.status != PaymentStatus.SUCCESS:
            logger.warning("Attempt to activate with failed transaction", extra={
                'user_id': user_id,
                'transaction_id': transaction.transaction_id,
                'status': transaction.status.value
            })
            return False
        
        # Validate amount matches plan
        expected_amount = plan.value['price_ngn']
        if abs(transaction.amount - expected_amount) > 0.01:
            logger.warning("Transaction amount mismatch", extra={
                'user_id': user_id,
                'expected': expected_amount,
                'actual': transaction.amount
            })
            return False
        
        premium_data = await get_premium_data(user_id)
        now = datetime.utcnow()
        
        # Calculate new expiry
        if premium_data['status'] == PremiumStatus.ACTIVE and premium_data.get('expiry'):
            # Extend from current expiry
            start_date = datetime.fromisoformat(premium_data['expiry'])
        else:
            # Start from now
            start_date = now
        
        new_expiry = calculate_expiry_date(start_date, plan)
        
        # Update premium data
        premium_data.update({
            'status': PremiumStatus.ACTIVE,
            'expiry': new_expiry,
            'plan': plan.value['id'],
            'subscription_id': f"sub_{user_id}_{int(time.time())}",
            'activation_date': now.isoformat(),
            'last_transaction': transaction.transaction_id,
            'last_renewal': now.isoformat()
        })
        
        await store_premium_data(user_id, premium_data)
        
        logger.info("Premium activated successfully", extra={
            'user_id': user_id,
            'action': 'activate',
            'plan': plan.value['id'],
            'expiry': new_expiry,
            'transaction_id': transaction.transaction_id,
            'amount': transaction.amount
        })
        
        return True
        
    except Exception as e:
        logger.error("Premium activation failed", exc_info=True, extra={
            'user_id': user_id,
            'action': 'activate',
            'error': str(e)
        })
        return False

async def renew_premium(user_id: int, plan: PremiumPlan = PremiumPlan.MONTHLY) -> bool:
    """Renew existing premium subscription."""
    try:
        premium_data = await get_premium_data(user_id)
        
        if premium_data['status'] != PremiumStatus.ACTIVE:
            logger.warning("Attempt to renew inactive premium", extra={
                'user_id': user_id,
                'current_status': premium_data['status']
            })
            return False
        
        now = datetime.utcnow()
        current_expiry = datetime.fromisoformat(premium_data['expiry'])
        new_expiry = calculate_expiry_date(current_expiry, plan)
        
        premium_data.update({
            'expiry': new_expiry,
            'plan': plan.value['id'],
            'last_renewal': now.isoformat()
        })
        
        await store_premium_data(user_id, premium_data)
        
        logger.info("Premium renewed successfully", extra={
            'user_id': user_id,
            'action': 'renew',
            'plan': plan.value['id'],
            'new_expiry': new_expiry
        })
        
        return True
        
    except Exception as e:
        logger.error("Premium renewal failed", exc_info=True, extra={
            'user_id': user_id,
            'action': 'renew',
            'error': str(e)
        })
        return False

async def check_premium_expiry(user_id: int) -> None:
    """Enforce premium expiry check."""
    try:
        premium_data = await get_premium_data(user_id)
        
        if (premium_data['status'] == PremiumStatus.ACTIVE and 
            premium_data.get('expiry')):
            
            expiry = datetime.fromisoformat(premium_data['expiry'])
            if datetime.utcnow() > expiry:
                old_status = premium_data['status']
                old_expiry = premium_data['expiry']
                
                premium_data.update({
                    'status': PremiumStatus.EXPIRED,
                    'expiry': None,
                    'last_renewal': None
                })
                
                await store_premium_data(user_id, premium_data)
                
                logger.info("Premium subscription expired", extra={
                    'user_id': user_id,
                    'action': 'expire',
                    'previous_status': old_status,
                    'previous_expiry': old_expiry,
                    'plan': premium_data.get('plan', 'unknown')
                })
    except Exception as e:
        logger.error("Error checking premium expiry", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })

async def downgrade_premium(user_id: int) -> bool:
    """Handle premium downgrade/cancellation."""
    try:
        premium_data = await get_premium_data(user_id)
        
        if premium_data['status'] == PremiumStatus.ACTIVE:
            now = datetime.utcnow()
            premium_data.update({
                'status': PremiumStatus.CANCELLED,
                'last_renewal': now.isoformat(),
                'downgrade_date': now.isoformat()
            })
            await store_premium_data(user_id, premium_data)
            
            logger.info("Premium subscription cancelled", extra={
                'user_id': user_id,
                'action': 'downgrade',
                'plan': premium_data.get('plan')
            })
            
            return True
        else:
            logger.info("No active premium to cancel", extra={
                'user_id': user_id,
                'current_status': premium_data['status']
            })
            return False
        
    except Exception as e:
        logger.error("Premium downgrade failed", exc_info=True, extra={
            'user_id': user_id,
            'action': 'downgrade',
            'error': str(e)
        })
        return False

def premium_required(handler: Callable[[types.Message, FSMContext], Awaitable[None]]) -> Callable:
    """Decorator for premium-only features with proper error handling."""
    async def wrapper(message: types.Message, state: FSMContext) -> None:
        user_id = message.from_user.id
        
        try:
            await check_premium_expiry(user_id)
            premium_data = await get_premium_data(user_id)
            
            if premium_data['status'] != PremiumStatus.ACTIVE:
                status_emoji = get_premium_status_emoji(premium_data['status'])
                await message.reply(
                    f"{status_emoji} *Premium Required*\n\n"
                    f"This feature requires an active premium subscription.\n\n"
                    f"💎 *Available Plans:*\n"
                    f"• {hbold('Weekly')} - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week\n"
                    f"• {hbold('Monthly')} - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month\n\n"
                    f"Upgrade with: `/upgrade weekly` or `/upgrade monthly`",
                    parse_mode='Markdown'
                )
                
                logger.warning("Premium access denied", extra={
                    'user_id': user_id,
                    'action': 'access_check',
                    'status': premium_data['status'],
                    'plan': premium_data.get('plan')
                })
                return
            
            # Premium active, execute handler
            await handler(message, state)
            
            logger.info("Premium feature accessed", extra={
                'user_id': user_id,
                'action': 'feature_access',
                'plan': premium_data['plan'],
                'days_remaining': (datetime.fromisoformat(premium_data['expiry']) - datetime.utcnow()).days
            })
            
        except Exception as e:
            logger.error("Premium feature execution error", exc_info=True, extra={
                'user_id': user_id,
                'action': 'feature_execution',
                'error': str(e)
            })
            await message.reply(
                f"❌ *Error*\n\n"
                f"An error occurred while using this premium feature.\n"
                f"Please try again or contact support.",
                parse_mode='Markdown'
            )
    
    return wrapper

async def premium_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /premium command for subscription management."""
    user_id = message.from_user.id
    
    try:
        await check_premium_expiry(user_id)
        premium_data = await get_premium_data(user_id)
        
        status_emoji = get_premium_status_emoji(premium_data['status'])
        
        if premium_data['status'] == PremiumStatus.ACTIVE:
            # Active subscription
            expiry = datetime.fromisoformat(premium_data['expiry'])
            days_left = (expiry - datetime.utcnow()).days
            
            plan_name = next(p.value['name'] for p in PremiumPlan if p.value['id'] == premium_data['plan'])
            
            response = f"{status_emoji} *Premium Active* - {plan_name}\n\n"
            response += f"✅ *Status:* Active\n"
            response += f"📅 *Expires:* {expiry.strftime('%Y-%m-%d')} ({days_left} days left)\n"
            response += f"🆔 *Subscription:* {premium_data.get('subscription_id', 'N/A')}\n\n"
            
            response += f"✨ *Your Features:*\n"
            for feature in PREMIUM_FEATURES:
                response += f"{feature}\n"
            
            response += f"\n💳 *Manage Subscription:*\n"
            response += f"• `/renew {plan_name.lower()}` - Extend current plan\n"
            response += f"• `/upgrade` - Switch plans\n"
            response += f"• `/downgrade` - Cancel subscription"
            
        else:
            # Inactive - show upgrade options
            response = f"{status_emoji} *Upgrade to Premium*\n\n"
            
            response += f"✨ *Premium Features:*\n"
            for feature in PREMIUM_FEATURES:
                response += f"{feature}\n"
            
            response += f"\n💎 *Choose Your Plan:*\n"
            response += f"{hbold(PremiumPlan.WEEKLY.value['name'])} - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week\n"
            response += f"  {PremiumPlan.WEEKLY.value['description']}\n\n"
            response += f"{hbold(PremiumPlan.MONTHLY.value['name'])} - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month\n"
            response += f"  {PremiumPlan.MONTHLY.value['description']} (Save 17% vs weekly!)\n\n"
            
            response += f"🚀 *Get Started:*\n"
            response += f"• `/upgrade weekly` - Start weekly plan\n"
            response += f"• `/upgrade monthly` - Start monthly plan\n\n"
            response += f"💳 *Payment:* Secure via Paystack"
        
        await message.reply(response, parse_mode='Markdown', disable_web_page_preview=True)
        
        logger.info("Premium status checked", extra={
            'user_id': user_id,
            'action': 'status_check',
            'status': premium_data['status'],
            'plan': premium_data.get('plan', 'none')
        })
        
    except Exception as e:
        logger.error("Premium command error", exc_info=True, extra={
            'user_id': user_id,
            'action': 'command',
            'error': str(e)
        })
        await message.reply(
            f"❌ *Error*\n\n"
            f"Unable to check premium status. Please try again.\n"
            f"Use `/upgrade weekly` or `/upgrade monthly` to get started.",
            parse_mode='Markdown'
        )

async def purchase_premium_handler(message: types.Message, state: FSMContext) -> None:
    """Handle premium purchase initiation with plan selection."""
    user_id = message.from_user.id
    
    # Parse plan from command
    command_text = message.text.replace("/upgrade", "").strip().lower()
    selected_plan = None
    
    if not command_text:
        # Show plan selection if no plan specified
        keyboard_markup = types.InlineKeyboardMarkup(row_width=1)
        
        weekly_btn = types.InlineKeyboardButton(
            f"{PremiumPlan.WEEKLY.value['name']} - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}",
            callback_data=f"upgrade_plan|weekly|{user_id}"
        )
        monthly_btn = types.InlineKeyboardButton(
            f"{PremiumPlan.MONTHLY.value['name']} - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}",
            callback_data=f"upgrade_plan|monthly|{user_id}"
        )
        
        cancel_btn = types.InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_upgrade|{user_id}")
        
        keyboard_markup.add(weekly_btn, monthly_btn, cancel_btn)
        
        response = (
            f"💎 *Choose Your Premium Plan*\n\n"
            f"Select a plan to get started:\n\n"
            f"• {hbold(PremiumPlan.WEEKLY.value['name'])} - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week\n"
            f"  {PremiumPlan.WEEKLY.value['description']}\n\n"
            f"• {hbold(PremiumPlan.MONTHLY.value['name'])} - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month\n"
            f"  {PremiumPlan.MONTHLY.value['description']}"
        )
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard_markup)
        return
    
    # Validate plan selection
    if command_text in ['weekly', 'week']:
        selected_plan = PremiumPlan.WEEKLY
    elif command_text in ['monthly', 'month']:
        selected_plan = PremiumPlan.MONTHLY
    else:
        await message.reply(
            f"❌ *Invalid Plan*\n\n"
            f"Please choose: `/upgrade weekly` or `/upgrade monthly`\n\n"
            f"Or use `/upgrade` for interactive selection.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Create transaction for selected plan
        amount = selected_plan.value['price_ngn']
        currency = "NGN"
        gateway = "paystack"  # Use Paystack for Naira
        
        transaction = await payment_orchestrator.create_transaction(
            user_id=user_id,
            amount=amount,
            currency=currency,
            gateway=gateway
        )
        
        # Store transaction and plan in state
        await state.update_data(
            premium_transaction=transaction.transaction_id,
            premium_plan=selected_plan.value['id'],
            payment_amount=amount,
            currency=currency
        )
        
        # Get payment URL
        payment_url = transaction.metadata.get('authorization_url', '')
        reference = transaction.metadata.get('reference', transaction.transaction_id)
        
        response = (
            f"💳 *Premium Purchase - {selected_plan.value['name']}*\n\n"
            f"📋 *Order Summary:*\n"
            f"• Plan: {hbold(selected_plan.value['name'])}\n"
            f"• Amount: {format_currency(amount)}\n"
            f"• Duration: {selected_plan.value['duration_days']} days\n\n"
            f"🆔 *Transaction:* {transaction.transaction_id}\n"
            f"🔗 *Reference:* `{reference}`\n\n"
            f"🔗 *Complete Payment:*\n"
            f"[Pay {format_currency(amount)} Now]({payment_url})\n\n"
            f"⏰ *Payment expires in 30 minutes*\n\n"
            f"💡 After payment, use `/activate` to confirm your subscription."
        )
        
        # Add status check button
        from callbacks import create_confirmation_keyboard
        status_callback = f"check_premium_status|{int(time.time())}|{user_id}|{transaction.transaction_id}"
        keyboard = create_confirmation_keyboard("Check Payment Status", status_callback)
        
        await message.reply(
            response,
            parse_mode='Markdown',
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        logger.info("Premium purchase initiated", extra={
            'user_id': user_id,
            'action': 'purchase_init',
            'plan': selected_plan.value['id'],
            'amount': amount,
            'transaction_id': transaction.transaction_id
        })
        
    except Exception as e:
        logger.error("Premium purchase initiation failed", exc_info=True, extra={
            'user_id': user_id,
            'action': 'purchase_init',
            'error': str(e)
        })
        await message.reply(
            f"❌ *Payment Error*\n\n"
            f"Failed to initiate payment. Please try again.\n"
            f"If the problem persists, contact support.",
            parse_mode='Markdown'
        )

async def activate_premium_handler(message: types.Message, state: FSMContext) -> None:
    """Handle premium activation after successful payment."""
    user_id = message.from_user.id
    
    try:
        data = await state.get_data()
        transaction_id = data.get('premium_transaction')
        plan_id = data.get('premium_plan')
        
        if not transaction_id:
            await message.reply(
                f"❌ *No Transaction*\n\n"
                f"No pending premium transaction found.\n"
                f"Start a new subscription with `/upgrade`.",
                parse_mode='Markdown'
            )
            return
        
        # Verify transaction
        transaction = await payment_orchestrator.get_transaction(transaction_id)
        if not transaction:
            await message.reply("Transaction not found. Please start a new purchase.")
            return
        
        # Determine plan
        if not plan_id:
            plan_id = PremiumPlan.MONTHLY.value['id']  # Default
        
        plan = next(p for p in PremiumPlan if p.value['id'] == plan_id)
        
        # Activate premium
        if await activate_premium(user_id, transaction, plan):
            plan_name = plan.value['name']
            expiry = datetime.fromisoformat((await get_premium_data(user_id))['expiry'])
            
            response = (
                f"🎉 *Premium Activated!*\n\n"
                f"✅ *Welcome to {plan_name} Premium!*\n\n"
                f"📅 *Active until:* {expiry.strftime('%Y-%m-%d')}\n"
                f"🆔 *Subscription:* {(await get_premium_data(user_id))['subscription_id']}\n\n"
                f"✨ *Your Features:*\n"
            )
            
            for feature in PREMIUM_FEATURES:
                response += f"{feature}\n"
            
            response += f"\n💎 *Manage:*\n"
            response += f"• `/premium` - View status\n"
            response += f"• `/renew {plan_name.lower()}` - Extend subscription"
            
            await message.reply(response, parse_mode='Markdown')
            await state.finish()
            
            logger.info("Premium activation completed", extra={
                'user_id': user_id,
                'action': 'activation_complete',
                'plan': plan.value['id'],
                'transaction_id': transaction_id
            })
        else:
            await message.reply(
                f"❌ *Activation Failed*\n\n"
                f"Payment verification failed. Please contact support with transaction ID:\n"
                f"`{transaction_id}`",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error("Premium activation handler error", exc_info=True, extra={
            'user_id': user_id,
            'action': 'activation_handler',
            'error': str(e)
        })
        await message.reply(
            f"❌ *Error*\n\n"
            f"An error occurred during activation. Please try again or contact support.",
            parse_mode='Markdown'
        )

async def renew_premium_handler(message: types.Message, state: FSMContext) -> None:
    """Handle premium renewal with plan selection."""
    user_id = message.from_user.id
    
    # Parse plan from command
    command_text = message.text.replace("/renew", "").strip().lower()
    selected_plan = None
    
    if not command_text:
        # Default to current plan or monthly
        premium_data = await get_premium_data(user_id)
        if premium_data['status'] == PremiumStatus.ACTIVE and premium_data.get('plan'):
            current_plan_id = premium_data['plan']
            selected_plan = next(p for p in PremiumPlan if p.value['id'] == current_plan_id)
        else:
            selected_plan = PremiumPlan.MONTHLY
    else:
        if command_text in ['weekly', 'week']:
            selected_plan = PremiumPlan.WEEKLY
        elif command_text in ['monthly', 'month']:
            selected_plan = PremiumPlan.MONTHLY
        else:
            await message.reply(
                f"❌ *Invalid Plan*\n\n"
                f"Please use: `/renew weekly` or `/renew monthly`\n\n"
                f"Or use `/renew` to extend your current plan.",
                parse_mode='Markdown'
            )
            return
    
    try:
        # Check if user has active premium
        await check_premium_expiry(user_id)
        premium_data = await get_premium_data(user_id)
        
        if premium_data['status'] != PremiumStatus.ACTIVE:
            await message.reply(
                f"❌ *No Active Subscription*\n\n"
                f"You need an active premium subscription to renew.\n"
                f"Start with `/upgrade {selected_plan.value['id']}`",
                parse_mode='Markdown'
            )
            return
        
        # Create renewal transaction
        amount = selected_plan.value['price_ngn']
        transaction = await payment_orchestrator.create_transaction(
            user_id=user_id,
            amount=amount,
            currency="NGN",
            gateway="paystack"
        )
        
        await state.update_data(
            premium_transaction=transaction.transaction_id,
            premium_plan=selected_plan.value['id'],
            payment_amount=amount,
            is_renewal=True
        )
        
        payment_url = transaction.metadata.get('authorization_url', '')
        reference = transaction.metadata.get('reference', transaction.transaction_id)
        
        response = (
            f"🔄 *Premium Renewal - {selected_plan.value['name']}*\n\n"
            f"📋 *Renewal Details:*\n"
            f"• Plan: {hbold(selected_plan.value['name'])}\n"
            f"• Amount: {format_currency(amount)}\n"
            f"• Extend: {selected_plan.value['duration_days']} more days\n\n"
            f"🆔 *Transaction:* {transaction.transaction_id}\n"
            f"🔗 *Reference:* `{reference}`\n\n"
            f"🔗 *Complete Payment:*\n"
            f"[Pay {format_currency(amount)} Now]({payment_url})\n\n"
            f"⏰ *Payment expires in 30 minutes*"
        )
        
        keyboard = create_confirmation_keyboard("Check Status", f"check_renewal|{int(time.time())}|{user_id}|{transaction.transaction_id}")
        
        await message.reply(
            response,
            parse_mode='Markdown',
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        logger.info("Premium renewal initiated", extra={
            'user_id': user_id,
            'action': 'renewal_init',
            'plan': selected_plan.value['id'],
            'amount': amount,
            'transaction_id': transaction.transaction_id
        })
        
    except Exception as e:
        logger.error("Premium renewal initiation failed", exc_info=True, extra={
            'user_id': user_id,
            'action': 'renewal_init',
            'error': str(e)
        })
        await message.reply(
            f"❌ *Renewal Error*\n\n"
            f"Failed to initiate renewal. Please try again.",
            parse_mode='Markdown'
        )

async def downgrade_premium_handler(message: types.Message, state: FSMContext) -> None:
    """Handle premium downgrade/cancellation."""
    user_id = message.from_user.id
    
    try:
        # Show confirmation dialog
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton("✅ Confirm Cancel", callback_data=f"confirm_downgrade|{user_id}")
        keep_btn = types.InlineKeyboardButton("❌ Keep Premium", callback_data=f"cancel_downgrade|{user_id}")
        keyboard.add(confirm_btn, keep_btn)
        
        response = (
            f"⚠️ *Cancel Premium Subscription*\n\n"
            f"Are you sure you want to cancel your premium subscription?\n\n"
            f"💡 *Note:* Your premium access will continue until the end of your current billing period.\n\n"
            f"• No further charges will be made\n"
            f"• You can resubscribe anytime\n"
            f"• All your data and settings remain intact"
        )
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        logger.error("Premium downgrade handler error", exc_info=True, extra={
            'user_id': user_id,
            'action': 'downgrade_handler',
            'error': str(e)
        })
        await message.reply(
            f"❌ *Error*\n\n"
            f"Unable to process cancellation request. Please try again.",
            parse_mode='Markdown'
        )

def register_premium_handlers(dp: Dispatcher) -> None:
    """Register all premium handlers."""
    # aiogram 3.x syntax
    dp.message.register(premium_command_handler, Command("premium"))
    dp.message.register(purchase_premium_handler, Command("upgrade"))
    dp.message.register(activate_premium_handler, Command("activate"))
    dp.message.register(renew_premium_handler, Command("renew"))
    dp.message.register(downgrade_premium_handler, Command("downgrade"))
    
    # Register callback handlers for plan selection
    from handlers.callbacks import process_callback_query
    
    # Extend callback processing for premium-specific actions
    async def handle_premium_callbacks(callback: types.CallbackQuery, state: FSMContext) -> None:
        data = callback.data.split('|')
        action = data[0]
        
        if action == "upgrade_plan":
            plan_name = data[1]
            user_id = int(data[2])
            
            if callback.from_user.id != user_id:
                await callback.answer("This action is not for you.", show_alert=True)
                return
            
            if plan_name == "weekly":
                selected_plan = PremiumPlan.WEEKLY
            else:
                selected_plan = PremiumPlan.MONTHLY
            
            # Trigger purchase for selected plan
            message = types.Message(
                message_id=callback.message.message_id,
                from_user=callback.from_user,
                date=callback.message.date,
                chat=callback.message.chat,
                text=f"/upgrade {plan_name}"
            )
            await purchase_premium_handler(message, state)
            await callback.answer(f"Starting {plan_name} plan purchase...", show_alert=False)
            
        elif action == "cancel_upgrade":
            await callback.message.edit_text("Premium upgrade cancelled.")
            await callback.answer("Cancelled", show_alert=True)
            
        elif action == "confirm_downgrade":
            user_id = int(data[1])
            if callback.from_user.id == user_id:
                if await downgrade_premium(user_id):
                    await callback.message.edit_text(
                        "✅ *Subscription Cancelled*\n\n"
                        "Your premium subscription has been cancelled.\n"
                        "Access continues until your current billing period ends.\n\n"
                        "You can resubscribe anytime with `/upgrade`.",
                        parse_mode='Markdown'
                    )
                    await callback.answer("Subscription cancelled", show_alert=True)
                else:
                    await callback.answer("No active subscription to cancel.", show_alert=True)
            else:
                await callback.answer("This action is not for you.", show_alert=True)
                
        elif action == "cancel_downgrade":
            await callback.message.edit_text("✅ Premium subscription kept active.")
            await callback.answer("Kept active", show_alert=True)
    
    # Register premium callback handler - aiogram 3.x syntax
    dp.callback_query.register(
        handle_premium_callbacks,
        lambda c: c.data and c.data.startswith(('upgrade_plan|', 'cancel_upgrade|', 'confirm_downgrade|', 'cancel_downgrade|'))
    )
