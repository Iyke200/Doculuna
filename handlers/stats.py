# stats.py
import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
from io import StringIO
import csv

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import bold as hbold, code as hcode
from dotenv import load_dotenv

# Assuming Redis for stats storage (fallback to in-memory)
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=5, decode_responses=True)
    REDIS_AVAILABLE = True
except ImportError:
    from collections import defaultdict, Counter
    user_stats = defaultdict(lambda: defaultdict(int))
    daily_stats = defaultdict(lambda: Counter())
    tool_usage = Counter()
    premium_usage = defaultdict(int)
    REDIS_AVAILABLE = False

# Import from other modules
from database.db import get_user_data, get_all_users  # type: ignore
from handlers.premium import get_premium_data, PremiumStatus  # type: ignore
from handlers.start import get_user_preferences  # type: ignore

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s - metric=%(metric)s - value=%(value)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class StatType(Enum):
    """Types of statistics tracked."""
    USER_ACTIVE = "user_active"
    USER_NEW = "user_new"
    TOOL_USAGE = "tool_usage"
    PREMIUM_UPGRADE = "premium_upgrade"
    PREMIUM_USAGE = "premium_usage"
    COMMAND_USAGE = "command_usage"
    REFERRAL_CREATED = "referral_created"
    REFERRAL_CONVERSION = "referral_conversion"

# Stats retention periods
STATS_RETENTION = {
    'daily': 90,  # 90 days
    'weekly': 52,  # 1 year
    'monthly': 24,  # 2 years
    'lifetime': None  # Permanent
}

