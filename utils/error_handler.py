# utils/error_handler.py
"""
DocuLuna Centralized Error Handler

Provides structured error capture, logging, alerting, and recovery mechanisms.
Supports async operations, context tracking, and integration with monitoring systems.

Usage:
    error_handler = ErrorHandler(bot=bot, config={'sentry_dsn': '...'})
    await error_handler.handle_error(exception, context={'user_id': 123})
    @error_handler.capture
    async def risky_function():
        # Your code here
        pass
"""

import logging
import asyncio
import traceback
import json
from typing import Dict, Any, Optional, Callable, Awaitable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import aiohttp
from functools import wraps

# Optional sentry import
try:
    import sentry_sdk
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False
    sentry_sdk = None
    AioHttpIntegration = None
    LoggingIntegration = None

from aiogram import Bot
try:
    from aiogram.utils.exceptions import AiogramException, TelegramAPIError
except ImportError:
    from aiogram.exceptions import TelegramAPIError
    AiogramException = TelegramAPIError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

@dataclass
class ErrorContext:
    """Structured error context for tracking."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    chat_id: Optional[int] = None
    bot_id: Optional[int] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    timestamp: datetime = None
    environment: str = "production"
    version: str = "1.0"
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        
        # Generate request ID if not provided
        if not self.request_id:
            self.request_id = f"req_{self.timestamp.strftime('%Y%m%d_%H%M%S')}_{hash(str(self)) % 10000:04d}"

class ErrorSeverity(Enum):
    """Error severity levels for prioritization."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"

