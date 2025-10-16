# utils/referral_utils.py
"""
DocuLuna Referral Utilities

Handles referral code generation, tracking, fraud prevention, reward assignment,
multi-level referrals (Phase 2), and comprehensive audit logging.
Integrates with premium system for conversion rewards.

Usage:
    from utils import referral_utils
    
    # Initialize
    referral_manager = referral_utils.ReferralManager(config={})
    
    # Generate code
    code = await referral_manager.generate_referral_code(user_id=123)
    
    # Process referral
    result = await referral_manager.process_referral(new_user_id=456, code='REF12345')
    
    # Fraud check
    fraud_result = await referral_manager.check_for_fraud(user_id=456, ip_address='1.2.3.4')
    
    # Reward conversion
    reward = await referral_manager.process_conversion_reward(user_id=456, plan='monthly')
    
    # Audit report
    audit_log = await referral_manager.get_audit_log(user_id=123, limit=10)
"""

import logging
import time
import secrets
import string
import json
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from hashlib import sha256
import asyncio
import ipaddress
from functools import wraps

from handlers.premium import PremiumPlan, PremiumStatus, get_premium_data  # type: ignore
from handlers.payments import Transaction, PaymentStatus  # type: ignore
from handlers.stats import stats_tracker, StatType  # type: ignore
from utils.error_handler import ErrorHandler, ErrorContext  # type: ignore
from database.db import get_user_data, update_user_data  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class ReferralRecord:
    """Referral tracking record."""
    referrer_id: int
    referred_id: int
    referral_code: str
    referred_at: datetime
    has_converted: bool = False
    conversion_date: Optional[datetime] = None
    conversion_plan: Optional[str] = None
    reward_amount: float = 0.0
    reward_status: str = "pending"
    level: int = 1  # For multi-level referrals
    audit_trail: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.audit_trail is None:
            self.audit_trail = []

class ReferralFraudType(Enum):
    """Types of referral fraud detected."""
    SELF_REFERRAL = "self_referral"
    IP_MATCH = "ip_match"
    MULTI_ACCOUNT = "multi_account"
    GEO_ANOMALY = "geo_anomaly"
    RAPID_REFERRALS = "rapid_referrals"
    PATTERN_MATCH = "pattern_match"
    BLOCKED_IP = "blocked_ip"

@dataclass
class FraudDetectionResult:
    """Result of fraud detection check."""
    fraud_detected: bool
    threats: List[ReferralFraudType]
    severity: str  # "low", "medium", "high"
    description: str
    confidence: float  # 0-1
    block_access: bool = False
    audit_logged: bool = True

