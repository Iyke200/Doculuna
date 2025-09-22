# upgrade.py
import logging
import time
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import RetryAfter
from aiogram.utils.markdown import hbold, hcode
from dotenv import load_dotenv

# Import from other modules
from premium import PremiumPlan, PremiumStatus, activate_premium, get_premium_data, downgrade_premium  # type: ignore
from payments import payment_orchestrator, Transaction, PaymentStatus  # type: ignore
from referrals import process_premium_conversion_reward  # type: ignore
from stats import stats_tracker, StatType  # type: ignore
from db import get_user_data, update_user_data  # type: ignore

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s - plan=%(plan)s - transaction_id=%(transaction_id)s - status=%(status)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class UpgradeStatus(Enum):
    """Upgrade process states."""
    PENDING = "pending"
    PROCESSING = "processing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"

class UpgradeRollbackContext:
    """Context manager for safe upgrade operations with automatic rollback."""
    
    def __init__(self, user_id: int, transaction_id: str, original_state: Dict[str, Any]):
        self.user_id = user_id
        self.transaction_id = transaction_id
        self.original_state = original_state
        self.rollback_needed = False
        self.rollback_executed = False
        
    def __enter__(self):
        return self
    
    def mark_for_rollback(self):
        """Mark current operation for rollback."""
        self.rollback_needed = True
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback_needed = True
        
        if self.rollback_needed and not self.rollback_executed:
            self.rollback()
        
        # Re-raise exception if not handled
        return exc_type is None

def create_upgrade_rollback(user_id: int, transaction_id: str, 
                          original_premium_state: Dict[str, Any]) -> UpgradeRollbackContext:
    """Create rollback context for upgrade operation."""
    return UpgradeRollbackContext(user_id, transaction_id, original_premium_state)

async def validate_upgrade_eligibility(user_id: int, plan: PremiumPlan) -> Dict[str, Any]:
    """Validate user eligibility for upgrade."""
    try:
        # Get current premium status
        current_premium = await get_premium_data(user_id)
        current_status = current_premium.get('status', PremiumStatus.EXPIRED.value)
        current_plan = current_premium.get('plan', 'basic')
        
        validation_result = {
            'eligible': True,
            'current_status': current_status,
            'current_plan': current_plan,
            'plan': plan.value['id'],
            'price': plan.value['price_ngn'],
            'currency': 'NGN',
            'warnings': [],
            'can_proceed': True
        }
        
        # Check if user is already on higher/better plan
        if current_status == PremiumStatus.ACTIVE.value:
            current_plan_obj = next((p for p in PremiumPlan if p.value['id'] == current_plan), None)
            target_plan_obj = plan
            
            if current_plan_obj and target_plan_obj:
                if current_plan_obj.value['duration_days'] >= target_plan_obj.value['duration_days']:
                    validation_result['warnings'].append(
                        f"Current {current_plan_obj.value['name']} plan expires in {(datetime.fromisoformat(current_premium['expiry']) - datetime.utcnow()).days} days"
                    )
                    validation_result['can_proceed'] = True  # Still allow, but inform
        
        # Check for pending transactions
        pending_txn = await get_pending_upgrade_transaction(user_id)
        if pending_txn:
            validation_result['warnings'].append(f"Pending transaction: {pending_txn['transaction_id']}")
            validation_result['can_proceed'] = False
        
        # Check payment method restrictions (future)
        # validation_result['payment_methods'] = await get_available_payment_methods(user_id)
        
        logger.info("Upgrade eligibility validated", extra={
            'user_id': user_id,
            'current_plan': current_plan,
            'target_plan': plan.value['id'],
            'eligible': validation_result['eligible'],
            'can_proceed': validation_result['can_proceed']
        })
        
        return validation_result
        
    except Exception as e:
        logger.error("Upgrade eligibility validation failed", exc_info=True, extra={
            'user_id': user_id,
            'plan': plan.value['id'],
            'error': str(e)
        })
        return {
            'eligible': False,
            'error': 'Validation failed',
            'current_status': 'unknown',
            'current_plan': 'unknown',
            'plan': plan.value['id'],
            'can_proceed': False
        }

