# database/db.py
import aiosqlite
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from config import DB_PATH as DATABASE_PATH

logger = logging.getLogger(__name__)

# Minimal schema fallback if schema.sql missing
MINIMAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_premium INTEGER DEFAULT 0,
    premium_expiry DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    usage_today INTEGER DEFAULT 0,
    usage_reset_date DATE DEFAULT CURRENT_DATE,
    referral_count INTEGER DEFAULT 0,
    referral_earnings INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tool TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_success INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    referral_code TEXT UNIQUE,
    referral_count INTEGER DEFAULT 0,
    premium_days_earned INTEGER DEFAULT 0,
    total_earnings INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS payment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    payment_method TEXT,
    status TEXT DEFAULT 'pending',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    feedback TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS referral_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS premium_expiry_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    warning_sent DATETIME DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE
);
"""

async def init_db():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        stat = shutil.disk_usage(os.path.dirname(DATABASE_PATH))
        if stat.free < 50 * 1024 * 1024:  # 50 MB threshold
            logger.error("Insufficient storage for database initialization")
            raise Exception("Low disk space")
        
        schema_sql = MINIMAL_SCHEMA  # Fallback
        schema_file = "database/schema.sql"
        if os.path.exists(schema_file):
            with open(schema_file, "r") as f:
                schema_sql = f.read()
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.executescript(schema_sql)
            
            # Check table existence before migrations
            async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'") as cursor:
                if not await cursor.fetchone():
                    logger.warning("Users table missing; using minimal schema")
            
            # Migrations
            async with conn.execute("PRAGMA table_info(users)") as cursor:
                columns = [column[1] for column in await cursor.fetchall()]
            
            if 'usage_today' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN usage_today INTEGER DEFAULT 0")
                logger.info("Added usage_today column")
            
            if 'usage_reset_date' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN usage_reset_date DATE")
                await conn.execute("UPDATE users SET usage_reset_date = date('now') WHERE usage_reset_date IS NULL")
                logger.info("Added usage_reset_date column")
            
            if 'referral_count' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
                logger.info("Added referral_count column")
            
            if 'referral_earnings' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN referral_earnings INTEGER DEFAULT 0")
                logger.info("Added referral_earnings column")
            
            # Add is_banned for ban functionality
            if 'is_banned' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
                logger.info("Added is_banned column")
            
            # Add role column for admin functionality
            if 'role' not in columns:
                await conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                logger.info("Added role column")
            
            # Referral columns
            async with conn.execute("PRAGMA table_info(referrals)") as cursor:
                ref_columns = [column[1] for column in await cursor.fetchall()]
            if 'premium_days_earned' not in ref_columns:
                await conn.execute("ALTER TABLE referrals ADD COLUMN premium_days_earned INTEGER DEFAULT 0")
                logger.info("Added premium_days_earned to referrals")
            if 'total_earnings' not in ref_columns:
                await conn.execute("ALTER TABLE referrals ADD COLUMN total_earnings INTEGER DEFAULT 0")
                logger.info("Added total_earnings to referrals")
            
            # Payment logs status column
            async with conn.execute("PRAGMA table_info(payment_logs)") as cursor:
                payment_columns = [column[1] for column in await cursor.fetchall()]
            if 'status' not in payment_columns:
                await conn.execute("ALTER TABLE payment_logs ADD COLUMN status TEXT DEFAULT 'pending'")
                logger.info("Added status column to payment_logs")
            
            await conn.commit()
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

# [Rest of functions unchanged, except ban/unban impl and transactions]

async def ban_user(user_id: int) -> bool:
    """Ban user by setting is_banned=1."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error banning user {user_id}: {e}")
        return False

async def unban_user(user_id: int) -> bool:
    """Unban user by setting is_banned=0."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error unbanning user {user_id}: {e}")
        return False

async def add_referral_reward(user_id: int, amount: int, plan_type: str):
    """Add referral reward to user with transaction."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("BEGIN")
            try:
                await conn.execute("""
                    INSERT INTO referral_rewards (user_id, amount, plan_type, timestamp)
                    VALUES (?, ?, ?, datetime('now'))
                """, (user_id, amount, plan_type))
                await conn.execute("""
                    UPDATE referrals 
                    SET total_earnings = COALESCE(total_earnings, 0) + ?
                    WHERE user_id = ?
                """, (amount, user_id))
                await conn.commit()
            except:
                await conn.rollback()
                raise
    except Exception as e:
        logger.error(f"Error adding referral reward for user {user_id}: {e}")