class StatsTracker:
    """Central statistics tracking system."""
    
    def __init__(self):
        self.stats_prefix = "stats"
        self.user_activity_prefix = "user_activity"
        
    async def track_user_activity(self, user_id: int, activity_type: str, 
                                metadata: Dict[str, Any] = None) -> None:
        """Track user activity with metadata."""
        try:
            now = datetime.utcnow()
            date_str = now.strftime('%Y-%m-%d')
            timestamp = now.isoformat()
            
            activity_data = {
                'user_id': user_id,
                'activity_type': activity_type,
                'timestamp': timestamp,
                'date': date_str,
                'metadata': metadata or {}
            }
            
            # Store individual activity
            activity_key = f"{self.user_activity_prefix}:{user_id}:{int(time.time())}"
            
            if REDIS_AVAILABLE:
                redis_client.setex(activity_key, 30 * 86400, json.dumps(activity_data))  # 30 days
            else:
                user_stats[user_id][activity_key] = activity_data
            
            # Update daily counters
            daily_key = f"{self.stats_prefix}:daily:{date_str}:{activity_type}"
            if REDIS_AVAILABLE:
                redis_client.incr(daily_key)
                # Set expiry for daily stats
                redis_client.expire(daily_key, STATS_RETENTION['daily'] * 86400)
            else:
                daily_stats[date_str][activity_type] += 1
            
            logger.debug("User activity tracked", extra={
                'user_id': user_id,
                'activity_type': activity_type,
                'date': date_str,
                'metadata': metadata
            })
            
        except Exception as e:
            logger.error("Failed to track user activity", exc_info=True, extra={
                'user_id': user_id,
                'activity_type': activity_type,
                'error': str(e)
            })
    
    async def track_tool_usage(self, user_id: int, tool_name: str, 
                             duration: float = 0, result: str = "success") -> None:
        """Track specific tool usage."""
        try:
            metadata = {
                'tool': tool_name,
                'duration': duration,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.track_user_activity(user_id, StatType.TOOL_USAGE.value, metadata)
            
            # Update global tool counter
            tool_key = f"{self.stats_prefix}:tools:{tool_name}:{result}"
            if REDIS_AVAILABLE:
                redis_client.incr(tool_key)
            else:
                tool_usage[f"{tool_name}:{result}"] += 1
                
        except Exception as e:
            logger.error("Failed to track tool usage", exc_info=True, extra={
                'user_id': user_id,
                'tool_name': tool_name,
                'error': str(e)
            })
    
    async def track_premium_usage(self, user_id: int, feature: str, 
                                usage_type: str = "access") -> None:
        """Track premium feature usage."""
        try:
            metadata = {
                'feature': feature,
                'usage_type': usage_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.track_user_activity(user_id, StatType.PREMIUM_USAGE.value, metadata)
            
            # Update premium usage counter
            premium_key = f"{self.stats_prefix}:premium:{feature}:{usage_type}"
            if REDIS_AVAILABLE:
                redis_client.incr(premium_key)
            else:
                premium_usage[f"{feature}:{usage_type}"] += 1
                
        except Exception as e:
            logger.error("Failed to track premium usage", exc_info=True, extra={
                'user_id': user_id,
                'feature': feature,
                'error': str(e)
            })
    
    async def track_command_usage(self, user_id: int, command: str) -> None:
        """Track command usage."""
        try:
            await self.track_user_activity(user_id, f"{StatType.COMMAND_USAGE.value}:{command}")
            
            # Update command counter
            cmd_key = f"{self.stats_prefix}:commands:{command}"
            if REDIS_AVAILABLE:
                redis_client.incr(cmd_key)
            else:
                # In-memory counter
                if 'command_usage' not in user_stats[user_id]:
                    user_stats[user_id]['command_usage'] = Counter()
                user_stats[user_id]['command_usage'][command] += 1
                
        except Exception as e:
            logger.error("Failed to track command usage", exc_info=True, extra={
                'user_id': user_id,
                'command': command,
                'error': str(e)
            })
    
    async def record_user_session(self, user_id: int, session_duration: float = None) -> None:
        """Record user session activity."""
        try:
            now = datetime.utcnow()
            date_str = now.strftime('%Y-%m-%d')
            
            session_key = f"{self.user_activity_prefix}:{user_id}:{date_str}"
            session_data = {
                'user_id': user_id,
                'date': date_str,
                'session_count': 1,
                'total_duration': session_duration or 0,
                'last_active': now.isoformat(),
                'activities': 1
            }
            
            if REDIS_AVAILABLE:
                # Use Redis hash for session data
                pipe = redis_client.pipeline()
                pipe.multi()
                pipe.hincrby(session_key, 'session_count', 1)
                if session_duration:
                    pipe.hincrbyfloat(session_key, 'total_duration', session_duration)
                pipe.hset(session_key, 'last_active', now.isoformat())
                pipe.hincrby(session_key, 'activities', 1)
                pipe.expire(session_key, STATS_RETENTION['daily'] * 86400)
                pipe.execute()
            else:
                if session_key not in user_stats[user_id]:
                    user_stats[user_id][session_key] = session_data
                else:
                    existing = user_stats[user_id][session_key]
                    existing['session_count'] += 1
                    if session_duration:
                        existing['total_duration'] += session_duration
                    existing['last_active'] = now.isoformat()
                    existing['activities'] += 1
            
        except Exception as e:
            logger.error("Failed to record user session", exc_info=True, extra={
                'user_id': user_id,
                'error': str(e)
            })

# Global stats tracker
stats_tracker = StatsTracker()

async def get_active_users(period: str = 'daily', count: int = 100) -> List[int]:
    """Get list of recently active users."""
    try:
        end_date = datetime.utcnow()
        if period == 'daily':
            start_date = end_date - timedelta(days=1)
        elif period == 'weekly':
            start_date = end_date - timedelta(weeks=1)
        elif period == 'monthly':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)  # Default weekly
        
        date_range = []
        current = start_date
        while current <= end_date:
            date_range.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        active_users = set()
        
        if REDIS_AVAILABLE:
            # Check daily activity keys
            for date_str in date_range:
                activity_pattern = f"{stats_tracker.user_activity_prefix}:*:activity:{date_str}"
                # Note: Redis KEYS with patterns can be slow in production
                # Consider using Redis Streams or SCAN for large datasets
                keys = redis_client.keys(f"{stats_tracker.user_activity_prefix}:*:{date_str}")
                for key in keys:
                    if 'activity' in key:
                        user_id = key.split(':')[1]
                        active_users.add(int(user_id))
        else:
            # In-memory lookup
            for date_str in date_range:
                for user_id, activities in user_stats.items():
                    for activity_key, activity_data in activities.items():
                        if (isinstance(activity_data, dict) and 
                            activity_data.get('date') == date_str):
                            active_users.add(user_id)
        
        return sorted(list(active_users))[:count]
        
    except Exception as e:
        logger.error("Failed to get active users", exc_info=True, extra={
            'period': period,
            'count': count,
            'error': str(e)
        })
        return []

async def get_tool_usage_frequency(days: int = 30, top_n: int = 10) -> Dict[str, Any]:
    """Get most used tools in the last N days."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        usage_data = Counter()
        
        if REDIS_AVAILABLE:
            # Get tool usage keys from last N days
            for i in range(days):
                date_str = (end_date - timedelta(days=i)).strftime('%Y-%m-%d')
                pattern = f"{stats_tracker.stats_prefix}:tools:*:{date_str}"
                # Note: Use SCAN in production for better performance
                keys = redis_client.keys(f"{stats_tracker.stats_prefix}:tools:*:{date_str}")
                
                for key in keys:
                    count = redis_client.get(key)
                    if count:
                        tool_name = key.split(':')[3]  # Extract tool name
                        usage_data[tool_name] += int(count)
        else:
            # In-memory aggregation
            for tool, count in tool_usage.items():
                if ':' in tool:  # Format: tool_name:result
                    tool_name = tool.split(':')[0]
                    usage_data[tool_name] += count
        
        # Get top N tools
        top_tools = usage_data.most_common(top_n)
        
        return {
            'period_days': days,
            'total_usage': sum(count for _, count in top_tools),
            'top_tools': [
                {'tool': tool, 'usage_count': count, 'percentage': round(count/sum(c for _, c in top_tools)*100, 1)}
                for tool, count in top_tools
            ]
        }
        
    except Exception as e:
        logger.error("Failed to get tool usage frequency", exc_info=True, extra={
            'days': days,
            'top_n': top_n,
            'error': str(e)
        })
        return {'period_days': days, 'total_usage': 0, 'top_tools': []}

async def get_premium_vs_free_usage(days: int = 30) -> Dict[str, Any]:
    """Get premium vs free usage comparison."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        total_users = 0
        premium_users = 0
        premium_usage_count = 0
        free_usage_count = 0
        
        # Get all users from this period
        active_users = await get_active_users('daily' if days <= 7 else 'weekly', 10000)
        total_users = len(active_users)
        
        for user_id in active_users:
            try:
                # Check premium status
                premium_data = await get_premium_data(user_id)
                is_premium = premium_data['status'] == PremiumStatus.ACTIVE.value
                
                if is_premium:
                    premium_users += 1
                    # Count premium feature usage
                    premium_features = await get_user_premium_usage(user_id, days)
                    premium_usage_count += sum(premium_features.values())
                else:
                    # Count free user activity
                    free_features = await get_user_free_usage(user_id, days)
                    free_usage_count += sum(free_features.values())
                    
            except Exception as user_e:
                logger.debug("Skipping user in stats calculation", extra={
                    'user_id': user_id,
                    'error': str(user_e)
                })
                continue
        
        total_usage = premium_usage_count + free_usage_count
        premium_percentage = round((premium_users / total_users * 100), 1) if total_users > 0 else 0
        premium_usage_percentage = round((premium_usage_count / total_usage * 100), 1) if total_usage > 0 else 0
        
        return {
            'period_days': days,
            'total_users': total_users,
            'premium_users': premium_users,
            'premium_user_percentage': premium_percentage,
            'total_feature_usage': total_usage,
            'premium_feature_usage': premium_usage_count,
            'free_feature_usage': free_usage_count,
            'premium_usage_percentage': premium_usage_percentage
        }
        
    except Exception as e:
        logger.error("Failed to get premium vs free usage", exc_info=True, extra={
            'days': days,
            'error': str(e)
        })
        return {
            'period_days': days,
            'total_users': 0,
            'premium_users': 0,
            'premium_user_percentage': 0,
            'total_feature_usage': 0,
            'premium_feature_usage': 0,
            'free_feature_usage': 0,
            'premium_usage_percentage': 0
        }

async def get_user_premium_usage(user_id: int, days: int = 30) -> Dict[str, int]:
    """Get premium feature usage for specific user."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        usage = Counter()
        
        if REDIS_AVAILABLE:
            # Pattern for premium usage keys
            pattern = f"{stats_tracker.user_activity_prefix}:{user_id}:*"
            keys = redis_client.keys(pattern)
            
            for key in keys:
                if 'premium_usage' in key:
                    data = redis_client.get(key)
                    if data:
                        activity = json.loads(data)
                        if (datetime.fromisoformat(activity['timestamp']) >= start_date and 
                            activity['activity_type'] == StatType.PREMIUM_USAGE.value):
                            feature = activity['metadata'].get('feature', 'unknown')
                            usage[feature] += 1
        else:
            # In-memory lookup
            for activity_key, activity_data in user_stats[user_id].items():
                if (isinstance(activity_data, dict) and 
                    activity_data.get('activity_type') == StatType.PREMIUM_USAGE.value and
                    datetime.fromisoformat(activity_data['timestamp']) >= start_date):
                    
                    feature = activity_data['metadata'].get('feature', 'unknown')
                    usage[feature] += 1
        
        return dict(usage)
        
    except Exception as e:
        logger.error("Failed to get user premium usage", exc_info=True, extra={
            'user_id': user_id,
            'days': days,
            'error': str(e)
        })
        return {}

async def get_user_free_usage(user_id: int, days: int = 30) -> Dict[str, int]:
    """Get free feature usage for specific user."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        usage = Counter()
        
        if REDIS_AVAILABLE:
            pattern = f"{stats_tracker.user_activity_prefix}:{user_id}:*"
            keys = redis_client.keys(pattern)
            
            for key in keys:
                if 'tool_usage' in key or 'command_usage' in key:
                    data = redis_client.get(key)
                    if data:
                        activity = json.loads(data)
                        if datetime.fromisoformat(activity['timestamp']) >= start_date:
                            activity_type = activity['activity_type']
                            if activity_type == StatType.TOOL_USAGE.value:
                                tool = activity['metadata'].get('tool', 'unknown')
                                usage[tool] += 1
                            elif activity_type.startswith(StatType.COMMAND_USAGE.value):
                                command = activity_type.split(':')[-1]
                                usage[command] += 1
        else:
            # In-memory lookup
            for activity_key, activity_data in user_stats[user_id].items():
                if isinstance(activity_data, dict):
                    timestamp = datetime.fromisoformat(activity_data['timestamp'])
                    if timestamp >= start_date:
                        activity_type = activity_data['activity_type']
                        
                        if activity_type == StatType.TOOL_USAGE.value:
                            tool = activity_data['metadata'].get('tool', 'unknown')
                            usage[tool] += 1
                        elif activity_type.startswith(StatType.COMMAND_USAGE.value):
                            command = activity_type.split(':')[-1]
                            usage[command] += 1
        
        return dict(usage)
        
    except Exception as e:
        logger.error("Failed to get user free usage", exc_info=True, extra={
            'user_id': user_id,
            'days': days,
            'error': str(e)
        })
        return {}

async def get_admin_stats(period: str = 'daily') -> Dict[str, Any]:
    """Get comprehensive admin statistics."""
    try:
        if period == 'daily':
            days = 1
        elif period == 'weekly':
            days = 7
        elif period == 'monthly':
            days = 30
        else:
            days = 7
        
        # Basic metrics
        total_users = len(await get_all_users())
        active_users = await get_active_users(period, total_users)
        new_users = await get_new_users(days)
        
        # Usage metrics
        tool_usage_data = await get_tool_usage_frequency(days, 10)
        premium_data = await get_premium_vs_free_usage(days)
        
        # Revenue metrics (placeholder for actual integration)
        revenue_data = await get_revenue_stats(days)
        
        # Engagement metrics
        engagement_data = await get_engagement_stats(days)
        
        return {
            'period': period,
            'period_days': days,
            'total_users': total_users,
            'active_users': len(active_users),
            'active_percentage': round(len(active_users)/total_users*100, 1) if total_users > 0 else 0,
            'new_users': len(new_users),
            'new_user_percentage': round(len(new_users)/total_users*100, 1) if total_users > 0 else 0,
            'tool_usage': tool_usage_data,
            'premium_stats': premium_data,
            'revenue_stats': revenue_data,
            'engagement_stats': engagement_data,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get admin stats", exc_info=True, extra={
            'period': period,
            'error': str(e)
        })
        return {
            'period': period,
            'period_days': 1,
            'total_users': 0,
            'active_users': 0,
            'active_percentage': 0,
            'new_users': 0,
            'new_user_percentage': 0,
            'tool_usage': {'top_tools': []},
            'premium_stats': {},
            'revenue_stats': {},
            'engagement_stats': {},
            'generated_at': datetime.utcnow().isoformat()
        }

