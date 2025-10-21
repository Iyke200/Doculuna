# utils/usage_tracker.py
"""
DocuLuna Usage Tracker

Provides activity tracking, rate-limiting, quota enforcement, and usage analytics.
Integrates with stats and premium systems for comprehensive monitoring.

Usage:
    from utils import usage_tracker
    
    # Initialize
    tracker = usage_tracker.UsageTracker(config={})
    
    # Track usage
    await tracker.track_activity(user_id=123, activity_type='api_call', metadata={'endpoint': '/process'})
    
    # Rate limit check
    is_allowed = await tracker.check_rate_limit(user_id=123, limit_key='api_requests', limit=100, period=3600)
    
    # Enforce quota
    quota_result = await tracker.enforce_quota(user_id=123, feature='document_process', increment=1)
    
    # Get analytics
    analytics = await tracker.get_usage_analytics(period='daily')
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List, Callable, Awaitable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio
from collections import defaultdict, Counter

from utils.error_handler import ErrorHandler, ErrorContext  # type: ignore
from handlers.premium import PremiumStatus, get_premium_data  # type: ignore
from database.db import update_user_data  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class ActivityRecord:
    """Activity tracking record."""
    user_id: int
    activity_type: str
    timestamp: datetime
    duration: Optional[float] = None
    success: bool = True
    metadata: Dict[str, Any] = None
    quota_consumed: int = 1
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    limit: int
    period_seconds: int
    block_duration: Optional[int] = None  # Seconds to block on violation
    warning_threshold: float = 0.8  # Warn at 80% usage

@dataclass
class QuotaConfig:
    """Quota configuration."""
    limit: int
    period: str  # 'daily', 'weekly', 'monthly'
    overage_allowed: int = 0  # Allowed overage before block
    multiplier_premium: float = 2.0

class UsageTracker:
    """
    Comprehensive usage tracking and limiting system.
    
    Features:
        - Activity logging with metadata
        - Configurable rate limiting
        - Quota enforcement with premium multipliers
        - Usage analytics and reporting
        - Integration with error handler
        - Automatic cleanup of old records
    
    Args:
        config: Configuration dictionary
        redis_client: Redis client for persistent storage
        error_handler: Error handler instance
        retention_days: Days to retain usage data
        rate_limits: Dict of rate limit configs
        quota_configs: Dict of quota configs
    """
    
    DEFAULT_CONFIG = {
        'retention_days': 90,
        'rate_limits': {
            'api_requests': RateLimitConfig(limit=100, period_seconds=3600, block_duration=3600),
            'file_uploads': RateLimitConfig(limit=20, period_seconds=86400, block_duration=0),
            'commands': RateLimitConfig(limit=200, period_seconds=86400, warning_threshold=0.9)
        },
        'quota_configs': {
            'document_processing': QuotaConfig(limit=10, period='daily', overage_allowed=2, multiplier_premium=5.0),
            'ai_queries': QuotaConfig(limit=50, period='daily', overage_allowed=0, multiplier_premium=10.0),
            'storage': QuotaConfig(limit=100, period='monthly', overage_allowed=20, multiplier_premium=10.0)
        },
        'analytics_periods': ['daily', 'weekly', 'monthly'],
        'cleanup_interval_hours': 24
    }
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
        error_handler: Optional[ErrorHandler] = None,
        retention_days: int = 90,
        rate_limits: Optional[Dict[str, RateLimitConfig]] = None,
        quota_configs: Optional[Dict[str, QuotaConfig]] = None
    ):
        self.config = config or {}
        self.redis_client = redis_client
        self.error_handler = error_handler or ErrorHandler()
        self.retention_days = retention_days or self.DEFAULT_CONFIG['retention_days']
        self.rate_limits = rate_limits or self.DEFAULT_CONFIG['rate_limits']
        self.quota_configs = quota_configs or self.DEFAULT_CONFIG['quota_configs']
        
        # Storage prefixes
        self.activity_prefix = "usage:activity"
        self.rate_prefix = "usage:rate"
        self.quota_prefix = "usage:quota"
        self.analytics_prefix = "usage:analytics"
        
        # Redis availability
        self.redis_available = bool(self.redis_client and hasattr(self.redis_client, 'set'))
        
        # Cleanup task
        self.cleanup_task = asyncio.create_task(self._schedule_cleanup())
        
        logger.info("UsageTracker initialized", extra={
            'redis_available': self.redis_available,
            'rate_limits_count': len(self.rate_limits),
            'quota_configs_count': len(self.quota_configs),
            'retention_days': self.retention_days
        })
    
    async def track_activity(
        self,
        user_id: int,
        activity_type: str,
        duration: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track user activity with quota enforcement."""
        try:
            start_time = time.time()
            
            # Create record
            record = ActivityRecord(
                user_id=user_id,
                activity_type=activity_type,
                duration=duration,
                success=success,
                metadata=metadata or {},
                quota_consumed=1  # Default consumption
            )
            
            # Store activity
            await self._store_activity(record)
            
            # Update quotas if applicable
            quota_update = await self._update_quota(record)
            
            # Update analytics
            await self._update_analytics(record)
            
            # Track in stats system
            await stats_tracker.track_user_activity(
                user_id, 
                activity_type,
                {'quota_update': quota_update}
            )
            
            logger.debug("Activity tracked", extra={
                'user_id': user_id,
                'activity_type': activity_type,
                'duration': duration,
                'success': success,
                'quota_consumed': record.quota_consumed,
                'tracking_time_ms': round((time.time() - start_time) * 1000, 2)
            })
            
            return True
            
        except Exception as e:
            await self.error_handler.handle_error(
                e,
                context=ErrorContext(user_id=user_id, operation='track_activity'),
                extra_data={'activity_type': activity_type, 'metadata': metadata}
            )
            return False
    
    async def _store_activity(self, record: ActivityRecord) -> None:
        """Store activity record."""
        try:
            key = f"{self.activity_prefix}:{record.user_id}:{int(time.time())}"
            data = asdict(record)
            
            if self.redis_available:
                ttl = self.retention_days * 86400
                await self.redis_client.setex(key, ttl, json.dumps(data, default=str))
            else:
                # In-memory
                if 'activity_store' not in globals():
                    globals()['activity_store'] = defaultdict(list)
                globals()['activity_store'][record.user_id].append(data)
                
        except Exception as e:
            logger.error("Failed to store activity", extra={'error': str(e)})
    
    async def _update_quota(self, record: ActivityRecord) -> Dict[str, Any]:
        """Update quotas for tracked activities."""
        try:
            quota_update = {
                'updated': False,
                'over_quota': False,
                'quota_consumed': record.quota_consumed
            }
            
            # Check if activity type is quota-tracked
            if record.activity_type not in self.quota_configs:
                return quota_update
            
            quota_config = self.quota_configs[record.activity_type]
            premium_data = await get_premium_data(record.user_id)
            
            # Calculate effective quota
            if premium_data['status'] == PremiumStatus.ACTIVE.value:
                effective_quota = quota_config.limit * quota_config.multiplier_premium
            else:
                effective_quota = quota_config.limit
            
            # Get current usage
            current_usage = await self._get_current_usage(
                record.user_id,
                record.activity_type,
                quota_config.period
            )
            
            # Check if over quota
            if current_usage + record.quota_consumed > effective_quota + quota_config.overage_allowed:
                quota_update['over_quota'] = True
                quota_update['updated'] = False
                
                await self.error_handler.handle_error(
                    Exception("Quota exceeded"),
                    context=ErrorContext(user_id=record.user_id, operation=record.activity_type),
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.BUSINESS_LOGIC
                )
                
                return quota_update
            
            # Increment usage
            if self.redis_available:
                await self.redis_client.incr(quota_key, record.quota_consumed)
            else:
                # In-memory
                if 'quota_store' not in globals():
                    globals()['quota_store'] = defaultdict(int)
                globals()['quota_store'][quota_key] += record.quota_consumed
                
            quota_update['updated'] = True
            
            return quota_update
            
        except Exception as e:
            logger.error("Quota update failed", extra={'error': str(e)})
            return quota_update
    
    async def _update_analytics(self, record: ActivityRecord) -> None:
        """Update usage analytics."""
        try:
            # Mock implementation - expand in production
            pass
            
        except Exception as e:
            logger.error("Analytics update failed", extra={'error': str(e)})
    
    async def check_rate_limit(
        self,
        user_id: int,
        limit_key: str,
        limit: int,
        period: int,
        increment: int = 1
    ) -> bool:
        """Check and enforce rate limit."""
        try:
            rate_key = f"{self.rate_prefix}:{user_id}:{limit_key}"
            
            if self.redis_available:
                current = await self.redis_client.get(rate_key) or 0
                current = int(current)
                
                if current + increment > limit:
                    logger.warning("Rate limit exceeded", extra={
                        'user_id': user_id,
                        'limit_key': limit_key,
                        'current': current,
                        'limit': limit
                    })
                    return False
                
                await self.redis_client.incr(rate_key, increment)
                await self.redis_client.expire(rate_key, period)
                
                return True
            else:
                # In-memory fallback
                if 'rate_store' not in globals():
                    globals()['rate_store'] = defaultdict(int)
                current = globals()['rate_store'][rate_key]
                
                if current + increment > limit:
                    return False
                
                globals()['rate_store'][rate_key] += increment
                
                # Mock expiration (not accurate)
                return True
            
        except Exception as e:
            logger.error("Rate limit check failed", extra={'error': str(e)})
            return True  # Fail open on error
    
    async def enforce_quota(
        self,
        user_id: int,
        feature: str,
        increment: int = 1
    ) -> bool:
        """Enforce feature quota."""
        try:
            if feature not in self.quota_configs:
                return True  # No quota for feature
            
            quota_config = self.quota_configs[feature]
            premium_data = await get_premium_data(user_id)
            is_premium = premium_data['status'] == PremiumStatus.ACTIVE.value
            
            # Calculate limit
            limit = quota_config.premium_quota if is_premium else quota_config.limit
            
            current_usage = await self._get_current_usage(
                user_id, feature, quota_config.period
            )
            
            if current_usage + increment > limit:
                await self.error_handler.handle_error(
                    Exception("Quota exceeded"),
                    context=ErrorContext(user_id=user_id, operation=f"quota_enforce_{feature}"),
                    severity=ErrorSeverity.WARNING
                )
                return False
            
            # Increment
            await self._increment_quota(quota_key, increment)
            
            return True
            
        except Exception as e:
            logger.error("Quota enforcement failed", extra={'error': str(e)})
            return True  # Fail open
    
    async def _get_current_usage(self, user_id: int, feature: str, period: str) -> int:
        """Get current quota usage."""
        try:
            if not self.redis_available:
                return 0
            
            now = datetime.utcnow()
            if period == 'daily':
                date_str = now.strftime('%Y-%m-%d')
            elif period == 'weekly':
                date_str = now.strftime('%Y-W%W')
            elif period == 'monthly':
                date_str = now.strftime('%Y-%m')
            else:
                date_str = 'lifetime'
            
            quota_key = f"{self.quota_prefix}:{user_id}:{feature}:{date_str}"
            usage = await self.redis_client.get(quota_key)
            
            return int(usage or 0)
            
        except Exception as e:
            logger.error("Failed to get quota usage", extra={'error': str(e)})
            return 0
    
    async def _increment_quota(self, quota_key: str, increment: int) -> None:
        """Increment quota counter."""
        try:
            if self.redis_available:
                await self.redis_client.incr(quota_key, increment)
                await self.redis_client.expire(quota_key, 90 * 86400)  # Retention
            else:
                # In-memory
                if 'quota_store' not in globals():
                    globals()['quota_store'] = defaultdict(int)
                globals()['quota_store'][quota_key] += increment
                
        except Exception as e:
            logger.error("Failed to increment quota", extra={'error': str(e)})
    
    async def get_usage_analytics(self, period: str = 'daily', feature: Optional[str] = None) -> Dict[str, Any]:
        """Get usage analytics."""
        try:
            if not self.redis_available:
                return {'error': 'Analytics unavailable - Redis required'}
            
            days = {
                'daily': 1,
                'weekly': 7,
                'monthly': 30
            }.get(period, 7)
            
            now = datetime.utcnow()
            start_date = now - timedelta(days=days)
            
            analytics = {
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': now.isoformat(),
                'total_activities': 0,
                'total_users': 0,
                'average_per_user': 0.0,
                'features': {},
                'quota_violations': 0,
                'rate_limits_hit': 0
            }
            
            # Mock implementation - expand in production
            # ...
            
            logger.info("Usage analytics generated", extra={
                'period': period,
                'feature': feature,
                'total_activities': analytics['total_activities']
            })
            
            return analytics
            
        except Exception as e:
            logger.error("Failed to get usage analytics", extra={'error': str(e)})
            return {'error': 'Analytics generation failed'}

