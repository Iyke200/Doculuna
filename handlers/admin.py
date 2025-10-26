import logging
import time
import os
import sys
import datetime as dt
from datetime import timedelta
from typing import Callable, Awaitable, Dict, Any, List, Tuple
import aiosqlite
import psutil
import asyncio
import shutil

from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from config import ADMIN_USER_IDS, DB_PATH, FREE_USAGE_LIMIT

# Assuming database.db functions are updated to async; stubs below if needed

from database.db import (
    get_user_role, ban_user, unban_user, get_all_users,
    get_user_by_id, update_user_data, add_usage_log,
    get_usage_count, update_user_premium_status, get_pending_payments,
    log_admin_action
)

load_dotenv()
if not os.getenv('BOT_TOKEN'):  # Example check; adjust as needed
    logging.warning(".env file not found or missing BOT_TOKEN")

BOT_START_TIME = time.time()

# Simple time-based cache for admin stats (expires after 30 seconds)
_stats_cache = {}
_cache_ttl = 30  # seconds

async def _get_cached_or_fetch_async(cache_key: str, fetch_func: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, Any]:
    """Get cached value or fetch fresh data if expired (async version)"""
    now = time.time()
    if cache_key in _stats_cache:
        cached_time, cached_value = _stats_cache[cache_key]
        if now - cached_time < _cache_ttl:
            return cached_value
    # Cache expired or doesn't exist, fetch fresh data
    fresh_value = await fetch_func()
    _stats_cache[cache_key] = (now, fresh_value)
    return fresh_value

# Define role levels
ROLE_LEVELS = {
    'superadmin': 3,
    'moderator': 2,
    'support': 1,
    'premium': 0,
    'user': 0
}

# In-memory rate limiting
RATE_LIMIT = 10  # max commands per minute per admin
user_command_times: dict[int, list[float]] = {}