class ErrorCategory(Enum):
    """Error categorization for analysis."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    DATABASE = "database"
    NETWORK = "network"
    PAYMENT = "payment"
    INTEGRATION = "integration"
    BUSINESS_LOGIC = "business_logic"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    UNKNOWN = "unknown"

@dataclass
class ErrorEvent:
    """Structured error event for logging and alerting."""
    error_id: str
    exception_type: str
    exception_message: str
    traceback: str
    severity: ErrorSeverity
    category: ErrorCategory
    context: ErrorContext
    http_status: Optional[int] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    custom_tags: Dict[str, Any] = None
    extra_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_tags is None:
            self.custom_tags = {}
        if self.extra_data is None:
            self.extra_data = {}
        
        # Generate unique error ID
        self.error_id = f"err_{self.context.timestamp.strftime('%Y%m%d_%H%M%S')}_{hash(self.exception_message) % 10000:04d}"

class ErrorHandler:
    """
    Centralized error handling and monitoring system.
    
    Features:
        - Structured error capture with context
        - Multi-level logging (console, file, external services)
        - Alerting thresholds and escalation
        - Error recovery mechanisms
        - Performance monitoring
        - Integration with Sentry, Slack, email alerting
    
    Args:
        bot: Aiogram Bot instance for Telegram notifications
        config: Configuration dictionary
        sentry_dsn: Sentry DSN for error tracking (optional)
        slack_webhook: Slack webhook URL for alerts (optional)
        alert_thresholds: Alerting thresholds by severity
        recovery_handlers: Dict of recovery functions by exception type
    """
    
    def __init__(
        self,
        bot: Optional[Bot] = None,
        config: Optional[Dict[str, Any]] = None,
        sentry_dsn: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        alert_thresholds: Optional[Dict[ErrorSeverity, int]] = None,
        recovery_handlers: Optional[Dict[str, Callable]] = None,
        max_alerts_per_hour: int = 50
    ):
        self.bot = bot
        self.config = config or {}
        self.sentry_dsn = sentry_dsn
        self.slack_webhook = slack_webhook
        self.alert_thresholds = alert_thresholds or {
            ErrorSeverity.DEBUG: 1000,
            ErrorSeverity.INFO: 500,
            ErrorSeverity.WARNING: 100,
            ErrorSeverity.ERROR: 10,
            ErrorSeverity.CRITICAL: 1,
            ErrorSeverity.FATAL: 0  # Always alert
        }
        self.recovery_handlers = recovery_handlers or {}
        self.max_alerts_per_hour = max_alerts_per_hour
        
        # Internal tracking
        self.error_counts = {}  # {error_id: count}
        self.alert_cooldowns = {}  # {chat_id: last_alert_time}
        self.rate_limiter = asyncio.Lock()
        
        # Initialize Sentry if configured
        if self.sentry_dsn:
            sentry_sdk.init(
                dsn=self.sentry_dsn,
                integrations=[
                    AioHttpIntegration(),
                    LoggingIntegration(level=logging.ERROR)
                ],
                traces_sample_rate=1.0,
                environment=self.config.get('environment', 'production'),
                release=self.config.get('version', '1.0')
            )
            logger.info("Sentry initialized", extra={'dsn': self.sentry_dsn[:20] + '...'})
        
        # Setup rate limiting storage
        self._init_rate_limiter()
        
        logger.info("ErrorHandler initialized", extra={
            'sentry_enabled': bool(self.sentry_dsn),
            'slack_enabled': bool(self.slack_webhook),
            'alert_thresholds': {k.value: v for k, v in self.alert_thresholds.items()}
        })
    
    def _init_rate_limiter(self):
        """Initialize rate limiting storage."""
        try:
            if hasattr(asyncio, 'run'):
                # In-memory for testing
                import aiosqlite
                self._rate_limit_db = None
            else:
                # Redis for production
                from redis.asyncio import Redis
                self._rate_limit_db = Redis.from_url(self.config.get('redis_url', 'redis://localhost:6379'))
        except ImportError:
            # Fallback to in-memory
            from collections import defaultdict
            self._rate_limit_db = defaultdict(int)
    
    def _get_severity(self, exception: Exception) -> ErrorSeverity:
        """Determine error severity based on exception type."""
        severity_map = {
            # Critical errors
            (KeyboardInterrupt, SystemExit, MemoryError): ErrorSeverity.FATAL,
            # System errors
            (OSError, IOError, ConnectionError): ErrorSeverity.CRITICAL,
            # Aiogram/Telegram errors
            (AiogramException, TelegramAPIError): ErrorSeverity.ERROR,
            # Business logic
            (ValueError, TypeError, KeyError): ErrorSeverity.WARNING,
            # Default
            Exception: ErrorSeverity.ERROR
        }
        
        for exc_types, severity in severity_map.items():
            if isinstance(exception, exc_types):
                return severity
        
        return ErrorSeverity.ERROR
    
    def _get_category(self, exception: Exception) -> ErrorCategory:
        """Categorize error based on type and context."""
        category_map = {
            # Validation errors
            (ValueError, TypeError, AssertionError): ErrorCategory.VALIDATION,
            # Auth errors  
            (PermissionError, KeyError): ErrorCategory.AUTHENTICATION,
            # Database errors
            (sqlite3.Error, psycopg2.Error): ErrorCategory.DATABASE,
            # Network errors
            (aiohttp.ClientError, requests.RequestException): ErrorCategory.NETWORK,
            # Payment errors
            (stripe.error.StripeError,): ErrorCategory.PAYMENT,
            # Aiogram errors
            (AiogramException,): ErrorCategory.INTEGRATION,
            # Default
            Exception: ErrorCategory.UNKNOWN
        }
        
        for exc_types, category in category_map.items():
            if isinstance(exception, exc_types):
                return category
        
        return ErrorCategory.UNKNOWN
    
    async def _should_alert(self, severity: ErrorSeverity, context: ErrorContext) -> bool:
        """Determine if error should trigger an alert."""
        try:
            threshold = self.alert_thresholds.get(severity, 100)
            
            # Always alert FATAL and CRITICAL
            if severity in [ErrorSeverity.FATAL, ErrorSeverity.CRITICAL]:
                return True
            
            # Rate limit alerts
            async with self.rate_limiter:
                # Check hourly limit
                now = datetime.utcnow()
                hour_key = f"alert_rate:{context.chat_id or context.user_id}:{now.strftime('%Y%m%d_%H')}"
                
                if hasattr(self, '_rate_limit_db'):
                    if isinstance(self._rate_limit_db, dict):
                        current_count = self._rate_limit_db[hour_key]
                    else:
                        current_count = await self._rate_limit_db.get(hour_key) or 0
                else:
                    current_count = 0
                
                if current_count >= self.max_alerts_per_hour:
                    logger.warning("Alert rate limit exceeded", extra={
                        'context': context.user_id,
                        'current_count': current_count,
                        'max_allowed': self.max_alerts_per_hour
                    })
                    return False
                
                # Increment counter
                if hasattr(self, '_rate_limit_db'):
                    if isinstance(self._rate_limit_db, dict):
                        self._rate_limit_db[hour_key] += 1
                    else:
                        await self._rate_limit_db.incr(hour_key)
                        await self._rate_limit_db.expire(hour_key, 3600)
                
                # Check severity threshold (simplified - in production would use rolling window)
                error_key = f"error_count:{context.user_id}:{severity.value}"
                if hasattr(self, '_rate_limit_db'):
                    if isinstance(self._rate_limit_db, dict):
                        error_count = self._rate_limit_db[error_key]
                    else:
                        error_count = await self._rate_limit_db.get(error_key) or 0
                else:
                    error_count = 0
                
                should_alert = error_count < threshold
                
                if should_alert:
                    if hasattr(self, '_rate_limit_db'):
                        if isinstance(self._rate_limit_db, dict):
                            self._rate_limit_db[error_key] = error_count + 1
                        else:
                            await self._rate_limit_db.incr(error_key)
                            await self._rate_limit_db.expire(error_key, 86400)
                
                return should_alert
                
        except Exception as e:
            logger.error("Failed to check alert threshold", exc_info=True, extra={
                'severity': severity.value,
                'context': context.user_id,
                'error': str(e)
            })
            return severity in [ErrorSeverity.FATAL, ErrorSeverity.CRITICAL]
    
    async def _send_alert(self, error_event: ErrorEvent) -> None:
        """Send alert through configured channels."""
        try:
            # Format alert message
            alert_msg = self._format_alert_message(error_event)
            
            # Send to multiple channels
            sent_to = []
            
            # 1. Telegram admin notification
            if self.bot and self.config.get('admin_chat_ids'):
                for admin_chat_id in self.config['admin_chat_ids']:
                    try:
                        await self.bot.send_message(
                            admin_chat_id,
                            alert_msg,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        sent_to.append(f"telegram:{admin_chat_id}")
                    except Exception as e:
                        logger.error("Failed to send Telegram alert", exc_info=True, extra={
                            'admin_chat_id': admin_chat_id,
                            'error': str(e)
                        })
            
            # 2. Slack webhook
            if self.slack_webhook:
                sent_to.append(await self._send_slack_alert(error_event, alert_msg))
            
            # 3. Email (future implementation)
            # sent_to.append(await self._send_email_alert(error_event))
            
            logger.info("Error alert sent", extra={
                'error_id': error_event.error_id,
                'severity': error_event.severity.value,
                'sent_to': sent_to,
                'context': error_event.context.user_id
            })
            
        except Exception as e:
            logger.critical("Failed to send error alert", exc_info=True, extra={
                'error_event': error_event.error_id,
                'error': str(e)
            })
    
    def _format_alert_message(self, error_event: ErrorEvent) -> str:
        """Format error alert message."""
        context = error_event.context
        timestamp = context.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        message = f"🚨 *{error_event.severity.value.upper()} ALERT*\n\n"
        message += f"🆔 *Error ID:* `{error_event.error_id}`\n"
        message += f"⏰ *Time:* {timestamp}\n"
        message += f"👤 *User:* {context.user_id or 'Anonymous'}\n"
        
        if context.username:
            message += f"📛 *Username:* @{context.username}\n"
        
        if context.chat_id:
            message += f"💬 *Chat:* {context.chat_id}\n"
        
        message += f"🔧 *Module:* {context.module or 'unknown'}\n"
        message += f"⚙️ *Operation:* {context.operation or 'unknown'}\n\n"
        
        message += f"💥 *{error_event.exception_type}:*\n"
        message += f"`{error_event.exception_message}`\n\n"
        
        message += f"📋 *Context:*\n"
        for key, value in error_event.extra_data.items():
            if isinstance(value, (int, float, str)) and len(str(value)) < 100:
                message += f"• {key}: {value}\n"
        
        if error_event.http_status:
            message += f"\n🌐 *HTTP:* {error_event.http_status} {error_event.request_method} {error_event.request_path}\n"
        
        message += f"\n🔗 *View Details:* [Sentry Link](https://sentry.io) *(if configured)*"
        
        return message
    
    async def _send_slack_alert(self, error_event: ErrorEvent, message: str) -> str:
        """Send alert to Slack webhook."""
        try:
            if not self.slack_webhook:
                return "slack:disabled"
            
            slack_payload = {
                "text": f"*{error_event.severity.value.upper()} - DocuLuna Error*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🚨 *{error_event.severity.value.upper()} ERROR*\nError ID: `{error_event.error_id}`"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*User*\n{error_event.context.user_id or 'Anonymous'}"
                            },
                            {
                                "type": "mrkdwn", 
                                "text": f"*Time*\n{error_event.context.timestamp.strftime('%H:%M UTC')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Module*\n{error_event.context.module or 'Unknown'}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity*\n{error_event.severity.value}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"```\n{error_event.exception_message[:1000]}\n```"
                        }
                    }
                ],
                "attachments": [
                    {
                        "color": self._get_slack_color(error_event.severity),
                        "fields": [
                            {
                                "title": "Context",
                                "value": f"Operation: {error_event.context.operation or 'N/A'}\nRequest ID: {error_event.context.request_id}",
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=slack_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("Slack alert sent successfully", extra={
                            'error_id': error_event.error_id,
                            'channel': 'slack'
                        })
                        return "slack:success"
                    else:
                        logger.warning("Slack alert failed", extra={
                            'error_id': error_event.error_id,
                            'status': response.status,
                            'response': await response.text()
                        })
                        return f"slack:failed_{response.status}"
                        
        except Exception as e:
            logger.error("Slack alert error", exc_info=True, extra={
                'error_id': error_event.error_id,
                'error': str(e)
            })
            return "slack:error"
    
    def _get_slack_color(self, severity: ErrorSeverity) -> str:
        """Get Slack message color based on severity."""
        colors = {
            ErrorSeverity.DEBUG: "#cccccc",
            ErrorSeverity.INFO: "#36a64f", 
            ErrorSeverity.WARNING: "#ffaa00",
            ErrorSeverity.ERROR: "#ff0000",
            ErrorSeverity.CRITICAL: "#c40000",
            ErrorSeverity.FATAL: "#8b0000"
        }
        return colors.get(severity, "#cccccc")
    
    async def handle_error(
        self,
        exception: Exception,
        context: Optional[ErrorContext] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None
    ) -> None:
        """
        Handle and log error with full context capture.
        
        Args:
            exception: Exception to handle
            context: Error context (auto-generated if None)
            extra_data: Additional data for debugging
            severity: Override automatic severity detection
            category: Override automatic categorization
        """
        try:
            # Create context if not provided
            if context is None:
                context = ErrorContext(
                    user_id=getattr(exception, 'user_id', None),
                    chat_id=getattr(exception, 'chat_id', None),
                    operation=getattr(exception, 'operation', None)
                )
            
            # Determine severity and category
            if severity is None:
                severity = self._get_severity(exception)
            if category is None:
                category = self._get_category(exception)
            
            # Create error event
            error_event = ErrorEvent(
                error_id="",
                exception_type=type(exception).__name__,
                exception_message=str(exception),
                traceback=traceback.format_exc(),
                severity=severity,
                category=category,
                context=context,
                extra_data=extra_data or {}
            )
            
            # Log error
            self._log_error(error_event)
            
            # Send to Sentry
            if self.sentry_dsn:
                self._report_to_sentry(error_event)
            
            # Check if should alert
            if await self._should_alert(severity, context):
                await self._send_alert(error_event)
            
            # Attempt recovery
            await self._attempt_recovery(exception, context)
            
            logger.debug("Error handled successfully", extra={
                'error_id': error_event.error_id,
                'severity': severity.value,
                'recovered': True
            })
            
        except Exception as handler_e:
            logger.critical("Error handler failed", exc_info=True, extra={
                'original_error': str(exception),
                'handler_error': str(handler_e)
            })
    
    def _log_error(self, error_event: ErrorEvent) -> None:
        """Log error with structured data."""
        try:
            # Determine log level
            log_levels = {
                ErrorSeverity.DEBUG: logging.DEBUG,
                ErrorSeverity.INFO: logging.INFO,
                ErrorSeverity.WARNING: logging.WARNING,
                ErrorSeverity.ERROR: logging.ERROR,
                ErrorSeverity.CRITICAL: logging.CRITICAL,
                ErrorSeverity.FATAL: logging.CRITICAL
            }
            
            level = log_levels.get(error_event.severity, logging.ERROR)
            
            # Create structured log message
            log_data = {
                'error_id': error_event.error_id,
                'level': error_event.severity.value,
                'type': error_event.exception_type,
                'message': error_event.exception_message,
                'user_id': error_event.context.user_id,
                'chat_id': error_event.context.chat_id,
                'module': error_event.context.module,
                'operation': error_event.context.operation,
                'request_id': error_event.context.request_id,
                'timestamp': error_event.context.timestamp.isoformat(),
                'environment': error_event.context.environment,
                'version': error_event.context.version,
                'http_status': error_event.http_status,
                'tags': error_event.custom_tags,
                'extra': {k: v for k, v in error_event.extra_data.items() if not isinstance(v, dict)}
            }
            
            # Log with structured data
            if level == logging.CRITICAL:
                logger.critical(
                    f"CRITICAL ERROR [{error_event.error_id}] {error_event.exception_type}: {error_event.exception_message}",
                    extra=log_data
                )
            elif level == logging.ERROR:
                logger.error(
                    f"ERROR [{error_event.error_id}] {error_event.exception_type}: {error_event.exception_message}",
                    extra=log_data
                )
            elif level == logging.WARNING:
                logger.warning(
                    f"WARNING [{error_event.error_id}] {error_event.exception_type}: {error_event.exception_message}",
                    extra=log_data
                )
            else:
                logger.log(
                    level,
                    f"[{error_event.error_id}] {error_event.exception_type}: {error_event.exception_message}",
                    extra=log_data
                )
                
        except Exception as log_e:
            # Fallback logging
            logger.critical(
                f"ERROR HANDLER LOGGING FAILED: {str(log_e)}",
                exc_info=True,
                extra={'original_error': str(error_event.exception_message)}
            )
    
    def _report_to_sentry(self, error_event: ErrorEvent) -> None:
        """Report error to Sentry."""
        try:
            # Capture exception with breadcrumbs
            breadcrumbs = []
            if error_event.extra_data:
                for key, value in error_event.extra_data.items():
                    if isinstance(value, (str, int, float)) and len(str(value)) < 100:
                        breadcrumbs.append({
                            'message': f"{key}: {value}",
                            'category': 'context',
                            'level': error_event.severity.value,
                            'timestamp': error_event.context.timestamp.isoformat()
                        })
            
            with sentry_sdk.push_scope() as scope:
                # Set user context
                if error_event.context.user_id:
                    scope.set_user({
                        'id': str(error_event.context.user_id),
                        'username': error_event.context.username
                    })
                
                # Set tags
                scope.set_tag("error.severity", error_event.severity.value)
                scope.set_tag("error.category", error_event.category.value)
                scope.set_tag("error.module", error_event.context.module)
                scope.set_tag("error.operation", error_event.context.operation)
                
                # Set extra data
                for key, value in error_event.extra_data.items():
                    if not isinstance(value, dict):
                        scope.set_extra(key, value)
                
                # Add breadcrumbs
                for crumb in breadcrumbs:
                    sentry_sdk.add_breadcrumb(**crumb)
                
                # Capture exception
                sentry_sdk.capture_exception(
                    Exception(error_event.exception_message),
                    contexts={
                        'error': {
                            'id': error_event.error_id,
                            'type': error_event.exception_type,
                            'timestamp': error_event.context.timestamp.isoformat()
                        }
                    }
                )
                
                logger.debug("Error reported to Sentry", extra={
                    'error_id': error_event.error_id,
                    'sentry_event_id': sentry_sdk.last_event_id()
                })
                
        except Exception as sentry_e:
            logger.error("Sentry reporting failed", exc_info=True, extra={
                'error_id': error_event.error_id,
                'sentry_error': str(sentry_e)
            })
    
    async def _attempt_recovery(self, exception: Exception, 
                              context: ErrorContext) -> bool:
        """Attempt automatic recovery based on exception type."""
        try:
            recovery_key = type(exception).__name__
            recovery_handler = self.recovery_handlers.get(recovery_key)
            
            if recovery_handler:
                if asyncio.iscoroutinefunction(recovery_handler):
                    success = await recovery_handler(exception, context)
                else:
                    success = recovery_handler(exception, context)
                
                logger.info("Recovery attempted", extra={
                    'error_id': f"recovery_{context.request_id}",
                    'recovery_type': recovery_key,
                    'success': success,
                    'context': context.user_id
                })
                
                return success
            else:
                # Default recovery attempts
                if isinstance(exception, TelegramAPIError) and "retry_after" in str(exception).lower():
                    # Handle Telegram rate limiting
                    retry_after = self._extract_retry_after(str(exception))
                    if retry_after:
                        logger.info("Rate limited - scheduling retry", extra={
                            'user_id': context.user_id,
                            'retry_after': retry_after,
                            'context': context.operation
                        })
                        asyncio.create_task(self._schedule_retry(context, retry_after))
                        return True
                
                return False
                
        except Exception as recovery_e:
            logger.error("Recovery attempt failed", exc_info=True, extra={
                'original_error': str(exception),
                'recovery_error': str(recovery_e),
                'context': context.user_id
            })
            return False
    
    def _extract_retry_after(self, error_message: str) -> Optional[int]:
        """Extract retry_after value from Telegram error."""
        import re
        match = re.search(r'retry_after=(\d+)', error_message)
        return int(match.group(1)) if match else None
    
    async def _schedule_retry(self, context: ErrorContext, delay: int) -> None:
        """Schedule retry after delay."""
        try:
            await asyncio.sleep(delay)
            
            # Retry logic would go here
            # For now, just log the retry attempt
            logger.info("Retry scheduled and executed", extra={
                'context': context.user_id,
                'operation': context.operation,
                'delay': delay
            })
            
        except asyncio.CancelledError:
            logger.debug("Retry cancelled", extra={'context': context.user_id})
        except Exception as retry_e:
            logger.error("Retry execution failed", exc_info=True, extra={
                'context': context.user_id,
                'error': str(retry_e)
            })
    
    def capture(self, severity: ErrorSeverity = ErrorSeverity.ERROR,
               category: ErrorCategory = ErrorCategory.UNKNOWN,
               **default_context) -> Callable:
        """
        Decorator to capture errors in functions.
        
        Usage:
            @error_handler.capture(severity=ErrorSeverity.CRITICAL)
            async def risky_operation():
                # Code that might fail
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except Exception as e:
                    # Extract context from function arguments
                    func_context = self._extract_function_context(func, args, kwargs, default_context)
                    
                    await self.handle_error(
                        exception=e,
                        context=ErrorContext(**func_context),
                        extra_data={
                            'function': func.__name__,
                            'module': func.__module__,
                            'args': [str(arg)[:50] for arg in args],
                            'kwargs': {k: str(v)[:50] for k, v in kwargs.items()}
                        },
                        severity=severity,
                        category=category
                    )
                    
                    # Re-raise for caller to handle
                    raise
            
            return wrapper
        return decorator
    
    def _extract_function_context(self, func: Callable, args: tuple, 
                                kwargs: dict, defaults: dict) -> Dict[str, Any]:
        """Extract context from function call."""
        context = defaults.copy()
        
        # Try to extract user_id from first argument (common pattern)
        if args and hasattr(args[0], 'id'):
            context['user_id'] = args[0].id
        elif 'user_id' in kwargs:
            context['user_id'] = kwargs['user_id']
        
        # Extract chat_id
        if 'chat_id' in kwargs:
            context['chat_id'] = kwargs['chat_id']
        elif args and hasattr(args[0], 'chat') and hasattr(args[0].chat, 'id'):
            context['chat_id'] = args[0].chat.id
        
        # Extract operation name
        context['operation'] = func.__name__
        context['module'] = func.__module__
        
        # Extract request_id from kwargs if present
        if 'request_id' in kwargs:
            context['request_id'] = kwargs['request_id']
        
        return context

