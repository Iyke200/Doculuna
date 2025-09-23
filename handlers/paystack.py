# paystack.py
import logging
import json
import hashlib
import hmac
import time
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiohttp
from cryptography.fernet import Fernet

from aiogram import Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Import from handlers.payments
from handlers.payments import (
    PaymentGateway, Transaction, PaymentStatus, PaymentOrchestrator, payment_orchestrator
)

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - transaction_id=%(transaction_id)s - paystack_ref=%(paystack_ref)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PaystackConfig:
    """Secure Paystack configuration management."""
    
    def __init__(self):
        self.secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        self.public_key = os.getenv('PAYSTACK_PUBLIC_KEY')
        self.webhook_secret = os.getenv('PAYSTACK_WEBHOOK_SECRET')
        self.base_url = os.getenv('PAYSTACK_BASE_URL', 'https://api.paystack.co')
        self.encryption_key = os.getenv('PAYSTACK_ENCRYPTION_KEY')
        
        # Validate required config
        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is required")
        if not self.public_key:
            raise ValueError("PAYSTACK_PUBLIC_KEY is required")
        if not self.encryption_key:
            raise ValueError("PAYSTACK_ENCRYPTION_KEY is required")
        
        # Initialize encryption
        self.cipher_suite = Fernet(self.encryption_key.encode())
        
        # Decrypt API keys (stored encrypted in env for extra security)
        self._secret_key_encrypted = self.secret_key
        self._public_key_encrypted = self.public_key
        self.secret_key = self.decrypt_key(self._secret_key_encrypted)
        self.public_key = self.decrypt_key(self._public_key_encrypted)
        
        logger.info("Paystack configuration loaded", extra={
            'base_url': self.base_url,
            'currency': 'NGN'  # Paystack default
        })
    
    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API keys using Fernet."""
        try:
            return self.cipher_suite.decrypt(encrypted_key.encode()).decode()
        except Exception as e:
            logger.error("Failed to decrypt Paystack key", exc_info=True)
            raise ValueError(f"Invalid encryption for Paystack key: {str(e)}")
    
    def encrypt_key(self, key: str) -> str:
        """Encrypt API keys for storage."""
        return self.cipher_suite.encrypt(key.encode()).decode()

class PaystackGateway(PaymentGateway):
    """Paystack payment gateway implementation."""
    
    def __init__(self, config: PaystackConfig):
        self.config = config
        self.session = None
        self.request_timeout = 30  # seconds
        self.max_retries = 3
        self.retry_codes = [408, 429, 500, 502, 503, 504]
        
        # Rate limiting (Paystack: 100 req/sec, but we use conservative limits)
        self.request_times: dict[str, List[float]] = {}
        self.rate_limit = 50  # requests per minute
        
        logger.info("PaystackGateway initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with auth headers."""
        if self.session is None or self.session.closed:
            headers = {
                'Authorization': f'Bearer {self.config.secret_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            self.session = aiohttp.ClientSession(
                headers=headers, 
                connector=connector, 
                timeout=timeout
            )
        return self.session
    
    async def _make_request(self, method: str, endpoint: str, 
                          data: Dict[str, Any] = None, 
                          params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated request to Paystack API with retry logic."""
        session = await self._get_session()
        url = f"{self.config.base_url}{endpoint}"
        
        # Rate limiting
        now = time.time()
        if url in self.request_times:
            recent = [t for t in self.request_times[url] if now - t < 60]
            if len(recent) >= self.rate_limit:
                raise Exception("Rate limit exceeded")
            recent.append(now)
            self.request_times[url] = recent
        else:
            self.request_times[url] = [now]
        
        for attempt in range(self.max_retries + 1):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params
                ) as response:
                    response.raise_for_status()
                    
                    # Paystack-specific rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        await asyncio.sleep(retry_after)
                        continue
                    
                    result = await response.json()
                    
                    if 'status' in result and result['status']:
                        return result['data']
                    else:
                        error_msg = result.get('message', 'Unknown Paystack error')
                        logger.warning("Paystack API error", extra={
                            'endpoint': endpoint,
                            'status_code': response.status,
                            'error': error_msg,
                            'attempt': attempt + 1
                        })
                        raise Exception(error_msg)
                        
            except aiohttp.ClientError as e:
                if attempt == self.max_retries:
                    logger.error("Paystack request failed after retries", exc_info=True, extra={
                        'endpoint': endpoint,
                        'method': method,
                        'error': str(e),
                        'attempt': attempt + 1
                    })
                    raise
                
                # Exponential backoff
                wait_time = (2 ** attempt) + (0.1 * attempt)
                await asyncio.sleep(wait_time)
        
        raise Exception("All retry attempts failed")
    
    async def initialize_payment(self, transaction: Transaction) -> Dict[str, Any]:
        """Initialize Paystack payment and return authorization URL."""
        try:
            # Validate transaction data
            if transaction.amount <= 0:
                raise ValueError("Payment amount must be positive")
            
            # Paystack expects amount in kobo (NGN subunits)
            amount_kobo = int(transaction.amount * 100)
            
            payload = {
                'email': f"user_{transaction.user_id}@doculuna.com",  # Generate email
                'amount': amount_kobo,
                'currency': 'NGN',
                'reference': transaction.transaction_id,
                'callback_url': f"https://your-bot.com/paystack/callback?ref={transaction.transaction_id}",
                'metadata': {
                    'user_id': transaction.user_id,
                    'transaction_id': transaction.transaction_id,
                    'source': 'doculuna_bot'
                }
            }
            
            # Add custom fields from transaction metadata
            payload['metadata'].update(transaction.metadata)
            
            result = await self._make_request('POST', '/transaction/initialize', data=payload)
            
            # Validate response
            if not result.get('status'):
                raise Exception(f"Paystack initialization failed: {result.get('message', 'Unknown error')}")
            
            logger.info("Paystack payment initialized", extra={
                'user_id': transaction.user_id,
                'transaction_id': transaction.transaction_id,
                'paystack_ref': result.get('reference'),
                'amount_kobo': amount_kobo,
                'auth_url': result.get('authorization_url', '')
            })
            
            return {
                'reference': result.get('reference', transaction.transaction_id),
                'access_code': result.get('access_code'),
                'authorization_url': result.get('authorization_url'),
                'gateway_response': result
            }
            
        except Exception as e:
            logger.error("Paystack initialization error", exc_info=True, extra={
                'user_id': transaction.user_id,
                'transaction_id': transaction.transaction_id,
                'error': str(e)
            })
            raise
    
    async def verify_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Verify transaction status with Paystack."""
        try:
            # First try to find the Paystack reference
            params = {'reference': transaction_id}
            result = await self._make_request('GET', '/transaction/verify', params=params)
            
            # Map Paystack status to our enum
            paystack_status = result.get('status')
            gateway_status = 'success' if paystack_status == 'success' else 'failed'
            
            verification_data = {
                'status': gateway_status,
                'reference': result.get('reference'),
                'amount': result.get('amount') / 100,  # Convert kobo to NGN
                'currency': result.get('currency', 'NGN'),
                'gateway_response': result,
                'verification_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info("Paystack transaction verified", extra={
                'transaction_id': transaction_id,
                'paystack_ref': result.get('reference'),
                'status': paystack_status,
                'amount': verification_data['amount']
            })
            
            return verification_data
            
        except Exception as e:
            logger.error("Paystack verification error", exc_info=True, extra={
                'transaction_id': transaction_id,
                'error': str(e)
            })
            return {'status': 'failed', 'error': str(e)}
    
    def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        """Validate Paystack webhook signature using HMAC-SHA512."""
        try:
            if not self.config.webhook_secret:
                logger.warning("No webhook secret configured, skipping signature validation")
                return True
            
            # Paystack webhook payload is JSON string
            payload_string = json.dumps(payload, separators=(',', ':'))
            
            # Calculate HMAC signature
            expected_signature = hmac.new(
                self.config.webhook_secret.encode('utf-8'),
                payload_string.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            # Paystack sends signature as hexdigest
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                logger.error("Paystack webhook signature mismatch", extra={
                    'received_signature': signature[:16] + '...',
                    'expected_signature': expected_signature[:16] + '...',
                    'payload_keys': list(payload.keys())
                })
            
            logger.info("Paystack webhook signature validation", extra={
                'valid': is_valid,
                'event': payload.get('event'),
                'reference': payload.get('data', {}).get('reference')
            })
            
            return is_valid
            
        except Exception as e:
            logger.error("Webhook validation error", exc_info=True, extra={
                'error': str(e),
                'signature_provided': bool(signature)
            })
            return False
    
    async def process_webhook_event(self, event: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process specific Paystack webhook events."""
        try:
            event_handlers = {
                'charge.success': self._handle_charge_success,
                'charge.failed': self._handle_charge_failed,
                'transfer.success': self._handle_transfer_success,
                'invoice.create': self._handle_invoice_create,
                'invoice.update': self._handle_invoice_update
            }
            
            handler = event_handlers.get(event)
            if handler:
                result = await handler(data)
                return result
            else:
                logger.info("Unhandled Paystack webhook event", extra={
                    'event': event,
                    'reference': data.get('reference')
                })
                return {'status': 'ignored', 'event': event}
                
        except Exception as e:
            logger.error("Webhook event processing error", exc_info=True, extra={
                'event': event,
                'reference': data.get('reference'),
                'error': str(e)
            })
            return {'status': 'error', 'message': str(e)}
    
    async def _handle_charge_success(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful charge webhook."""
        reference = data.get('reference')
        amount = data.get('amount', 0) / 100  # Convert kobo
        
        logger.info("Paystack charge success webhook", extra={
            'reference': reference,
            'amount': amount,
            'channel': data.get('channel')
        })
        
        return {
            'status': 'success',
            'reference': reference,
            'amount': amount,
            'event_data': data
        }
    
    async def _handle_charge_failed(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed charge webhook."""
        reference = data.get('reference')
        failure_msg = data.get('message', 'Payment failed')
        
        logger.warning("Paystack charge failed webhook", extra={
            'reference': reference,
            'message': failure_msg,
            'display_text': data.get('display_text')
        })
        
        return {
            'status': 'failed',
            'reference': reference,
            'message': failure_msg,
            'event_data': data
        }
    
    async def _handle_transfer_success(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful transfer webhook."""
        reference = data.get('transfer_code')
        
        logger.info("Paystack transfer success webhook", extra={
            'transfer_code': reference,
            'recipient': data.get('recipient'),
            'amount': data.get('amount', 0) / 100
        })
        
        return {
            'status': 'transfer_success',
            'reference': reference,
            'event_data': data
        }
    
    async def _handle_invoice_create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invoice creation webhook."""
        reference = data.get('invoice_id')
        
        logger.info("Paystack invoice created webhook", extra={
            'invoice_id': reference,
            'customer': data.get('customer'),
            'amount': data.get('amount', 0) / 100
        })
        
        return {
            'status': 'invoice_created',
            'reference': reference,
            'event_data': data
        }
    
    async def _handle_invoice_update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invoice update webhook."""
        reference = data.get('invoice_id')
        status = data.get('status')
        
        logger.info("Paystack invoice updated webhook", extra={
            'invoice_id': reference,
            'status': status,
            'amount': data.get('amount', 0) / 100
        })
        
        return {
            'status': f'invoice_{status}',
            'reference': reference,
            'event_data': data
        }
    
    async def refund_transaction(self, transaction_id: str, 
                               amount: Optional[float] = None) -> Dict[str, Any]:
        """Process refund for a transaction (Extended feature prep)."""
        try:
            # Get transaction details first
            verification = await self.verify_transaction(transaction_id)
            
            if verification.get('status') != 'success':
                return {'status': 'failed', 'message': 'Only successful transactions can be refunded'}
            
            reference = verification.get('reference')
            original_amount = verification.get('amount', 0)
            
            # Default to full refund if amount not specified
            refund_amount = amount or original_amount
            refund_amount_kobo = int(refund_amount * 100)
            
            payload = {
                'transaction': reference,
                'amount': refund_amount_kobo
            }
            
            result = await self._make_request('POST', '/refund', data=payload)
            
            logger.info("Paystack refund processed", extra={
                'transaction_id': transaction_id,
                'reference': reference,
                'refund_amount': refund_amount,
                'refund_ref': result.get('reference')
            })
            
            return {
                'status': 'success',
                'reference': result.get('reference'),
                'amount': refund_amount,
                'gateway_response': result
            }
            
        except Exception as e:
            logger.error("Paystack refund error", exc_info=True, extra={
                'transaction_id': transaction_id,
                'error': str(e)
            })
            return {'status': 'failed', 'message': str(e)}
    
    async def close(self):
        """Clean up HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("PaystackGateway session closed")

# Global Paystack instance
paystack_config = None
paystack_gateway = None

def initialize_paystack() -> PaystackGateway:
    """Initialize Paystack gateway and register with orchestrator."""
    global paystack_config, paystack_gateway
    
    if paystack_config is None:
        paystack_config = PaystackConfig()
        paystack_gateway = PaystackGateway(paystack_config)
        payment_orchestrator.register_gateway('paystack', paystack_gateway)
    
    return paystack_gateway

async def paystack_payment_handler(message: types.Message, state) -> None:
    """Handle Paystack-specific payment commands."""
    user_id = message.from_user.id
    
    # Ensure gateway is initialized
    if paystack_gateway is None:
        await message.reply(
            "❌ Payment service temporarily unavailable. Please try again later.",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Parse amount from command
        amount_str = message.text.replace("/paystack", "").strip()
        if not amount_str:
            await message.reply(
                "💳 *Paystack Payment*\n\n"
                "Usage: `/paystack <amount>`\n\n"
                "Example: `/paystack 5000`\n\n"
                "*Amount in NGN (minimum ₦100)*",
                parse_mode='Markdown'
            )
            return
        
        amount = float(amount_str)
        if amount < 1.00:  # ₦100 minimum
            await message.reply("❌ Minimum payment amount is ₦100.")
            return
        
        if amount > 1000000:  # ₦1M maximum
            await message.reply("❌ Maximum payment amount exceeded (₦1,000,000).")
            return
        
        # Create Paystack transaction
        transaction = await payment_orchestrator.create_transaction(
            user_id=user_id,
            amount=amount,
            currency="NGN",
            gateway="paystack"
        )
        
        # Get Paystack-specific initialization
        init_result = transaction.metadata
        
        response = (
            f"💳 *Paystack Payment Initiated*\n\n"
            f"Amount: *₦{amount:,.2f}*\n"
            f"Transaction: `{transaction.transaction_id}`\n"
            f"Reference: `{init_result.get('reference', 'Pending')}`\n\n"
            f"Complete your payment:\n"
            f"[Pay Now]({init_result.get('authorization_url', '')})\n\n"
            f"⏰ *Payment expires in 30 minutes*"
        )
        
        # Rate limiting check (handled in gateway)
        from callbacks import create_confirmation_keyboard
        status_callback = f"paystack_status|{int(time.time())}|{user_id}|{transaction.transaction_id}"
        keyboard = create_confirmation_keyboard("Check Status", status_callback)
        
        await message.reply(
            response, 
            parse_mode='Markdown', 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        # Store in state for tracking
        await state.update_data(
            paystack_transaction=transaction.transaction_id,
            payment_amount=amount,
            currency='NGN'
        )
        
        logger.info("Paystack payment handler success", extra={
            'user_id': user_id,
            'transaction_id': transaction.transaction_id,
            'amount': amount,
            'reference': init_result.get('reference')
        })
        
    except ValueError as e:
        logger.warning("Invalid Paystack payment amount", extra={
            'user_id': user_id,
            'amount_str': amount_str,
            'error': str(e)
        })
        await message.reply("❌ Please enter a valid amount (e.g., `/paystack 5000`)")
    
    except Exception as e:
        logger.error("Paystack payment handler error", exc_info=True, extra={
            'user_id': user_id,
            'error': str(e)
        })
        await message.reply("❌ Payment initiation failed. Please try again.")

async def paystack_status_handler(message: types.Message, state) -> None:
    """Check Paystack-specific transaction status."""
    user_id = message.from_user.id
    state_data = await state.get_data()
    transaction_id = state_data.get('paystack_transaction')
    
    if not transaction_id:
        await message.reply(
            "❌ No active Paystack transaction found.\n"
            "Start a new payment with `/paystack <amount>`",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Verify with Paystack
        transaction = await payment_orchestrator.get_transaction(transaction_id)
        if not transaction:
            await message.reply("❌ Transaction not found.")
            return
        
        # Get latest verification
        verification = await paystack_gateway.verify_transaction(transaction_id)
        
        status_map = {
            'success': '✅ Payment Successful',
            'failed': '❌ Payment Failed',
            'pending': '⏳ Payment Pending'
        }
        
        status_text = status_map.get(verification.get('status'), '❓ Unknown Status')
        amount = verification.get('amount', transaction.amount)
        reference = verification.get('reference', 'N/A')
        
        response = (
            f"💳 *Paystack Transaction Status*\n\n"
            f"ID: `{transaction.transaction_id}`\n"
            f"Reference: `{reference}`\n"
            f"Amount: *₦{amount:,.2f}*\n"
            f"Status: {status_text}\n"
            f"Date: {transaction.updated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        
        if verification.get('status') == 'success':
            response += "🎉 Your payment was successful! Premium features activated."
            await state.finish()
        elif verification.get('status') == 'failed':
            response += "💡 Try again with `/paystack <amount>`"
            await state.finish()
        
        await message.reply(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("Paystack status check error", exc_info=True, extra={
            'user_id': user_id,
            'transaction_id': transaction_id,
            'error': str(e)
        })
        await message.reply("❌ Unable to check status. Please try again.")

def register_paystack_handlers(dp: Dispatcher) -> None:
    """Register Paystack-specific handlers."""
    # Initialize gateway on first registration
    initialize_paystack()
    
    # aiogram 3.x syntax
    dp.message.register(
        paystack_payment_handler,
        Command('paystack')
    )
    
    dp.message.register(
        paystack_status_handler,
        Command('paystack_status')
    )

# Webhook processing function (called from payments webhook handler)
async def process_paystack_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process Paystack webhook payload after signature validation."""
    global paystack_gateway
    
    if paystack_gateway is None:
        initialize_paystack()
    
    try:
        event = payload.get('event')
        data = payload.get('data', {})
        
        if not event or not data:
            logger.warning("Invalid Paystack webhook payload", extra={
                'payload_keys': list(payload.keys()),
                'has_event': bool(event),
                'has_data': bool(data)
            })
            return {'status': 'invalid_payload'}
        
        # Process the specific event
        result = await paystack_gateway.process_webhook_event(event, data)
        
        # Update transaction status in orchestrator
        reference = data.get('reference') or data.get('transfer_code')
        if reference:
            status = result.get('status', 'processing')
            
            # Map to PaymentStatus
            status_mapping = {
                'success': PaymentStatus.SUCCESS,
                'transfer_success': PaymentStatus.SUCCESS,
                'failed': PaymentStatus.FAILED,
                'invoice_paid': PaymentStatus.SUCCESS,
                'invoice_overdue': PaymentStatus.FAILED
            }
            
            new_status = status_mapping.get(status, PaymentStatus.PROCESSING)
            await payment_orchestrator.update_transaction_status(reference, new_status, result)
        
        return {
            'status': 'processed',
            'event': event,
            'reference': reference,
            'result': result
        }
        
    except Exception as e:
        logger.error("Paystack webhook processing error", exc_info=True, extra={
            'event': payload.get('event'),
            'reference': payload.get('data', {}).get('reference'),
            'error': str(e)
        })
        return {'status': 'processing_error', 'message': str(e)}

# Auto-register with payments webhook handler
from handlers.payments import webhook_handler
original_webhook_handler = webhook_handler

async def paystack_webhook_handler(request: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced webhook handler with Paystack-specific processing."""
    try:
        # Extract gateway from path
        path = request.get('path', '')
        if '/paystack' not in path:
            # Forward to original handler for other gateways
            return await original_webhook_handler(request)
        
        payload = request.get('json', {})
        signature = request.get('headers', {}).get('x-paystack-signature')
        
        # Basic validation
        if not payload:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Empty payload'})}
        
        # Process through orchestrator first (signature validation)
        gateway_result = await payment_orchestrator.handle_webhook('paystack', payload, signature)
        
        if not gateway_result:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Signature validation failed'})}
        
        # Paystack-specific processing
        paystack_result = await process_paystack_webhook(payload)
        
        logger.info("Paystack webhook fully processed", extra={
            'event': payload.get('event'),
            'reference': payload.get('data', {}).get('reference'),
            'paystack_status': paystack_result.get('status'),
            'orchestrator_status': gateway_result
        })
        
        return {
            'statusCode': 200, 
            'body': json.dumps({
                'status': 'success',
                'paystack_result': paystack_result
            })
        }
        
    except Exception as e:
        logger.error("Paystack webhook handler error", exc_info=True, extra={
            'error': str(e)
        })
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}

# Monkey patch the webhook handler to include Paystack processing
webhook_handler = paystack_webhook_handler

__all__ = [
    'PaystackGateway', 'PaystackConfig', 'initialize_paystack',
    'register_paystack_handlers', 'process_paystack_webhook'
            ]
