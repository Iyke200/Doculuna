
import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

DB_FILE = "database/doculuna.db"

def init_db():
    """Initialize the database with required tables."""
    try:
        os.makedirs("database", exist_ok=True)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_premium BOOLEAN DEFAULT FALSE,
                premium_expires TIMESTAMP,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                last_usage TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tool_used TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Payments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_type TEXT,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                screenshot_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_user(user_id):
    """Get user from database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'is_premium': bool(result[4]),
                'premium_expires': result[5],
                'referred_by': result[6],
                'referral_count': result[7],
                'usage_count': result[8],
                'last_usage': result[9],
                'created_at': result[10]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

def create_user(user_id, username=None, first_name=None, last_name=None, referred_by=None):
    """Create a new user in the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, referred_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, referred_by))
        
        conn.commit()
        conn.close()
        logger.info(f"User {user_id} created successfully")
        
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")

def add_user(user_id, username=None, first_name=None, last_name=None, referred_by=None):
    """Alias for create_user function."""
    return create_user(user_id, username, first_name, last_name, referred_by)

def get_all_users():
    """Get all users from database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users")
        results = cursor.fetchall()
        
        conn.close()
        
        users = []
        for result in results:
            users.append({
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'is_premium': bool(result[4]),
                'premium_expires': result[5],
                'referred_by': result[6],
                'referral_count': result[7],
                'usage_count': result[8],
                'last_usage': result[9],
                'created_at': result[10]
            })
        
        return users
        
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

def get_pending_payments():
    """Get all pending payments."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, u.first_name, u.username 
            FROM payments p 
            JOIN users u ON p.user_id = u.user_id 
            WHERE p.status = 'pending'
            ORDER BY p.created_at DESC
        ''')
        results = cursor.fetchall()
        
        conn.close()
        
        payments = []
        for result in results:
            payments.append({
                'id': result[0],
                'user_id': result[1],
                'plan_type': result[2],
                'amount': result[3],
                'status': result[4],
                'screenshot_file_id': result[5],
                'created_at': result[6],
                'processed_at': result[7],
                'first_name': result[8],
                'username': result[9]
            })
        
        return payments
        
    except Exception as e:
        logger.error(f"Error getting pending payments: {e}")
        return []

def update_user_premium(user_id, is_premium, expires_at=None):
    """Update user premium status."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET is_premium = ?, premium_expires = ?
            WHERE user_id = ?
        ''', (is_premium, expires_at, user_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Updated premium status for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error updating premium status for user {user_id}: {e}")

def increment_user_usage(user_id):
    """Increment user's usage count."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE users 
            SET usage_count = usage_count + 1, last_usage = ?
            WHERE user_id = ?
        ''', (current_time, user_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error incrementing usage for user {user_id}: {e}")

def get_user_by_username(username):
    """Get user by username."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'is_premium': bool(result[4]),
                'premium_expires': result[5],
                'referred_by': result[6],
                'referral_count': result[7],
                'usage_count': result[8],
                'last_usage': result[9],
                'created_at': result[10]
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting user by username {username}: {e}")
        return None

def get_referral_stats(user_id):
    """Get referral statistics for a user."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return result[0] or 0
        return 0
        
    except Exception as e:
        logger.error(f"Error getting referral stats for user {user_id}: {e}")
        return 0
