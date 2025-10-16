# utils/premium_utils.py
"""
DocuLuna Premium Utilities

Handles premium-only feature gating, quota management, access validation,
and subscription lifecycle management. Provides decorators for easy premium
feature protection and comprehensive usage tracking.

Usage:
    from utils import premium_utils
    
    # Initialize
    premium_manager = premium_utils.PremiumManager(bot=bot, config={})
    
    # Protect premium features
    @premium_manager.require_premium
    async def advanced_ai_analysis(message):
        # Premium-only code here
        pass
    
    # Check user quota
    quota_info = await premium_manager.check_user_quota(user_id=123, feature='ai_analysis')
    
    # Admin overrides
    await premium_manager.grant_temp_access(user_id=123, duration_hours=24)
"""

import logging
import time
import json
from typing import Dict, Any, Optional, Callable, Awaitable, Union
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from dataclasses import dataclass, asdict
import asyncio

from aiogram import Bot, types
from aiogram.dispatcher import FSMContext

# Local imports
from handlers.premium import PremiumPlan, PremiumStatus, get_premium_data  # type: ignore
from handlers.payments import payment_orchestrator  # type: ignore
from handlers.stats import stats_tracker, StatType  # type: ignore
from utils.error_handler import ErrorHandler, ErrorContext, ErrorSeverity  # type: ignore
from database.db import get_user_data, update_user_data  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class QuotaInfo:
    """User quota and usage information."""
    feature: str
    user_id: int
    current_usage: int
    quota_limit: int
    reset_time: Optional[datetime]
    period: str  # 'daily', 'weekly', 'monthly'
    percentage_used: float
    is_over_quota: bool
    premium_multiplier: float = 1.0
    last_reset: Optional[datetime] = None

class QuotaPeriod(Enum):
    """Quota reset periods."""
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    LIFETIME = "lifetime"

@dataclass
class PremiumAccessResult:
    """Result of premium access check."""
    granted: bool
    user_id: int
    premium_status: PremiumStatus
    plan: Optional[str]
    days_remaining: Optional[int]
    reason: str
    temp_access: bool = False
    temp_expires: Optional[datetime] = None
    quota_info: Optional[QuotaInfo] = None

class FeatureQuota:
    """
    Feature-specific quota configuration.
    
    Args:
        feature_name: Unique feature identifier
        free_quota: Daily quota for free users
        premium_quota: Daily quota for premium users  
        period: Reset period (daily/weekly/monthly)
        premium_multiplier: Usage multiplier for premium (e.g., 10x)
        track_usage: Whether to track and enforce this quota
    """
    
    DEFAULT_QUOTAS = {
        'ai_analysis': {
            'free_quota': 5,
            'premium_quota': 500,
            'period': QuotaPeriod.DAILY,
            'premium_multiplier': 10.0,
            'track_usage': True
        },
        'document_processing': {
            'free_quota': 3,
            'premium_quota': 300,
            'period': QuotaPeriod.DAILY,
            'premium_multiplier': 10.0,
            'track_usage': True
        },
        'advanced_search': {
            'free_quota': 10,
            'premium_quota': 1000,
            'period': QuotaPeriod.WEEKLY,
            'premium_multiplier': 5.0,
            'track_usage': True
        },
        'priority_support': {
            'free_quota': 1,
            'premium_quota': 50,
            'period': QuotaPeriod.DAILY,
            'premium_multiplier': 2.0,
            'track_usage': True
        },
        'export_features': {
            'free_quota': 2,
            'premium_quota': 200,
            'period': QuotaPeriod.MONTHLY,
            'premium_multiplier': 10.0,
            'track_usage': True
        }
    }
    
    def __init__(
        self,
        feature_name: str,
        free_quota: int,
        premium_quota: int,
        period: QuotaPeriod = QuotaPeriod.DAILY,
        premium_multiplier: float = 1.0,
        track_usage: bool = True
    ):
        self.feature_name = feature_name
        self.free_quota = free_quota
        self.premium_quota = premium_quota
        self.period = period
        self.premium_multiplier = premium_multiplier
        self.track_usage = track_usage
        
        # Validate configuration
        if free_quota < 0 or premium_quota < 0:
            raise ValueError("Quotas must be non-negative")
        if premium_multiplier < 1.0:
            raise ValueError("Premium multiplier must be >= 1.0")
        
        logger.debug("FeatureQuota initialized", extra={
            'feature': feature_name,
            'free_quota': free_quota,
            'premium_quota': premium_quota,
            'period': period.value,
            'multiplier': premium_multiplier
        })

