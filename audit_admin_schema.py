import aiosqlite
import asyncio
from config import DB_PATH

async def audit_database():
    """Comprehensive database schema audit for admin panel"""
    async with aiosqlite.connect(DB_PATH) as conn:
        print("=" * 60)
        print("DATABASE SCHEMA AUDIT FOR ADMIN PANEL")
        print("=" * 60)
        
        # Check all tables
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = await cursor.fetchall()
        print(f"\n✓ Tables found: {[t[0] for t in tables]}\n")
        
        # 1. Check users table
        print("=" * 60)
        print("1. USERS TABLE")
        print("=" * 60)
        cursor = await conn.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        user_columns = [col[1] for col in columns]
        print(f"Columns: {user_columns}")
        
        required_users_cols = ['user_id', 'username', 'first_name', 'is_premium', 'created_at', 'last_active']
        missing_users = [col for col in required_users_cols if col not in user_columns]
        if missing_users:
            print(f"⚠️  MISSING: {missing_users}")
        else:
            print("✓ All required columns present")
        
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        count = await cursor.fetchone()
        print(f"Total users: {count[0]}")
        
        # 2. Check usage_logs table
        print("\n" + "=" * 60)
        print("2. USAGE_LOGS TABLE")
        print("=" * 60)
        cursor = await conn.execute("PRAGMA table_info(usage_logs)")
        columns = await cursor.fetchall()
        usage_columns = [col[1] for col in columns]
        print(f"Columns: {usage_columns}")
        
        required_usage_cols = ['user_id', 'tool', 'timestamp', 'is_success']
        missing_usage = [col for col in required_usage_cols if col not in usage_columns]
        if missing_usage:
            print(f"⚠️  MISSING: {missing_usage}")
        else:
            print("✓ All required columns present")
        
        cursor = await conn.execute("SELECT COUNT(*) FROM usage_logs")
        count = await cursor.fetchone()
        print(f"Total usage logs: {count[0]}")
        
        # 3. Check payment_logs table
        print("\n" + "=" * 60)
        print("3. PAYMENT_LOGS TABLE")
        print("=" * 60)
        try:
            cursor = await conn.execute("PRAGMA table_info(payment_logs)")
            columns = await cursor.fetchall()
            payment_columns = [col[1] for col in columns]
            print(f"Columns: {payment_columns}")
            
            required_payment_cols = ['user_id', 'amount', 'timestamp', 'status', 'plan_type']
            missing_payment = [col for col in required_payment_cols if col not in payment_columns]
            if missing_payment:
                print(f"⚠️  MISSING: {missing_payment}")
            else:
                print("✓ All required columns present")
            
            cursor = await conn.execute("SELECT COUNT(*) FROM payment_logs")
            count = await cursor.fetchone()
            print(f"Total payment logs: {count[0]}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        # 4. Test admin panel queries
        print("\n" + "=" * 60)
        print("4. TESTING ADMIN PANEL QUERIES")
        print("=" * 60)
        
        # Query 1: Total users
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            result = await cursor.fetchone()
            print(f"✓ Total users query: {result[0]}")
        except Exception as e:
            print(f"❌ Total users query failed: {e}")
        
        # Query 2: Premium users
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
            result = await cursor.fetchone()
            print(f"✓ Premium users query: {result[0]}")
        except Exception as e:
            print(f"❌ Premium users query failed: {e}")
        
        # Query 3: Active today (from usage_logs)
        try:
            cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) = date('now')")
            result = await cursor.fetchone()
            print(f"✓ Active today query: {result[0]}")
        except Exception as e:
            print(f"❌ Active today query failed: {e}")
        
        # Query 4: New this week
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-7 days')")
            result = await cursor.fetchone()
            print(f"✓ New this week query: {result[0]}")
        except Exception as e:
            print(f"❌ New this week query failed: {e}")
        
        # Query 5: Files processed today
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM usage_logs WHERE date(timestamp) = date('now') AND is_success = 1")
            result = await cursor.fetchone()
            print(f"✓ Files processed today: {result[0]}")
        except Exception as e:
            print(f"❌ Files processed query failed: {e}")
        
        # Query 6: Revenue 24h
        try:
            cursor = await conn.execute("SELECT SUM(amount) FROM payment_logs WHERE date(timestamp) >= date('now', '-1 day')")
            result = await cursor.fetchone()
            print(f"✓ Revenue 24h query: {result[0] or 0}")
        except Exception as e:
            print(f"❌ Revenue query failed: {e}")
        
        # Query 7: Active 7 days
        try:
            cursor = await conn.execute("SELECT COUNT(DISTINCT user_id) FROM usage_logs WHERE date(timestamp) >= date('now', '-7 days')")
            result = await cursor.fetchone()
            print(f"✓ Active 7 days query: {result[0]}")
        except Exception as e:
            print(f"❌ Active 7 days query failed: {e}")
        
        # Query 8: Inactive 30 days
        try:
            cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE last_active < date('now', '-30 days')")
            result = await cursor.fetchone()
            print(f"✓ Inactive 30 days query: {result[0]}")
        except Exception as e:
            print(f"❌ Inactive 30 days query failed: {e}")
        
        print("\n" + "=" * 60)
        print("AUDIT COMPLETE")
        print("=" * 60)

asyncio.run(audit_database())