async def get_new_users(days: int = 7) -> List[int]:
    """Get users who joined in the last N days."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        new_users = []
        
        all_users = await get_all_users()
        for user_data in all_users:
            try:
                created_at = datetime.fromisoformat(user_data.get('created_at', ''))
                if start_date <= created_at <= end_date:
                    new_users.append(user_data['user_id'])
            except (ValueError, TypeError):
                continue
        
        return new_users
        
    except Exception as e:
        logger.error("Failed to get new users", exc_info=True, extra={
            'days': days,
            'error': str(e)
        })
        return []

async def get_revenue_stats(days: int = 30) -> Dict[str, Any]:
    """Get revenue statistics (placeholder for payment integration)."""
    try:
        # This would integrate with payments module
        from payments import payment_orchestrator  # type: ignore
        
        total_revenue = 0.0
        transaction_count = 0
        weekly_revenue = 0.0
        monthly_revenue = 0.0
        
        # Mock data for now - replace with actual payment queries
        mock_transactions = [
            {'amount': 1000, 'plan': 'weekly'},
            {'amount': 3500, 'plan': 'monthly'},
            {'amount': 1000, 'plan': 'weekly'},
            {'amount': 3500, 'plan': 'monthly'} * 5
        ]
        
        for txn in mock_transactions[-days:]:  # Last N transactions
            total_revenue += txn['amount']
            transaction_count += 1
            if txn['plan'] == 'weekly':
                weekly_revenue += txn['amount']
            else:
                monthly_revenue += txn['amount']
        
        avg_transaction = total_revenue / transaction_count if transaction_count > 0 else 0
        
        return {
            'period_days': days,
            'total_revenue': total_revenue,
            'transaction_count': transaction_count,
            'average_transaction': round(avg_transaction, 2),
            'weekly_revenue': weekly_revenue,
            'monthly_revenue': monthly_revenue,
            'weekly_percentage': round(weekly_revenue/total_revenue*100, 1) if total_revenue > 0 else 0,
            'monthly_percentage': round(monthly_revenue/total_revenue*100, 1) if total_revenue > 0 else 0
        }
        
    except Exception as e:
        logger.error("Failed to get revenue stats", exc_info=True, extra={
            'days': days,
            'error': str(e)
        })
        return {
            'period_days': days,
            'total_revenue': 0.0,
            'transaction_count': 0,
            'average_transaction': 0.0,
            'weekly_revenue': 0.0,
            'monthly_revenue': 0.0,
            'weekly_percentage': 0,
            'monthly_percentage': 0
        }

async def get_engagement_stats(days: int = 30) -> Dict[str, Any]:
    """Get user engagement statistics."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        total_sessions = 0
        total_duration = 0.0
        avg_session_duration = 0.0
        retention_rate = 0.0
        
        # Calculate from user activity
        if REDIS_AVAILABLE:
            # Get session keys from last N days
            for i in range(days):
                date_str = (end_date - timedelta(days=i)).strftime('%Y-%m-%d')
                session_pattern = f"{stats_tracker.user_activity_prefix}:*:{date_str}"
                keys = redis_client.keys(session_pattern)
                
                for key in keys:
                    data = redis_client.get(key)
                    if data:
                        session = json.loads(data)
                        total_sessions += session.get('session_count', 1)
                        total_duration += session.get('total_duration', 0)
        else:
            # In-memory calculation
            for user_id, user_data in user_stats.items():
                for session_key, session_data in user_data.items():
                    if (isinstance(session_data, dict) and 
                        'date' in session_data and 
                        start_date <= datetime.fromisoformat(session_data['date']) <= end_date):
                        
                        total_sessions += session_data.get('session_count', 1)
                        total_duration += session_data.get('total_duration', 0)
        
        avg_session_duration = total_duration / total_sessions if total_sessions > 0 else 0
        
        # Retention (day 1 vs day 7 users still active)
        day1_users = await get_new_users(1)
        day7_users = await get_new_users(8)  # Users from 8 days ago
        retained_users = set(day1_users) & set(await get_active_users('daily', len(day1_users)))
        retention_rate = len(retained_users) / len(day1_users) * 100 if day1_users else 0
        
        return {
            'period_days': days,
            'total_sessions': total_sessions,
            'total_duration_minutes': round(total_duration / 60, 1),
            'average_session_duration': round(avg_session_duration, 1),
            'day1_retention': round(retention_rate, 1),
            'active_users': len(await get_active_users('daily'))
        }
        
    except Exception as e:
        logger.error("Failed to get engagement stats", exc_info=True, extra={
            'days': days,
            'error': str(e)
        })
        return {
            'period_days': days,
            'total_sessions': 0,
            'total_duration_minutes': 0,
            'average_session_duration': 0,
            'day1_retention': 0,
            'active_users': 0
        }