class PremiumManager:
    """
    Comprehensive premium feature management system.
    
    Handles access control, quota enforcement, temporary access grants,
    and subscription lifecycle management with admin overrides.
    
    Args:
        bot: Aiogram Bot instance
        config: Configuration dictionary
        redis_client: Redis client for quota storage (optional)
        error_handler: Error handler instance (optional)
        default_plan: Default premium plan for temp access
        temp_access_duration_hours: Default temp access duration
    """
    
    # Default quota configuration for all features
    GLOBAL_QUOTA_CONFIG = {
        'default_free_quota': 5,
        'default_premium_quota': 500,
        'default_period': QuotaPeriod.DAILY,
        'default_multiplier': 10.0,
        'quota_retention_days': 90
    }
    
    def __init__(
        self,
        bot: Optional[Bot] = None,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
        error_handler: Optional[ErrorHandler] = None,
        default_plan: PremiumPlan = PremiumPlan.MONTHLY,
        temp_access_duration_hours: int = 24
    ):
        self.bot = bot
        self.config = config or {}
        self.redis_client = redis_client
        self.error_handler = error_handler or ErrorHandler(bot=bot)
        self.default_plan = default_plan
        self.temp_access_duration_hours = temp_access_duration_hours
        
        # Quota storage prefix
        self.quota_prefix = "premium:quota"
        self.temp_access_prefix = "premium:temp_access"
        self.feature_access_prefix = "premium:feature_access"
        
        # Load feature quotas
        self.feature_quotas = self._load_feature_quotas()
        
        # Admin override list (from config)
        self.admin_override_users = set(self.config.get('admin_override_users', []))
        
        # Initialize Redis if available
        self.redis_available = bool(self.redis_client and hasattr(self.redis_client, 'set'))
        
        logger.info("PremiumManager initialized", extra={
            'admin_overrides': len(self.admin_override_users),
            'feature_quotas': len(self.feature_quotas),
            'redis_available': self.redis_available,
            'temp_access_hours': temp_access_duration_hours
        })
    
    def _load_feature_quotas(self) -> Dict[str, FeatureQuota]:
        """Load feature quota configuration."""
        quotas = {}
        
        # Use configured quotas
        configured_quotas = self.config.get('feature_quotas', {})
        
        for feature_name, config in configured_quotas.items():
            try:
                period = QuotaPeriod(config.get('period', QuotaPeriod.DAILY.value))
                quota = FeatureQuota(
                    feature_name=feature_name,
                    free_quota=config.get('free_quota', self.GLOBAL_QUOTA_CONFIG['default_free_quota']),
                    premium_quota=config.get('premium_quota', self.GLOBAL_QUOTA_CONFIG['default_premium_quota']),
                    period=period,
                    premium_multiplier=config.get('premium_multiplier', self.GLOBAL_QUOTA_CONFIG['default_multiplier']),
                    track_usage=config.get('track_usage', True)
                )
                quotas[feature_name] = quota
            except Exception as e:
                logger.error(f"Failed to load quota for {feature_name}", extra={'error': str(e)})
        
        # Add default quotas for unconfigured features
        for default_feature in FeatureQuota.DEFAULT_QUOTAS:
            if default_feature not in quotas:
                config = FeatureQuota.DEFAULT_QUOTAS[default_feature]
                period = QuotaPeriod(config['period'])
                quotas[default_feature] = FeatureQuota(
                    feature_name=default_feature,
                    free_quota=config['free_quota'],
                    premium_quota=config['premium_quota'],
                    period=period,
                    premium_multiplier=config.get('premium_multiplier', 10.0),
                    track_usage=True
                )
        
        logger.debug("Feature quotas loaded", extra={
            'total_quotas': len(quotas),
            'configured': len(configured_quotas)
        })
        
        return quotas
    
    async def check_premium_access(
        self,
        user_id: int,
        feature: Optional[str] = None,
        enforce_quota: bool = True,
        admin_override: bool = False
    ) -> PremiumAccessResult:
        """
        Check if user has premium access for a specific feature.
        
        Args:
            user_id: User identifier
            feature: Specific feature to check (None for general access)
            enforce_quota: Whether to enforce feature quotas
            admin_override: Bypass all checks (admin only)
            
        Returns:
            PremiumAccessResult with access decision and details
        """
        try:
            start_time = time.time()
            
            # Admin override check
            if admin_override or user_id in self.admin_override_users:
                result = PremiumAccessResult(
                    granted=True,
                    user_id=user_id,
                    premium_status=PremiumStatus.ACTIVE,
                    plan=self.default_plan.value['id'],
                    days_remaining=None,
                    reason="admin_override",
                    temp_access=False
                )
                logger.debug("Premium access granted - admin override", extra={
                    'user_id': user_id,
                    'feature': feature,
                    'access_time_ms': round((time.time() - start_time) * 1000, 2)
                })
                return result
            
            # Get premium data
            premium_data = await get_premium_data(user_id)
            current_status = premium_data.get('status', PremiumStatus.EXPIRED.value)
            current_plan = premium_data.get('plan', 'basic')
            
            # Check subscription status
            if current_status == PremiumStatus.ACTIVE.value:
                # Calculate days remaining
                expiry = datetime.fromisoformat(premium_data['expiry'])
                days_remaining = max(0, (expiry - datetime.utcnow()).days)
                
                # Check if expired (edge case)
                if datetime.utcnow() > expiry:
                    await self._enforce_premium_expiry(user_id)
                    current_status = PremiumStatus.EXPIRED.value
                    days_remaining = 0
                else:
                    result = PremiumAccessResult(
                        granted=True,
                        user_id=user_id,
                        premium_status=current_status,
                        plan=current_plan,
                        days_remaining=days_remaining,
                        reason="active_subscription"
                    )
                    
                    # Check feature quota if required
                    if enforce_quota and feature and feature in self.feature_quotas:
                        quota_result = await self._check_feature_quota(
                            user_id, feature, current_plan, days_remaining
                        )
                        result.quota_info = quota_result
                        
                        if quota_result.is_over_quota:
                            result.granted = False
                            result.reason = "quota_exceeded"
                    
                    logger.debug("Premium access granted - active subscription", extra={
                        'user_id': user_id,
                        'feature': feature,
                        'plan': current_plan,
                        'days_remaining': days_remaining,
                        'quota_ok': not result.quota_info.is_over_quota if result.quota_info else True,
                        'access_time_ms': round((time.time() - start_time) * 1000, 2)
                    })
                    return result
            
            # Check temporary access
            temp_access = await self._check_temp_access(user_id)
            if temp_access:
                result = PremiumAccessResult(
                    granted=True,
                    user_id=user_id,
                    premium_status=PremiumStatus.ACTIVE,
                    plan=temp_access.get('plan', self.default_plan.value['id']),
                    days_remaining=None,
                    reason="temp_access",
                    temp_access=True,
                    temp_expires=temp_access.get('expires_at')
                )
                logger.debug("Premium access granted - temporary", extra={
                    'user_id': user_id,
                    'feature': feature,
                    'expires_in': (temp_access['expires_at'] - datetime.utcnow()).total_seconds() / 3600,
                    'access_time_ms': round((time.time() - start_time) * 1000, 2)
                })
                return result
            
            # No access - suggest upgrade
            result = PremiumAccessResult(
                granted=False,
                user_id=user_id,
                premium_status=current_status,
                plan=current_plan,
                days_remaining=0,
                reason="no_active_subscription"
            )
            
            logger.debug("Premium access denied", extra={
                'user_id': user_id,
                'feature': feature,
                'current_status': current_status,
                'access_time_ms': round((time.time() - start_time) * 1000, 2)
            })
            
            return result
            
        except Exception as e:
            # Log access check failure
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(
                    user_id=user_id,
                    operation=f"premium_access_check_{feature or 'general'}"
                ),
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.SYSTEM
            )
            
            # Return denied access on error
            return PremiumAccessResult(
                granted=False,
                user_id=user_id,
                premium_status=PremiumStatus.EXPIRED,
                plan='basic',
                days_remaining=0,
                reason="access_check_failed"
            )
    
    async def _check_feature_quota(
        self,
        user_id: int,
        feature: str,
        current_plan: str,
        days_remaining: int
    ) -> QuotaInfo:
        """Check feature-specific quota usage."""
        try:
            if feature not in self.feature_quotas:
                # No quota defined - allow unlimited
                return QuotaInfo(
                    feature=feature,
                    user_id=user_id,
                    current_usage=0,
                    quota_limit=-1,  # Unlimited
                    reset_time=None,
                    period=QuotaPeriod.LIFETIME,
                    percentage_used=0.0,
                    is_over_quota=False
                )
            
            quota_config = self.feature_quotas[feature]
            if not quota_config.track_usage:
                return QuotaInfo(
                    feature=feature,
                    user_id=user_id,
                    current_usage=0,
                    quota_limit=0,  # Not tracked
                    reset_time=None,
                    period=QuotaPeriod.LIFETIME,
                    percentage_used=0.0,
                    is_over_quota=False
                )
            
            # Determine quota limit based on plan
            if current_plan == 'basic':
                quota_limit = quota_config.free_quota
                multiplier = 1.0
            else:
                quota_limit = quota_config.premium_quota
                multiplier = quota_config.premium_multiplier
            
            # Get current usage
            current_usage = await self._get_feature_usage(
                user_id, feature, quota_config.period
            )
            
            # Calculate reset time
            reset_time = self._calculate_reset_time(quota_config.period)
            
            percentage_used = (current_usage / quota_limit * 100) if quota_limit > 0 else 0
            is_over_quota = current_usage >= quota_limit
            
            quota_info = QuotaInfo(
                feature=feature,
                user_id=user_id,
                current_usage=current_usage,
                quota_limit=quota_limit,
                reset_time=reset_time,
                period=quota_config.period.value,
                percentage_used=percentage_used,
                is_over_quota=is_over_quota,
                premium_multiplier=multiplier
            )
            
            logger.debug("Feature quota checked", extra={
                'user_id': user_id,
                'feature': feature,
                'current_usage': current_usage,
                'quota_limit': quota_limit,
                'percentage_used': percentage_used,
                'is_over_quota': is_over_quota,
                'plan': current_plan
            })
            
            return quota_info
            
        except Exception as e:
            logger.error("Quota check failed", exc_info=True, extra={
                'user_id': user_id,
                'feature': feature,
                'error': str(e)
            })
            # Default to no quota on error
            return QuotaInfo(
                feature=feature,
                user_id=user_id,
                current_usage=0,
                quota_limit=-1,  # Unlimited on error
                reset_time=None,
                period=QuotaPeriod.LIFETIME.value,
                percentage_used=0.0,
                is_over_quota=False
            )
    
    async def _get_feature_usage(self, user_id: int, feature: str, 
                               period: QuotaPeriod) -> int:
        """Get feature usage count for period."""
        try:
            if not self.redis_available:
                # In-memory fallback (not production-ready)
                return 0
            
            # Calculate time range
            now = datetime.utcnow()
            if period == QuotaPeriod.DAILY:
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == QuotaPeriod.WEEKLY:
                # Start of week (Monday)
                days_to_subtract = now.weekday()
                start_time = now - timedelta(days=days_to_subtract)
                start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == QuotaPeriod.MONTHLY:
                start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return 0  # Lifetime not tracked this way
            
            start_timestamp = int(start_time.timestamp())
            
            # Redis key pattern: premium:quota:{user_id}:{feature}:{period}:{date}
            pattern = f"{self.quota_prefix}:{user_id}:{feature}:{period.value}:*"
            
            # Use Redis SCAN for large datasets (more efficient than KEYS)
            cursor = 0
            total_usage = 0
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                if not keys:
                    break
                
                for key in keys:
                    key_parts = key.decode().split(':')
                    if len(key_parts) >= 6:
                        try:
                            key_timestamp = int(key_parts[-1])
                            if key_timestamp >= start_timestamp:
                                usage = await self.redis_client.get(key)
                                total_usage += int(usage or 0)
                        except (ValueError, TypeError):
                            continue
            
            return total_usage
            
        except Exception as e:
            logger.error("Failed to get feature usage", exc_info=True, extra={
                'user_id': user_id,
                'feature': feature,
                'period': period.value,
                'error': str(e)
            })
            return 0
    
    def _calculate_reset_time(self, period: QuotaPeriod) -> Optional[datetime]:
        """Calculate next reset time for quota period."""
        now = datetime.utcnow()
        
        if period == QuotaPeriod.DAILY:
            reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif period == QuotaPeriod.WEEKLY:
            days_to_monday = 7 - now.weekday()
            reset_time = now + timedelta(days=days_to_monday)
            reset_time = reset_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == QuotaPeriod.MONTHLY:
            if now.day == 1:
                reset_time = now
            else:
                next_month = now.replace(day=1) + timedelta(days=32)
                reset_time = next_month.replace(day=1)
        else:
            return None
        
        return reset_time
    
    async def _enforce_premium_expiry(self, user_id: int) -> None:
        """Enforce premium subscription expiry."""
        try:
            # This should be called from premium.py periodically
            # Implementation delegates to premium module
            from handlers.premium import check_premium_expiry
            await check_premium_expiry(user_id)
            
            logger.debug("Premium expiry enforced", extra={'user_id': user_id})
            
        except Exception as e:
            logger.error("Failed to enforce premium expiry", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
    
    async def _check_temp_access(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Check if user has temporary premium access."""
        try:
            if not self.redis_available:
                return None
            
            temp_key = f"{self.temp_access_prefix}:{user_id}"
            data = await self.redis_client.get(temp_key)
            
            if data:
                temp_data = json.loads(data)
                expires_at = datetime.fromisoformat(temp_data['expires_at'])
                
                if datetime.utcnow() < expires_at:
                    return {
                        'plan': temp_data.get('plan', self.default_plan.value['id']),
                        'expires_at': expires_at,
                        'granted_at': datetime.fromisoformat(temp_data['granted_at']),
                        'reason': temp_data.get('reason', 'admin_grant')
                    }
                else:
                    # Clean up expired temp access
                    await self.redis_client.delete(temp_key)
            
            return None
            
        except Exception as e:
            logger.error("Failed to check temp access", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
            return None
    
    async def grant_temp_access(
        self,
        user_id: int,
        duration_hours: Optional[int] = None,
        plan: Optional[PremiumPlan] = None,
        reason: str = "admin_grant"
    ) -> bool:
        """
        Grant temporary premium access to user.
        
        Args:
            user_id: User to grant access
            duration_hours: Access duration in hours (default: 24)
            plan: Premium plan for temp access (default: monthly)
            reason: Reason for granting access
            
        Returns:
            True if temp access granted successfully
        """
        try:
            duration = duration_hours or self.temp_access_duration_hours
            selected_plan = plan or self.default_plan
            
            expires_at = datetime.utcnow() + timedelta(hours=duration)
            
            temp_data = {
                'user_id': user_id,
                'plan': selected_plan.value['id'],
                'expires_at': expires_at.isoformat(),
                'granted_at': datetime.utcnow().isoformat(),
                'reason': reason,
                'duration_hours': duration
            }
            
            temp_key = f"{self.temp_access_prefix}:{user_id}"
            
            if self.redis_available:
                await self.redis_client.setex(
                    temp_key,
                    int(duration * 3600),  # TTL in seconds
                    json.dumps(temp_data)
                )
            else:
                # In-memory (not production)
                if 'temp_access_store' not in globals():
                    globals()['temp_access_store'] = {}
                globals()['temp_access_store'][temp_key] = temp_data
            
            # Track temp access grant
            await stats_tracker.track_user_activity(
                user_id,
                "premium_temp_access_granted",
                temp_data
            )
            
            logger.info("Temporary premium access granted", extra={
                'user_id': user_id,
                'duration_hours': duration,
                'plan': selected_plan.value['id'],
                'reason': reason,
                'expires_at': expires_at.isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error("Failed to grant temp access", exc_info=True, extra={
                'user_id': user_id,
                'duration_hours': duration_hours,
                'reason': reason,
                'error': str(e)
            })
            return False
    
    async def revoke_temp_access(self, user_id: int) -> bool:
        """Revoke temporary premium access."""
        try:
            temp_key = f"{self.temp_access_prefix}:{user_id}"
            
            if self.redis_available:
                deleted = await self.redis_client.delete(temp_key)
            else:
                if 'temp_access_store' in globals():
                    deleted = 1 if temp_key in globals()['temp_access_store'] else 0
                    if deleted:
                        del globals()['temp_access_store'][temp_key]
            
            if deleted:
                await stats_tracker.track_user_activity(
                    user_id,
                    "premium_temp_access_revoked",
                    {'revoked_at': datetime.utcnow().isoformat()}
                )
                
                logger.info("Temporary premium access revoked", extra={'user_id': user_id})
                return True
            else:
                logger.warning("No temporary access found to revoke", extra={'user_id': user_id})
                return False
                
        except Exception as e:
            logger.error("Failed to revoke temp access", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
            return False
    
    def require_premium(
        self,
        feature: Optional[str] = None,
        enforce_quota: bool = True,
        message_on_deny: Optional[str] = None,
        temp_access_hours: Optional[int] = None,
        on_deny_callback: Optional[Callable] = None
    ) -> Callable:
        """
        Decorator to require premium access for functions.
        
        Args:
            feature: Specific feature for quota checking
            enforce_quota: Whether to enforce feature quotas
            message_on_deny: Custom denial message
            temp_access_hours: Grant temporary access on first denial
            on_deny_callback: Callback when access denied
            
        Usage:
            @premium_manager.require_premium(feature='ai_analysis')
            async def advanced_feature(message):
                # Premium-only implementation
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user_id from arguments
                user_id = None
                message = None
                state = None
                
                # Common patterns for extracting user_id
                if args:
                    if isinstance(args[0], types.Message):
                        message = args[0]
                        user_id = message.from_user.id
                        state = args[1] if len(args) > 1 and isinstance(args[1], FSMContext) else None
                    elif hasattr(args[0], 'id'):
                        user_id = args[0].id
                
                if not user_id and 'user_id' in kwargs:
                    user_id = kwargs['user_id']
                
                if not user_id:
                    # Fallback - deny access
                    if message:
                        await message.reply(
                            "❌ *Access Denied*\n\n"
                            "User identification failed. Please try again.",
                            parse_mode='Markdown'
                        )
                    return
                    
                try:
                    # Check premium access
                    access_result = await self.check_premium_access(
                        user_id,
                        feature=feature,
                        enforce_quota=enforce_quota
                    )
                    
                    if access_result.granted:
                        # Grant access - track usage if quota enabled
                        if feature and enforce_quota and access_result.quota_info:
                            await self._increment_feature_usage(
                                user_id, feature, access_result.quota_info
                            )
                        
                        # Execute function
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                        
                        logger.debug("Premium feature executed successfully", extra={
                            'user_id': user_id,
                            'feature': feature or 'general',
                            'plan': access_result.plan,
                            'temp_access': access_result.temp_access
                        })
                        
                        return result
                    
                    else:
                        # Access denied
                        denial_reason = access_result.reason
                        
                        # Grant temporary access on first denial
                        if (temp_access_hours and 
                            denial_reason == "no_active_subscription" and
                            not access_result.temp_access):
                            
                            granted = await self.grant_temp_access(
                                user_id,
                                duration_hours=temp_access_hours,
                                reason="first_time_grace"
                            )
                            
                            if granted:
                                # Retry access check
                                access_result = await self.check_premium_access(user_id, feature)
                                if access_result.granted:
                                    # Execute with temp access
                                    if asyncio.iscoroutinefunction(func):
                                        result = await func(*args, **kwargs)
                                    else:
                                        result = func(*args, **kwargs)
                                    
                                    logger.info("Premium access granted via grace period", extra={
                                        'user_id': user_id,
                                        'feature': feature,
                                        'grace_hours': temp_access_hours
                                    })
                                    
                                    return result
                        
                        # Send denial message
                        if message:
                            await self._send_premium_deny_message(
                                message, access_result, feature, on_deny_callback
                            )
                        
                        logger.info("Premium access denied", extra={
                            'user_id': user_id,
                            'feature': feature,
                            'reason': denial_reason,
                            'days_remaining': access_result.days_remaining
                        })
                        
                        return None
                
                except Exception as e:
                    # Capture decorator error
                    await self.error_handler.handle_error(
                        e,
                        context=ErrorContext(
                            user_id=user_id,
                            operation=f"premium_decorator_{func.__name__}",
                            module=func.__module__
                        ),
                        extra_data={
                            'feature': feature,
                            'function': func.__name__,
                            'args_count': len(args)
                        },
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.SYSTEM
                    )
                    
                    if message:
                        await message.reply(
                            "⚠️ *System Error*\n\n"
                            "Premium check failed. Please try again or contact support.",
                            parse_mode='Markdown'
                        )
                    
                    return None
            
            return wrapper
        
        return decorator
    
    async def _send_premium_deny_message(
        self,
        message: types.Message,
        access_result: PremiumAccessResult,
        feature: Optional[str],
        on_deny_callback: Optional[Callable]
    ) -> None:
        """Send premium denial message to user."""
        try:
            user_id = message.from_user.id
            reason = access_result.reason
            
            if reason == "no_active_subscription":
                deny_text = (
                    f"🔒 *Premium Feature Locked*\n\n"
                    f"This {feature or 'feature'} requires a premium subscription.\n\n"
                    f"💎 *Choose Your Plan:*\n"
                )
                
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                
                # Weekly plan
                weekly_btn = types.InlineKeyboardButton(
                    f"🧪 {PremiumPlan.WEEKLY.value['name']} - {format_currency(PremiumPlan.WEEKLY.value['price_ngn'])}/week",
                    callback_data="upgrade_select|weekly"
                )
                
                # Monthly plan
                monthly_btn = types.InlineKeyboardButton(
                    f"💎 {PremiumPlan.MONTHLY.value['name']} - {format_currency(PremiumPlan.MONTHLY.value['price_ngn'])}/month",
                    callback_data="upgrade_select|monthly"
                )
                
                keyboard.add(weekly_btn, monthly_btn)
                
                # Add feature info if specified
                if feature and feature in self.feature_quotas:
                    quota = self.feature_quotas[feature]
                    deny_text += f"\n📊 *{feature.title()}*: {quota.free_quota}/day (free) → {quota.premium_quota}/day (premium)\n"
                
                deny_text += f"\n✨ *Premium Includes:*\n• Unlimited {feature or 'features'}\n• Advanced AI tools\n• Priority support\n\n"
                deny_text += f"🚀 *Get started:* Tap a plan above!"
                
                await message.reply(deny_text, parse_mode='Markdown', reply_markup=keyboard)
                
            elif reason == "quota_exceeded":
                quota_info = access_result.quota_info
                if quota_info:
                    reset_time = quota_info.reset_time
                    reset_text = f"Resets: {reset_time.strftime('%b %d, %H:%M')}" if reset_time else "Unknown"
                    
                    deny_text = (
                        f"⏳ *Quota Reached*\n\n"
                        f"You've used all {quota_info.current_usage}/{quota_info.quota_limit} "
                        f"{quota_info.feature} uses for today.\n\n"
                        f"📊 *Usage:* {quota_info.percentage_used:.0f}% ({quota_info.current_usage}/{quota_info.quota_limit})\n"
                        f"{reset_text}\n\n"
                    )
                    
                    if quota_info.quota_limit < 50:  # Suggest upgrade for low quotas
                        deny_text += f"💎 *Want unlimited?* Upgrade to premium for {self.feature_quotas[quota_info.feature].premium_quota} uses/day!\n\n"
                        keyboard = types.InlineKeyboardMarkup()
                        upgrade_btn = types.InlineKeyboardButton("💎 Upgrade Now", callback_data="upgrade_select|monthly")
                        keyboard.add(upgrade_btn)
                        await message.reply(deny_text, parse_mode='Markdown', reply_markup=keyboard)
                    else:
                        await message.reply(deny_text, parse_mode='Markdown')
                
            else:
                # Generic denial
                deny_text = (
                    f"🔒 *Access Denied*\n\n"
                    f"{reason.replace('_', ' ').title()}\n\n"
                    f"💎 *Upgrade* for full access: `/upgrade`"
                )
                await message.reply(deny_text, parse_mode='Markdown')
            
            # Execute callback if provided
            if on_deny_callback:
                if asyncio.iscoroutinefunction(on_deny_callback):
                    await on_deny_callback(message, access_result)
                else:
                    on_deny_callback(message, access_result)
                    
        except Exception as e:
            logger.error("Failed to send premium denial message", exc_info=True, extra={
                'user_id': message.from_user.id,
                'reason': reason,
                'feature': feature,
                'error': str(e)
            })
    
    async def _increment_feature_usage(self, user_id: int, feature: str, 
                                     quota_info: QuotaInfo) -> None:
        """Increment feature usage count."""
        try:
            if not self.redis_available:
                logger.debug("Feature usage not tracked - Redis unavailable", extra={
                    'user_id': user_id,
                    'feature': feature
                })
                return
            
            # Generate key with timestamp
            now = datetime.utcnow()
            if quota_info.period == QuotaPeriod.DAILY:
                date_str = now.strftime('%Y-%m-%d')
            elif quota_info.period == QuotaPeriod.WEEKLY:
                date_str = now.strftime('%Y-W%U')
            elif quota_info.period == QuotaPeriod.MONTHLY:
                date_str = now.strftime('%Y-%m')
            else:
                date_str = 'lifetime'
            
            quota_key = f"{self.quota_prefix}:{user_id}:{feature}:{quota_info.period}:{date_str}"
            
            # Increment usage (atomic)
            if isinstance(self.redis_client, dict):
                # In-memory fallback
                if quota_key not in self.redis_client:
                    self.redis_client[quota_key] = 0
                self.redis_client[quota_key] += 1
            else:
                await self.redis_client.incr(quota_key)
                await self.redis_client.expire(quota_key, 90 * 86400)  # 90 days TTL
            
            logger.debug("Feature usage incremented", extra={
                'user_id': user_id,
                'feature': feature,
                'new_usage': quota_info.current_usage + 1,
                'quota_key': quota_key
            })
            
        except Exception as e:
            logger.error("Failed to increment feature usage", exc_info=True, extra={
                'user_id': user_id,
                'feature': feature,
                'error': str(e)
            })
    
    async def get_user_quota_summary(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive quota summary for user."""
        try:
            premium_data = await get_premium_data(user_id)
            current_plan = premium_data.get('plan', 'basic')
            is_premium = premium_data.get('status') == PremiumStatus.ACTIVE.value
            
            summary = {
                'user_id': user_id,
                'premium_status': premium_data.get('status'),
                'current_plan': current_plan,
                'is_premium': is_premium,
                'days_remaining': 0,
                'features': {},
                'total_quota_usage': 0,
                'total_quota_limits': 0
            }
            
            if is_premium:
                expiry = datetime.fromisoformat(premium_data['expiry'])
                summary['days_remaining'] = max(0, (expiry - datetime.utcnow()).days)
            
            # Get quota info for all tracked features
            for feature_name, quota_config in self.feature_quotas.items():
                if quota_config.track_usage:
                    quota_info = await self._check_feature_quota(
                        user_id, feature_name, current_plan, summary['days_remaining']
                    )
                    
                    summary['features'][feature_name] = asdict(quota_info)
                    
                    if quota_info.quota_limit > 0:
                        summary['total_quota_usage'] += quota_info.current_usage
                        summary['total_quota_limits'] += quota_info.quota_limit
            
            # Calculate overall utilization
            if summary['total_quota_limits'] > 0:
                summary['overall_utilization'] = round(
                    summary['total_quota_usage'] / summary['total_quota_limits'] * 100, 1
                )
            else:
                summary['overall_utilization'] = 0.0
            
            # Add quota warnings
            warnings = []
            for feature, quota in summary['features'].items():
                if quota['is_over_quota']:
                    warnings.append(f"{feature}: {quota['current_usage']}/{quota['quota_limit']} used")
            
            summary['quota_warnings'] = warnings
            
            logger.debug("Quota summary generated", extra={
                'user_id': user_id,
                'tracked_features': len(summary['features']),
                'quota_warnings': len(warnings),
                'overall_utilization': summary['overall_utilization']
            })
            
            return summary
            
        except Exception as e:
            logger.error("Failed to generate quota summary", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })
            return {
                'user_id': user_id,
                'error': 'Quota summary unavailable',
                'features': {},
                'quota_warnings': []
            }
    
    async def admin_override_access(self, user_id: int, enable: bool = True) -> bool:
        """Enable/disable admin override for user (temporary)."""
        try:
            if enable:
                # Add to override list (in-memory for now)
                self.admin_override_users.add(user_id)
                logger.info("Admin override enabled", extra={'user_id': user_id})
            else:
                self.admin_override_users.discard(user_id)
                logger.info("Admin override disabled", extra={'user_id': user_id})
            
            return True
            
        except Exception as e:
            logger.error("Failed to set admin override", exc_info=True, extra={
                'user_id': user_id,
                'enable': enable,
                'error': str(e)
            })
            return False
    
    async def get_premium_user_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get premium user statistics and revenue metrics.
        
        Args:
            days: Lookback period in days
            
        Returns:
            Comprehensive premium statistics
        """
        try:
            from handlers.stats import get_premium_vs_free_usage  # type: ignore
            
            # Get usage statistics
            usage_stats = await get_premium_vs_free_usage(days)
            
            # Get revenue data (mock for now)
            revenue_data = {
                'period_days': days,
                'total_revenue': 0.0,
                'transaction_count': 0,
                'average_transaction': 0.0,
                'monthly_revenue': 0.0,
                'weekly_revenue': 0.0
            }
            
            # Calculate churn rate (simplified)
            total_premium = usage_stats['premium_users']
            active_premium = sum(1 for uid in await get_active_users('daily') 
                               if await get_premium_data(uid)['status'] == PremiumStatus.ACTIVE.value)
            
            churn_rate = ((total_premium - active_premium) / total_premium * 100) if total_premium > 0 else 0
            
            stats = {
                'period_days': days,
                'total_premium_users': total_premium,
                'active_premium_users': active_premium,
                'premium_user_retention': round((active_premium / total_premium * 100), 1) if total_premium > 0 else 0,
                'churn_rate': round(churn_rate, 1),
                'premium_usage_percentage': usage_stats['premium_usage_percentage'],
                'top_premium_features': await self._get_top_premium_features(days),
                'revenue': revenue_data,
                'subscription_distribution': await self._get_plan_distribution(),
                'generated_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Premium stats generated", extra={
                'period_days': days,
                'premium_users': total_premium,
                'active_premium': active_premium,
                'churn_rate': churn_rate
            })
            
            return stats
            
        except Exception as e:
            logger.error("Failed to generate premium stats", exc_info=True, extra={
                'days': days,
                'error': str(e)
            })
            return {
                'period_days': days,
                'error': 'Statistics unavailable',
                'total_premium_users': 0,
                'active_premium_users': 0
            }
    
    async def _get_top_premium_features(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get most used premium features."""
        try:
            from handlers.stats import get_user_premium_usage  # type: ignore
            
            # Get active premium users
            active_premium_users = []
            all_users = await get_all_users()
            
            for user_data in all_users[:100]:  # Limit for performance
                user_id = user_data['user_id']
                premium_data = await get_premium_data(user_id)
                if premium_data['status'] == PremiumStatus.ACTIVE.value:
                    active_premium_users.append(user_id)
            
            # Aggregate feature usage
            feature_usage = {}
            for user_id in active_premium_users[:50]:  # Sample for performance
                usage = await get_user_premium_usage(user_id, days)
                for feature, count in usage.items():
                    feature_usage[feature] = feature_usage.get(feature, 0) + count
            
            # Sort by usage
            sorted_features = sorted(feature_usage.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return [
                {
                    'feature': feature,
                    'usage_count': count,
                    'percentage_of_total': round(count / sum(v for _, v in sorted_features) * 100, 1)
                }
                for feature, count in sorted_features
            ]
            
        except Exception as e:
            logger.error("Failed to get top premium features", exc_info=True, extra={
                'days': days,
                'error': str(e)
            })
            return []
    
    async def _get_plan_distribution(self) -> Dict[str, Any]:
        """Get current subscription plan distribution."""
        try:
            plan_counts = {}
            total_premium = 0
            
            all_users = await get_all_users()
            for user_data in all_users:
                user_id = user_data['user_id']
                premium_data = await get_premium_data(user_id)
                
                if premium_data['status'] == PremiumStatus.ACTIVE.value:
                    plan = premium_data.get('plan', 'unknown')
                    plan_counts[plan] = plan_counts.get(plan, 0) + 1
                    total_premium += 1
            
            distribution = {
                'total_premium_users': total_premium,
                'plans': {}
            }
            
            for plan_id, count in plan_counts.items():
                plan_obj = next((p for p in PremiumPlan if p.value['id'] == plan_id), None)
                plan_name = plan_obj.value['name'] if plan_obj else plan_id.title()
                percentage = round(count / total_premium * 100, 1) if total_premium > 0 else 0
                
                distribution['plans'][plan_name] = {
                    'count': count,
                    'percentage': percentage,
                    'price_ngn': plan_obj.value['price_ngn'] if plan_obj else 0
                }
            
            return distribution
            
        except Exception as e:
            logger.error("Failed to get plan distribution", exc_info=True, extra={'error': str(e)})
            return {'total_premium_users': 0, 'plans': {}}

# Global premium manager
premium_manager: Optional[PremiumManager] = None

def initialize_premium_manager(
    bot: Bot,
    config: Dict[str, Any] = None,
    redis_client: Optional[Any] = None
) -> PremiumManager:
    """Initialize global premium manager."""
    global premium_manager
    
    if premium_manager is None:
        from utils.error_handler import initialize_error_handler  # type: ignore
        error_handler = initialize_error_handler(bot, config)
        
        premium_manager = PremiumManager(
            bot=bot,
            config=config or {},
            redis_client=redis_client,
            error_handler=error_handler
        )
    
    return premium_manager

# Convenience decorators and functions
def require_premium(feature: Optional[str] = None, **kwargs):
    """Convenience function for premium requirement decorator."""
    global premium_manager
    if not premium_manager:
        raise RuntimeError("Premium manager not initialized")
    
    return premium_manager.require_premium(feature=feature, **kwargs)

async def check_premium_access(user_id: int, feature: Optional[str] = None, **kwargs):
    """Convenience function for premium access check."""
    global premium_manager
    if not premium_manager:
        raise RuntimeError("Premium manager not initialized")
    
    return await premium_manager.check_premium_access(user_id, feature, **kwargs)

def format_currency(amount: float) -> str:
    """Format Naira currency display."""
    return f"₦{amount:,.0f}"