async def get_pending_upgrade_transaction(user_id: int) -> Optional[Dict[str, Any]]:
    """Check for pending upgrade transactions."""
    try:
        # Check recent transactions
        user_transactions = await payment_orchestrator.list_user_transactions(user_id, limit=5)
        
        for transaction in user_transactions:
            if (transaction.status in [PaymentStatus.PENDING.value, PaymentStatus.INITIALIZED.value] and
                'upgrade' in transaction.metadata.get('purpose', '').lower()):
                
                return {
                    'transaction_id': transaction.transaction_id,
                    'status': transaction.status.value,
                    'amount': transaction.amount,
                    'created_at': transaction.created_at.isoformat(),
                    'metadata': transaction.metadata
                }
        
        return None
        
    except Exception as e:
        logger.error("Failed to check pending transactions", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        return None

async def initiate_upgrade(user_id: int, plan: PremiumPlan, 
                         payment_method: str = 'paystack') -> Dict[str, Any]:
    """Initiate upgrade process with transaction creation."""
    try:
        # Step 1: Validate eligibility
        eligibility = await validate_upgrade_eligibility(user_id, plan)
        if not eligibility['can_proceed']:
            return {
                'success': False,
                'error': 'Cannot proceed with upgrade',
                'reason': eligibility.get('warnings', ['Unknown error']),
                'eligibility': eligibility
            }
        
        # Step 2: Create transaction
        transaction_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        transaction_metadata = {
            'purpose': 'premium_upgrade',
            'plan': plan.value['id'],
            'user_id': user_id,
            'amount': plan.value['price_ngn'],
            'currency': 'NGN',
            'initiated_at': now.isoformat(),
            'upgrade_id': transaction_id
        }
        
        # Create transaction through orchestrator
        transaction = await payment_orchestrator.create_transaction(
            user_id=user_id,
            amount=plan.value['price_ngn'],
            currency='NGN',
            gateway=payment_method
        )
        
        if not transaction:
            return {
                'success': False,
                'error': 'Failed to create transaction',
                'transaction_id': None
            }
        
        # Update transaction metadata
        transaction.metadata.update(transaction_metadata)
        await payment_orchestrator.update_transaction_status(
            transaction.transaction_id,
            PaymentStatus.INITIALIZED,
            transaction_metadata
        )
        
        # Step 3: Store upgrade state
        upgrade_state = {
            'user_id': user_id,
            'transaction_id': transaction.transaction_id,
            'plan': plan.value['id'],
            'amount': plan.value['price_ngn'],
            'status': UpgradeStatus.PENDING.value,
            'created_at': now.isoformat(),
            'metadata': transaction_metadata
        }
        
        upgrade_key = f"upgrade:{user_id}:{transaction.transaction_id}"
        if REDIS_AVAILABLE:
            redis_client.setex(upgrade_key, 3600, json.dumps(upgrade_state))  # 1 hour
        else:
            # In-memory storage
            if 'upgrade_states' not in globals():
                globals()['upgrade_states'] = {}
            globals()['upgrade_states'][upgrade_key] = upgrade_state
        
        # Step 4: Track for stats
        await stats_tracker.track_user_activity(
            user_id, 
            StatType.PREMIUM_UPGRADE.value,
            {'plan': plan.value['id'], 'amount': plan.value['price_ngn']}
        )
        
        logger.info("Upgrade initiated successfully", extra={
            'user_id': user_id,
            'transaction_id': transaction.transaction_id,
            'plan': plan.value['id'],
            'amount': plan.value['price_ngn'],
            'payment_method': payment_method
        })
        
        return {
            'success': True,
            'transaction_id': transaction.transaction_id,
            'authorization_url': transaction.metadata.get('authorization_url'),
            'reference': transaction.metadata.get('reference'),
            'amount': plan.value['price_ngn'],
            'plan': plan.value['id'],
            'status': UpgradeStatus.PENDING.value,
            'next_step': 'payment',
            'upgrade_state': upgrade_state
        }
        
    except Exception as e:
        logger.error("Upgrade initiation failed", exc_info=True, extra={
            'user_id': user_id,
            'plan': plan.value['id'],
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Initiation failed',
            'transaction_id': None
        }

async def verify_upgrade_payment(user_id: int, transaction_id: str, 
                               expected_amount: float) -> Dict[str, Any]:
    """Verify payment and complete upgrade process."""
    try:
        # Step 1: Get transaction
        transaction = await payment_orchestrator.get_transaction(transaction_id)
        if not transaction:
            return {
                'success': False,
                'error': 'Transaction not found',
                'status': 'failed'
            }
        
        # Step 2: Validate amount
        if abs(transaction.amount - expected_amount) > 0.01:
            logger.warning("Payment amount mismatch", extra={
                'user_id': user_id,
                'transaction_id': transaction_id,
                'expected': expected_amount,
                'actual': transaction.amount
            })
            return {
                'success': False,
                'error': 'Payment amount incorrect',
                'status': 'failed'
            }
        
        # Step 3: Get upgrade state
        upgrade_state = await get_upgrade_state(user_id, transaction_id)
        if not upgrade_state:
            return {
                'success': False,
                'error': 'Upgrade session expired',
                'status': 'expired'
            }
        
        plan_id = upgrade_state['plan']
        plan = next((p for p in PremiumPlan if p.value['id'] == plan_id), PremiumPlan.MONTHLY)
        
        # Step 4: Capture original state for rollback
        original_premium_state = await get_premium_data(user_id)
        original_state = {
            'status': original_premium_state.get('status'),
            'expiry': original_premium_state.get('expiry'),
            'plan': original_premium_state.get('plan'),
            'snapshot_at': datetime.utcnow().isoformat()
        }
        
        # Step 5: Process upgrade with rollback protection
        rollback_ctx = create_upgrade_rollback(user_id, transaction_id, original_state)
        
        with rollback_ctx:
            # Update transaction status
            await payment_orchestrator.update_transaction_status(
                transaction_id,
                PaymentStatus.PROCESSING,
                {'verification_step': 'in_progress'}
            )
            
            # Process referral reward if applicable
            referral_result = await process_premium_conversion_reward(user_id, transaction, plan)
            
            # Activate premium subscription
            activation_success = await activate_premium(user_id, transaction, plan)
            
            if not activation_success:
                rollback_ctx.mark_for_rollback()
                return {
                    'success': False,
                    'error': 'Premium activation failed',
                    'status': 'activation_failed',
                    'referral_processed': referral_result.get('success', False)
                }
            
            # Update upgrade state
            upgrade_state['status'] = UpgradeStatus.COMPLETED.value
            upgrade_state['completed_at'] = datetime.utcnow().isoformat()
            upgrade_state['referral_reward'] = referral_result
            upgrade_state['activation_success'] = True
            
            await store_upgrade_state(user_id, transaction_id, upgrade_state)
            
            # Clean up upgrade state after delay
            asyncio.create_task(cleanup_upgrade_state(user_id, transaction_id))
        
        # Step 6: Track successful upgrade
        await stats_tracker.track_user_activity(
            user_id,
            f"{StatType.PREMIUM_UPGRADE.value}:success",
            {
                'plan': plan.value['id'],
                'amount': transaction.amount,
                'transaction_id': transaction_id,
                'referral_reward': referral_result.get('reward_amount', 0)
            }
        )
        
        logger.info("Upgrade verification completed successfully", extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'plan': plan.value['id'],
            'amount': transaction.amount,
            'referral_reward': referral_result.get('reward_amount', 0)
        })
        
        return {
            'success': True,
            'transaction_id': transaction_id,
            'plan': plan.value['id'],
            'status': UpgradeStatus.COMPLETED.value,
            'referral_reward': referral_result,
            'new_expiry': (await get_premium_data(user_id)).get('expiry'),
            'next_step': 'enjoy'
        }
        
    except Exception as e:
        logger.error("Upgrade verification failed", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'expected_amount': expected_amount,
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Verification process failed',
            'status': 'processing_error'
        }

async def handle_failed_upgrade(user_id: int, transaction_id: str, 
                             failure_reason: str = "unknown") -> Dict[str, Any]:
    """Handle upgrade failure with notification and cleanup."""
    try:
        # Update transaction status
        await payment_orchestrator.update_transaction_status(
            transaction_id,
            PaymentStatus.FAILED,
            {'failure_reason': failure_reason, 'handled_at': datetime.utcnow().isoformat()}
        )
        
        # Update upgrade state
        upgrade_state = await get_upgrade_state(user_id, transaction_id)
        if upgrade_state:
            upgrade_state['status'] = UpgradeStatus.FAILED.value
            upgrade_state['failure_reason'] = failure_reason
            upgrade_state['failed_at'] = datetime.utcnow().isoformat()
            await store_upgrade_state(user_id, transaction_id, upgrade_state)
        
        # Track failed upgrade
        await stats_tracker.track_user_activity(
            user_id,
            f"{StatType.PREMIUM_UPGRADE.value}:failed",
            {'reason': failure_reason, 'transaction_id': transaction_id}
        )
        
        logger.warning("Upgrade failed and handled", extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'failure_reason': failure_reason
        })
        
        return {
            'success': True,
            'handled': True,
            'status': 'failure_handled',
            'failure_reason': failure_reason
        }
        
    except Exception as e:
        logger.error("Failed to handle upgrade failure", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'failure_reason': failure_reason,
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Failure handling failed',
            'status': 'error'
        }

