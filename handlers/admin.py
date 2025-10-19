# admin.py - Advanced Admin Control System
import logging
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Callable, Awaitable, Dict, Any
import sqlite3

from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from config import ADMIN_USER_IDS, DB_PATH, FREE_USAGE_LIMIT
from database.db import (
    get_user_role, ban_user, unban_user, get_all_users, 
    get_user_by_id, update_user_data, add_usage_log,
    get_usage_count, update_user_premium_status, get_pending_payments
)

load_dotenv()

# Define role levels
ROLE_LEVELS = {
    'superadmin': 3,
    'moderator': 2,
    'support': 1,
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
    datefmt='%Y-%m-%d %H:%M:%S'
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
    return True

def admin_only(min_role: str = 'support') -> Callable:
    """Decorator for role-based access control"""
    min_level = ROLE_LEVELS.get(min_role, 1)

    def decorator(handler: Callable[[types.Message], Awaitable[None]]) -> Callable:
        async def wrapper(message: types.Message) -> None:
            user_id = message.from_user.id
            role = get_user_role(user_id)
            role_level = ROLE_LEVELS.get(role, 0)
            if role_level < min_level:
                await message.reply("❌ Unauthorized access")
                return
            if not rate_limit_check(user_id):
                await message.reply("⚠️ Rate limit exceeded. Please wait.")
                return
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error in admin handler: {e}", exc_info=True)
                await message.reply("⚠️ An error occurred")

        return wrapper
    return decorator

# === ENHANCED DASHBOARD ===

async def admin_command_handler(message: types.Message, state: FSMContext) -> None:
    """Enhanced admin dashboard with real-time stats"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await message.reply("❌ Unauthorized")
        return
    
    try:
        # Get real-time statistics
        stats = await get_dashboard_stats()
        
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

# === STATISTICS GATHERING ===

async def get_dashboard_stats() -> Dict[str, Any]:
    """Get real-time dashboard statistics"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Premium users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]
        
        # Active today
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) = date('now')")
        active_today = cursor.fetchone()[0]
        
        # New this week
        cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-7 days')")
        new_this_week = cursor.fetchone()[0] if cursor.fetchone() else 0
        
        # Files processed today
        cursor.execute("SELECT COUNT(*) FROM usage_logs WHERE date(timestamp) = date('now') AND is_success = 1")
        files_processed = cursor.fetchone()[0]
        
        # Revenue (from payment_logs if exists)
        try:
            cursor.execute("SELECT SUM(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-1 day')")
            revenue_24h = cursor.fetchone()[0] or 0
        except:
            revenue_24h = 0
        
        conn.close()
        
        # System stats
        import shutil
        disk = shutil.disk_usage(".")
        disk_usage = f"{disk.used // (2**30)}GB/{disk.total // (2**30)}GB"
        
        # Uptime calculation (simplified)
        uptime = "Running"
        
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

# === CALLBACK HANDLERS ===

async def handle_admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    """Handle admin panel callbacks"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_USER_IDS:
        await callback.answer("❌ Unauthorized", show_alert=True)
        return
    
    data = callback.data
    
    try:
        if data == "admin_refresh":
            # Refresh dashboard
            stats = await get_dashboard_stats()
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
            
            await callback.message.edit_text(admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
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
        elif data == "back_admin":
            # Return to main menu
            await admin_command_handler(callback.message, state)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Error in admin callback {data}: {e}", exc_info=True)
        await callback.answer("⚠️ Error occurred", show_alert=True)

# === USER MANAGEMENT ===

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
    builder.button(text="« Back", callback_data="admin_refresh")
    builder.adjust(2, 2, 2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_user_management_stats() -> Dict[str, Any]:
    """Get user management statistics"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium = cursor.fetchone()[0]
        
        free = total - premium
        premium_percent = (premium / total * 100) if total > 0 else 0
        free_percent = (free / total * 100) if total > 0 else 0
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-7 days')")
        active_7d = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_active < date('now', '-30 days')")
        result = cursor.fetchone()
        inactive_30d = result[0] if result else 0
        
        conn.close()
        
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