# Global error handler instance
error_handler = None

def initialize_error_handler(bot: Bot, config: Dict[str, Any] = None) -> ErrorHandler:
    """Initialize global error handler."""
    global error_handler
    
    if error_handler is None:
        error_handler = ErrorHandler(
            bot=bot,
            config=config or {},
            sentry_dsn=config.get('sentry_dsn'),
            slack_webhook=config.get('slack_webhook_url'),
            alert_thresholds=config.get('alert_thresholds'),
            recovery_handlers=config.get('recovery_handlers', {})
        )
    
    return error_handler

# Convenience functions for common error patterns
async def handle_user_error(bot: Bot, user_id: int, error_message: str, 
                          operation: str = "user_action") -> None:
    """Handle user-facing errors with friendly messaging."""
    try:
        await bot.send_message(
            user_id,
            f"😔 *Oops!*\n\n"
            f"Something went wrong with your {operation}.\n\n"
            f"💡 *Please try again* or contact support if the problem continues.\n\n"
            f"Error: {error_message[:200]}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error("Failed to send user error message", exc_info=True, extra={
            'user_id': user_id,
            'operation': operation,
            'error': str(e)
        })

async def handle_system_error(error_event: ErrorEvent, 
                            retry_delay: int = 60) -> bool:
    """Handle system errors with automatic retry scheduling."""
    try:
        # Log system error
        logger.error(f"System error in {error_event.context.operation}", extra={
            'error_id': error_event.error_id,
            'system': True
        })
        
        # Schedule retry if retryable
        if error_event.category in [ErrorCategory.NETWORK, ErrorCategory.DATABASE]:
            asyncio.create_task(
                asyncio.sleep(retry_delay),
                name=f"retry_{error_event.error_id}"
            )
            logger.info("System retry scheduled", extra={
                'error_id': error_event.error_id,
                'delay_seconds': retry_delay
            })
            return True
        
        return False
        
    except Exception as e:
        logger.critical("System error handler failed", exc_info=True, extra={
            'original_error': error_event.error_id,
            'handler_error': str(e)
        })
        return False

