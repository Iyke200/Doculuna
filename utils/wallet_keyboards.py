from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_wallet_keyboard() -> InlineKeyboardMarkup:
    """Get wallet main menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="📊 Referral Stats", callback_data="ref_stats")],
        [
            InlineKeyboardButton(text="📜 Withdrawal History", callback_data="withdraw_history"),
            InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")
        ]
    ])
    return keyboard

def get_withdrawal_admin_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    """Get admin approval/rejection keyboard for withdrawal requests."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{withdrawal_id}")
        ]
    ])
    return keyboard

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Get cancel keyboard for FSM flows."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_withdrawal")]
    ])
    return keyboard