async def update_user_data(user_id: int, data: Dict[str, Any]):
    """Generic user data update with type guards."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            # Premium handling
            if 'is_premium' in data or 'premium_expiry' in data:
                if data.get('is_premium'):
                    days = data.get('days', 30)
                    await update_user_premium_status(user_id, days)
            
            # Other updates
            update_fields = []
            values = []
            for key, value in data.items():
                if key in ['username', 'last_active', 'preferences', 'onboarding_complete', 
                          'onboarding_date', 'language', 'timezone', 'total_interactions',
                          'premium_status', 'referral_used', 'usage_today', 'usage_reset_date']:
                    if isinstance(value, (str, int, float, bool)):
                        update_fields.append(f"{key} = ?")
                        values.append(value)
                    else:
                        logger.warning(f"Skipping non-primitive value for {key}: {type(value)}")
            
            if update_fields:
                values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
                await conn.execute(query, values)
                await conn.commit()
    except Exception as e:
        logger.error(f"Error updating user data for {user_id}: {e}")

async def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data by user ID."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        logger.error(f"Error getting user data for {user_id}: {e}")
        return None

async def create_user(user_data: Dict[str, Any]) -> bool:
    """Create a new user."""
    try:
        user_id = user_data.get('user_id')
        username = user_data.get('username', '')
        first_name = user_data.get('first_name', '')
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, last_active, usage_today, usage_reset_date)
                VALUES (?, ?, ?, datetime('now'), datetime('now'), 0, date('now'))
            """, (user_id, username, first_name))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False

async def get_all_users() -> List[Dict[str, Any]]:
    """Get all users."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

async def get_user_role(user_id: int) -> str:
    """Get user role (admin, premium, or user)."""
    try:
        # Check if user is an admin first
        from config import ADMIN_USER_IDS
        if user_id in ADMIN_USER_IDS:
            return 'superadmin'
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("SELECT role, is_premium FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    # Return the role column if set, otherwise fall back to premium/user
                    role = row[0]
                    if role and role != 'user':
                        return role
                    return 'premium' if row[1] else 'user'
                return 'user'
    except Exception as e:
        logger.error(f"Error getting user role for {user_id}: {e}")
        return 'user'

async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID (alias for get_user_data)."""
    return await get_user_data(user_id)

async def add_usage_log(user_id: int, tool: str, is_success: bool = True) -> bool:
    """Log user tool usage."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("""
                INSERT INTO usage_logs (user_id, tool, timestamp, is_success)
                VALUES (?, ?, datetime('now'), ?)
            """, (user_id, tool, 1 if is_success else 0))
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding usage log for user {user_id}: {e}")
        return False

async def get_usage_count(user_id: int, days: int = 1) -> int:
    """Get usage count for a user within specified days."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("""
                SELECT COUNT(*) FROM usage_logs 
                WHERE user_id = ? AND date(timestamp) >= date('now', '-' || ? || ' days')
            """, (user_id, days)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        logger.error(f"Error getting usage count for {user_id}: {e}")
        return 0

async def update_user_premium_status(user_id: int, days: int) -> bool:
    """Update user premium status."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("""
                UPDATE users 
                SET is_premium = 1, 
                    premium_expiry = date('now', '+' || ? || ' days')
                WHERE user_id = ?
            """, (days, user_id))
            await conn.commit()
            return conn.total_changes > 0
    except Exception as e:
        logger.error(f"Error updating premium status for {user_id}: {e}")
        return False

async def expire_premium_statuses() -> int:
    """Check and expire premium statuses for users whose expiry date has passed."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            cursor = await conn.execute("""
                UPDATE users 
                SET is_premium = 0
                WHERE is_premium = 1 
                AND premium_expiry IS NOT NULL 
                AND premium_expiry < datetime('now')
            """)
            await conn.commit()
            expired_count = cursor.rowcount
            if expired_count > 0:
                logger.info(f"Expired premium status for {expired_count} user(s)")
            return expired_count
    except Exception as e:
        logger.error(f"Error expiring premium statuses: {e}")
        return 0

async def get_pending_payments() -> List[Dict[str, Any]]:
    """Get all pending payments."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT * FROM payment_logs 
                WHERE status = 'pending' 
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting pending payments: {e}")
        return []