# Global usage tracker
usage_tracker: Optional[UsageTracker] = None

def initialize_usage_tracker(
    config: Dict[str, Any] = None,
    redis_client: Optional[Any] = None,
    error_handler_instance: Optional[ErrorHandler] = None
) -> UsageTracker:
    """Initialize global usage tracker."""
    global usage_tracker
    
    if usage_tracker is None:
        usage_tracker = UsageTracker(
            config=config or {},
            redis_client=redis_client,
            error_handler=error_handler_instance
        )
    
    return usage_tracker

def format_currency(amount: float) -> str:
    """Format Naira currency."""
    return f"₦{amount:,.0f}"

async def check_usage_limit(user_id: int) -> bool:
    """Check if user has exceeded their usage limit."""
    try:
        from database.db import get_user_data, update_user_data
        from datetime import date
        
        user_data = get_user_data(user_id)
        if not user_data:
            return True
        
        usage_today = user_data.get('usage_today', 0)
        usage_reset_date = user_data.get('usage_reset_date')
        is_premium = user_data.get('is_premium', False)
        
        today = date.today().isoformat()
        
        if usage_reset_date != today:
            update_user_data(user_id, {'usage_today': 0, 'usage_reset_date': today})
            usage_today = 0
            logger.info(f"Reset daily usage for user {user_id} - new day detected")
        
        if is_premium:
            return True
        
        from config import FREE_USAGE_LIMIT
        return usage_today < FREE_USAGE_LIMIT
    except Exception as e:
        logger.error(f"Error checking usage limit: {e}")
        return True

async def increment_usage(user_id: int):
    """Increment user's usage counter."""
    try:
        from database.db import get_user_data, update_user_data
        from datetime import date
        
        user_data = get_user_data(user_id)
        if user_data:
            usage_today = user_data.get('usage_today', 0)
            usage_reset_date = user_data.get('usage_reset_date')
            today = date.today().isoformat()
            
            if usage_reset_date != today:
                usage_today = 0
                logger.info(f"Reset daily usage for user {user_id} during increment - new day detected")
            
            update_user_data(user_id, {
                'usage_today': usage_today + 1,
                'usage_reset_date': today
            })
            logger.info(f"Usage incremented for user {user_id}: {usage_today + 1}")
    except Exception as e:
        logger.error(f"Error incrementing usage: {e}")