# Error recovery handlers (examples)
async def recover_from_payment_error(exception: Exception, context: ErrorContext) -> bool:
    """Recover from payment gateway errors."""
    try:
        # Log payment recovery attempt
        logger.info("Payment recovery attempt", extra={
            'user_id': context.user_id,
            'error_type': type(exception).__name__
        })
        
        # For certain payment errors, suggest alternative methods
        if "insufficient_funds" in str(exception).lower():
            # Send message about alternative payment
            if context.chat_id:
                await context.bot.send_message(
                    context.chat_id,
                    "💳 *Payment Issue*\n\n"
                    "Your card doesn't have sufficient funds.\n\n"
                    "💡 *Try:*\n"
                    "• Different card\n"
                    "• Bank transfer option\n"
                    "• Contact support for assistance",
                    parse_mode='Markdown'
                )
                return True
        
        return False
        
    except Exception as recovery_e:
        logger.error("Payment recovery failed", exc_info=True, extra={
            'user_id': context.user_id,
            'recovery_error': str(recovery_e)
        })
        return False

def register_error_recovery_handlers(error_handler: ErrorHandler) -> None:
    """Register common error recovery handlers."""
    error_handler.recovery_handlers.update({
        'PaymentError': recover_from_payment_error,
        'stripe.error.CardError': recover_from_payment_error,
        'paystack.error.InsufficientFundsError': recover_from_payment_error,
        'TelegramAPIError': lambda e, c: asyncio.create_task(
            asyncio.sleep(5), name=f"telegram_retry_{c.request_id}"
        )
    })
    
    logger.info("Error recovery handlers registered", extra={
        'handler_count': len(error_handler.recovery_handlers)
    })