async def export_stats(format_type: str = 'json', period: str = 'monthly') -> str:
    """Export statistics in JSON or CSV format."""
    try:
        stats = await get_admin_stats(period)
        
        if format_type.lower() == 'csv':
            # Generate CSV
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Metric', 'Value', 'Period'])
            
            # Basic metrics
            writer.writerow(['Total Users', stats['total_users'], period])
            writer.writerow(['Active Users', stats['active_users'], period])
            writer.writerow(['Active %', f"{stats['active_percentage']}%", period])
            writer.writerow(['New Users', stats['new_users'], period])
            writer.writerow(['New User %', f"{stats['new_user_percentage']}%", period])
            
            # Premium metrics
            writer.writerow([], '')  # Empty row
            writer.writerow(['Premium Users', stats['premium_stats']['premium_users'], period])
            writer.writerow(['Premium %', f"{stats['premium_stats']['premium_user_percentage']}%", period])
            writer.writerow(['Premium Usage %', f"{stats['premium_stats']['premium_usage_percentage']}%", period])
            
            # Tool usage
            writer.writerow([], '')  # Empty row
            writer.writerow(['Top Tool', 'Usage', f"{stats['tool_usage']['period_days']} days"])
            for tool_data in stats['tool_usage']['top_tools']:
                writer.writerow([tool_data['tool'], tool_data['usage_count'], tool_data['percentage']])
            
            return output.getvalue()
        else:
            # JSON format
            return json.dumps(stats, indent=2, default=str)
            
    except Exception as e:
        logger.error("Failed to export stats", exc_info=True, extra={
            'format': format_type,
            'period': period,
            'error': str(e)
        })
        return json.dumps({'error': 'Export failed', 'message': str(e)})