async def handle_upgrade_rollback(user_id: int, transaction_id: str, 
                               original_state: Dict[str, Any]) -> bool:
    """Perform rollback of failed upgrade."""
    try:
        logger.info("Starting upgrade rollback", extra={
            'user_id': user_id,
            'transaction_id': transaction_id
        })
        
        # Restore premium state
        if original_state['status'] == PremiumStatus.ACTIVE.value and original_state.get('expiry'):
            # Reactivate original premium if it was active
            from payments import Transaction, PaymentStatus
            rollback_transaction = Transaction(
                transaction_id=f"rollback_{uuid.uuid4()}",
                user_id=user_id,
                amount=0.0,
                currency="NGN",
                gateway="rollback",
                status=PaymentStatus.SUCCESS,
                metadata={
                    'purpose': 'rollback_restoration',
                    'original_expiry': original_state['expiry'],
                    'original_plan': original_state['plan']
                },
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            original_plan = next((p for p in PremiumPlan if p.value['id'] == original_state['plan']), PremiumPlan.MONTHLY)
            restore_success = await activate_premium(user_id, rollback_transaction, original_plan)
        else:
            # Downgrade to free if originally free
            restore_success = await downgrade_premium(user_id)
        
        # Clean up failed transaction references
        await cleanup_failed_upgrade_state(user_id, transaction_id)
        
        # Track rollback
        await stats_tracker.track_user_activity(
            user_id,
            f"{StatType.PREMIUM_UPGRADE.value}:rolled_back",
            {'original_state': original_state, 'transaction_id': transaction_id}
        )
        
        logger.info("Upgrade rollback completed", extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'restore_success': restore_success,
            'original_status': original_state['status']
        })
        
        return restore_success
        
    except Exception as e:
        logger.error("Rollback failed", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        return False

async def get_upgrade_state(user_id: int, transaction_id: str) -> Optional[Dict[str, Any]]:
    """Get current upgrade state."""
    try:
        upgrade_key = f"upgrade:{user_id}:{transaction_id}"
        
        if REDIS_AVAILABLE:
            data = redis_client.get(upgrade_key)
            if data:
                return json.loads(data)
        else:
            if 'upgrade_states' in globals() and upgrade_key in globals()['upgrade_states']:
                return globals()['upgrade_states'][upgrade_key]
        
        return None
        
    except Exception as e:
        logger.error("Failed to get upgrade state", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        return None

async def store_upgrade_state(user_id: int, transaction_id: str, 
                            upgrade_state: Dict[str, Any]) -> None:
    """Store upgrade state."""
    try:
        upgrade_key = f"upgrade:{user_id}:{transaction_id}"
        
        if REDIS_AVAILABLE:
            ttl = 3600 if upgrade_state['status'] == UpgradeStatus.PENDING.value else 86400
            redis_client.setex(upgrade_key, ttl, json.dumps(upgrade_state))
        else:
            if 'upgrade_states' not in globals():
                globals()['upgrade_states'] = {}
            globals()['upgrade_states'][upgrade_key] = upgrade_state
            
    except Exception as e:
        logger.error("Failed to store upgrade state", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })

async def cleanup_upgrade_state(user_id: int, transaction_id: str, delay: int = 300) -> None:
    """Clean up upgrade state after delay."""
    try:
        await asyncio.sleep(delay)
        
        upgrade_key = f"upgrade:{user_id}:{transaction_id}"
        
        if REDIS_AVAILABLE:
            redis_client.delete(upgrade_key)
        else:
            if 'upgrade_states' in globals() and upgrade_key in globals()['upgrade_states']:
                del globals()['upgrade_states'][upgrade_key]
                
    except Exception as e:
        logger.error("Failed to cleanup upgrade state", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })

async def cleanup_failed_upgrade_state(user_id: int, transaction_id: str) -> None:
    """Immediate cleanup of failed upgrade state."""
    try:
        upgrade_key = f"upgrade:{user_id}:{transaction_id}"
        
        if REDIS_AVAILABLE:
            redis_client.delete(upgrade_key)
        else:
            if 'upgrade_states' in globals() and upgrade_key in globals()['upgrade_states']:
                del globals()['upgrade_states'][upgrade_key]
                
        logger.info("Failed upgrade state cleaned up", extra={
            'user_id': user_id,
            'transaction_id': transaction_id
        })
        
    except Exception as e:
        logger.error("Failed to cleanup failed upgrade state", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })

async def send_upgrade_status_notification(bot, user_id: int, 
                                         upgrade_result: Dict[str, Any]) -> None:
    """Send upgrade status notification to user."""
    try:
        status_emojis = {
            UpgradeStatus.COMPLETED.value: "🎉",
            UpgradeStatus.FAILED.value: "❌", 
            UpgradeStatus.ROLLED_BACK.value: "🔄",
            UpgradeStatus.CANCELLED.value: "⏸️"
        }
        
        emoji = status_emojis.get(upgrade_result.get('status', ''), "ℹ️")
        status = upgrade_result.get('status', 'unknown')
        
        if status == UpgradeStatus.COMPLETED.value:
            plan_name = next((p.value['name'] for p in PremiumPlan if p.value['id'] == upgrade_result.get('plan')), 'Premium')
            expiry = upgrade_result.get('new_expiry')
            
            if expiry:
                expiry_date = datetime.fromisoformat(expiry)
                days_left = max(0, (expiry_date - datetime.utcnow()).days)
                expiry_text = f"Expires: {expiry_date.strftime('%b %d, %Y')} ({days_left} days)"
            else:
                expiry_text = "Duration: Unlimited"
            
            notification = (
                f"{emoji} *Upgrade Successful!*\n\n"
                f"✨ *Welcome to {plan_name} Premium!*\n\n"
                f"💎 *Your Plan:* {plan_name}\n"
                f"📅 *{expiry_text}*\n\n"
                f"🎁 *What's Included:*\n"
                f"• 📄 Unlimited document uploads\n"
                f"• 🧠 Advanced AI analysis\n"
                f"• ⚡ Priority processing\n"
                f"• 🎨 Ad-free experience\n\n"
                f"🚀 *Try it now:* Upload a document or use `/help`\n"
                f"📊 *Manage:* `/premium`"
            )
            
            # Check for referral reward
            referral_reward = upgrade_result.get('referral_reward')
            if referral_reward and referral_reward.get('success'):
                reward_amount = referral_reward.get('reward_amount', 0)
                if reward_amount > 0:
                    notification += f"\n\n🎉 *Bonus:* Your friend earned {format_currency(reward_amount)} for your upgrade!"
            
        elif status == UpgradeStatus.FAILED.value:
            reason = upgrade_result.get('error', 'Unknown error')
            notification = (
                f"{emoji} *Upgrade Failed*\n\n"
                f"😔 *Sorry about that!*\n\n"
                f"❌ *Issue:* {reason}\n\n"
                f"💡 *What to do:*\n"
                f"• Try again with `/upgrade`\n"
                f"• Check your payment method\n"
                f"• Contact support if issues persist\n\n"
                f"📞 *Support:* /help"
            )
            
        else:  # Cancelled or other status
            reason = upgrade_result.get('error', 'Cancelled by user')
            notification = (
                f"{emoji} *Upgrade {status.replace('_', ' ').title()}\n\n"
                f"ℹ️ *Status:* {reason}\n\n"
                f"💎 *No worries!* You can try again anytime:\n"
                f"• `/upgrade weekly` - ₦1,000/week\n"
                f"• `/upgrade monthly` - ₦3,500/month\n\n"
                f"📋 *Current plan:* {upgrade_result.get('current_plan', 'Free')}"
            )
        
        try:
            await bot.send_message(user_id, notification, parse_mode='Markdown')
            logger.info("Upgrade notification sent", extra={
                'user_id': user_id,
                'status': status,
                'notification_type': 'success' if status == UpgradeStatus.COMPLETED.value else 'failure'
            })
        except Exception as notify_e:
            logger.error("Failed to send upgrade notification", exc_info=True, extra={
                'user_id': user_id,
                'status': status,
                'error': str(notify_e)
            })
            
    except Exception as e:
        logger.error("Failed to process upgrade notification", exc_info=True, extra={
            'user_id': user_id,
            'upgrade_result': upgrade_result,
            'error': str(e)
        })

