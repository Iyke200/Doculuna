# payments.py
import logging
import json
import hashlib
import hmac
import time
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType
from aiogram.utils.exceptions import RetryAfter
from dotenv import load_dotenv
import aiohttp
import asyncio

# Assuming Redis for transaction storage (fallback to in-memory)
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict
    transaction_store = defaultdict(dict)
    webhook_pending = defaultdict(list)
    REDIS_AVAILABLE = False

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - transaction_id=%(transaction_id)s - status=%(status)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PaymentStatus(Enum):
    """Transaction status tracking."""
    PENDING = "pending"
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

@dataclass
class Transaction:
    """Transaction data structure."""
    transaction_id: str
    user_id: int
    amount: float
    currency: str
    gateway: str
    status: PaymentStatus
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    webhook_received: bool = False
    retry_count: int = 0

class PaymentGateway(ABC):
    """Abstract base class for payment gateways."""
    
    @abstractmethod
    async def initialize_payment(self, transaction: Transaction) -> Dict[str, Any]:
        """Initialize payment with gateway-specific logic."""
        pass
    
    @abstractmethod
    async def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Verify transaction status with gateway."""
        pass
    
    @abstractmethod
    def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """Validate incoming webhook signature."""
        pass

class PaymentOrchestrator:
    """Abstract payment orchestration layer."""
    
    def __init__(self):
        self.gateways: Dict[str, PaymentGateway] = {}
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
    def register_gateway(self, gateway_name: str, gateway: PaymentGateway) -> None:
        """Register a payment gateway."""
        self.gateways[gateway_name] = gateway
        logger.info("Payment gateway registered", extra={
            'gateway': gateway_name
        })
    
    async def create_transaction(self, user_id: int, amount: float, 
                               currency: str = "USD", gateway: str = "paystack") -> Transaction:
        """Create and initialize a new transaction."""
        transaction_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        transaction = Transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=amount,
            currency=currency,
            gateway=gateway,
            status=PaymentStatus.PENDING,
            metadata={},
            created_at=now,
            updated_at=now
        )
        
        # Store transaction
        await self._store_transaction(transaction)
        
        # Initialize with gateway
        try:
            gateway_instance = self.gateways.get(gateway)
            if not gateway_instance:
                raise ValueError(f"Gateway {gateway} not registered")
            
            init_result = await gateway_instance.initialize_payment(transaction)
            transaction.metadata.update(init_result)
            transaction.status = PaymentStatus.INITIALIZED
            transaction.updated_at = now
            
            await self._store_transaction(transaction)
            
            logger.info("Transaction created", extra={
                'user_id': user_id,
                'transaction_id': transaction_id,
                'amount': amount,
                'gateway': gateway,
                'status': transaction.status.value
            })
            
        except Exception as e:
            transaction.status = PaymentStatus.FAILED
            transaction.updated_at = now
            await self._store_transaction(transaction)
            
            logger.error("Transaction creation failed", exc_info=True, extra={
                'user_id': user_id,
                'transaction_id': transaction_id,
                'error': str(e)
            })
            raise
        
        return transaction
    
    async def update_transaction_status(self, transaction_id: str, 
                                      new_status: PaymentStatus, 
                                      metadata: Dict[str, Any] = None) -> bool:
        """Update transaction status with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                transaction = await self._get_transaction(transaction_id)
                if not transaction:
                    logger.warning("Transaction not found", extra={
                        'transaction_id': transaction_id
                    })
                    return False
                
                transaction.status = new_status
                transaction.updated_at = datetime.utcnow()
                if metadata:
                    transaction.metadata.update(metadata)
                
                await self._store_transaction(transaction)
                
                logger.info("Transaction status updated", extra={
                    'transaction_id': transaction_id,
                    'status': new_status.value,
                    'attempt': attempt + 1
                })
                
                return True
                
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error("Failed to update transaction after retries", exc_info=True, extra={
                        'transaction_id': transaction_id,
                        'status': new_status.value,
                        'error': str(e)
                    })
                    return False
                
                await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
    
    async def verify_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Verify transaction status with gateway."""
        try:
            transaction = await self._get_transaction(transaction_id)
            if not transaction:
                return None
            
            gateway_instance = self.gateways.get(transaction.gateway)
            if not gateway_instance:
                logger.error("Gateway not found for verification", extra={
                    'transaction_id': transaction_id,
                    'gateway': transaction.gateway
                })
                return transaction
            
            verification = await gateway_instance.verify_transaction(transaction_id)
            
            # Update status based on verification
            if verification.get('status') == 'success':
                await self.update_transaction_status(transaction_id, PaymentStatus.SUCCESS, verification)
            elif verification.get('status') == 'failed':
                await self.update_transaction_status(transaction_id, PaymentStatus.FAILED, verification)
            
            return await self._get_transaction(transaction_id)
            
        except Exception as e:
            logger.error("Transaction verification failed", exc_info=True, extra={
                'transaction_id': transaction_id,
                'error': str(e)
            })
            return await self._get_transaction(transaction_id)
    
    async def handle_webhook(self, gateway: str, payload: Dict[str, Any], 
                           signature: str = None) -> bool:
        """Process incoming webhook with signature validation."""
        try:
            # Validate signature
            gateway_instance = self.gateways.get(gateway)
            if not gateway_instance or not gateway_instance.validate_webhook(payload, signature):
                logger.error("Webhook signature validation failed", extra={
                    'gateway': gateway,
                    'transaction_id': payload.get('reference', 'unknown')
                })
                return False
            
            transaction_id = payload.get('reference') or payload.get('transaction_id')
            if not transaction_id:
                logger.error("Missing transaction ID in webhook", extra={
                    'gateway': gateway,
                    'payload_keys': list(payload.keys())
                })
                return False
            
            # Update transaction based on webhook data
            status_map = {
                'success': PaymentStatus.SUCCESS,
                'failed': PaymentStatus.FAILED,
                'cancelled': PaymentStatus.CANCELLED
            }
            
            webhook_status = payload.get('status', payload.get('event'))
            new_status = status_map.get(webhook_status, PaymentStatus.PROCESSING)
            
            metadata = {
                'webhook_received': True,
                'webhook_data': payload,
                'webhook_timestamp': datetime.utcnow().isoformat()
            }
            
            success = await self.update_transaction_status(transaction_id, new_status, metadata)
            
            if success:
                logger.info("Webhook processed successfully", extra={
                    'gateway': gateway,
                    'transaction_id': transaction_id,
                    'status': new_status.value
                })
            
            return success
            
        except Exception as e:
            logger.error("Webhook processing failed", exc_info=True, extra={
                'gateway': gateway,
                'transaction_id': payload.get('reference', 'unknown'),
                'error': str(e)
            })
            return False
    
    async def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Retrieve transaction by ID."""
        return await self._get_transaction(transaction_id)
    
    async def list_user_transactions(self, user_id: int, 
                                   limit: int = 10, offset: int = 0) -> List[Transaction]:
        """List transactions for a user."""
        if REDIS_AVAILABLE:
            # Redis pattern: transactions:user_id:*
            pattern = f"transaction:{user_id}:*"
            keys = redis_client.keys(pattern)
            if not keys:
                return []
            
            # Get latest transactions (reverse chronological)
            transaction_ids = sorted(keys, reverse=True)[offset:offset + limit]
            transactions = []
            
            for key in transaction_ids:
                transaction_data = redis_client.get(key)
                if transaction_data:
                    transaction = Transaction(**json.loads(transaction_data))
                    transactions.append(transaction)
            
            return transactions
        else:
            # In-memory fallback
            user_transactions = [
                t for t in transaction_store.values() 
                if hasattr(t, 'user_id') and t.user_id == user_id
            ]
            return sorted(user_transactions, key=lambda x: x.updated_at, reverse=True)[offset:offset + limit]
    
    async def _store_transaction(self, transaction: Transaction) -> None:
        """Internal: Store transaction in persistence layer."""
        transaction_key = f"transaction:{transaction.user_id}:{transaction.transaction_id}"
        transaction_data = {
            'transaction_id': transaction.transaction_id,
            'user_id': transaction.user_id,
            'amount': transaction.amount,
            'currency': transaction.currency,
            'gateway': transaction.gateway,
            'status': transaction.status.value,
            'metadata': transaction.metadata,
            'created_at': transaction.created_at.isoformat(),
            'updated_at': transaction.updated_at.isoformat(),
            'webhook_received': transaction.webhook_received,
            'retry_count': transaction.retry_count
        }
        
        if REDIS_AVAILABLE:
            # Set with 7-day expiration
            redis_client.setex(transaction_key, 604800, json.dumps(transaction_data))
        else:
            transaction_store[transaction_key] = transaction
    
    async def _get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Internal: Retrieve transaction from persistence layer."""
        # First try to find by transaction_id across all users
        if REDIS_AVAILABLE:
            pattern = f"transaction:*:*"
            keys = redis_client.keys(pattern)
            for key in keys:
                if transaction_id in key:
                    data = redis_client.get(key)
                    if data:
                        transaction_dict = json.loads(data)
                        return Transaction(**transaction_dict)
            return None
        else:
            for key, transaction in transaction_store.items():
                if hasattr(transaction, 'transaction_id') and transaction.transaction_id == transaction_id:
                    return transaction
            return None

# Global orchestrator instance
payment_orchestrator = PaymentOrchestrator()

async def process_payment_message(message: types.Message, state: FSMContext) -> None:
    """Handle payment initiation via message commands."""
    user_id = message.from_user.id
    
    # Input validation
    try:
        amount_str = message.text.replace("/pay", "").strip()
        if not amount_str:
            await message.reply(
                "💳 *Payment Options*\n\n"
                "Usage: `/pay <amount>`\n\n"
                "Example: `/pay 25.99`\n\n"
                "*Supported currencies: USD*",
                parse_mode='Markdown'
            )
            return
        
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if amount > 10000:  # Reasonable limit
            await message.reply("❌ Maximum payment amount exceeded.")
            return
            
    except ValueError:
        await message.reply("❌ Please enter a valid amount (e.g., `/pay 25.99`)")
        return
    
    try:
        # Create transaction
        transaction = await payment_orchestrator.create_transaction(
            user_id=user_id,
            amount=amount,
            currency="USD",
            gateway="paystack"  # Default gateway
        )
        
        # Store in FSM for callback handling
        await state.update_data(
            current_transaction=transaction.transaction_id,
            payment_amount=amount
        )
        
        # Send payment link or QR (gateway-specific)
        payment_url = transaction.metadata.get('authorization_url', f"https://pay.example.com/{transaction.transaction_id}")
        
        response = (
            f"💳 *Payment Initiated*\n\n"
            f"Amount: *${amount}*\n"
            f"Transaction: `{transaction.transaction_id}`\n\n"
            f"Click below to complete payment:\n"
            f"[Pay Now]({payment_url})\n\n"
            f"⏰ *Payment expires in 15 minutes*"
        )
        
        # Add inline keyboard for status check
        from callbacks import create_confirmation_keyboard
        status_callback = f"check_status|{int(time.time())}|{user_id}|status_{transaction.transaction_id}"
        keyboard = create_confirmation_keyboard("Check Status", status_callback)
        
        await message.reply(response, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=True)
        
    except Exception as e:
        logger.error("Payment initiation failed", exc_info=True, extra={
            'user_id': user_id,
            'amount': amount_str,
            'error': str(e)
        })
        await message.reply("❌ Payment initiation failed. Please try again.")

async def check_payment_status(message: types.Message, state: FSMContext) -> None:
    """Check payment status via command or callback."""
    user_id = message.from_user.id
    state_data = await state.get_data()
    transaction_id = state_data.get('current_transaction')
    
    if not transaction_id:
        await message.reply("❌ No active transaction found. Start a new payment with `/pay <amount>`")
        return
    
    try:
        transaction = await payment_orchestrator.get_transaction(transaction_id)
        if not transaction:
            await message.reply("❌ Transaction not found.")
            return
        
        status_text = {
            PaymentStatus.PENDING: "⏳ Pending",
            PaymentStatus.INITIALIZED: "🔄 Processing",
            PaymentStatus.PROCESSING: "🔄 Processing", 
            PaymentStatus.SUCCESS: "✅ Completed",
            PaymentStatus.FAILED: "❌ Failed",
            PaymentStatus.EXPIRED: "⏰ Expired",
            PaymentStatus.CANCELLED: "❌ Cancelled"
        }.get(transaction.status, "❓ Unknown")
        
        response = (
            f"💳 *Transaction Status*\n\n"
            f"ID: `{transaction.transaction_id}`\n"
            f"Amount: *${transaction.amount}*\n"
            f"Status: {status_text}\n"
            f"Date: {transaction.updated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        
        if transaction.status == PaymentStatus.SUCCESS:
            response += "🎉 Payment successful! Your premium features are now active."
            await state.finish()
        elif transaction.status in [PaymentStatus.FAILED, PaymentStatus.EXPIRED, PaymentStatus.CANCELLED]:
            response += "💡 Start a new payment with `/pay <amount>`"
            await state.finish()
        
        await message.reply(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("Status check failed", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        await message.reply("❌ Unable to check status. Please try again.")

async def webhook_handler(request: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP webhook endpoint handler (for external webhook server)."""
    try:
        # Extract gateway from URL path or headers
        gateway = request.get('path', '').split('/')[-1] or 'paystack'
        payload = request.get('json', {})
        signature = request.get('headers', {}).get('x-paystack-signature')
        
        success = await payment_orchestrator.handle_webhook(gateway, payload, signature)
        
        if success:
            return {'statusCode': 200, 'body': json.dumps({'status': 'success'})}
        else:
            return {'statusCode': 400, 'body': json.dumps({'status': 'validation_failed'})}
            
    except Exception as e:
        logger.error("Webhook handler error", exc_info=True, extra={
            'gateway': gateway,
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'status': 'internal_error'})}

def register_payment_handlers(dp: Dispatcher) -> None:
    """Register payment-related handlers."""
    dp.register_message_handler(
        process_payment_message,
        commands=['pay'],
        state="*"
    )
    
    dp.register_message_handler(
        check_payment_status,
        commands=['status'],
        state="*"
    )

# Export orchestrator for gateway registration
__all__ = ['payment_orchestrator', 'PaymentGateway', 'PaymentStatus', 'Transaction', 'register_payment_handlers']