async def log_admin_action(admin_id: int, action: str, details: str = "") -> bool:
    """Log admin actions."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("""
                INSERT INTO admin_action_logs (admin_id, action, details, timestamp)
                VALUES (?, ?, ?, datetime('now'))
            """, (admin_id, action, details))
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error logging admin action: {e}")
        return False

async def get_or_create_wallet(user_id: int) -> Dict[str, Any]:
    """Get or create wallet for user."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("""
                INSERT OR IGNORE INTO wallets (user_id, balance, total_earned, last_updated)
                VALUES (?, 0, 0, datetime('now'))
            """, (user_id,))
            await conn.commit()
            
            async with conn.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {"user_id": user_id, "balance": 0, "total_earned": 0}
    except Exception as e:
        logger.error(f"Error getting/creating wallet for {user_id}: {e}")
        return {"user_id": user_id, "balance": 0, "total_earned": 0}

async def update_wallet_balance(user_id: int, amount: int, operation: str = "add") -> bool:
    """Update wallet balance (add or deduct)."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await get_or_create_wallet(user_id)
            
            if operation == "add":
                await conn.execute("""
                    UPDATE wallets 
                    SET balance = balance + ?, 
                        total_earned = total_earned + ?,
                        last_updated = datetime('now')
                    WHERE user_id = ?
                """, (amount, amount, user_id))
            elif operation == "deduct":
                async with conn.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row or row[0] < amount:
                        return False
                
                await conn.execute("""
                    UPDATE wallets 
                    SET balance = balance - ?,
                        last_updated = datetime('now')
                    WHERE user_id = ?
                """, (amount, user_id))
            
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating wallet for {user_id}: {e}")
        return False

async def create_referral_code(user_id: int) -> str:
    """Create or get referral code for user."""
    referral_code = f"DOCU{user_id}"
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            await conn.execute("""
                INSERT OR IGNORE INTO referrals (user_id, referral_code, referral_count, premium_days_earned, total_earnings)
                VALUES (?, ?, 0, 0, 0)
            """, (user_id, referral_code))
            await conn.commit()
            return referral_code
    except Exception as e:
        logger.error(f"Error creating referral code for {user_id}: {e}")
        return referral_code