async def upgrade_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /upgrade command with plan selection."""
    user_id = message.from_user.id
    
    try:
        # Track command usage
        await stats_tracker.track_command_usage(user_id, 'upgrade')
        
        # Parse plan from command
        command_parts = message.text.split()
        selected_plan_id = None
        
        if len(command_parts) > 1:
            plan_arg = command_parts[1].lower()
            if plan_arg in ['weekly', 'week']:
                selected_plan_id = PremiumPlan.WEEKLY.value['id']
            elif plan_arg in ['monthly', 'month']:
                selected_plan_id = PremiumPlan.MONTHLY.value['id']
        
        # If no specific plan, show selection
        if not selected_plan_id:
            await show_plan_selection(message, state)
            return
        
        # Get selected plan
        selected_plan = next((p for p in PremiumPlan if p.value['id'] == selected_plan_id), None)
        if not selected_plan:
            await message.reply(
                f"❌ *Invalid Plan*\n\n"
                f"Please choose: `/upgrade weekly` or `/upgrade monthly`",
                parse_mode='Markdown'
            )
            return
        
        # Show plan details and confirm
        await show_plan_confirmation(message, state, selected_plan)
        
    except Exception as e:
        logger.error("Upgrade command handler error", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        await message.reply(
            f"❌ *Upgrade Error*\n\n"
            f"Something went wrong. Please try `/upgrade` again.\n"
            f"Contact support if the issue persists.",
            parse_mode='Markdown'
        )

async def show_plan_selection(message: types.Message, state: FSMContext) -> None:
    """Show interactive plan selection."""
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        # Weekly plan button
        weekly_text = (
            f"{hbold(PremiumPlan.WEEKLY.value['name'])}\n"
            f"{format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week\n"
            f"_Perfect for trying premium features_"
        )
        weekly_btn = types.InlineKeyboardButton(
            f"🧪 {weekly_text}", 
            callback_data=f"upgrade_select|weekly"
        )
        
        # Monthly plan button  
        monthly_text = (
            f"{hbold(PremiumPlan.MONTHLY.value['name'])}\n"
            f"{format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month\n"
            f"_Best value - save 17% vs weekly!_"
        )
        monthly_btn = types.InlineKeyboardButton(
            f"💎 {monthly_text}",
            callback_data=f"upgrade_select|monthly"
        )
        
        keyboard.add(weekly_btn, monthly_btn)
        
        # Info footer
        info_text = (
            f"💎 *Premium Features*\n\n"
            f"✨ *Unlimited* document processing\n"
            f"🧠 *Advanced* AI analysis\n"
            f"⚡ *Priority* support & processing\n"
            f"🎨 *Ad-free* experience\n\n"
            f"🔒 *Secure* - Your data stays private\n"
            f"💳 *Paystack* - Trusted payments"
        )
        
        await message.reply(info_text, parse_mode='Markdown', reply_markup=keyboard)
        
        logger.info("Plan selection shown", extra={'user_id': message.from_user.id})
        
    except Exception as e:
        logger.error("Failed to show plan selection", exc_info=True, extra={
            'user_id': message.from_user.id,
            'error': str(e)
        })
        await message.reply(
            f"💎 *Choose Your Plan:*\n\n"
            f"• `/upgrade weekly` - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week\n"
            f"• `/upgrade monthly` - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month\n\n"
            f"💬 Reply with your choice!",
            parse_mode='Markdown'
        )

async def show_plan_confirmation(message: types.Message, state: FSMContext, 
                               plan: PremiumPlan) -> None:
    """Show plan confirmation with payment button."""
    try:
        user_id = message.from_user.id
        
        # Check eligibility
        eligibility = await validate_upgrade_eligibility(user_id, plan)
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Confirmation buttons
        confirm_btn = types.InlineKeyboardButton(
            f"💳 Pay {format_currency(plan.value['price_ngn'])}",
            callback_data=f"upgrade_confirm|{plan.value['id']}"
        )
        cancel_btn = types.InlineKeyboardButton("❌ Cancel", callback_data="upgrade_cancel")
        
        keyboard.add(confirm_btn, cancel_btn)
        
        # Add current plan info if upgrading from premium
        plan_info = f"💎 *{plan.value['name']} Premium*\n\n"
        plan_info += f"💰 *Price:* {format_currency(plan.value['price_ngn'])}\n"
        plan_info += f"📅 *Duration:* {plan.value['duration_days']} days\n"
        plan_info += f"🌍 *Currency:* NGN\n\n"
        
        if eligibility['current_status'] == PremiumStatus.ACTIVE.value:
            current_plan_obj = next((p for p in PremiumPlan if p.value['id'] == eligibility['current_plan']), None)
            if current_plan_obj:
                days_left = (datetime.fromisoformat((await get_premium_data(user_id))['expiry']) - datetime.utcnow()).days
                plan_info += f"🔄 *Current:* {current_plan_obj.value['name']} ({days_left} days left)\n"
                plan_info += f"_Your new plan will start after current plan ends_\n\n"
        
        # Features list
        plan_info += f"✨ *What's Included:*\n"
        features = [
            "📄 Unlimited documents",
            "🧠 Advanced AI analysis", 
            "⚡ Priority processing",
            "🎨 Ad-free experience",
            "🔔 Priority support"
        ]
        
        for feature in features:
            plan_info += f"• {feature}\n"
        
        plan_info += f"\n💳 *Payment:* Secure via Paystack\n"
        plan_info += f"🔒 *Cancel anytime* - No long-term commitment\n\n"
        
        if eligibility['warnings']:
            plan_info += f"ℹ️ *Note:* {' | '.join(eligibility['warnings'])}\n\n"
        
        plan_info += f"👇 *Ready to upgrade?*"
        
        await message.reply(plan_info, parse_mode='Markdown', reply_markup=keyboard)
        
        # Store plan selection in state
        await state.update_data(
            selected_plan=plan.value['id'],
            upgrade_amount=plan.value['price_ngn']
        )
        
        logger.info("Plan confirmation shown", extra={
            'user_id': user_id,
            'plan': plan.value['id'],
            'amount': plan.value['price_ngn'],
            'eligibility_warnings': len(eligibility['warnings'])
        })
        
    except Exception as e:
        logger.error("Failed to show plan confirmation", exc_info=True, extra={
            'user_id': message.from_user.id,
            'plan': plan.value['id'],
            'error': str(e)
        })
        await message.reply(
            f"❌ *Error*\n\n"
            f"Unable to show plan details. Please try `/upgrade {plan.value['id']}` again.",
            parse_mode='Markdown'
        )

async def handle_upgrade_callbacks(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle upgrade-related callbacks."""
    user_id = callback.from_user.id
    data = callback.data
    
    try:
        if data.startswith('upgrade_select|'):
            # Plan selection from inline keyboard
            plan_id = data.split('|')[1]
            plan = next((p for p in PremiumPlan if p.value['id'] == plan_id), None)
            
            if plan:
                await show_plan_confirmation(callback.message, state, plan)
                await callback.answer(f"Selected {plan.value['name']} plan")
            else:
                await callback.answer("Invalid plan selection")
                
        elif data.startswith('upgrade_confirm|'):
            # Payment confirmation
            plan_id = data.split('|')[1]
            plan = next((p for p in PremiumPlan if p.value['id'] == plan_id), None)
            
            if not plan:
                await callback.answer("Invalid plan")
                return
            
            # Initiate upgrade
            result = await initiate_upgrade(user_id, plan)
            
            if result['success']:
                # Show payment instructions
                payment_url = result['authorization_url']
                reference = result['reference']
                
                payment_text = (
                    f"💳 *Payment Required*\n\n"
                    f"📋 *Order Summary:*\n"
                    f"• Plan: {hbold(plan.value['name'])}\n"
                    f"• Amount: {format_currency(plan.value['price_ngn'])}\n"
                    f"• Transaction: `{result['transaction_id']}`\n"
                    f"• Reference: `{reference}`\n\n"
                    f"🔗 *Complete Payment:*\n"
                    f"[Pay Now]({payment_url})\n\n"
                    f"⏰ *Payment expires in 30 minutes*\n\n"
                    f"✅ *After payment:* Use `/activate {result['transaction_id']}` to complete"
                )
                
                keyboard = types.InlineKeyboardMarkup()
                status_btn = types.InlineKeyboardButton("🔍 Check Status", callback_data=f"upgrade_status|{result['transaction_id']}")
                cancel_btn = types.InlineKeyboardButton("❌ Cancel", callback_data="upgrade_cancel")
                keyboard.add(status_btn, cancel_btn)
                
                await callback.message.edit_text(payment_text, parse_mode='Markdown', reply_markup=keyboard)
                await callback.answer("Payment initiated - complete via link above")
                
                # Store transaction in state
                await state.update_data(
                    pending_transaction=result['transaction_id'],
                    upgrade_plan=plan.value['id']
                )
            else:
                error_msg = result.get('error', 'Unknown error')
                await callback.message.edit_text(
                    f"❌ *Upgrade Failed*\n\n{error_msg}\n\nTry again with `/upgrade`",
                    parse_mode='Markdown'
                )
                await callback.answer("Upgrade initiation failed")
                
        elif data.startswith('upgrade_status|'):
            # Check payment status
            transaction_id = data.split('|')[1]
            result = await check_upgrade_status(user_id, transaction_id)
            
            if result['success'] and result['status'] == UpgradeStatus.COMPLETED.value:
                # Success - show completion
                plan_name = next((p.value['name'] for p in PremiumPlan if p.value['id'] == result['plan']), 'Premium')
                notification = (
                    f"🎉 *Upgrade Complete!*\n\n"
                    f"✨ *Welcome to {plan_name} Premium!*\n\n"
                    f"✅ *Status:* Activated successfully\n"
                    f"💎 *Plan:* {plan_name}\n"
                    f"📅 *Active until:* {result['new_expiry']}\n\n"
                    f"🚀 *Start using premium features now!*\n"
                    f"📄 Upload a document or try `/help`"
                )
                
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                upload_btn = types.InlineKeyboardButton("📄 Try Document", callback_data="upgrade_try_now")
                help_btn = types.InlineKeyboardButton("📖 Commands", callback_data="upgrade_help")
                keyboard.add(upload_btn, help_btn)
                
                await callback.message.edit_text(notification, parse_mode='Markdown', reply_markup=keyboard)
                await callback.answer("Upgrade completed! 🎉")
                
                # Send detailed notification
                await send_upgrade_status_notification(callback.bot, user_id, result)
                
            elif result['success'] and result['status'] in [UpgradeStatus.PENDING.value, UpgradeStatus.PROCESSING.value]:
                status_text = "⏳ Processing" if result['status'] == UpgradeStatus.PROCESSING.value else "⏳ Pending"
                await callback.message.edit_text(
                    f"🔄 *{status_text}*\n\n"
                    f"Transaction: `{result['transaction_id']}`\n"
                    f"Amount: {format_currency(result['amount'])}\n\n"
                    f"⏰ Please wait 1-2 minutes, then use `/activate {result['transaction_id']}`",
                    parse_mode='Markdown'
                )
                await callback.answer(f"Status: {status_text.lower()}")
                
            else:
                # Failed or cancelled
                await callback.message.edit_text(
                    f"❌ *{result.get('status', 'Failed').title()}\n\n"
                    f"{result.get('error', 'Unknown error')}\n\n"
                    f"Try again with `/upgrade`",
                    parse_mode='Markdown'
                )
                await callback.answer("Upgrade failed")
                
        elif data == 'upgrade_cancel':
            # Cancel upgrade
            state_data = await state.get_data()
            pending_txn = state_data.get('pending_transaction')
            
            if pending_txn:
                cancel_result = await cancel_pending_upgrade(user_id, pending_txn)
                status_text = "cancelled" if cancel_result['success'] else "failed to cancel"
            else:
                status_text = "nothing to cancel"
            
            await callback.message.edit_text(
                f"⏹️ *Upgrade Cancelled*\n\n"
                f"Status: {status_text}\n\n"
                f"💎 You can try again anytime with `/upgrade`",
                parse_mode='Markdown'
            )
            await callback.answer("Upgrade cancelled")
            
        elif data in ['upgrade_try_now', 'upgrade_help']:
            # Post-upgrade actions
            if data == 'upgrade_try_now':
                await callback.message.edit_text(
                    "📄 *Ready to try Premium?*\n\n"
                    "Simply send me any document file and experience the premium AI analysis!\n\n"
                    "💡 *Supported:* PDF, DOCX, Images, Text files\n\n"
                    "⚡ *Premium perks:* Faster processing, deeper insights, unlimited uploads",
                    parse_mode='Markdown'
                )
            else:
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
            
        await state.finish()  # Clear upgrade state
        
    except Exception as e:
        logger.error("Upgrade callback handler error", exc_info=True, extra={
            'user_id': user_id,
            'callback_data': data,
            'error': str(e)
        })
        await callback.answer("Something went wrong. Use /upgrade to try again.")

