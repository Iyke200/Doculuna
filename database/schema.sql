-- schema.sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_premium INTEGER DEFAULT 0,
    premium_expiry DATETIME
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tool TEXT,
    timestamp DATETIME,
    is_success INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    referral_code TEXT UNIQUE,
    referral_count INTEGER DEFAULT 0,
    premium_days_earned INTEGER DEFAULT 0,
    total_earnings INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    feedback TEXT,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS payment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    payment_method TEXT,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS referral_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    plan_type TEXT,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS premium_expiry_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    warning_sent DATETIME,
    expiry_date DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