async def track_referral(referrer_id: int, referred_id: int) -> bool:
    """Track a referral relationship (pending until payment)."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("SELECT referred_id FROM referral_relationships WHERE referred_id = ?", (referred_id,)) as cursor:
                if await cursor.fetchone():
                    return False
            
            await conn.execute("""
                INSERT INTO referral_relationships (referrer_id, referred_id, status, created_at)
                VALUES (?, ?, 'pending', datetime('now'))
            """, (referrer_id, referred_id))
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error tracking referral {referrer_id} -> {referred_id}: {e}")
        return False

async def complete_referral(referred_id: int, plan_type: str) -> Optional[int]:
    """Complete referral when referred user makes a purchase. Returns referrer_id if successful."""
    try:
        reward_map = {"weekly": 150, "monthly": 350}
        reward_amount = reward_map.get(plan_type, 0)
        
        if reward_amount == 0:
            return None
        
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("""
                SELECT referrer_id FROM referral_relationships 
                WHERE referred_id = ? AND status = 'pending'
            """, (referred_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                referrer_id = row[0]
            
            await conn.execute("BEGIN")
            try:
                await conn.execute("""
                    UPDATE referral_relationships 
                    SET status = 'completed', plan_type = ?, reward_amount = ?, rewarded_at = datetime('now')
                    WHERE referred_id = ?
                """, (plan_type, reward_amount, referred_id))
                
                await conn.execute("""
                    INSERT OR IGNORE INTO wallets (user_id, balance, total_earned)
                    VALUES (?, 0, 0)
                """, (referrer_id,))
                
                await conn.execute("""
                    UPDATE wallets 
                    SET balance = balance + ?, total_earned = total_earned + ?, last_updated = datetime('now')
                    WHERE user_id = ?
                """, (reward_amount, reward_amount, referrer_id))
                
                await conn.commit()
                logger.info(f"Referral completed: {referrer_id} earned ₦{reward_amount} from {referred_id}")
                return referrer_id
            except:
                await conn.rollback()
                raise
    except Exception as e:
        logger.error(f"Error completing referral for {referred_id}: {e}")
        return None

async def get_referral_stats(user_id: int) -> Dict[str, Any]:
    """Get referral statistics for a user."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            
            async with conn.execute("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                       SUM(CASE WHEN status = 'completed' THEN reward_amount ELSE 0 END) as total_earned
                FROM referral_relationships
                WHERE referrer_id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "total_referrals": row["total"] or 0,
                        "completed": row["completed"] or 0,
                        "pending": row["pending"] or 0,
                        "total_earned": row["total_earned"] or 0
                    }
                return {"total_referrals": 0, "completed": 0, "pending": 0, "total_earned": 0}
    except Exception as e:
        logger.error(f"Error getting referral stats for {user_id}: {e}")
        return {"total_referrals": 0, "completed": 0, "pending": 0, "total_earned": 0}

async def create_withdrawal_request(user_id: int, amount: int, account_name: str, bank_name: str, account_number: str) -> Optional[int]:
    """Create a withdrawal request."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            wallet = await get_or_create_wallet(user_id)
            if wallet["balance"] < amount:
                return None
            
            async with conn.execute("""
                SELECT COUNT(*) FROM withdrawal_requests 
                WHERE user_id = ? AND status = 'pending'
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    return None
            
            async with conn.execute("""
                INSERT INTO withdrawal_requests (user_id, amount, account_name, bank_name, account_number, status, requested_at)
                VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))
            """, (user_id, amount, account_name, bank_name, account_number)) as cursor:
                await conn.commit()
                return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error creating withdrawal request for {user_id}: {e}")
        return None

async def get_withdrawal_requests(user_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get withdrawal requests filtered by user and/or status."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            
            query = "SELECT * FROM withdrawal_requests WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY requested_at DESC"
            
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting withdrawal requests: {e}")
        return []

async def process_withdrawal(withdrawal_id: int, admin_id: int, approved: bool, notes: str = "") -> bool:
    """Process a withdrawal request (approve or reject)."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            async with conn.execute("""
                SELECT user_id, amount, status FROM withdrawal_requests WHERE id = ?
            """, (withdrawal_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[2] != 'pending':
                    return False
                
                user_id, amount = row[0], row[1]
            
            await conn.execute("BEGIN")
            try:
                if approved:
                    wallet = await get_or_create_wallet(user_id)
                    if wallet["balance"] < amount:
                        await conn.rollback()
                        return False
                    
                    await conn.execute("""
                        UPDATE wallets 
                        SET balance = balance - ?, last_updated = datetime('now')
                        WHERE user_id = ?
                    """, (amount, user_id))
                    
                    status = 'approved'
                else:
                    status = 'rejected'
                
                await conn.execute("""
                    UPDATE withdrawal_requests 
                    SET status = ?, processed_at = datetime('now'), processed_by = ?, notes = ?
                    WHERE id = ?
                """, (status, admin_id, notes, withdrawal_id))
                
                await conn.commit()
                return True
            except:
                await conn.rollback()
                raise
    except Exception as e:
        logger.error(f"Error processing withdrawal {withdrawal_id}: {e}")
        return False

async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top referrers by total earned (weekly leaderboard)."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("""
                SELECT w.user_id, u.username, w.total_earned
                FROM wallets w
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE w.total_earned > 0
                ORDER BY w.total_earned DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return []