async def check_upgrade_status(user_id: int, transaction_id: str) -> Dict[str, Any]:
    """Check current upgrade status."""
    try:
        # Get transaction status
        transaction = await payment_orchestrator.get_transaction(transaction_id)
        if not transaction:
            return {
                'success': False,
                'error': 'Transaction not found',
                'status': UpgradeStatus.FAILED.value
            }
        
        # Map payment status to upgrade status
        status_map = {
            PaymentStatus.PENDING.value: UpgradeStatus.PENDING.value,
            PaymentStatus.INITIALIZED.value: UpgradeStatus.PROCESSING.value,
            PaymentStatus.PROCESSING.value: UpgradeStatus.VERIFYING.value,
            PaymentStatus.SUCCESS.value: UpgradeStatus.COMPLETED.value,
            PaymentStatus.FAILED.value: UpgradeStatus.FAILED.value,
            PaymentStatus.CANCELLED.value: UpgradeStatus.CANCELLED.value
        }
        
        upgrade_status = status_map.get(transaction.status.value, UpgradeStatus.FAILED.value)
        
        # If completed, verify premium activation
        plan = None
        new_expiry = None
        if upgrade_status == UpgradeStatus.COMPLETED.value:
            upgrade_state = await get_upgrade_state(user_id, transaction_id)
            if upgrade_state:
                plan_id = upgrade_state.get('plan')
                plan = next((p for p in PremiumPlan if p.value['id'] == plan_id), None)
                
                # Check if premium is actually active
                premium_data = await get_premium_data(user_id)
                if premium_data.get('status') == PremiumStatus.ACTIVE.value:
                    new_expiry = premium_data.get('expiry')
                else:
                    # Premium not activated - this is an error
                    upgrade_status = UpgradeStatus.FAILED.value
                    logger.error("Premium not activated after successful payment", extra={
                        'user_id': user_id,
                        'transaction_id': transaction_id
                    })
        
        result = {
            'success': True,
            'transaction_id': transaction_id,
            'status': upgrade_status,
            'amount': transaction.amount,
            'plan': plan.value['id'] if plan else None,
            'new_expiry': new_expiry
        }
        
        if upgrade_status == UpgradeStatus.COMPLETED.value:
            result['next_step'] = 'activated'
        elif upgrade_status in [UpgradeStatus.PENDING.value, UpgradeStatus.PROCESSING.value]:
            result['next_step'] = 'awaiting_payment'
        else:
            result['next_step'] = 'failed'
        
        logger.info("Upgrade status checked", extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'status': upgrade_status,
            'premium_active': new_expiry is not None
        })
        
        return result
        
    except Exception as e:
        logger.error("Failed to check upgrade status", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        return {
            'success': False,
            'error': 'Status check failed',
            'status': UpgradeStatus.FAILED.value
        }

async def activate_upgrade_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /activate command to complete upgrade."""
    user_id = message.from_user.id
    
    try:
        # Parse transaction ID
        command_parts = message.text.split()
        if len(command_parts) < 2:
            await message.reply(
                "❌ *Missing Transaction ID*\n\n"
                "Usage: `/activate <transaction_id>`\n\n"
                "Find your transaction ID in the payment confirmation message.",
                parse_mode='Markdown'
            )
            return
        
        transaction_id = command_parts[1].strip()
        
        # Get state data
        state_data = await state.get_data()
        pending_txn = state_data.get('pending_transaction', '')
        
        # Use provided ID or pending transaction
        txn_to_check = transaction_id if transaction_id != 'latest' else pending_txn
        
        if not txn_to_check:
            await message.reply(
                "❌ *No Transaction*\n\n"
                "No pending transaction found. Start with `/upgrade` or provide transaction ID.",
                parse_mode='Markdown'
            )
            return
        
        # Verify payment and activate
        upgrade_state = await get_upgrade_state(user_id, txn_to_check)
        if not upgrade_state:
            await message.reply(
                f"❌ *Expired Session*\n\n"
                f"The upgrade session for `{txn_to_check}` has expired.\n"
                f"Please start a new upgrade with `/upgrade`.",
                parse_mode='Markdown'
            )
            return
        
        plan_id = upgrade_state['plan']
        plan = next((p for p in PremiumPlan if p.value['id'] == plan_id), PremiumPlan.MONTHLY)
        expected_amount = plan.value['price_ngn']
        
        # Check status
        result = await check_upgrade_status(user_id, txn_to_check)
        
        if result['status'] == UpgradeStatus.COMPLETED.value:
            # Already completed
            await message.reply(
                f"✅ *Already Activated!*\n\n"
                f"Your {plan.value['name']} Premium is active!\n"
                f"📅 Expires: {result['new_expiry']}\n\n"
                f"🚀 Start using premium features now!",
                parse_mode='Markdown'
            )
            
        elif result['status'] in [UpgradeStatus.PENDING.value, UpgradeStatus.PROCESSING.value]:
            # Still processing
            await message.reply(
                f"⏳ *Processing Payment*\n\n"
                f"Transaction: `{txn_to_check}`\n"
                f"Status: {result['status'].replace('_', ' ').title()}\n\n"
                f"⏰ Please wait 1-2 minutes and try again.\n"
                f"If still pending, contact support.",
                parse_mode='Markdown'
            )
            
        else:
            # Verify and activate
            verification = await verify_upgrade_payment(user_id, txn_to_check, expected_amount)
            
            if verification['success']:
                # Success
                await send_upgrade_status_notification(message.bot, user_id, verification)
                
                success_msg = (
                    f"🎉 *Premium Activated!*\n\n"
                    f"✨ *Welcome to {plan.value['name']} Premium!*\n\n"
                    f"✅ Transaction: `{txn_to_check}`\n"
                    f"💎 Plan: {plan.value['name']}\n"
                    f"💰 Amount: {format_currency(expected_amount)}\n"
                    f"📅 Active until: {verification['new_expiry']}\n\n"
                    f"🚀 *Your premium features are ready!*\n"
                    f"📄 Try uploading a document now!"
                )
                
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                upload_btn = types.InlineKeyboardButton("📄 Try Document", callback_data="upgrade_try_now")
                help_btn = types.InlineKeyboardButton("📖 Premium Help", callback_data="upgrade_help")
                keyboard.add(upload_btn, help_btn)
                
                await message.reply(success_msg, parse_mode='Markdown', reply_markup=keyboard)
                await state.finish()
                
            else:
                # Failed verification
                error_msg = verification.get('error', 'Unknown verification error')
                await message.reply(
                    f"❌ *Activation Failed*\n\n"
                    f"Transaction: `{txn_to_check}`\n"
                    f"Error: {error_msg}\n\n"
                    f"💡 *Try:*\n"
                    f"• Check payment status\n"
                    f"• Contact support with transaction ID\n"
                    f"• Start new upgrade with `/upgrade`",
                    parse_mode='Markdown'
                )
                await handle_failed_upgrade(user_id, txn_to_check, error_msg)
    
    except Exception as e:
        logger.error("Activate upgrade handler error", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        await message.reply(
            f"❌ *Activation Error*\n\n"
            f"Something went wrong during activation.\n"
            f"Please try again or contact support.",
            parse_mode='Markdown'
        )

async def downgrade_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /downgrade command."""
    user_id = message.from_user.id
    
    try:
        # Check current status
        premium_data = await get_premium_data(user_id)
        
        if premium_data['status'] != PremiumStatus.ACTIVE.value:
            await message.reply(
                f"ℹ️ *No Active Subscription*\n\n"
                f"You're currently on the free plan.\n\n"
                f"💎 *Want premium?* Use `/upgrade` to get started!\n\n"
                f"Plans:\n"
                f"• Weekly: ₦1,000 (7 days)\n"
                f"• Monthly: ₦3,500 (30 days)",
                parse_mode='Markdown'
            )
            return
        
        # Show confirmation
        from premium import downgrade_premium_handler
        await downgrade_premium_handler(message, state)
        
        # Track downgrade
        await stats_tracker.track_user_activity(
            user_id,
            f"{StatType.PREMIUM_UPGRADE.value}:downgrade",
            {'current_plan': premium_data.get('plan', 'unknown')}
        )
        
    except Exception as e:
        logger.error("Downgrade command handler error", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        await message.reply(
            f"❌ *Downgrade Error*\n\n"
            f"Unable to process downgrade request.\n"
            f"Please try again or contact support.",
            parse_mode='Markdown'
        )

async def cancel_pending_upgrade(user_id: int, transaction_id: str) -> Dict[str, Any]:
    """Cancel pending upgrade."""
    try:
        # Update transaction status
        await payment_orchestrator.update_transaction_status(
            transaction_id,
            PaymentStatus.CANCELLED,
            {'cancelled_by': 'user', 'cancelled_at': datetime.utcnow().isoformat()}
        )
        
        # Clean up state
        await cleanup_upgrade_state(user_id, transaction_id, 0)  # Immediate cleanup
        
        # Track cancellation
        await stats_tracker.track_user_activity(
            user_id,
            f"{StatType.PREMIUM_UPGRADE.value}:cancelled",
            {'transaction_id': transaction_id}
        )
        
        logger.info("Pending upgrade cancelled", extra={
            'user_id': user_id,
            'transaction_id': transaction_id
        })
        
        return {'success': True, 'transaction_id': transaction_id}
        
    except Exception as e:
        logger.error("Failed to cancel pending upgrade", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        return {'success': False, 'error': str(e)}

def format_currency(amount: float) -> str:
    """Format Naira currency."""
    return f"₦{amount:,.0f}"

def register_upgrade_handlers(dp: Dispatcher) -> None:
    """Register all upgrade handlers."""
    # Main commands
    dp.register_message_handler(upgrade_command_handler, Command("upgrade"), state="*")
    dp.register_message_handler(activate_upgrade_handler, Command("activate"), state="*")
    dp.register_message_handler(downgrade_command_handler, Command("downgrade"), state="*")
    
    # Callback handlers
    from callbacks import process_callback_query
    original_process = process_callback_query
    
    async def enhanced_upgrade_callback(callback: types.CallbackQuery, state: FSMContext):
        """Enhanced callback handler for upgrades."""
        if callback.data and callback.data.startswith('upgrade_'):
            await handle_upgrade_callbacks(callback, state)
            return
        
        # Original processing
        await original_process(callback, state)
    
    # Monkey patch
    import callbacks
    if not hasattr(callbacks, 'original_callback_process'):
        callbacks.original_callback_process = original_process
    callbacks.process_callback_query = enhanced_upgrade_callback
    
    logger.info("Upgrade handlers registered with rollback protection")

__all__ = [
    'initiate_upgrade', 'verify_upgrade_payment', 'handle_failed_upgrade',
    'handle_upgrade_rollback', 'UpgradeStatus', 'UpgradeRollbackContext',
    'register_upgrade_handlers', 'format_currency'
]