# === ANALYTICS ===

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
    builder.button(text="« Back", callback_data="admin_refresh")
    builder.adjust(2, 2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_analytics_data() -> Dict[str, Any]:
    """Get analytics data"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        # New users in last 30 days
        cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-30 days')")
        result = cursor.fetchone()
        new_users_30d = result[0] if result else 0
        
        # Growth rate
        cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-60 days') AND date(created_at) < date('now', '-30 days')")
        result = cursor.fetchone()
        prev_month = result[0] if result else 1
        growth_rate = ((new_users_30d - prev_month) / prev_month * 100) if prev_month > 0 else 0
        
        # Active users
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) = date('now')")
        dau = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-7 days')")
        wau = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-30 days')")
        mau = cursor.fetchone()[0]
        
        # Average uses per user
        cursor.execute("SELECT AVG(use_count) FROM (SELECT user_id, COUNT(*) as use_count FROM usage_logs WHERE date(timestamp) >= date('now', '-30 days') GROUP BY user_id)")
        avg_uses = cursor.fetchone()[0] or 0
        
        # Revenue
        try:
            cursor.execute("SELECT SUM(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-30 days')")
            revenue_30d = cursor.fetchone()[0] or 0
        except:
            revenue_30d = 0
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0] or 1
        arpu = revenue_30d / total_users if total_users > 0 else 0
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_subs = cursor.fetchone()[0]
        
        conversion_rate = (premium_subs / total_users * 100) if total_users > 0 else 0
        
        conn.close()
        
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

# === PAYMENTS ===

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
        f"Monthly Plans: <b>{payments['monthly_plans']}</b> (₦{payments['monthly_revenue']:,.0f})\n\n"
        f"⏳ <b>Status</b>\n"
        f"Pending: <b>{payments['pending']}</b>\n"
        f"Completed: <b>{payments['completed']}</b>\n"
        f"Failed: <b>{payments['failed']}</b>\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Recent Transactions", callback_data="payments_recent")
    builder.button(text="⏳ Pending Payments", callback_data="payments_pending")
    builder.button(text="💾 Export Report", callback_data="payments_export")
    builder.button(text="« Back", callback_data="admin_refresh")
    builder.adjust(2, 2)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_payment_stats() -> Dict[str, Any]:
    """Get payment statistics"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        # Total revenue
        try:
            cursor.execute("SELECT SUM(amount), COUNT(*), AVG(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-30 days')")
            row = cursor.fetchone()
            total_revenue = row[0] or 0
            total_transactions = row[1] or 0
            avg_transaction = row[2] or 0
            
            cursor.execute("SELECT COUNT(*), SUM(amount) FROM payment_logs WHERE plan_type = 'weekly' AND date(timestamp) >= date('now', '-30 days')")
            weekly_row = cursor.fetchone()
            weekly_plans = weekly_row[0] or 0
            weekly_revenue = weekly_row[1] or 0
            
            cursor.execute("SELECT COUNT(*), SUM(amount) FROM payment_logs WHERE plan_type = 'monthly' AND date(timestamp) >= date('now', '-30 days')")
            monthly_row = cursor.fetchone()
            monthly_plans = monthly_row[0] or 0
            monthly_revenue = monthly_row[1] or 0
        except:
            total_revenue = 0
            total_transactions = 0
            avg_transaction = 0
            weekly_plans = 0
            weekly_revenue = 0
            monthly_plans = 0
            monthly_revenue = 0
        
        conn.close()
        
        return {
            'total_revenue': total_revenue,
            'total_transactions': total_transactions,
            'avg_transaction': avg_transaction,
            'weekly_plans': weekly_plans,
            'weekly_revenue': weekly_revenue,
            'monthly_plans': monthly_plans,
            'monthly_revenue': monthly_revenue,
            'pending': 0,
            'completed': total_transactions,
            'failed': 0
        }
    except Exception as e:
        logger.error(f"Error getting payment stats: {e}")
        return {'total_revenue': 0, 'total_transactions': 0, 'avg_transaction': 0, 'weekly_plans': 0, 'weekly_revenue': 0, 'monthly_plans': 0, 'monthly_revenue': 0, 'pending': 0, 'completed': 0, 'failed': 0}

# === ACTIVITY LOGS ===

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
    builder.button(text="« Back", callback_data="admin_refresh")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_recent_activity() -> list:
    """Get recent activity logs"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, tool, timestamp, is_success 
            FROM usage_logs 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        
        logs = []
        for row in cursor.fetchall():
            user_id, tool, timestamp, success = row
            status = "✅" if success else "❌"
            logs.append(f"{status} User {user_id} - {tool} - {timestamp}")
        
        conn.close()
        return logs if logs else ["No recent activity"]
    except Exception as e:
        logger.error(f"Error getting activity logs: {e}")
        return ["Error loading logs"]

# === USER SEARCH ===

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
    await callback.answer()

# === BROADCAST ===

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

# === SYSTEM TOOLS ===

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
        f"Python: <b>{system['python_version']}</b>\n"
        f"Status: <b>{system['status']}</b>\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Restart Bot", callback_data="system_restart")
    builder.button(text="💾 Backup DB", callback_data="system_backup")
    builder.button(text="🧹 Clean Logs", callback_data="system_clean")
    builder.button(text="📊 System Logs", callback_data="system_logs")
    builder.button(text="« Back", callback_data="admin_refresh")
    builder.adjust(2, 2, 1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

async def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    try:
        import shutil
        
        # Database size
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        db_size = f"{db_size_bytes // 1024:.1f} KB"
        
        # Table count
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        conn.close()
        
        # Disk usage
        disk = shutil.disk_usage(".")
        disk_used = f"{disk.used // (2**30)} GB"
        disk_free = f"{disk.free // (2**30)} GB"
        
        # Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        return {
            'db_size': db_size,
            'table_count': table_count,
            'disk_used': disk_used,
            'disk_free': disk_free,
            'python_version': python_version,
            'status': '✅ Running'
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {'db_size': 'Unknown', 'table_count': 0, 'disk_used': 'Unknown', 'disk_free': 'Unknown', 'python_version': 'Unknown', 'status': '⚠️ Error'}

# === USER ACTIONS ===

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
        update_user_data(user_id, {'usage_today': 0})
        await callback.answer("✅ Usage reset successfully", show_alert=True)
        builder = InlineKeyboardBuilder()
        builder.button(text="« Back", callback_data="admin_users")
        await callback.message.edit_text(
            f"✅ Usage reset for user {user_id}",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.answer("Unknown action", show_alert=True)

async def list_users(callback: types.CallbackQuery, premium_only: bool = False):
    """List users"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        
        if premium_only:
            cursor.execute("SELECT user_id, username, is_premium FROM users WHERE is_premium = 1 LIMIT 10")
            title = "⭐ PREMIUM USERS"
        else:
            cursor.execute("SELECT user_id, username, is_premium FROM users LIMIT 10")
            title = "📋 ALL USERS"
        
        rows = cursor.fetchall()
        conn.close()
        
        text = f"<b>{title}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        
        for row in rows:
            user_id, username, is_premium = row
            status = "⭐" if is_premium else "👤"
            text += f"{status} {username or 'N/A'} ({user_id})\n"
        
        text += f"\n<i>Showing first 10 users</i>"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="« Back", callback_data="admin_users")
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        await callback.answer("⚠️ Error loading users", show_alert=True)

