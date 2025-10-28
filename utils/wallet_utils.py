import logging
from typing import Optional
from database.db import (
    get_or_create_wallet,
    create_referral_code,
    get_referral_stats
)

logger = logging.getLogger(__name__)

async def get_wallet_info(user_id: int) -> dict:
    """Get complete wallet information for a user."""
    wallet = await get_or_create_wallet(user_id)
    referral_code = await create_referral_code(user_id)
    referral_stats = await get_referral_stats(user_id)
    
    return {
        "balance": wallet.get("balance", 0),
        "total_earned": wallet.get("total_earned", 0),
        "referral_code": referral_code,
        "total_referrals": referral_stats.get("total_referrals", 0),
        "completed_referrals": referral_stats.get("completed", 0),
        "pending_referrals": referral_stats.get("pending", 0),
        "referral_earnings": referral_stats.get("total_earned", 0)
    }

async def format_wallet_message(user_id: int) -> str:
    """Format wallet information into a display message."""
    wallet_info = await get_wallet_info(user_id)
    
    message = f"""💼 <b>Doculuna Wallet</b>

💰 Balance: ₦{wallet_info['balance']:,}
📊 Total Earned: ₦{wallet_info['total_earned']:,}

👥 Referrals: {wallet_info['total_referrals']}
🔗 Referral Code: <code>{wallet_info['referral_code']}</code>

Earn rewards by referring users to upgrade!
• Weekly Plan → ₦150 reward
• Monthly Plan → ₦350 reward"""
    
    return message

async def get_referral_link(user_id: int, bot_username: str) -> str:
    """Generate referral link for a user."""
    referral_code = await create_referral_code(user_id)
    return f"https://t.me/{bot_username}?start={referral_code}"