# FSM States for admin actions
class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_broadcast_message = State()
    waiting_for_premium_days = State()
    waiting_for_usage_reset = State()

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler('bot_errors.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def rate_limit_check(user_id: int) -> bool:
    """Simple in-memory rate limiter"""
    now = time.time()
    if user_id in user_command_times:
        recent_times = [t for t in user_command_times[user_id] if now - t < 60]
        if len(recent_times) >= RATE_LIMIT:
            return False
        recent_times.append(now)
        user_command_times[user_id] = recent_times
    else:
        user_command_times[user_id] = [now]
    # Prune old entries periodically (simple cleanup)
    if len(user_command_times[user_id]) > 20:  # Keep last 20 max
        user_command_times[user_id] = user_command_times[user_id][-20:]
    return True

async def is_admin(user_id: int):
    """Helper to check if user is admin"""
    # First check if user is in ADMIN_USER_IDS
    if user_id in ADMIN_USER_IDS:
        return True
    
    # Then check if user has an elevated role (not 'user' or 'premium')
    role = await get_user_role(user_id)
    role_level = ROLE_LEVELS.get(role, 0)
    return role_level >= ROLE_LEVELS.get('support', 1)

def admin_only(min_role: str = 'support') -> Callable:
    """Decorator for role-based access control"""
    min_level = ROLE_LEVELS.get(min_role, 1)

    def decorator(handler: Callable[[types.Message, FSMContext], Awaitable[None]]) -> Callable:  
        async def wrapper(message: types.Message, state: FSMContext) -> None:  
            user_id = message.from_user.id  
            if not await is_admin(user_id):  
                await message.reply("❌ Unauthorized access")  
                return  
            role = await get_user_role(user_id)  
            role_level = ROLE_LEVELS.get(role, 0)  
            if role_level < min_level:  
                await message.reply("❌ Insufficient permissions")  
                return  
            if not rate_limit_check(user_id):  
                await message.reply("⚠️ Rate limit exceeded. Please wait.")  
                return  
            try:  
                await handler(message, state)  
                await log_admin_action(user_id, handler.__name__, f"Role check: {role}")  
            except Exception as e:  
                logger.error(f"Error in admin handler: {e}", exc_info=True)  
                await message.reply("⚠️ An error occurred")  

        return wrapper  
    return decorator

# Helper for DB queries
async def fetch_one(query: str, params=()):
    """Safe async DB fetch one row"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(query, params) as cursor:
                return await cursor.fetchone()
    except aiosqlite.OperationalError as e:
        if "no such table" in str(e).lower() or "no such column" in str(e).lower():
            logger.warning(f"Schema mismatch: {e}")
            return None
        logger.error(f"DB fetch error: {e}")
        return None
    except Exception as e:
        logger.error(f"DB fetch error: {e}")
        return None

async def fetch_all(query: str, params=()):
    """Safe async DB fetch all rows"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(query, params) as cursor:
                return await cursor.fetchall()
    except aiosqlite.OperationalError as e:
        if "no such table" in str(e).lower() or "no such column" in str(e).lower():
            logger.warning(f"Schema mismatch: {e}")
            return []
        logger.error(f"DB fetch error: {e}")
        return []
    except Exception as e:
        logger.error(f"DB fetch error: {e}")
        return []

# Dedicated write helper with commit
async def execute_write(query: str, params=()):
    """Execute UPDATE/INSERT/DELETE with commit"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(query, params)
            await db.commit()  # Critical: Persist changes
            return True
    except aiosqlite.OperationalError as e:
        if "no such table" in str(e).lower() or "no such column" in str(e).lower():
            logger.warning(f"Schema mismatch: {e}")
        else:
            logger.error(f"DB write error: {e}")
        return False
    except Exception as e:
        logger.error(f"DB write error: {e}")
        return False

# Schema confirmation helper (run once on startup or via command)
async def verify_schema():
    """Verify key columns exist"""
    columns_to_check = {
        'users': ['user_id', 'username', 'is_premium', 'role', 'created_at', 'last_active'],
        'usage_logs': ['user_id', 'tool', 'timestamp', 'is_success'],
        'payment_logs': ['id', 'user_id', 'amount', 'status', 'plan_type', 'timestamp']
    }
    issues = []
    for table, cols in columns_to_check.items():
        rows = await fetch_all(f"PRAGMA table_info({table})")
        column_names = [r[1].lower() for r in rows if r]  # r[1] is column name
        for col in cols:
            if col.lower() not in column_names:
                issues.append(f"{table}.{col}")
    if issues:
        logger.warning(f"Schema issues: {issues}")
    return issues

# Schema verification will be called after database initialization if needed
# asyncio.create_task(verify_schema())

# DB migrations: Simple manual version check
DB_VERSION = 1  # Increment on changes
async def check_db_version():
    row = await fetch_one("PRAGMA user_version")
    current_version = row[0] if row else 0
    if current_version < DB_VERSION:
        # Apply migrations
        if current_version == 0:
            await execute_write("CREATE TABLE IF NOT EXISTS admin_action_logs (id INTEGER PRIMARY KEY, admin_id INTEGER, action TEXT, details TEXT, timestamp TEXT)")
            # Add more CREATE/ALTER as needed
            await execute_write(f"PRAGMA user_version = {DB_VERSION}")
        logger.info(f"DB migrated to version {DB_VERSION}")
    return current_version

# Call on startup
asyncio.create_task(check_db_version())

async def admin_command_handler(message: types.Message, state: FSMContext) -> None:
    """Enhanced admin dashboard with real-time stats"""
    user_id = message.from_user.id

    if not await is_admin(user_id):  
        await message.reply("❌ Unauthorized")  
        return  

    try:  
        # Get real-time statistics (cached for 30 seconds)  
        stats = await _get_cached_or_fetch_async('dashboard_stats', get_dashboard_stats)  

        admin_text = (  
            "👑 <b>ADMIN CONTROL PANEL</b>\n"  
            "━━━━━━━━━━━━━━━━━━\n\n"  
            f"📊 <b>System Overview</b>\n"  
            f"👥 Total Users: <b>{stats['total_users']}</b>\n"  
            f"✨ Premium Users: <b>{stats['premium_users']}</b>\n"  
            f"📈 Active Today: <b>{stats['active_today']}</b>\n"  
            f"🆕 New This Week: <b>{stats['new_this_week']}</b>\n\n"  
            f"⚙️ <b>System Health</b>\n"  
            f"💾 Database: <b>{stats['db_status']}</b>\n"  
            f"📦 Disk Usage: <b>{stats['disk_usage']}</b>\n"  
            f"⏰ Uptime: <b>{stats['uptime']}</b>\n\n"  
            f"🔄 <b>Activity (24h)</b>\n"  
            f"📄 Files Processed: <b>{stats['files_processed']}</b>\n"  
            f"💰 Revenue: <b>₦{stats['revenue_24h']:,.0f}</b>\n\n"  
            "Select an action below:"  
        )  

        builder = InlineKeyboardBuilder()  
        builder.button(text="👥 User Management", callback_data="admin_users")  
        builder.button(text="📊 Analytics", callback_data="admin_analytics")  
        builder.button(text="💰 Payments", callback_data="admin_payments")  
        builder.button(text="📈 Activity Logs", callback_data="admin_logs")  
        builder.button(text="🔍 Search User", callback_data="admin_search")  
        builder.button(text="📢 Broadcast", callback_data="admin_broadcast")  
        builder.button(text="⚙️ System Tools", callback_data="admin_system")  
        builder.button(text="🔄 Refresh", callback_data="admin_refresh")  
        builder.adjust(2, 2, 2, 2)  

        await message.reply(admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")  

    except Exception as e:  
        logger.error(f"Error in admin dashboard: {e}", exc_info=True)  
        await message.reply("⚠️ Error loading admin panel")

async def get_dashboard_stats() -> Dict[str, Any]:
    """Get real-time dashboard statistics"""
    try:
        # Total users
        row = await fetch_one("SELECT COUNT(*) FROM users")
        total_users = row[0] if row else 0

        # Premium users  
        row = await fetch_one("SELECT COUNT(*) FROM users WHERE is_premium = 1")  
        premium_users = row[0] if row else 0  

        # Active today  
        row = await fetch_one("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) = date('now')")  
        active_today = row[0] if row else 0  

        # New this week  
        row = await fetch_one("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-7 days')")  
        new_this_week = row[0] if row else 0  

        # Files processed today  
        row = await fetch_one("SELECT COUNT(*) FROM usage_logs WHERE date(timestamp) = date('now') AND is_success = 1")  
        files_processed = row[0] if row else 0  

        # Revenue (from payment_logs if exists)  
        try:  
            row = await fetch_one("SELECT SUM(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-1 day')")  
            revenue_24h = row[0] or 0  
        except:  
            revenue_24h = 0  

        # System stats  
        disk = shutil.disk_usage(".")  
        disk_usage = f"{disk.used // (2**30)}GB/{disk.total // (2**30)}GB"  

        # Uptime calculation  
        uptime = str(timedelta(seconds=int(time.time() - BOT_START_TIME)))  

        return {  
            'total_users': total_users,  
            'premium_users': premium_users,  
            'active_today': active_today,  
            'new_this_week': new_this_week,  
            'files_processed': files_processed,  
            'revenue_24h': revenue_24h,  
            'db_status': '✅ Online',  
            'disk_usage': disk_usage,  
            'uptime': uptime  
        }  
    except Exception as e:  
        logger.error(f"Error getting dashboard stats: {e}")  
        return {  
            'total_users': 0,  
            'premium_users': 0,  
            'active_today': 0,  
            'new_this_week': 0,  
            'files_processed': 0,  
            'revenue_24h': 0,  
            'db_status': '⚠️ Error',  
            'disk_usage': 'Unknown',  
            'uptime': 'Unknown'  
        }

async def handle_admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    """Handle admin panel callbacks"""
    user_id = callback.from_user.id

    if not await is_admin(user_id):  
        await callback.answer("❌ Unauthorized", show_alert=True)  
        return  

    data = callback.data  

    try:  
        if data == "admin_refresh":  
            # Refresh dashboard  
            await render_dashboard(callback)  
            await callback.answer("✅ Refreshed")  

        elif data == "admin_users":  
            await handle_user_management(callback)  
        elif data == "admin_analytics":  
            await handle_analytics(callback)  
        elif data == "admin_payments":  
            await handle_payments(callback)  
        elif data == "admin_logs":  
            await handle_activity_logs(callback)  
        elif data == "admin_search":  
            await handle_user_search(callback, state)  
        elif data == "admin_broadcast":  
            await handle_broadcast_menu(callback, state)  
        elif data == "admin_system":  
            await handle_system_tools(callback)  
        elif data.startswith("user_"):  
            await handle_user_action(callback, state)  
        elif data.startswith("analytics_"):  
            await handle_analytics_period(callback)  
        elif data.startswith("payments_"):  
            await handle_payments_action(callback)  
        elif data.startswith("logs_"):  
            await handle_logs(callback)  
        elif data.startswith("system_"):  
            await handle_system_action(callback)  
        elif data == "back_admin":  
            # Return to main menu  
            await render_dashboard(callback)  
            await callback.answer()  

    except Exception as e:  
        logger.error(f"Error in admin callback {data}: {e}", exc_info=True)  
        await callback.answer("⚠️ Error occurred", show_alert=True)

async def render_dashboard(callback_or_message, stats=None):
    """Shared function to render dashboard"""
    if stats is None:
        stats = await get_dashboard_stats()
    text = (
        "👑 <b>ADMIN CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>System Overview</b>\n"
        f"👥 Total Users: <b>{stats['total_users']}</b>\n"
        f"✨ Premium Users: <b>{stats['premium_users']}</b>\n"
        f"📈 Active Today: <b>{stats['active_today']}</b>\n"
        f"🆕 New This Week: <b>{stats['new_this_week']}</b>\n\n"
        f"⚙️ <b>System Health</b>\n"
        f"💾 Database: <b>{stats['db_status']}</b>\n"
        f"📦 Disk Usage: <b>{stats['disk_usage']}</b>\n"
        f"⏰ Uptime: <b>{stats['uptime']}</b>\n\n"
        f"🔄 <b>Activity (24h)</b>\n"
        f"📄 Files Processed: <b>{stats['files_processed']}</b>\n"
        f"💰 Revenue: <b>₦{stats['revenue_24h']:,.0f}</b>\n\n"
        "Select an action below:"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 User Management", callback_data="admin_users")
    builder.button(text="📊 Analytics", callback_data="admin_analytics")
    builder.button(text="💰 Payments", callback_data="admin_payments")
    builder.button(text="📈 Activity Logs", callback_data="admin_logs")
    builder.button(text="🔍 Search User", callback_data="admin_search")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")
    builder.button(text="⚙️ System Tools", callback_data="admin_system")
    builder.button(text="🔄 Refresh", callback_data="admin_refresh")
    builder.adjust(2, 2, 2, 2)

    if isinstance(callback_or_message, types.CallbackQuery):  
        await callback_or_message.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")  
    else:  
        await callback_or_message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")

async def handle_user_management(callback: types.CallbackQuery):
    """Display user management options"""
    stats = await get_user_management_stats()

    text = (  
        "👥 <b>USER MANAGEMENT</b>\n"  
        "━━━━━━━━━━━━━━━━━━\n\n"  
        f"📊 <b>User Statistics</b>\n"  
        f"Total: <b>{stats['total']}</b>\n"  
        f"Premium: <b>{stats['premium']}</b> ({stats['premium_percent']:.1f}%)\n"  
        f"Free: <b>{stats['free']}</b> ({stats['free_percent']:.1f}%)\n"  
        f"Active (7d): <b>{stats['active_7d']}</b>\n"  
        f"Inactive (30d+): <b>{stats['inactive_30d']}</b>\n\n"  
        "Select an action:"  
    )  

    builder = InlineKeyboardBuilder()  
    builder.button(text="📋 List All Users", callback_data="user_list_all")  
    builder.button(text="⭐ Premium Users", callback_data="user_list_premium")  
    builder.button(text="🔍 Search User", callback_data="admin_search")  
    builder.button(text="🎁 Grant Premium", callback_data="user_grant_premium")  
    builder.button(text="🔄 Reset Usage", callback_data="user_reset_usage")  
    builder.button(text="🚫 Ban User", callback_data="user_ban")  
    builder.button(text="✅ Unban User", callback_data="user_unban")  
    builder.button(text="« Back", callback_data="back_admin")  
    builder.adjust(2, 2, 2, 1)  

    await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
    await callback.answer()

async def get_user_management_stats() -> Dict[str, Any]:
    """Get user management statistics"""
    try:
        row = await fetch_one("SELECT COUNT(*) FROM users")
        total = row[0] if row else 0

        row = await fetch_one("SELECT COUNT(*) FROM users WHERE is_premium = 1")  
        premium = row[0] if row else 0  

        free = total - premium  
        premium_percent = (premium / total * 100) if total > 0 else 0  
        free_percent = (free / total * 100) if total > 0 else 0  

        row = await fetch_one("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-7 days')")  
        active_7d = row[0] if row else 0  

        row = await fetch_one("SELECT COUNT(*) FROM users WHERE last_active < date('now', '-30 days')")  
        inactive_30d = row[0] if row else 0  

        return {  
            'total': total,  
            'premium': premium,  
            'free': free,  
            'premium_percent': premium_percent,  
            'free_percent': free_percent,  
            'active_7d': active_7d,  
            'inactive_30d': inactive_30d  
        }  
    except Exception as e:  
        logger.error(f"Error getting user stats: {e}")  
        return {'total': 0, 'premium': 0, 'free': 0, 'premium_percent': 0, 'free_percent': 0, 'active_7d': 0, 'inactive_30d': 0}

async def handle_analytics(callback: types.CallbackQuery):
    """Display analytics dashboard"""
    analytics = await get_analytics_data()

    text = (  
        "📊 <b>ANALYTICS DASHBOARD</b>\n"  
        "━━━━━━━━━━━━━━━━━━\n\n"  
        f"📈 <b>Growth Metrics (30 days)</b>\n"  
        f"New Users: <b>{analytics['new_users_30d']}</b>\n"  
        f"Growth Rate: <b>{analytics['growth_rate']:.1f}%</b>\n"  
        f"Conversion Rate: <b>{analytics['conversion_rate']:.1f}%</b>\n\n"  
        f"🎯 <b>Engagement</b>\n"  
        f"Daily Active Users: <b>{analytics['dau']}</b>\n"  
        f"Weekly Active Users: <b>{analytics['wau']}</b>\n"  
        f"Monthly Active Users: <b>{analytics['mau']}</b>\n"  
        f"Avg Uses/User: <b>{analytics['avg_uses']:.1f}</b>\n\n"  
        f"💰 <b>Revenue (30 days)</b>\n"  
        f"Total Revenue: <b>₦{analytics['revenue_30d']:,.0f}</b>\n"  
        f"ARPU: <b>₦{analytics['arpu']:.0f}</b>\n"  
        f"Premium Subs: <b>{analytics['premium_subs']}</b>\n"  
    )  

    builder = InlineKeyboardBuilder()  
    builder.button(text="📅 Daily Report", callback_data="analytics_daily")  
    builder.button(text="📊 Weekly Report", callback_data="analytics_weekly")  
    builder.button(text="📈 Monthly Report", callback_data="analytics_monthly")  
    builder.button(text="💾 Export Data", callback_data="analytics_export")  
    builder.button(text="« Back", callback_data="back_admin")  
    builder.adjust(2, 2, 1)  

    await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
    await callback.answer()

async def handle_analytics_period(callback: types.CallbackQuery):
    """Handle analytics period callbacks"""
    data = callback.data
    period = "daily" if "daily" in data else "weekly" if "weekly" in data else "monthly"
    days = 1 if period == "daily" else 7 if period == "weekly" else 30
    text = f"📊 <b>{period.upper()} ANALYTICS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    # Add period-specific stats here, e.g., query for that period
    row = await fetch_one(f"SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-{days} days')")
    new = row[0] if row else 0
    text += f"New Users: <b>{new}</b>\n"
    # Growth rate
    prev_days = days * 2
    row = await fetch_one(f"SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-{prev_days} days') AND date(created_at) < date('now', '-{days} days')")
    prev = row[0] if row else 1
    growth_rate = ((new - prev) / prev * 100) if prev > 0 else 0
    text += f"Growth Rate: <b>{growth_rate:.1f}%</b>\n"
    # Top 3 active users
    rows = await fetch_all(f"SELECT user_id, COUNT(*) as count FROM usage_logs WHERE date(timestamp) >= date('now', '-{days} days') GROUP BY user_id ORDER BY count DESC LIMIT 3")
    text += "\nTop Active Users:\n"
    for row in rows:
        text += f"• User {row[0]}: {row[1]} uses\n"
    if not rows:
        text += "No active users.\n"
    builder = InlineKeyboardBuilder()
    builder.button(text="« Back", callback_data="admin_analytics")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_analytics_data() -> Dict[str, Any]:
    """Get analytics data"""
    try:
        row = await fetch_one("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-30 days')")
        new_users_30d = row[0] if row else 0

        # Growth rate  
        row = await fetch_one("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-60 days') AND date(created_at) < date('now', '-30 days')")  
        prev_month = row[0] if row else 1  
        growth_rate = ((new_users_30d - prev_month) / prev_month * 100) if prev_month > 0 else 0  

        # Active users  
        row = await fetch_one("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) = date('now')")  
        dau = row[0] if row else 0  

        row = await fetch_one("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-7 days')")  
        wau = row[0] if row else 0  

        row = await fetch_one("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-30 days')")  
        mau = row[0] if row else 0  

        # Average uses per user  
        row = await fetch_one("SELECT AVG(use_count) FROM (SELECT user_id, COUNT(*) as use_count FROM usage_logs WHERE date(timestamp) >= date('now', '-30 days') GROUP BY user_id)")  
        avg_uses = row[0] or 0  

        # Revenue  
        try:  
            row = await fetch_one("SELECT SUM(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-30 days')")  
            revenue_30d = row[0] or 0  
        except:  
            revenue_30d = 0  

        row = await fetch_one("SELECT COUNT(*) FROM users")  
        total_users = row[0] or 1  
        arpu = revenue_30d / total_users if total_users > 0 else 0  

        row = await fetch_one("SELECT COUNT(*) FROM users WHERE is_premium = 1")  
        premium_subs = row[0] if row else 0  

        conversion_rate = (premium_subs / total_users * 100) if total_users > 0 else 0  

        return {  
            'new_users_30d': new_users_30d,  
            'growth_rate': growth_rate,  
            'dau': dau,  
            'wau': wau,  
            'mau': mau,  
            'avg_uses': avg_uses,  
            'revenue_30d': revenue_30d,  
            'arpu': arpu,  
            'premium_subs': premium_subs,  
            'conversion_rate': conversion_rate  
        }  
    except Exception as e:  
        logger.error(f"Error getting analytics: {e}")  
        return {'new_users_30d': 0, 'growth_rate': 0, 'dau': 0, 'wau': 0, 'mau': 0, 'avg_uses': 0, 'revenue_30d': 0, 'arpu': 0, 'premium_subs': 0, 'conversion_rate': 0}

async def handle_payments(callback: types.CallbackQuery):
    """Display payment management"""
    payments = await get_payment_stats()

    text = (  
        "💰 <b>PAYMENT MANAGEMENT</b>\n"  
        "━━━━━━━━━━━━━━━━━━\n\n"  
        f"📊 <b>Overview (30 days)</b>\n"  
        f"Total Revenue: <b>₦{payments['total_revenue']:,.0f}</b>\n"  
        f"Transactions: <b>{payments['total_transactions']}</b>\n"  
        f"Avg Transaction: <b>₦{payments['avg_transaction']:.0f}</b>\n\n"  
        f"📈 <b>Breakdown</b>\n"  
        f"Weekly Plans: <b>{payments['weekly_plans']}</b> (₦{payments['weekly_revenue']:,.0f})\n"  
        f"Monthly Plans: <b>{payments['monthly_plans']}</b> (₦{payments['monthly_revenue']:.0f})\n\n"  
        f"⏳ <b>Status</b>\n"  
        f"Pending: <b>{payments['pending']}</b>\n"  
        f"Completed: <b>{payments['completed']}</b>\n"  
        f"Failed: <b>{payments['failed']}</b>\n"  
    )  

    builder = InlineKeyboardBuilder()  
    builder.button(text="📋 Recent Transactions", callback_data="payments_recent")  
    builder.button(text="⏳ Pending Payments", callback_data="payments_pending")  
    builder.button(text="💾 Export Report", callback_data="payments_export")  
    builder.button(text="🔄 Refresh", callback_data="payments_refresh")  
    builder.button(text="« Back", callback_data="back_admin")  
    builder.adjust(2, 2, 1)  

    await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
    await callback.answer()

async def handle_payments_action(callback: types.CallbackQuery):
    """Handle payments actions"""
    data = callback.data
    text = "Unknown payments action."  # Default
    if data == "payments_recent":
        rows = await fetch_all("SELECT * FROM payment_logs ORDER BY timestamp DESC LIMIT 10")
        text = "💳 <b>Recent Payments (Last 10)</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows:
            # Assume columns: id, user_id, amount, status, plan_type, timestamp
            text += f"• ID: {row[0]}, User: {row[1]}, Amount: ₦{row[2]:.2f}, Status: {row[3]}, Plan: {row[4]}, Time: {row[5]}\n"
        if not rows:
            text += "No recent payments."
    elif data == "payments_pending":
        rows = await fetch_all("SELECT * FROM payment_logs WHERE status = 'pending' ORDER BY timestamp DESC LIMIT 10")
        text = "⏳ <b>Pending Payments</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows:
            text += f"• ID: {row[0]}, User: {row[1]}, Amount: ₦{row[2]:.2f}, Time: {row[5]}\n"
        if not rows:
            text += "No pending payments."
    elif data == "payments_export":
        text = "💾 Export initiated (placeholder - implement CSV download or file send)."
    elif data == "payments_refresh":
        await handle_payments(callback)
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="« Back", callback_data="admin_payments")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_payment_stats() -> Dict[str, Any]:
    """Get payment statistics"""
    try:
        try:
            row = await fetch_one("SELECT SUM(amount), COUNT(*), AVG(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-30 days')")
            total_revenue = row[0] or 0
            total_transactions = row[1] or 0
            avg_transaction = row[2] or 0

            row = await fetch_one("SELECT COUNT(*), SUM(amount) FROM payment_logs WHERE plan_type = 'weekly' AND date(timestamp) >= date('now', '-30 days')")  
            weekly_plans = row[0] or 0  
            weekly_revenue = row[1] or 0  

            row = await fetch_one("SELECT COUNT(*), SUM(amount) FROM payment_logs WHERE plan_type = 'monthly' AND date(timestamp) >= date('now', '-30 days')")  
            monthly_plans = row[0] or 0  
            monthly_revenue = row[1] or 0  

            row = await fetch_one("SELECT COUNT(*) FROM payment_logs WHERE status = 'pending' AND date(timestamp) >= date('now', '-30 days')")  
            pending = row[0] or 0  

            row = await fetch_one("SELECT COUNT(*) FROM payment_logs WHERE status = 'success' AND date(timestamp) >= date('now', '-30 days')")  
            completed = row[0] or 0  

            row = await fetch_one("SELECT COUNT(*) FROM payment_logs WHERE status = 'failed' AND date(timestamp) >= date('now', '-30 days')")  
            failed = row[0] or 0  
        except:  
            total_revenue = total_transactions = avg_transaction = weekly_plans = weekly_revenue = monthly_plans = monthly_revenue = pending = completed = failed = 0  

        return {  
            'total_revenue': total_revenue,  
            'total_transactions': total_transactions,  
            'avg_transaction': avg_transaction,  
            'weekly_plans': weekly_plans,  
            'weekly_revenue': weekly_revenue,  
            'monthly_plans': monthly_plans,  
            'monthly_revenue': monthly_revenue,  
            'pending': pending,  
            'completed': completed,  
            'failed': failed  
        }  
    except Exception as e:  
        logger.error(f"Error getting payment stats: {e}")  
        return {'total_revenue': 0, 'total_transactions': 0, 'avg_transaction': 0, 'weekly_plans': 0, 'weekly_revenue': 0, 'monthly_plans': 0, 'monthly_revenue': 0, 'pending': 0, 'completed': 0, 'failed': 0}

async def handle_activity_logs(callback: types.CallbackQuery):
    """Display recent activity logs"""
    logs = await get_recent_activity()

    text = (  
        "📈 <b>ACTIVITY LOGS</b>\n"  
        "━━━━━━━━━━━━━━━━━━\n\n"  
        "<b>Recent Activity (Last 10)</b>\n\n"  
    )  

    for log in logs[:10]:  
        text += f"• {log}\n"  

    builder = InlineKeyboardBuilder()  
    builder.button(text="🔄 Refresh", callback_data="admin_logs")  
    builder.button(text="📊 Full Report", callback_data="logs_full")  
    builder.button(text="« Back", callback_data="back_admin")  
    builder.adjust(2, 1)  

    await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
    await callback.answer()

async def handle_logs(callback: types.CallbackQuery):
    """Handle logs callbacks"""
    data = callback.data
    if data == "logs_full":
        rows = await fetch_all("SELECT user_id, tool, timestamp, is_success FROM usage_logs ORDER BY timestamp DESC LIMIT 20")
        text = "📊 <b>FULL LOGS (Last 20)</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for row in rows:
            user_id, tool, timestamp, success = row
            status = "✅" if success else "❌"
            text += f"{status} User {user_id} - {tool} - {timestamp}\n"
        if not rows:
            text += "No logs available."
        builder = InlineKeyboardBuilder()
        builder.button(text="« Back", callback_data="admin_logs")
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()

async def get_recent_activity() -> list:
    """Get recent activity logs"""
    try:
        rows = await fetch_all("""
            SELECT user_id, tool, timestamp, is_success
            FROM usage_logs
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        logs = []  
        for row in rows:  
            user_id, tool, timestamp, success = row  
            status = "✅" if success else "❌"  
            logs.append(f"{status} User {user_id} - {tool} - {timestamp}")  
        return logs if logs else ["No recent activity"]  
    except Exception as e:  
        logger.error(f"Error getting activity logs: {e}")  
        return ["Error loading logs"]

async def handle_user_search(callback: types.CallbackQuery, state: FSMContext):
    """Initiate user search"""
    text = (
        "🔍 <b>SEARCH USER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Send the user ID to search:\n"
        "Format: <code>123456789</code>\n\n"
        "Or send /cancel to go back"
    )

    await callback.message.edit_text(text, parse_mode="HTML")  
    await state.set_state(AdminStates.waiting_for_user_id)  
    await state.update_data(action_type="search")  # Default to search  
    await callback.answer()

async def handle_broadcast_menu(callback: types.CallbackQuery, state: FSMContext):
    """Display broadcast menu"""
    text = (
        "📢 <b>BROADCAST MESSAGE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Send the message you want to broadcast to all users.\n\n"
        "⚠️ This will send to ALL registered users.\n\n"
        "Send /cancel to go back"
    )

    await callback.message.edit_text(text, parse_mode="HTML")  
    await state.set_state(AdminStates.waiting_for_broadcast_message)  
    await callback.answer()

async def handle_system_tools(callback: types.CallbackQuery):
    """Display system management tools"""
    system = await get_system_info()

    text = (  
        "⚙️ <b>SYSTEM TOOLS</b>\n"  
        "━━━━━━━━━━━━━━━━━━\n\n"  
        f"💾 <b>Database</b>\n"  
        f"Size: <b>{system['db_size']}</b>\n"  
        f"Tables: <b>{system['table_count']}</b>\n\n"  
        f"📦 <b>Storage</b>\n"  
        f"Used: <b>{system['disk_used']}</b>\n"  
        f"Free: <b>{system['disk_free']}</b>\n\n"  
        f"🔧 <b>System</b>\n"  
        f"CPU: <b>{system['cpu']}%</b>\n"  
        f"RAM: <b>{system['ram']}%</b>\n"  
        f"Python: <b>{system['python_version']}</b>\n"  
        f"Uptime: <b>{system['uptime']}</b>\n"  
        f"Status: <b>{system['status']}</b>\n"  
    )  

    builder = InlineKeyboardBuilder()  
    builder.button(text="🔄 Restart Bot", callback_data="system_restart")  
    builder.button(text="💾 Backup DB", callback_data="system_backup")  
    builder.button(text="🧹 Clean Logs", callback_data="system_clean")  
    builder.button(text="📊 System Logs", callback_data="system_logs")  
    builder.button(text="« Back", callback_data="back_admin")  
    builder.adjust(2, 2, 1)  

    await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
    await callback.answer()

async def handle_system_action(callback: types.CallbackQuery):
    """Handle system actions"""
    data = callback.data
    text = "⚙️ <b>SYSTEM ACTION</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if data == "system_restart":
        text += "🔄 Restarting bot...\n\n(Placeholder: Implement with os.execv(sys.executable, [sys.executable] + sys.argv) or signal handler.)"
        await log_admin_action(callback.from_user.id, "restart_bot")
        # For real: os.execv(sys.executable, [sys.executable] + sys.argv)
    elif data == "system_backup":
        backup_path = f"{DB_PATH}.backup.{int(time.time())}"
        shutil.copy2(DB_PATH, backup_path)
        text += f"💾 DB backed up to {backup_path}"
        await log_admin_action(callback.from_user.id, "db_backup", backup_path)
    elif data == "system_clean":
        # Clean old logs (placeholder: delete files >30 days)
        text += "🧹 Old logs cleaned (placeholder - implement file cleanup)."
        await log_admin_action(callback.from_user.id, "clean_logs")
    elif data == "system_logs":
        # Show recent error log lines
        try:
            with open('bot_errors.log', 'r') as f:
                lines = f.readlines()[-10:]
                text += "📊 <b>Recent Errors:</b>\n" + "".join(lines)
        except:
            text += "No error log found."
    builder = InlineKeyboardBuilder()
    builder.button(text="« Back", callback_data="admin_system")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    try:
        # Database size
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        db_size = f"{db_size_bytes / (1024 * 1024):.2f} MB"

        # Table count  
        row = await fetch_one("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")  
        table_count = row[0] if row else 0  

        # Disk usage  
        disk = shutil.disk_usage(".")  
        disk_used = f"{disk.used // (2**30)} GB"  
        disk_free = f"{disk.free // (2**30)} GB"  

        # System metrics  
        cpu = psutil.cpu_percent()  
        ram = psutil.virtual_memory().percent  

        # Uptime  
        uptime = str(timedelta(seconds=int(time.time() - BOT_START_TIME)))  

        # Python version  
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"  

        return {  
            'db_size': db_size,  
            'table_count': table_count,  
            'disk_used': disk_used,  
            'disk_free': disk_free,  
            'cpu': cpu,  
            'ram': ram,  
            'uptime': uptime,  
            'python_version': python_version,  
            'status': '✅ Running'  
        }  
    except Exception as e:  
        logger.error(f"Error getting system info: {e}")  
        return {'db_size': 'Unknown', 'table_count': 0, 'disk_used': 'Unknown', 'disk_free': 'Unknown', 'cpu': 0, 'ram': 0, 'uptime': 'Unknown', 'python_version': 'Unknown', 'status': '⚠️ Error'}

async def handle_user_action(callback: types.CallbackQuery, state: FSMContext):
    """Handle user-specific actions"""
    action = callback.data

    if action == "user_list_all":  
        await list_users(callback, premium_only=False)  
    elif action == "user_list_premium":  
        await list_users(callback, premium_only=True)  
    elif action == "user_grant_premium":  
        await callback.message.edit_text(  
            "🎁 <b>GRANT PREMIUM</b>\n\n"  
            "Send user ID and days separated by space:\n"  
            "Format: <code>123456789 30</code>\n\n"  
            "Or /cancel to go back",  
            parse_mode="HTML"  
        )  
        await state.set_state(AdminStates.waiting_for_premium_days)  
        await state.update_data(target_user_id=None)  # Flag for direct input  
        await callback.answer()  
    elif action == "user_reset_usage":  
        await callback.message.edit_text(  
            "🔄 <b>RESET USAGE</b>\n\n"  
            "Send the user ID to reset usage:\n"  
            "Format: <code>123456789</code>\n\n"  
            "Or /cancel to go back",  
            parse_mode="HTML"  
        )  
        await state.set_state(AdminStates.waiting_for_usage_reset)  
        await callback.answer()  
    elif action == "user_ban":  
        await callback.message.edit_text(  
            "🚫 <b>BAN USER</b>\n\n"  
            "Send the user ID to ban:\n"  
            "Format: <code>123456789</code>\n\n"  
            "Or /cancel to go back",  
            parse_mode="HTML"  
        )  
        await state.set_state(AdminStates.waiting_for_user_id)  
        await state.update_data(action_type="ban")  
        await callback.answer()  
    elif action == "user_unban":  
        await callback.message.edit_text(  
            "✅ <b>UNBAN USER</b>\n\n"  
            "Send the user ID to unban:\n"  
            "Format: <code>123456789</code>\n\n"  
            "Or /cancel to go back",  
            parse_mode="HTML"  
        )  
        await state.set_state(AdminStates.waiting_for_user_id)  
        await state.update_data(action_type="unban")  
        await callback.answer()  
    elif action.startswith("grant_premium_"):  
        user_id = int(action.split("_")[2])  
        await callback.message.edit_text(  
            f"🎁 <b>GRANT PREMIUM</b>\n\n"  
            f"Send number of days for user {user_id}:\n"  
            f"Format: <code>30</code>\n\n"  
            f"Or /cancel to go back",  
            parse_mode="HTML"  
        )  
        await state.update_data(target_user_id=user_id)  
        await state.set_state(AdminStates.waiting_for_premium_days)  
        await callback.answer()  
    elif action.startswith("reset_usage_"):  
        user_id = int(action.split("_")[2])  
        success = await update_user_data_async(user_id, {'usage_today': 0, 'usage_reset_date': dt.datetime.now().date().isoformat()})  
        if success:  
            logger.info(f"Admin {callback.from_user.id} reset usage for {user_id}")  
            await log_admin_action(callback.from_user.id, "reset_usage", str(user_id))  
            builder = InlineKeyboardBuilder()  
            builder.button(text="« Back", callback_data="admin_users")  
            await callback.message.edit_text(  
                f"✅ Usage reset for user {user_id}",  
                reply_markup=builder.as_markup()  
            )  
            await callback.answer("✅ Reset completed")  
        else:  
            await callback.answer("❌ Failed to reset usage", show_alert=True)  
    elif action.startswith("user_ban_"):  
        user_id = int(action.split("_")[2])  
        success = await ban_user_async(user_id)  # Async stub  
        if success:  
            await log_admin_action(callback.from_user.id, "ban_user", str(user_id))  
            builder = InlineKeyboardBuilder()  
            builder.button(text="« Back", callback_data="admin_users")  
            await callback.message.edit_text(f"🚫 User {user_id} banned.", reply_markup=builder.as_markup())  
            await callback.answer("✅ Banned")  
        else:  
            await callback.answer("❌ Failed to ban user", show_alert=True)  
    elif action.startswith("user_unban_"):  
        user_id = int(action.split("_")[2])  
        success = await unban_user_async(user_id)  # Async stub  
        if success:  
            await log_admin_action(callback.from_user.id, "unban_user", str(user_id))  
            builder = InlineKeyboardBuilder()  
            builder.button(text="« Back", callback_data="admin_users")  
            await callback.message.edit_text(f"✅ User {user_id} unbanned.", reply_markup=builder.as_markup())  
            await callback.answer("✅ Unbanned")  
        else:  
            await callback.answer("❌ Failed to unban user", show_alert=True)  
    else:  
        await callback.answer("Unknown action", show_alert=True)

# Async stubs for external DB funcs (updated with execute_write)
async def get_user_role(user_id: int):
    row = await fetch_one("SELECT role FROM users WHERE user_id = ?", (user_id,))
    return row[0] if row else 'user'

async def ban_user_async(user_id: int):
    return await execute_write("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))

async def unban_user_async(user_id: int):
    return await execute_write("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))

async def get_all_users():
    rows = await fetch_all("SELECT user_id FROM users")
    return [(r[0],) for r in rows]  # Tuple format

async def get_user_by_id(user_id: int):
    row = await fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return dict(row) if row else None

async def update_user_data_async(user_id: int, data: Dict[str, Any]):
    """Async version of update_user_data - single query for efficiency"""
    if not data:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in data)
    params = list(data.values()) + [user_id]
    return await execute_write(f"UPDATE users SET {set_clause} WHERE user_id = ?", params)

async def update_user_premium_status(user_id: int, days: int):
    """Updated with execute_write and user existence check"""
    user_data = await get_user_by_id(user_id)
    if not user_data:
        logger.warning(f"User {user_id} not found for premium grant")
        return False
    expiry = dt.datetime.now() + timedelta(days=days)
    success1 = await execute_write(
        "UPDATE users SET is_premium = 1, premium_expiry = ? WHERE user_id = ?",
        (expiry.isoformat(), user_id)
    )
    success2 = await execute_write(
        "UPDATE users SET role = ? WHERE user_id = ?",
        ('premium', user_id)
    )
    if success1 and success2:
        await log_admin_action(-1, "auto_promote", f"User {user_id} to premium")  # -1 for system
    return success1 and success2

async def get_pending_payments():
    return await fetch_all("SELECT * FROM payment_logs WHERE status = 'pending'")

# ... (other stubs if needed)

async def list_users(callback: types.CallbackQuery, premium_only: bool = False):
    """List users"""
    try:
        if premium_only:
            rows = await fetch_all("SELECT user_id, username, is_premium FROM users WHERE is_premium = 1 LIMIT 10")
            title = "⭐ PREMIUM USERS"
        else:
            rows = await fetch_all("SELECT user_id, username, is_premium FROM users LIMIT 10")
            title = "📋 ALL USERS"

        text = f"<b>{title}</b>\n━━━━━━━━━━━━━━━━━━\n\n"  

        for row in rows:  
            user_id, username, is_premium = row  
            status = "⭐" if is_premium else "👤"  
            text += f"{status} {username or 'N/A'} ({user_id})\n"  

        text += f"\n<i>Showing first 10 users</i>"  

        builder = InlineKeyboardBuilder()  
        builder.button(text="« Back", callback_data="admin_users")  

        await send_paginated_text(callback.message, text, builder.as_markup(), parse_mode="HTML")  
        await callback.answer()  
    except Exception as e:  
        logger.error(f"Error listing users: {e}")  
        await callback.answer("⚠️ Error loading users", show_alert=True)

async def cancel_state(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled ✅")

async def handle_user_id_input(message: types.Message, state: FSMContext):
    """Handle user ID input for search/ban/unban"""
    current_state = await state.get_state()
    if current_state is None or message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return

    try:  
        user_id = int(message.text.strip())  
        data = await state.get_data()  
        action_type = data.get('action_type', 'search')  

        user_exists = bool(await get_user_by_id(user_id))  

        if not user_exists and action_type != 'search':  
            await message.reply("❌ User not found")  
            await state.clear()  
            return  

        if action_type == 'ban':  
            success = await ban_user_async(user_id)  
            if success:  
                logger.info(f"Admin {message.from_user.id} banned user {user_id}")  
                await log_admin_action(message.from_user.id, "ban_user", str(user_id))  
                await message.reply(f"✅ User {user_id} has been banned.")  
            else:  
                await message.reply("❌ Failed to ban user")  
        elif action_type == 'unban':  
            success = await unban_user_async(user_id)  
            if success:  
                logger.info(f"Admin {message.from_user.id} unbanned user {user_id}")  
                await log_admin_action(message.from_user.id, "unban_user", str(user_id))  
                await message.reply(f"✅ User {user_id} has been unbanned.")  
            else:  
                await message.reply("❌ Failed to unban user")  
        else:  # search  
            user_data = await get_user_by_id(user_id)  

            if not user_data:  
                await message.reply("❌ User not found")  
                await state.clear()  
                return  

            # Display user profile  
            is_premium = user_data.get('is_premium', False)  
            username = user_data.get('username', 'N/A')  
            usage_today = user_data.get('usage_today', 0)  
            remaining = max(0, FREE_USAGE_LIMIT - usage_today)

            text = (  
                f"👤 <b>USER PROFILE</b>\n"  
                f"━━━━━━━━━━━━━━━━━━\n\n"  
                f"ID: <code>{user_id}</code>\n"  
                f"Username: <b>{username}</b>\n"  
                f"Status: {'⭐ Premium' if is_premium else '👤 Free'}\n"  
            )
            
            if not is_premium:
                text += f"Usage Today: <b>{usage_today}/{FREE_USAGE_LIMIT}</b> ({remaining} remaining)\n"
            else:
                text += f"Usage: <b>Unlimited ♾️</b>\n"  

            builder = InlineKeyboardBuilder()  
            builder.button(text="🎁 Grant Premium", callback_data=f"grant_premium_{user_id}")  
            builder.button(text="🔄 Reset Usage", callback_data=f"reset_usage_{user_id}")  
            builder.button(text="🚫 Ban", callback_data=f"user_ban_{user_id}")  
            builder.button(text="✅ Unban", callback_data=f"user_unban_{user_id}")  
            builder.button(text="« Back", callback_data="admin_users")  
            builder.adjust(2, 2)  

            await message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")  

        await state.clear()  

    except ValueError:  
        await message.reply("❌ Invalid user ID. Must be a number.")  
    except Exception as e:  
        logger.error(f"Error handling user action: {e}")  
        await message.reply("⚠️ Error occurred")  
    finally:  
        await state.clear()

async def handle_broadcast_input(message: types.Message, state: FSMContext):
    """Handle broadcast message input"""
    if message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return

    try:  
        users = await get_all_users()  
        sent_count = 0  
        failed_count = 0  

        await message.reply(f"📢 Broadcasting to {len(users)} users...")  

        async def send_to_user(u_id):  
            try:  
                await message.bot.send_message(u_id, message.text)  
                return True  
            except Exception as e:  
                logger.warning(f"Failed to send to {u_id}: {e}")  
                return False  

        tasks = [asyncio.create_task(send_to_user(u[0])) for u in users]  
        results = await asyncio.gather(*tasks, return_exceptions=True)  
        sent_count = sum(1 for r in results if isinstance(r, bool) and r)  
        failed_count = len(users) - sent_count  

        await message.reply(  
            f"✅ Broadcast complete!\n"  
            f"Sent: {sent_count}\n"  
            f"Failed: {failed_count}"  
        )  
        await log_admin_action(message.from_user.id, "broadcast", f"Sent to {sent_count} users")  
        await state.clear()  

    except Exception as e:  
        logger.error(f"Error broadcasting: {e}")  
        await message.reply("⚠️ Broadcast failed")  
        await state.clear()

async def handle_premium_grant_input(message: types.Message, state: FSMContext):
    """Handle premium grant input"""
    if message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return

    try:  
        data = await state.get_data()  
        if 'target_user_id' in data and data['target_user_id'] is not None:  
            # From profile: only days  
            user_id = data['target_user_id']  
            days = int(message.text.strip())  
        else:  
            # Direct: id days  
            parts = message.text.split()  
            if len(parts) != 2:  
                await message.reply("❌ Invalid format. Use: <user_id> <days>")  
                return  
            user_id = int(parts[0])  
            days = int(parts[1])  

        if days <= 0 or days > 365:  
            await message.reply("❌ Days must be between 1 and 365")  
            return  

        success = await update_user_premium_status(user_id, days)  
        if success:  
            logger.info(f"Admin {message.from_user.id} granted {days} days premium to {user_id}")  
            await log_admin_action(message.from_user.id, "grant_premium", f"User {user_id}, {days} days")  
            await message.reply(f"✅ Granted {days} days premium to user {user_id}")  
            # Notify user
            try:
                await message.bot.send_message(user_id, "🎉 Your premium subscription has been activated by an admin!")
            except:
                logger.warning(f"Could not notify user {user_id}")
        else:  
            await message.reply("❌ Failed to grant premium. Check logs.")  
        await state.clear()  

    except ValueError:  
        await message.reply("❌ Invalid input. Values must be numbers.")  
    except Exception as e:  
        logger.error(f"Error granting premium: {e}")  
        await message.reply("⚠️ Error occurred")  
    finally:  
        await state.clear()

async def handle_usage_reset_input(message: types.Message, state: FSMContext):
    """Handle usage reset input"""
    if message.text.startswith("/cancel"):
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return

    try:  
        user_id = int(message.text.strip())  
        success = await update_user_data_async(user_id, {'usage_today': 0, 'usage_reset_date': dt.datetime.now().date().isoformat()})  
        if success:  
            logger.info(f"Admin {message.from_user.id} reset usage for {user_id}")  
            await log_admin_action(message.from_user.id, "reset_usage", str(user_id))  
            await message.reply(f"✅ Usage reset for user {user_id}")  
        else:  
            await message.reply("❌ Failed to reset usage")  
        await state.clear()  
    except ValueError:  
        await message.reply("❌ Invalid user ID. Must be a number.")  
    except Exception as e:  
        logger.error(f"Error resetting usage: {e}")  
        await message.reply("⚠️ Error occurred")  
    finally:  
        await state.clear()

@admin_only(min_role='moderator')
async def ban_handler(message: types.Message, state: FSMContext) -> None:
    """Ban a user"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        user_id_to_ban = int(parts[1])
        if user_id_to_ban <= 0:
            raise ValueError("Invalid user ID")
        user_data = await get_user_by_id(user_id_to_ban)
        if not user_data:
            await message.reply("❌ User not found")
            return
    except ValueError:
        await message.reply("Usage: /ban <user_id>")
        return

    success = await ban_user_async(user_id_to_ban)  
    if success:  
        logger.info(f"Admin {message.from_user.id} banned user {user_id_to_ban}")  
        await log_admin_action(message.from_user.id, "ban_user", str(user_id_to_ban))  
        await message.reply(f"✅ User {user_id_to_ban} has been banned.")
    else:
        await message.reply("❌ Failed to ban user")

@admin_only(min_role='moderator')
async def unban_handler(message: types.Message, state: FSMContext) -> None:
    """Unban a user"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        user_id_to_unban = int(parts[1])
        if user_id_to_unban <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.reply("Usage: /unban <user_id>")
        return

    success = await unban_user_async(user_id_to_unban)  
    if success:  
        logger.info(f"Admin {message.from_user.id} unbanned user {user_id_to_unban}")  
        await log_admin_action(message.from_user.id, "unban_user", str(user_id_to_unban))  
        await message.reply(f"✅ User {user_id_to_unban} has been unbanned.")
    else:
        await message.reply("❌ Failed to unban user")

@admin_only(min_role='superadmin')
async def broadcast_handler(message: types.Message, state: FSMContext) -> None:
    """Broadcast message to all users"""
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.reply("Usage: /broadcast <message>")
        return

    users = await get_all_users()  
    sent_count = 0  
    async def send_to(u_id):  
        try:  
            await message.bot.send_message(u_id, text)  
            return True  
        except:  
            return False  

    tasks = [asyncio.create_task(send_to(u[0])) for u in users]  
    results = await asyncio.gather(*tasks, return_exceptions=True)  
    sent_count = sum(1 for r in results if isinstance(r, bool) and r)  

    logger.info(f"Admin {message.from_user.id} broadcasted to {sent_count} users")  
    await log_admin_action(message.from_user.id, "broadcast", f"Sent to {sent_count} users")  
    await message.reply(f"✅ Broadcast sent to {sent_count} users.")

async def send_paginated_text(message_or_callback, text: str, reply_markup=None, parse_mode=None):
    """Send text in chunks if >4096 chars"""
    if len(text) <= 4096:
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message_or_callback.reply(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        chunks = [text[i:i+4090] for i in range(0, len(text), 4090)]
        for i, chunk in enumerate(chunks[:-1]):
            if isinstance(message_or_callback, types.CallbackQuery):
                await message_or_callback.message.reply(chunk, parse_mode=parse_mode)
            else:
                await message_or_callback.reply(chunk, parse_mode=parse_mode)
        last_chunk = chunks[-1]
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(last_chunk, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message_or_callback.reply(last_chunk, reply_markup=reply_markup, parse_mode=parse_mode)

# Log admin actions (updated with execute_write)
async def log_admin_action(admin_id: int, action: str, details: str = ""):
    """Log admin actions to DB"""
    try:
        await execute_write("INSERT INTO admin_action_logs (admin_id, action, details, timestamp) VALUES (?, ?, ?, datetime('now'))", (admin_id, action, details))
    except Exception as e:
        logger.warning(f"Failed to log action {action}: {e}")  # Table may not exist

# Rate limit decorator for heavy queries
last_heavy_call = {}
def heavy_query_rate_limit(max_calls=5, period=60):
    """Decorator for heavy queries"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user_id = args[0].from_user.id if args and hasattr(args[0], 'from_user') else 0
            now = time.time()
            if user_id not in last_heavy_call:
                last_heavy_call[user_id] = []
            recent = [t for t in last_heavy_call[user_id] if now - t < period]
            if len(recent) >= max_calls:
                raise Exception("Rate limit exceeded for heavy query")
            recent.append(now)
            last_heavy_call[user_id] = recent
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Example usage: @heavy_query_rate_limit()
# async def some_heavy_func(...):

# Admin notifications (stub: call from payment/user signup)
async def send_admin_notification(action: str, details: str):
    """Send to all admins"""
    admins = ADMIN_USER_IDS
    text = f"🔔 Admin Alert: {action}\nDetails: {details}"
    for admin_id in admins:
        try:
            # Assume bot instance available; in practice, use dp.bot
            # await dp.bot.send_message(admin_id, text)
            logger.info(f"Notification sent to {admin_id}: {text}")
        except:
            pass

def register_admin_handlers(dp: Dispatcher) -> None:
    """Register all admin handlers"""
    # Commands
    dp.message.register(admin_command_handler, Command("admin"))
    dp.message.register(ban_handler, Command("ban"))
    dp.message.register(unban_handler, Command("unban"))
    dp.message.register(broadcast_handler, Command("broadcast"))
    dp.message.register(cancel_state, Command("cancel"))

    # Callbacks  
    dp.callback_query.register(  
        handle_admin_callbacks,  
        lambda c: c.data and (c.data.startswith("admin_") or c.data.startswith("user_") or  
                              c.data.startswith("payments_") or c.data.startswith("analytics_") or  
                              c.data.startswith("logs_") or c.data.startswith("system_") or  
                              c.data == "back_admin")  
    )  

    # FSM handlers  
    dp.message.register(handle_user_id_input, AdminStates.waiting_for_user_id)  
    dp.message.register(handle_broadcast_input, AdminStates.waiting_for_broadcast_message)  
    dp.message.register(handle_premium_grant_input, AdminStates.waiting_for_premium_days)  
    dp.message.register(handle_usage_reset_input, AdminStates.waiting_for_usage_reset)