class ReferralManager:
    """
    Comprehensive referral management system with fraud prevention.
    
    Features:
        - Secure code generation and validation
        - Multi-level referral tracking (up to 3 levels)
        - Fraud detection (IP matching, patterns, rate limiting)
        - Reward assignment on premium conversions
        - Audit logging and reporting
        - Integration with premium/payment systems
    
    Args:
        config: Configuration dictionary
        redis_client: Redis client for tracking
        error_handler: Error handler instance
        max_referrals_per_day: Max referrals per referrer per day
        fraud_threshold: Fraud confidence threshold for blocking
        ip_blacklist: Set of blocked IPs
    """
    
    REFERRAL_CONFIG = {
        'code_length': 8,
        'max_referrals_per_user': 100,
        'max_levels': 3,  # Multi-level depth
        'level_multipliers': [1.0, 0.5, 0.25],  # Reward multipliers for levels 1-3
        'reward_window_days': 60,  # 2 months for rewards
        'rate_limit_referrals_per_day': 10,
        'rate_limit_referrals_per_hour': 3,
        'fraud_detection_threshold': 0.7,  # Confidence to flag as fraud
        'ip_blacklist': set(),  # Blocked IPs
        'geo_anomaly_threshold_km': 1000,  # Flag if referrer/referred >1000km apart
        'audit_retention_days': 180
    }
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
        error_handler: Optional[ErrorHandler] = None,
        max_referrals_per_day: int = 10,
        fraud_threshold: float = 0.7
    ):
        self.config = config or {}
        self.redis_client = redis_client
        self.error_handler = error_handler or ErrorHandler()
        self.max_referrals_per_day = max_referrals_per_day
        self.fraud_threshold = fraud_threshold
        
        # Referral prefix for storage
        self.referral_prefix = "referral:utils"
        self.fraud_prefix = "fraud:referral"
        self.audit_prefix = "audit:referral"
        
        # Redis availability
        self.redis_available = bool(self.redis_client and hasattr(self.redis_client, 'set'))
        
        # IP blacklist from config
        self.ip_blacklist = set(self.config.get('ip_blacklist', []))
        
        # Fraud detection patterns
        self.fraud_patterns = [
            r'\b(bot|automated|script|test|fake)\b',  # Suspicious usernames
            r'(\d{1,3}\.){3}\d{1,3}',  # IP-like strings in codes (impossible but check)
            r'(proxy|vpn)',  # VPN/proxy indicators
        ]
        
        logger.info("ReferralManager initialized", extra={
            'redis_available': self.redis_available,
            'max_referrals_per_day': self.max_referrals_per_day,
            'fraud_threshold': self.fraud_threshold,
            'ip_blacklist_count': len(self.ip_blacklist),
            'max_levels': self.REFERRAL_CONFIG['max_levels']
        })
    
    async def generate_referral_code(self, referrer_id: int, referrer_role: str = 'user') -> Optional[str]:
        """
        Generate unique referral code with fraud checks.
        
        Args:
            referrer_id: Referrer user ID
            referrer_role: User role for eligibility
            
        Returns:
            Referral code or None if ineligible
        """
        try:
            # Validate eligibility
            if referrer_role not in ['user', 'support', 'moderator', 'superadmin']:
                logger.warning("Ineligible role for referral generation", extra={
                    'referrer_id': referrer_id,
                    'role': referrer_role
                })
                return None
            
            # Check existing code
            existing_code = await self._get_referral_code(referrer_id)
            if existing_code:
                return existing_code
            
            # Generate secure code
            code = self._generate_unique_code()
            now = datetime.utcnow()
            
            referral_data = {
                'code': code,
                'referrer_id': referrer_id,
                'created_at': now.isoformat(),
                'expires_at': (now + timedelta(days=self.REFERRAL_CONFIG['code_expiry_days'])).isoformat(),
                'usage_count': 0,
                'conversion_count': 0,
                'fraud_flags': 0,
                'levels': {},  # Multi-level referral tree
                'total_rewards': 0.0,
                'status': 'active'
            }
            
            # Store referral data
            await self._store_referral_data(referrer_id, referral_data)
            
            # Audit log
            await self._audit_log(referrer_id, 'code_generated', {'code': code})
            
            logger.info("Referral code generated", extra={
                'referrer_id': referrer_id,
                'code': code,
                'expires_in_days': self.REFERRAL_CONFIG['code_expiry_days']
            })
            
            return code
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(user_id=referrer_id, operation='generate_referral_code'),
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.BUSINESS_LOGIC
            )
            return None
    
    def _generate_unique_code(self) -> str:
        """Generate secure, unique referral code."""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(self.REFERRAL_CONFIG['code_length']))
            
            # Check uniqueness
            if not asyncio.get_running_loop().run_until_complete(self._code_exists(code)):
                return code
    
    async def _code_exists(self, code: str) -> bool:
        """Check if referral code exists."""
        try:
            code_key = f"{self.referral_prefix}:code:{code}"
            if self.redis_available:
                return bool(await self.redis_client.exists(code_key))
            else:
                return code_key in referral_store
        except Exception as e:
            logger.warning("Code existence check failed", extra={'error': str(e)})
            return False
    
    async def _store_referral_data(self, referrer_id: int, data: Dict[str, Any]) -> None:
        """Store referral data securely."""
        try:
            code = data['code']
            referrer_key = f"{self.referral_prefix}:user:{referrer_id}"
            code_key = f"{self.referral_prefix}:code:{code}"
            
            if self.redis_available:
                ttl = self.REFERRAL_CONFIG['code_expiry_days'] * 86400
                await self.redis_client.setex(referrer_key, ttl, code)
                await self.redis_client.setex(code_key, ttl, json.dumps(data, default=str))
            else:
                referral_store[referrer_key] = code
                referral_store[code_key] = data
                
        except Exception as e:
            logger.error("Failed to store referral data", exc_info=True, extra={
                'referrer_id': referrer_id,
                'error': str(e)
            })
    
    async def _get_referral_code(self, referrer_id: int) -> Optional[str]:
        """Get referrer's code."""
        try:
            referrer_key = f"{self.referral_prefix}:user:{referrer_id}"
            
            if self.redis_available:
                return await self.redis_client.get(referrer_key)
            else:
                return referral_store.get(referrer_key)
            
        except Exception as e:
            logger.error("Failed to get referral code", exc_info=True, extra={
                'referrer_id': referrer_id,
                'error': str(e)
            })
            return None
    
    async def process_referral(self, new_user_id: int, code: str) -> Dict[str, Any]:
        """Process new referral with fraud checks."""
        try:
            # Validate code
            validation = await self._validate_referral_code(code)
            if not validation['valid']:
                return validation
            
            referrer_id = validation['referrer_id']
            
            # Fraud check before processing
            fraud_result = await self.check_for_fraud(
                new_user_id,
                referrer_id=referrer_id,
                code=code,
                user_ip='192.168.1.1',  # Mock IP
                referrer_ip='192.168.1.2'  # Mock referrer IP
            )
            
            if fraud_result.fraud_detected and fraud_result.block_access:
                await self._audit_log(referrer_id, 'fraud_detected', {
                    'new_user_id': new_user_id,
                    'fraud_result': asdict(fraud_result)
                })
                return {'success': False, 'error': 'Referral blocked due to fraud detection'}
            
            # Check if already referred
            if await self._user_has_referral(new_user_id):
                return {'success': False, 'error': 'User already has a referral'}
            
            # Create record
            now = datetime.utcnow()
            record = ReferralRecord(
                referrer_id=referrer_id,
                referred_id=new_user_id,
                referral_code=code,
                referred_at=now,
                reward_amount=0.0  # Initial - updated on conversion
            )
            
            # Store record
            await self._store_referral_record(record)
            
            # Assign initial new user reward
            new_user_reward = await self._assign_new_user_reward(new_user_id, validation)
            
            # Update usage
            await self._increment_referral_usage(code)
            
            # Audit
            await self._audit_log(referrer_id, 'referral_processed', {
                'new_user_id': new_user_id,
                'code': code,
                'fraud_result': asdict(fraud_result),
                'new_user_reward': new_user_reward
            })
            
            logger.info("Referral processed successfully", extra={
                'referrer_id': referrer_id,
                'new_user_id': new_user_id,
                'code': code,
                'fraud_severity': fraud_result.severity
            })
            
            return {
                'success': True,
                'referrer_id': referrer_id,
                'code': code,
                'new_user_reward': new_user_reward,
                'fraud_result': asdict(fraud_result)
            }
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(user_id=new_user_id, operation='process_referral'),
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.BUSINESS_LOGIC
            )
            return {'success': False, 'error': str(e)}
    
    async def _validate_referral_code(self, code: str) -> Dict[str, Any]:
        """Validate referral code."""
        try:
            if len(code) != self.REFERRAL_CONFIG['code_length']:
                return {'valid': False, 'error': 'Invalid code length'}
            
            code_key = f"{self.referral_prefix}:code:{code}"
            
            if self.redis_available:
                data = await self.redis_client.get(code_key)
                if not data:
                    return {'valid': False, 'error': 'Code not found'}
                referral_data = json.loads(data)
            else:
                if code_key not in referral_store:
                    return {'valid': False, 'error': 'Code not found'}
                referral_data = referral_store[code_key]
            
            # Expiry check
            expiry = datetime.fromisoformat(referral_data['expires_at'])
            if datetime.utcnow() > expiry:
                return {'valid': False, 'error': 'Code expired'}
            
            # Usage limit
            if referral_data['usage_count'] >= self.REFERRAL_CONFIG['max_referrals_per_user']:
                return {'valid': False, 'error': 'Code usage limit reached'}
            
            return {'valid': True, 'referrer_id': referral_data['referrer_id']}
            
        except Exception as e:
            logger.error("Referral code validation failed", extra={'error': str(e)})
            return {'valid': False, 'error': 'Validation error'}
    
    async def check_for_fraud(
        self,
        user_id: int,
        referrer_id: Optional[int] = None,
        code: Optional[str] = None,
        user_ip: Optional[str] = None,
        referrer_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> FraudDetectionResult:
        """Perform comprehensive fraud detection."""
        threats = []
        confidence = 0.0
        description = "No threats detected"
        severity = "low"
        
        try:
            # Check self-referral
            if referrer_id == user_id:
                threats.append(ReferralFraudType.SELF_REFERRAL)
                confidence += 1.0
            
            # IP matching
            if user_ip and referrer_ip:
                user_ip_obj = ipaddress.ip_address(user_ip)
                referrer_ip_obj = ipaddress.ip_address(referrer_ip)
                
                if user_ip_obj == referrer_ip_obj:
                    threats.append(ReferralFraudType.IP_MATCH)
                    confidence += 0.8
                
                # Check VPN/proxy IPs (mock - in production use IP intelligence)
                if 'proxy' in user_agent.lower() or 'vpn' in user_agent.lower():
                    threats.append(ReferralFraudType.PATTERN_MATCH)
                    confidence += 0.5
                
                # Check geo anomaly (mock - use GeoIP database in production)
                if abs(hash(user_ip) - hash(referrer_ip)) > 1000:  # Mock distance
                    threats.append(ReferralFraudType.GEO_ANOMALY)
                    confidence += 0.6
            
            # Blocked IP
            if user_ip and user_ip in self.ip_blacklist:
                threats.append(ReferralFraudType.BLOCKED_IP)
                confidence += 1.0
            
            # Rapid referrals rate limiting
            recent_referrals = await self._get_recent_referrals(referrer_id)
            if len(recent_referrals) > self.REFERRAL_CONFIG['rate_limit_referrals_per_hour']:
                threats.append(ReferralFraudType.RAPID_REFERRALS)
                confidence += 0.7
            
            # Pattern matching
            if code and any(re.search(p, code) for p in self.fraud_patterns):
                threats.append(ReferralFraudType.PATTERN_MATCH)
                confidence += 0.5
            
            # Multi-account detection (mock - use device fingerprint in production)
            if await self._check_multi_account(user_id):
                threats.append(ReferralFraudType.MULTI_ACCOUNT)
                confidence += 0.9
            
            # Normalize confidence
            confidence = min(1.0, confidence / max(1, len(self.fraud_patterns)))
            
            # Determine severity
            if confidence > 0.9:
                severity = "high"
            elif confidence > 0.5:
                severity = "medium"
            else:
                severity = "low"
            
            block_access = confidence > self.fraud_threshold
            
            description = f"Detected {len(threats)} threats: {', '.join(t.value for t in threats)}"
            
            if threats:
                await self._audit_log(user_id, 'fraud_check', {
                    'threats': [t.value for t in threats],
                    'confidence': confidence,
                    'blocked': block_access
                })
            
            logger.debug("Fraud check completed", extra={
                'user_id': user_id,
                'referrer_id': referrer_id,
                'threats': [t.value for t in threats],
                'confidence': confidence,
                'severity': severity,
                'block_access': block_access
            })
            
            return FraudDetectionResult(
                fraud_detected=len(threats) > 0,
                threats=threats,
                severity=severity,
                description=description,
                confidence=confidence,
                block_access=block_access
            )
            
        except Exception as e:
            logger.error("Fraud detection failed", exc_info=True, extra={
                'user_id': user_id,
                'referrer_id': referrer_id,
                'error': str(e)
            })
            return FraudDetectionResult(
                fraud_detected=False,
                threats=[],
                severity="low",
                description="Fraud detection unavailable",
                confidence=0.0,
                block_access=False,
                audit_logged=False
            )
    
    async def _get_recent_referrals(self, referrer_id: int) -> List[Dict[str, Any]]:
        """Get recent referrals for rate limiting."""
        try:
            if not self.redis_available:
                return []
            
            pattern = f"{self.referral_prefix}:referrals:{referrer_id}:*"
            keys = await self.redis_client.keys(pattern)
            
            recent = []
            for key in keys:
                data = await self.redis_client.get(key)
                if data:
                    record = json.loads(data)
                    recent.append(record)
            
            return recent
            
        except Exception as e:
            logger.error("Failed to get recent referrals", extra={'error': str(e)})
            return []
    
    async def _check_multi_account(self, user_id: int) -> bool:
        """Check for multi-account fraud (mock implementation)."""
        # In production, check device ID, IP, fingerprint patterns
        # Mock: Random 10% detection for testing
        import random
        is_fraud = random.random() < 0.1
        
        return is_fraud
    
    async def _store_referral_record(self, record: ReferralRecord) -> None:
        """Store referral record."""
        try:
            referrer_key = f"{self.referral_prefix}:referrals:{record.referrer_id}:{record.referred_id}"
            referred_key = f"{self.referral_prefix}:referred:{record.referred_id}"
            
            record_json = json.dumps(asdict(record), default=str)
            
            if self.redis_available:
                ttl = self.REFERRAL_CONFIG['reward_window_days'] * 86400
                await self.redis_client.setex(referrer_key, ttl, record_json)
                await self.redis_client.setex(referred_key, ttl, record_json)
            else:
                referral_store[referrer_key] = asdict(record)
                referral_store[referred_key] = asdict(record)
                
        except Exception as e:
            logger.error("Failed to store referral record", extra={
                'referrer_id': record.referrer_id,
                'referred_id': record.referred_id,
                'error': str(e)
            })
    
    async def _user_has_referral(self, user_id: int) -> bool:
        """Check if user has been referred."""
        try:
            referred_key = f"{self.referral_prefix}:referred:{user_id}"
            
            if self.redis_available:
                return bool(await self.redis_client.exists(referred_key))
            else:
                return referred_key in referral_store
            
        except Exception as e:
            logger.error("Failed to check user referral", extra={
                'user_id': user_id,
                'error': str(e)
            })
            return False
    
    async def _assign_new_user_reward(self, new_user_id: int, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Assign initial referral reward to new user (3 free days)."""
        try:
            # Mock transaction for reward
            mock_transaction = Transaction(
                transaction_id=f"referral_reward_{new_user_id}_{int(time.time())}",
                user_id=new_user_id,
                amount=0.0,
                currency="NGN",
                gateway="referral_system",
                status=PaymentStatus.SUCCESS,
                metadata={
                    'reward_type': 'referral_signup',
                    'referral_code': validation['code'],
                    'referrer_id': validation['referrer_id']
                },
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Grant 3 days of premium (weekly plan equivalent)
            success = await activate_premium(new_user_id, mock_transaction, PremiumPlan.WEEKLY)
            
            if success:
                premium_data = await get_premium_data(new_user_id)
                expiry = datetime.fromisoformat(premium_data['expiry'])
                actual_days = max(0, (expiry - datetime.utcnow()).days)
                
                reward_value = REFERRAL_CONFIG['reward_new_referral']['value']
                
                await self._audit_log(new_user_id, 'new_user_reward_assigned', {
                    'reward_type': ReferralRewardType.PREMIUM_DAYS.value,
                    'reward_value': min(actual_days, reward_value),
                    'success': success
                })
                
                return {
                    'type': ReferralRewardType.PREMIUM_DAYS.value,
                    'value': min(actual_days, reward_value),
                    'success': success
                }
            else:
                return {
                    'type': ReferralRewardType.PREMIUM_DAYS.value,
                    'value': 0,
                    'success': False
                }
                
        except Exception as e:
            logger.error("New user reward assignment failed", extra={'error': str(e)})
            return {'type': ReferralRewardType.PREMIUM_DAYS.value, 'success': False}
    
    async def process_conversion_reward(self, referred_id: int, plan: PremiumPlan) -> Dict[str, Any]:
        """Process referral conversion reward for referrer."""
        try:
            # Get referral record
            referred_key = f"{self.referral_prefix}:referred:{referred_id}"
            if self.redis_available:
                data = await self.redis_client.get(referred_key)
                if not data:
                    return {'success': False, 'error': 'No referral record'}
                record = ReferralRecord(**json.loads(data))
            else:
                if referred_key not in referral_store:
                    return {'success': False, 'error': 'No referral record'}
                record = ReferralRecord(**referral_store[referred_key])
            
            # Check if already rewarded
            if record.has_converted:
                return {'success': False, 'error': 'Already rewarded'}
            
            # Check reward window
            if datetime.utcnow() > record.referred_at + timedelta(days=self.REFERRAL_CONFIG['reward_window_days']):
                return {'success': False, 'error': 'Reward window expired'}
            
            # Determine reward amount
            if plan == PremiumPlan.MONTHLY:
                reward_amount = self.REFERRAL_CONFIG['reward_monthly']
            else:
                reward_amount = self.REFERRAL_CONFIG['reward_weekly']
            
            # Assign to referrer
            success = await add_user_currency_credit(record.referrer_id, reward_amount)
            
            if success:
                # Update record
                record.has_converted = True
                record.conversion_date = datetime.utcnow()
                record.conversion_plan = plan.value['id']
                record.reward_amount = reward_amount
                
                # Store updated record
                await self._store_referral_record(record)
                
                # Update referrer levels (for multi-level)
                await self._update_multi_level_rewards(record, reward_amount)
                
                # Audit
                await self._audit_log(record.referrer_id, 'conversion_reward_assigned', {
                    'referred_id': referred_id,
                    'plan': plan.value['id'],
                    'reward_amount': reward_amount
                })
                
                logger.info("Conversion reward processed", extra={
                    'referrer_id': record.referrer_id,
                    'referred_id': referred_id,
                    'reward_amount': reward_amount,
                    'plan': plan.value['id']
                })
                
                return {'success': True, 'reward_amount': reward_amount}
            else:
                return {'success': False, 'error': 'Reward assignment failed'}
                
        except Exception as e:
            logger.error("Conversion reward processing failed", extra={
                'referred_id': referred_id,
                'error': str(e)
            })
            return {'success': False, 'error': str(e)}
    
    async def _update_multi_level_rewards(self, record: ReferralRecord, base_reward: float) -> None:
        """Update multi-level referral rewards."""
        try:
            current_referrer = record.referrer_id
            current_level = 1
            
            while current_level <= self.REFERRAL_CONFIG['max_levels']:
                # Get referrer's referrer
                referrer_referred_key = f"{self.referral_prefix}:referred:{current_referrer}"
                
                if self.redis_available:
                    referrer_data = await self.redis_client.get(referrer_referred_key)
                    if not referrer_data:
                        break
                    referrer_record = ReferralRecord(**json.loads(referrer_data))
                else:
                    if referrer_referred_key not in referral_store:
                        break
                    referrer_record = ReferralRecord(**referral_store[referrer_referred_key])
                
                # Calculate level reward
                multiplier = self.REFERRAL_CONFIG['level_multipliers'][current_level - 1]
                level_reward = base_reward * multiplier
                
                # Assign level reward
                success = await add_user_currency_credit(
                    referrer_record.referrer_id,
                    level_reward,
                    f"level_{current_level}_referral"
                )
                
                if success:
                    await self._audit_log(referrer_record.referrer_id, 'multi_level_reward', {
                        'original_referred_id': record.referred_id,
                        'level': current_level,
                        'reward_amount': level_reward
                    })
                
                current_referrer = referrer_record.referrer_id
                current_level += 1
                
        except Exception as e:
            logger.error("Multi-level reward update failed", extra={
                'original_referrer_id': record.referrer_id,
                'error': str(e)
            })
    
    async def get_audit_log(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get referral audit log for user."""
        try:
            audit_key = f"{self.audit_prefix}:{user_id}"
            
            if self.redis_available:
                logs = await self.redis_client.lrange(audit_key, 0, limit - 1)
                audit_logs = [json.loads(log) for log in logs]
            else:
                # In-memory fallback
                if audit_key not in referral_store:
                    referral_store[audit_key] = []
                audit_logs = referral_store[audit_key][:limit]
            
            return sorted(audit_logs, key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            logger.error("Failed to get audit log", extra={
                'user_id': user_id,
                'error': str(e)
            })
            return []
    
    async def _audit_log(self, user_id: int, action: str, details: Dict[str, Any]) -> None:
        """Log referral audit entry."""
        try:
            audit_key = f"{self.audit_prefix}:{user_id}"
            
            audit_entry = {
                'action': action,
                'timestamp': datetime.utcnow().isoformat(),
                'details': details,
                'system_version': '1.0'
            }
            
            if self.redis_available:
                ttl = self.REFERRAL_CONFIG['audit_retention_days'] * 86400
                await self.redis_client.lpush(audit_key, json.dumps(audit_entry))
                await self.redis_client.ltrim(audit_key, 0, 1000)  # Keep last 1000 entries
                await self.redis_client.expire(audit_key, ttl)
            else:
                if audit_key not in referral_store:
                    referral_store[audit_key] = []
                referral_store[audit_key].insert(0, audit_entry)
                referral_store[audit_key] = referral_store[audit_key][:1000]
            
            logger.debug("Audit log entry added", extra={
                'user_id': user_id,
                'action': action,
                'details_keys': list(details.keys())
            })
            
        except Exception as e:
            logger.error("Audit logging failed", extra={
                'user_id': user_id,
                'action': action,
                'error': str(e)
            })
    
    async def cleanup_expired_referrals(self) -> int:
        """Cleanup expired referrals and audit logs."""
        try:
            now = datetime.utcnow()
            cleaned = 0
            
            if self.redis_available:
                # Cleanup expired referral records
                pattern = f"{self.referral_prefix}:*"
                cursor = '0'
                while cursor != 0:
                    cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                    for key in keys:
                        ttl = await self.redis_client.ttl(key)
                        if ttl < 0:  # Expired
                            await self.redis_client.delete(key)
                            cleaned += 1
            
            else:
                # In-memory cleanup
                to_delete = []
                for key, data in referral_store.items():
                    if key.startswith(self.referral_prefix):
                        expiry = data.get('expires_at')
                        if expiry and datetime.fromisoformat(expiry) < now:
                            to_delete.append(key)
                
                for key in to_delete:
                    del referral_store[key]
                    cleaned += 1
            
            logger.info("Expired referrals cleaned up", extra={'cleaned_count': cleaned})
            return cleaned
            
        except Exception as e:
            logger.error("Referral cleanup failed", extra={'error': str(e)})
            return 0

# Global referral manager
referral_manager: Optional[ReferralManager] = None

def initialize_referral_manager(
    config: Dict[str, Any] = None,
    redis_client: Optional[Any] = None,
    error_handler_instance: Optional[ErrorHandler] = None
) -> ReferralManager:
    """Initialize global referral manager."""
    global referral_manager
    
    if referral_manager is None:
        referral_manager = ReferralManager(
            config=config or {},
            redis_client=redis_client,
            error_handler=error_handler_instance
        )
    
    return referral_manager

# Convenience functions
async def generate_referral_code(user_id: int, role: str) -> Optional[str]:
    """Generate referral code for user."""
    global referral_manager
    if not referral_manager:
        raise RuntimeError("Referral manager not initialized")
    
    return await referral_manager.generate_referral_code(user_id, role)

async def process_referral(new_user_id: int, code: str) -> Dict[str, Any]:
    """Process new referral."""
    global referral_manager
    if not referral_manager:
        raise RuntimeError("Referral manager not initialized")
    
    return await referral_manager.process_referral(new_user_id, code)

async def process_conversion_reward(referred_id: int, plan: PremiumPlan) -> Dict[str, Any]:
    """Process referral conversion reward."""
    global referral_manager
    if not referral_manager:
        raise RuntimeError("Referral manager not initialized")
    
    return await referral_manager.process_conversion_reward(referred_id, plan)

def format_currency(amount: float) -> str:
    """Format Naira currency."""
    return f"₦{amount:,.0f}"