# Admin-only stats dashboard
async def stats_dashboard_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /stats command for admin dashboard."""
    user_id = message.from_user.id
    
    # Admin authorization
    from admin import get_user_role  # type: ignore
    role = get_user_role(user_id)
    
    if role not in ['moderator', 'superadmin']:
        await message.reply("❌ *Admin Access Required*\n\nThis command is only available to administrators.")
        return
    
    try:
        # Get comprehensive stats
        daily_stats = await get_admin_stats('daily')
        weekly_stats = await get_admin_stats('weekly')
        monthly_stats = await get_admin_stats('monthly')
        
        # Format dashboard
        dashboard = f"📊 *DocuLuna Admin Dashboard* 📊\n\n"
        
        # Overview
        dashboard += f"🔢 *Total Users:* {daily_stats['total_users']:,}\n"
        dashboard += f"🟢 *Active Today:* {daily_stats['active_users']:,} ({daily_stats['active_percentage']}%) \n"
        dashboard += f"➕ *New Today:* {daily_stats['new_users']:,} ({daily_stats['new_user_percentage']}%) \n\n"
        
        # Premium stats
        dashboard += f"💎 *Premium Users:* {daily_stats['premium_stats']['premium_users']:,}\n"
        dashboard += f"📈 *Premium Usage:* {daily_stats['premium_stats']['premium_usage_percentage']}%\n\n"
        
        # Engagement
        dashboard += f"⚡ *Sessions Today:* {daily_stats['engagement_stats']['total_sessions']:,}\n"
        dashboard += f"⏱️ *Avg Session:* {daily_stats['engagement_stats']['average_session_duration']:.1f}s\n"
        dashboard += f"🎯 *Day 1 Retention:* {daily_stats['engagement_stats']['day1_retention']:.1f}%\n\n"
        
        # Top tools
        dashboard += f"🛠️ *Top Tools (Today):*\n"
        if daily_stats['tool_usage']['top_tools']:
            for i, tool_data in enumerate(daily_stats['tool_usage']['top_tools'][:5], 1):
                percentage = tool_data['percentage']
                dashboard += f"{i}. {hbold(tool_data['tool'])} - {tool_data['usage_count']:,} ({percentage}%)\n"
        else:
            dashboard += f"• No tool usage data yet\n"
        
        dashboard += f"\n💰 *Revenue Snapshot:*\n"
        dashboard += f"• Today: {format_currency(daily_stats['revenue_stats']['total_revenue'])}\n"
        dashboard += f"• Weekly: {format_currency(weekly_stats['revenue_stats']['total_revenue'])}\n"
        dashboard += f"• Monthly: {format_currency(monthly_stats['revenue_stats']['total_revenue'])}\n\n"
        
        # Quick actions
        dashboard += f"🔧 *Quick Actions:*\n"
        dashboard += f"• `/stats weekly` - Weekly view\n"
        dashboard += f"• `/stats monthly` - Monthly view\n"
        dashboard += f"• `/stats export json` - Export data\n"
        dashboard += f"• `/stats export csv` - CSV export\n\n"
        
        dashboard += f"📅 *Generated:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Add export buttons
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        weekly_btn = types.InlineKeyboardButton("📈 Weekly", callback_data="stats_weekly")
        monthly_btn = types.InlineKeyboardButton("📊 Monthly", callback_data="stats_monthly")
        json_btn = types.InlineKeyboardButton("📄 JSON Export", callback_data="stats_export_json")
        csv_btn = types.InlineKeyboardButton("📊 CSV Export", callback_data="stats_export_csv")
        
        keyboard.add(weekly_btn, monthly_btn)
        keyboard.add(json_btn, csv_btn)
        
        await message.reply(dashboard, parse_mode='Markdown', reply_markup=keyboard)
        
        logger.info("Admin stats dashboard shown", extra={
            'admin_id': user_id,
            'period': 'daily',
            'total_users': daily_stats['total_users']
        })
        
    except Exception as e:
        logger.error("Stats dashboard error", exc_info=True, extra={
            'admin_id': user_id,
            'error': str(e)
        })
        await message.reply(
            "❌ *Dashboard Error*\n\n"
            "Unable to generate statistics. Please try again later.\n"
            "Contact technical support if the issue persists."
        )

async def handle_stats_callbacks(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle stats dashboard callbacks."""
    user_id = callback.from_user.id
    data = callback.data
    
    # Admin authorization
    from admin import get_user_role  # type: ignore
    role = get_user_role(user_id)
    
    if role not in ['moderator', 'superadmin']:
        await callback.answer("Admin access required.")
        return
    
    try:
        if data == 'stats_weekly':
            await stats_dashboard_handler_weekly(callback.message, state)
        elif data == 'stats_monthly':
            await stats_dashboard_handler_monthly(callback.message, state)
        elif data == 'stats_export_json':
            export_data = await export_stats('json', 'monthly')
            await callback.message.reply_document(
                types.InputFile.from_string(
                    export_data, 
                    filename=f"doculuna_stats_{datetime.now().strftime('%Y%m%d')}.json"
                ),
                caption="📊 *Monthly Stats Export*\n\nJSON format for analysis."
            )
        elif data == 'stats_export_csv':
            export_data = await export_stats('csv', 'monthly')
            await callback.message.reply_document(
                types.InputFile.from_string(
                    export_data, 
                    filename=f"doculuna_stats_{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                caption="📊 *Monthly Stats Export*\n\nCSV format for spreadsheets."
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error("Stats callback error", exc_info=True, extra={
            'admin_id': user_id,
            'callback_data': data,
            'error': str(e)
        })
        await callback.answer("Export failed. Please try again.")

async def stats_dashboard_handler_weekly(message: types.Message, state: FSMContext) -> None:
    """Weekly stats dashboard."""
    await stats_dashboard_handler(message, state, 'weekly')

async def stats_dashboard_handler_monthly(message: types.Message, state: FSMContext) -> None:
    """Monthly stats dashboard."""
    await stats_dashboard_handler(message, state, 'monthly')

def register_stats_handlers(dp: Dispatcher) -> None:
    """Register all stats handlers."""
    # Main stats command with period parameter
    async def stats_command_wrapper(message: types.Message, state: FSMContext):
        text = message.text.strip()
        period = 'daily'
        
        if len(text.split()) > 1:
            period_arg = text.split()[1].lower()
            if period_arg in ['daily', 'weekly', 'monthly']:
                period = period_arg
        
        await stats_dashboard_handler(message, state, period)
    
    # aiogram 3.x syntax
    dp.message.register(
        stats_command_wrapper,
        Command("stats")
    )
    
    # Register callback handlers
    from handlers.callbacks import process_callback_query
    original_process = process_callback_query
    
    async def enhanced_stats_callback(callback: types.CallbackQuery, state: FSMContext):
        """Enhanced callback handler for stats."""
        if callback.data and callback.data.startswith('stats_'):
            await handle_stats_callbacks(callback, state)
            return
        
        # Original callback processing
        await original_process(callback, state)
    
    # Monkey patch
    import handlers.callbacks as callbacks
    if hasattr(callbacks, 'original_callback_process'):
        callbacks.process_callback_query = enhanced_stats_callback
    else:
        callbacks.original_callback_process = original_process
        callbacks.process_callback_query = enhanced_stats_callback
    
    logger.info("Stats handlers registered with admin dashboard")

# Track command usage for stats
async def track_stats_command_usage(user_id: int, command: str):
    """Track stats command usage for internal metrics."""
    try:
        await stats_tracker.track_command_usage(user_id, command)
    except Exception as e:
        logger.debug("Failed to track stats command usage", extra={
            'user_id': user_id,
            'command': command,
            'error': str(e)
        })

# Auto-track /stats command
def stats_command_decorator(handler):
    """Decorator to track stats command usage."""
    async def wrapper(message: types.Message, state: FSMContext):
        await track_stats_command_usage(message.from_user.id, 'stats')
        return await handler(message, state)
    return wrapper

__all__ = [
    'stats_tracker', 'StatsTracker', 'StatType',
    'get_active_users', 'get_tool_usage_frequency',
    'get_premium_vs_free_usage', 'get_admin_stats',
    'export_stats', 'register_stats_handlers'
    ]