# === MESSAGE HANDLERS FOR FSM ===

async def handle_user_id_input(message: types.Message, state: FSMContext):
    """Handle user ID input for search"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return
    
    try:
        user_id = int(message.text)
        user_data = get_user_by_id(user_id)
        
        if not user_data:
            await message.reply("❌ User not found")
            await state.clear()
            return
        
        # Display user profile
        is_premium = user_data.get('is_premium', False)
        username = user_data.get('username', 'N/A')
        usage_today = user_data.get('usage_today', 0)
        
        text = (
            f"👤 <b>USER PROFILE</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"ID: <code>{user_id}</code>\n"
            f"Username: <b>{username}</b>\n"
            f"Status: {'⭐ Premium' if is_premium else '👤 Free'}\n"
            f"Usage Today: <b>{usage_today}/{FREE_USAGE_LIMIT}</b>\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎁 Grant Premium", callback_data=f"grant_premium_{user_id}")
        builder.button(text="🔄 Reset Usage", callback_data=f"reset_usage_{user_id}")
        builder.button(text="« Back", callback_data="admin_users")
        builder.adjust(2, 1)
        
        await message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        
    except ValueError:
        await message.reply("❌ Invalid user ID. Must be a number.")
    except Exception as e:
        logger.error(f"Error handling user search: {e}")
        await message.reply("⚠️ Error occurred")
    finally:
        await state.clear()

async def handle_broadcast_input(message: types.Message, state: FSMContext):
    """Handle broadcast message input"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return
    
    try:
        users = get_all_users()
        sent_count = 0
        failed_count = 0
        
        await message.reply(f"📢 Broadcasting to {len(users)} users...")
        
        for user_data in users:
            try:
                user_id = user_data[0] if isinstance(user_data, tuple) else user_data.get('user_id')
                await message.bot.send_message(user_id, message.text)
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send to {user_id}: {e}")
        
        await message.reply(
            f"✅ Broadcast complete!\n"
            f"Sent: {sent_count}\n"
            f"Failed: {failed_count}"
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error broadcasting: {e}")
        await message.reply("⚠️ Broadcast failed")
        await state.clear()

async def handle_premium_grant_input(message: types.Message, state: FSMContext):
    """Handle premium grant input"""
    if message.text == "/cancel":
        await state.clear()
        await message.reply("Cancelled. Use /admin to return to panel.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.reply("❌ Invalid format. Use: <user_id> <days>")
            return
        
        user_id = int(parts[0])
        days = int(parts[1])
        
        if days <= 0 or days > 365:
            await message.reply("❌ Days must be between 1 and 365")
            return
        
        update_user_premium_status(user_id, days)
        await message.reply(f"✅ Granted {days} days premium to user {user_id}")
        await state.clear()
        
    except ValueError:
        await message.reply("❌ Invalid input. Both values must be numbers.")
    except Exception as e:
        logger.error(f"Error granting premium: {e}")
        await message.reply("⚠️ Error occurred")
    finally:
        await state.clear()

# === LEGACY COMMAND HANDLERS ===

@admin_only(min_role='moderator')
async def ban_handler(message: types.Message) -> None:
    """Ban a user"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        user_id_to_ban = int(parts[1])
        if user_id_to_ban <= 0:
            raise ValueError("Invalid user ID")
    except ValueError:
        await message.reply("Usage: /ban <user_id>")
        return

    ban_user(user_id_to_ban)
    logger.info(f"Admin {message.from_user.id} banned user {user_id_to_ban}")
    await message.reply(f"✅ User {user_id_to_ban} has been banned.")

@admin_only(min_role='moderator')
async def unban_handler(message: types.Message) -> None:
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

    unban_user(user_id_to_unban)
    logger.info(f"Admin {message.from_user.id} unbanned user {user_id_to_unban}")
    await message.reply(f"✅ User {user_id_to_unban} has been unbanned.")

@admin_only(min_role='superadmin')
async def broadcast_handler(message: types.Message) -> None:
    """Broadcast message to all users"""
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.reply("Usage: /broadcast <message>")
        return

    users = get_all_users()
    sent_count = 0
    for user_data in users:
        try:
            user_id = user_data[0] if isinstance(user_data, tuple) else user_data.get('user_id')
            await message.bot.send_message(user_id, text)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to user: {e}")

    logger.info(f"Admin {message.from_user.id} broadcasted to {sent_count} users")
    await message.reply(f"✅ Broadcast sent to {sent_count} users.")

# === REGISTRATION ===

def register_admin_handlers(dp: Dispatcher) -> None:
    """Register all admin handlers"""
    # Commands
    dp.message.register(admin_command_handler, Command("admin"))
    dp.message.register(ban_handler, Command("ban"))
    dp.message.register(unban_handler, Command("unban"))
    dp.message.register(broadcast_handler, Command("broadcast"))
    
    # Callbacks
    dp.callback_query.register(
        handle_admin_callbacks,
        lambda c: c.data.startswith("admin_") or c.data.startswith("user_") or 
                  c.data.startswith("payments_") or c.data.startswith("analytics_") or
                  c.data.startswith("logs_") or c.data.startswith("system_") or
                  c.data == "back_admin"
    )
    
    # FSM handlers
    dp.message.register(handle_user_id_input, AdminStates.waiting_for_user_id)
    dp.message.register(handle_broadcast_input, AdminStates.waiting_for_broadcast_message)
    dp.message.register(handle_premium_grant_input, AdminStates.waiting_for_premium_days)
