import aiosqlite
import asyncio

async def check_users():
    async with aiosqlite.connect('database/doculuna.db') as conn:
        # Check table structure first
        cursor = await conn.execute('PRAGMA table_info(users)')
        columns = await cursor.fetchall()
        print('Users table columns:')
        for col in columns:
            print(f'  {col[1]} ({col[2]})')
        
        # Get users with available columns
        cursor = await conn.execute('SELECT * FROM users LIMIT 10')
        rows = await cursor.fetchall()
        print(f'\nTotal rows: {len(rows)}')
        if rows:
            print('First few users:')
            for r in rows:
                print(f'  {r}')
        
        # Count total users
        cursor = await conn.execute('SELECT COUNT(*) FROM users')
        count = await cursor.fetchone()
        print(f'\nTotal users in database: {count[0]}')

asyncio.run(check_users())
