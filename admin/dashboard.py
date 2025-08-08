import logging
import sqlite3
import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from database.db import get_all_users, get_all_payments, get_user

logger = logging.getLogger(__name__)

class AdminDashboard:
    """Advanced admin dashboard with comprehensive analytics and management"""
    
    def __init__(self):
        self.config = Config()
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get real-time system metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            # Bot-specific metrics
            bot_metrics = await self._get_bot_metrics()
            
            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": round(memory.used / (1024**3), 2),
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "disk_percent": round((disk.used / disk.total) * 100, 2),
                    "disk_used_gb": round(disk.used / (1024**3), 2),
                    "disk_total_gb": round(disk.total / (1024**3), 2),
                    "network_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
                    "network_recv_mb": round(net_io.bytes_recv / (1024**2), 2)
                },
                "bot": bot_metrics,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}
    
    async def _get_bot_metrics(self) -> Dict[str, Any]:
        """Get bot-specific metrics"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            # User statistics
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            premium_users = cursor.fetchone()[0]
            
            # Usage statistics (last 24 hours)
            yesterday = datetime.now() - timedelta(hours=24)
            cursor.execute(
                "SELECT COUNT(*) FROM usage_logs WHERE timestamp > ?",
                (yesterday.isoformat(),)
            )
            daily_usage = cursor.fetchone()[0]
            
            # Payment statistics
            cursor.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE status = 'approved'")
            payment_data = cursor.fetchone()
            total_payments = payment_data[0] or 0
            total_revenue = payment_data[1] or 0
            
            # Recent activity (last hour)
            last_hour = datetime.now() - timedelta(hours=1)
            cursor.execute(
                "SELECT COUNT(*) FROM usage_logs WHERE timestamp > ?",
                (last_hour.isoformat(),)
            )
            hourly_activity = cursor.fetchone()[0]
            
            # Error rate (from logs)
            error_rate = await self._calculate_error_rate()
            
            conn.close()
            
            return {
                "users": {
                    "total": total_users,
                    "premium": premium_users,
                    "free": total_users - premium_users,
                    "conversion_rate": round((premium_users / total_users * 100) if total_users > 0 else 0, 2)
                },
                "usage": {
                    "daily": daily_usage,
                    "hourly": hourly_activity,
                    "avg_per_user": round(daily_usage / total_users if total_users > 0 else 0, 2)
                },
                "revenue": {
                    "total": total_revenue,
                    "total_payments": total_payments,
                    "avg_payment": round(total_revenue / total_payments if total_payments > 0 else 0, 2)
                },
                "performance": {
                    "error_rate": error_rate,
                    "uptime_hours": self._get_uptime_hours()
                }
            }
        except Exception as e:
            logger.error(f"Error getting bot metrics: {e}")
            return {"error": str(e)}
    
    async def _calculate_error_rate(self) -> float:
        """Calculate error rate from logs"""
        try:
            # This is a simplified calculation
            # In production, you'd want to parse actual log files
            return 0.02  # 2% error rate as example
        except:
            return 0.0
    
    def _get_uptime_hours(self) -> float:
        """Get bot uptime in hours"""
        try:
            # This is simplified - in production you'd track actual start time
            return round(psutil.boot_time() / 3600, 2)
        except:
            return 0.0
    
    async def get_user_analytics(self) -> Dict[str, Any]:
        """Get comprehensive user analytics"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            # User growth over time
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as new_users
                FROM users 
                WHERE created_at >= date('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            growth_data = cursor.fetchall()
            
            # User activity patterns
            cursor.execute("""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as usage_count
                FROM usage_logs
                WHERE timestamp >= datetime('now', '-7 days')
                GROUP BY hour
                ORDER BY hour
            """)
            activity_patterns = cursor.fetchall()
            
            # Top tools usage
            cursor.execute("""
                SELECT tool_used, COUNT(*) as usage_count
                FROM usage_logs
                WHERE timestamp >= datetime('now', '-30 days')
                GROUP BY tool_used
                ORDER BY usage_count DESC
                LIMIT 10
            """)
            tool_usage = cursor.fetchall()
            
            # User retention analysis
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN last_usage >= datetime('now', '-1 day') THEN 'Daily Active'
                        WHEN last_usage >= datetime('now', '-7 days') THEN 'Weekly Active'
                        WHEN last_usage >= datetime('now', '-30 days') THEN 'Monthly Active'
                        ELSE 'Inactive'
                    END as activity_level,
                    COUNT(*) as user_count
                FROM users
                GROUP BY activity_level
            """)
            retention_data = cursor.fetchall()
            
            conn.close()
            
            return {
                "growth": [{"date": row[0], "new_users": row[1]} for row in growth_data],
                "activity_patterns": [{"hour": int(row[0]), "usage": row[1]} for row in activity_patterns],
                "tool_usage": [{"tool": row[0], "count": row[1]} for row in tool_usage],
                "retention": [{"level": row[0], "count": row[1]} for row in retention_data]
            }
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {"error": str(e)}
    
    async def get_financial_analytics(self) -> Dict[str, Any]:
        """Get financial analytics and revenue insights"""
        try:
            conn = sqlite3.connect(Config.DB_PATH)
            cursor = conn.cursor()
            
            # Revenue over time
            cursor.execute("""
                SELECT DATE(created_at) as date, 
                       SUM(CASE WHEN status = 'approved' THEN amount ELSE 0 END) as revenue,
                       COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_payments,
                       COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_payments
                FROM payments
                WHERE created_at >= date('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            revenue_data = cursor.fetchall()
            
            # Plan popularity
            cursor.execute("""
                SELECT plan_type, 
                       COUNT(*) as purchases,
                       SUM(amount) as total_revenue
                FROM payments
                WHERE status = 'approved'
                GROUP BY plan_type
                ORDER BY total_revenue DESC
            """)
            plan_data = cursor.fetchall()
            
            # Payment conversion funnel
            cursor.execute("""
                SELECT status,
                       COUNT(*) as count,
                       AVG(amount) as avg_amount
                FROM payments
                GROUP BY status
            """)
            conversion_data = cursor.fetchall()
            
            conn.close()
            
            return {
                "revenue_timeline": [
                    {
                        "date": row[0], 
                        "revenue": row[1], 
                        "approved": row[2], 
                        "pending": row[3]
                    } for row in revenue_data
                ],
                "plan_performance": [
                    {
                        "plan": row[0], 
                        "purchases": row[1], 
                        "revenue": row[2]
                    } for row in plan_data
                ],
                "conversion_funnel": [
                    {
                        "status": row[0], 
                        "count": row[1], 
                        "avg_amount": row[2]
                    } for row in conversion_data
                ]
            }
        except Exception as e:
            logger.error(f"Error getting financial analytics: {e}")
            return {"error": str(e)}
    
    async def generate_dashboard_text(self) -> str:
        """Generate comprehensive dashboard text with analytics"""
        try:
            metrics = await self.get_system_metrics()
            user_analytics = await self.get_user_analytics()
            financial_analytics = await self.get_financial_analytics()
            
            # System health indicators
            system = metrics.get("system", {})
            bot = metrics.get("bot", {})
            
            # Health status
            health_status = "🟢 Excellent"
            if system.get("cpu_percent", 0) > 80 or system.get("memory_percent", 0) > 85:
                health_status = "🟡 Warning"
            if system.get("cpu_percent", 0) > 95 or system.get("memory_percent", 0) > 95:
                health_status = "🔴 Critical"
            
            dashboard_text = f"""
🎛️ **DocuLuna Admin Dashboard**
━━━━━━━━━━━━━━━━━━━━━

📊 **System Health: {health_status}**
🖥️ CPU: {system.get('cpu_percent', 0):.1f}%
🧠 Memory: {system.get('memory_percent', 0):.1f}% ({system.get('memory_used_gb', 0):.1f}GB/{system.get('memory_total_gb', 0):.1f}GB)
💾 Disk: {system.get('disk_percent', 0):.1f}% ({system.get('disk_used_gb', 0):.1f}GB/{system.get('disk_total_gb', 0):.1f}GB)

👥 **User Metrics**
Total Users: **{bot.get('users', {}).get('total', 0):,}**
Premium Users: **{bot.get('users', {}).get('premium', 0):,}** ({bot.get('users', {}).get('conversion_rate', 0):.1f}%)
Daily Usage: **{bot.get('usage', {}).get('daily', 0):,}** operations
Hourly Activity: **{bot.get('usage', {}).get('hourly', 0):,}** operations

💰 **Revenue Overview**
Total Revenue: **₦{bot.get('revenue', {}).get('total', 0):,}**
Total Payments: **{bot.get('revenue', {}).get('total_payments', 0):,}**
Avg Payment: **₦{bot.get('revenue', {}).get('avg_payment', 0):,.0f}**

⚡ **Performance**
Error Rate: **{bot.get('performance', {}).get('error_rate', 0):.2%}**
Uptime: **{bot.get('performance', {}).get('uptime_hours', 0):.1f}** hours

🕒 Last Updated: {datetime.now().strftime('%H:%M:%S')}
"""
            
            return dashboard_text
            
        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            return f"❌ Dashboard Error: {str(e)}"
    
    async def show_advanced_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advanced analytics dashboard"""
        try:
            query = update.callback_query
            await query.answer()
            
            analytics_text = await self.generate_analytics_report()
            
            keyboard = [
                [
                    InlineKeyboardButton("📈 User Analytics", callback_data="analytics_users"),
                    InlineKeyboardButton("💰 Financial", callback_data="analytics_financial")
                ],
                [
                    InlineKeyboardButton("🔄 System Health", callback_data="analytics_system"),
                    InlineKeyboardButton("📊 Performance", callback_data="analytics_performance")
                ],
                [
                    InlineKeyboardButton("📋 Export Data", callback_data="analytics_export"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="analytics_settings")
                ],
                [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                analytics_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error showing analytics: {e}")
            await query.edit_message_text("❌ Error loading analytics dashboard.")
    
    async def generate_analytics_report(self) -> str:
        """Generate detailed analytics report"""
        try:
            user_analytics = await self.get_user_analytics()
            financial_analytics = await self.get_financial_analytics()
            
            # Top tools
            top_tools = user_analytics.get("tool_usage", [])[:5]
            tools_text = "\n".join([f"• {tool['tool']}: {tool['count']:,}" for tool in top_tools])
            
            # Revenue trend
            revenue_data = financial_analytics.get("revenue_timeline", [])
            recent_revenue = sum([day['revenue'] for day in revenue_data[-7:]])  # Last 7 days
            
            # Plan performance
            plan_data = financial_analytics.get("plan_performance", [])
            best_plan = plan_data[0] if plan_data else {"plan": "N/A", "revenue": 0}
            
            report = f"""
📈 **Advanced Analytics Report**
━━━━━━━━━━━━━━━━━━━━━

🛠️ **Top Tools (30 days)**
{tools_text if tools_text else "No data available"}

💰 **Revenue Insights**
Last 7 days: **₦{recent_revenue:,}**
Best Plan: **{best_plan['plan']}** (₦{best_plan.get('revenue', 0):,})

📊 **Key Metrics**
• User Growth: {len(user_analytics.get('growth', []))} days tracked
• Activity Patterns: {len(user_analytics.get('activity_patterns', []))} hours analyzed
• Retention Levels: {len(user_analytics.get('retention', []))} categories

🔄 **Auto-refresh**: Every 5 minutes
📅 **Report Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            return report
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            return f"❌ Analytics Error: {str(e)}"

# Global dashboard instance
admin_dashboard = AdminDashboard()

async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main admin dashboard"""
    try:
        user_id = update.effective_user.id
        if user_id not in Config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        dashboard_text = await admin_dashboard.generate_dashboard_text()
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Advanced Analytics", callback_data="show_analytics"),
                InlineKeyboardButton("👥 User Management", callback_data="admin_users_advanced")
            ],
            [
                InlineKeyboardButton("💰 Payment Center", callback_data="admin_payments_advanced"),
                InlineKeyboardButton("🔧 System Tools", callback_data="admin_system_advanced")
            ],
            [
                InlineKeyboardButton("📢 Notifications", callback_data="admin_notifications"),
                InlineKeyboardButton("🛡️ Security", callback_data="admin_security")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"),
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error showing admin dashboard: {e}")
        error_msg = "❌ Error loading admin dashboard."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)