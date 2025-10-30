# referrals.py - Complete referral and withdrawal system
import logging
from typing import Optional
from datetime import datetime
from aiogram import Dispatcher, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_user_data, update_user_data
from config import MINIMUM_WITHDRAWAL_AMOUNT, PREMIUM_PLANS, ADMIN_USER_IDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFERRAL_CONFIG = {
    'reward_referrer_monthly': {'value': 500},
    'reward_referrer_weekly': {'value': 150}
}

class WithdrawalStates(StatesGroup):
    waiting_for_account_name = State()
    waiting_for_account_number = State()
    waiting_for_bank_name = State()
    confirming_details = State()

async def refer_command_handler(message: types.Message, state: FSMContext) -> None:
    """Handle /refer command - shows referral info and earnings."""
    user_id = message.from_user.id
    
    try:
        bot = message.bot
        bot_info = await bot.get_me()
        bot_username = bot_info.username or "DocuLuna_OfficialBot"
        
        user_data = await get_user_data(user_id)
        referral_earnings = user_data.get('referral_earnings', 0) if user_data else 0
        referral_count = user_data.get('referral_count', 0) if user_data else 0
        
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        monthly_reward = REFERRAL_CONFIG['reward_referrer_monthly']['value']
        weekly_reward = REFERRAL_CONFIG['reward_referrer_weekly']['value']
        
        referral_text = (
            "🎁 *DocuLuna Referral Program*\n\n"
            f"👥 Total Referrals: {referral_count}\n"
            f"💰 Total Earnings: ₦{referral_earnings:,}\n\n"
            "📊 *Earn When Your Referrals Upgrade:*\n"
            f"• ₦{monthly_reward} per Monthly Premium signup\n"
            f"• ₦{weekly_reward} per Weekly Premium signup\n\n"
            f"🔗 *Your Referral Link:*\n`{referral_link}`\n\n"
            f"💸 *Minimum Withdrawal:* ₦{MINIMUM_WITHDRAWAL_AMOUNT:,}\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Withdraw Earnings", callback_data="withdraw_earnings")
        builder.button(text="💳 Use for Premium", callback_data="use_for_premium")
        builder.button(text="📊 View Details", callback_data="referral_details")
        builder.button(text="⬅️ Back", callback_data="back_to_menu")
        builder.adjust(2, 1, 1)
        
        await message.reply(referral_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in refer command: {e}", exc_info=True)
        await message.reply("Error generating referral info. Please try again later.")

async def referral_details_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Show detailed referral statistics."""
    user_id = callback.from_user.id
    
    try:
        user_data = await get_user_data(user_id)
        referral_earnings = user_data.get('referral_earnings', 0) if user_data else 0
        referral_count = user_data.get('referral_count', 0) if user_data else 0
        
        import aiosqlite
        from config import DB_PATH
        
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM withdrawal_requests WHERE user_id = ? AND status = 'completed'",
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                total_withdrawn = result[0] if result else 0
            
            async with conn.execute(
                "SELECT SUM(amount) FROM withdrawal_requests WHERE user_id = ? AND status = 'completed'",
                (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                total_withdrawn_amount = result[0] if result and result[0] else 0
        
        details_text = (
            "📊 *Your Referral Statistics*\n\n"
            f"👥 Total Referrals: {referral_count}\n"
            f"💰 Current Balance: ₦{referral_earnings:,}\n"
            f"✅ Total Withdrawn: ₦{total_withdrawn_amount:,}\n"
            f"📤 Withdrawals Made: {total_withdrawn}\n\n"
            f"🎯 Keep sharing to earn more!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Withdraw", callback_data="withdraw_earnings")
        builder.button(text="⬅️ Back", callback_data="back_to_refer")
        builder.adjust(1)
        
        await callback.message.edit_text(details_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing referral details: {e}", exc_info=True)
        await callback.answer("Error loading details", show_alert=True)

async def withdraw_earnings_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Handle withdrawal request initiation."""
    user_id = callback.from_user.id
    
    try:
        user_data = await get_user_data(user_id)
        referral_earnings = user_data.get('referral_earnings', 0) if user_data else 0
        
        if referral_earnings < MINIMUM_WITHDRAWAL_AMOUNT:
            insufficient_text = (
                f"⚠️ *Insufficient Balance*\n\n"
                f"Current Balance: ₦{referral_earnings:,}\n"
                f"Minimum Withdrawal: ₦{MINIMUM_WITHDRAWAL_AMOUNT:,}\n"
                f"Needed: ₦{MINIMUM_WITHDRAWAL_AMOUNT - referral_earnings:,}\n\n"
                f"💡 You can use your balance to buy premium!\n"
                f"Your balance will be deducted from the premium price."
            )
            
            builder = InlineKeyboardBuilder()
            builder.button(text="💳 Buy Premium with Balance", callback_data="use_for_premium")
            builder.button(text="⬅️ Back", callback_data="back_to_refer")
            builder.adjust(1)
            
            await callback.message.edit_text(insufficient_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
            await callback.answer()
            return
        
        withdrawal_text = (
            f"💰 *Withdrawal Request*\n\n"
            f"Available Balance: ₦{referral_earnings:,}\n\n"
            f"Please enter your *account name* (as it appears on your bank account):"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Cancel", callback_data="back_to_refer")
        builder.adjust(1)
        
        await callback.message.edit_text(withdrawal_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await state.set_state(WithdrawalStates.waiting_for_account_name)
        await state.update_data(amount=referral_earnings)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error initiating withdrawal: {e}", exc_info=True)
        await callback.answer("Error processing request", show_alert=True)

async def account_name_handler(message: types.Message, state: FSMContext) -> None:
    """Handle account name input."""
    account_name = message.text.strip()
    
    if len(account_name) < 3:
        await message.reply("Please enter a valid account name (at least 3 characters).")
        return
    
    await state.update_data(account_name=account_name)
    await message.reply(
        "✅ Account name saved.\n\n"
        "Please enter your *account number*:",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawalStates.waiting_for_account_number)

async def account_number_handler(message: types.Message, state: FSMContext) -> None:
    """Handle account number input."""
    account_number = message.text.strip()
    
    if not account_number.isdigit() or len(account_number) < 10:
        await message.reply("Please enter a valid account number (10 digits).")
        return
    
    await state.update_data(account_number=account_number)
    await message.reply(
        "✅ Account number saved.\n\n"
        "Please enter your *bank name*:",
        parse_mode="Markdown"
    )
    await state.set_state(WithdrawalStates.waiting_for_bank_name)

async def bank_name_handler(message: types.Message, state: FSMContext) -> None:
    """Handle bank name input and show confirmation."""
    bank_name = message.text.strip()
    
    if len(bank_name) < 3:
        await message.reply("Please enter a valid bank name.")
        return
    
    await state.update_data(bank_name=bank_name)
    
    data = await state.get_data()
    account_name = data.get('account_name')
    account_number = data.get('account_number')
    amount = data.get('amount', 0)
    
    confirmation_text = (
        "📋 *Please confirm your withdrawal details:*\n\n"
        f"💰 Amount: ₦{amount:,}\n"
        f"👤 Account Name: {account_name}\n"
        f"🏦 Account Number: {account_number}\n"
        f"🏛 Bank: {bank_name}\n\n"
        "⚠️ Please verify these details carefully."
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm & Submit", callback_data="confirm_withdrawal")
    builder.button(text="❌ Cancel", callback_data="cancel_withdrawal")
    builder.adjust(1)
    
    await message.reply(confirmation_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(WithdrawalStates.confirming_details)

async def confirm_withdrawal_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Submit withdrawal request to admin for approval."""
    user_id = callback.from_user.id
    
    try:
        data = await state.get_data()
        amount = data.get('amount', 0)
        account_name = data.get('account_name')
        account_number = data.get('account_number')
        bank_name = data.get('bank_name')
        
        import aiosqlite
        from config import DB_PATH
        
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute("""
                INSERT INTO withdrawal_requests 
                (user_id, amount, account_name, account_number, bank_name, status, requested_at)
                VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))
            """, (user_id, amount, account_name, account_number, bank_name))
            
            request_id = cursor.lastrowid
            
            await update_user_data(user_id, {'referral_earnings': 0})
            
            await conn.commit()
        
        success_text = (
            "✅ *Withdrawal Request Submitted*\n\n"
            f"Request ID: #{request_id}\n"
            f"Amount: ₦{amount:,}\n\n"
            "Your request has been sent to the admin for processing.\n"
            "You will be notified once it's approved.\n\n"
            "⏱ Processing Time: 1-3 business days"
        )
        
        await callback.message.edit_text(success_text, parse_mode="Markdown")
        
        admin_notification = (
            "🔔 *New Withdrawal Request*\n\n"
            f"Request ID: #{request_id}\n"
            f"User ID: {user_id}\n"
            f"Username: @{callback.from_user.username or 'N/A'}\n"
            f"Amount: ₦{amount:,}\n"
            f"Account Name: {account_name}\n"
            f"Account Number: {account_number}\n"
            f"Bank: {bank_name}\n\n"
            f"Use /admin to review pending requests."
        )
        
        for admin_id in ADMIN_USER_IDS:
            try:
                await callback.bot.send_message(admin_id, admin_notification, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await state.clear()
        await callback.answer("Request submitted!")
        
    except Exception as e:
        logger.error(f"Error confirming withdrawal: {e}", exc_info=True)
        await callback.answer("Error submitting request", show_alert=True)

async def cancel_withdrawal_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel withdrawal request."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Withdrawal request cancelled.\n\n"
        "Use /refer to try again.",
        parse_mode="Markdown"
    )
    await callback.answer("Cancelled")

async def use_for_premium_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Allow user to use referral balance towards premium purchase."""
    user_id = callback.from_user.id
    
    try:
        user_data = await get_user_data(user_id)
        referral_earnings = user_data.get('referral_earnings', 0) if user_data else 0
        
        premium_text = (
            f"💳 *Buy Premium with Referral Balance*\n\n"
            f"Your Balance: ₦{referral_earnings:,}\n\n"
            f"*Available Plans:*\n"
        )
        
        builder = InlineKeyboardBuilder()
        
        for plan_key, plan_info in PREMIUM_PLANS.items():
            price = plan_info['price']
            name = plan_info['name']
            final_price = max(0, price - referral_earnings)
            
            if referral_earnings >= price:
                button_text = f"✅ {name} (FREE with balance!)"
            else:
                button_text = f"💎 {name} (Pay ₦{final_price:,})"
            
            premium_text += f"\n• {name}: ₦{price:,}"
            if referral_earnings > 0:
                premium_text += f" → ₦{final_price:,} after balance"
            
            builder.button(text=button_text, callback_data=f"premium_with_balance_{plan_key}")
        
        premium_text += "\n\n💡 Your balance will be automatically applied!"
        
        builder.button(text="⬅️ Back", callback_data="back_to_refer")
        builder.adjust(1)
        
        await callback.message.edit_text(premium_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing premium options: {e}", exc_info=True)
        await callback.answer("Error loading options", show_alert=True)

async def back_to_refer_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Go back to referral menu."""
    await state.clear()
    await refer_command_handler(callback.message, state)
    await callback.answer()

async def record_referral_use(referrer_id: int, new_user_id: int) -> bool:
    """Record when a referral is used."""
    try:
        new_user_data = await get_user_data(new_user_id)
        if new_user_data and new_user_data.get('referrer_id'):
            logger.info(f"Referral ignored (already claimed): referrer={referrer_id}, new_user={new_user_id}")
            return False
        
        if new_user_data:
            await update_user_data(new_user_id, {'referrer_id': referrer_id})
        else:
            await update_user_data(new_user_id, {'referrer_id': referrer_id})
        
        referrer_data = await get_user_data(referrer_id)
        if referrer_data:
            current_referrals = referrer_data.get('referral_count', 0)
            await update_user_data(referrer_id, {'referral_count': current_referrals + 1})
            logger.info(f"Referral recorded: referrer={referrer_id}, new_user={new_user_id}")
            return True
        else:
            logger.warning(f"Referrer data not found: {referrer_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error recording referral: {e}", exc_info=True)
        return False

async def process_premium_conversion_reward(referrer_id: int, plan_type: str) -> bool:
    """Process reward for premium conversion via referral."""
    try:
        config_key = f'reward_referrer_{plan_type}'
        if config_key not in REFERRAL_CONFIG:
            logger.error(f"Invalid plan_type: {plan_type}")
            return False
            
        reward_amount = REFERRAL_CONFIG[config_key]['value']
        user_data = await get_user_data(referrer_id)
        if user_data:
            current_earnings = user_data.get('referral_earnings', 0)
            await update_user_data(referrer_id, {'referral_earnings': current_earnings + reward_amount})
            logger.info(f"Referral reward processed: referrer={referrer_id}, plan={plan_type}, reward={reward_amount}")
            return True
        else:
            logger.warning(f"Referrer data not found for reward: {referrer_id}")
            return False
    except Exception as e:
        logger.error(f"Error processing referral reward: {e}", exc_info=True)
        return False

def register_referral_handlers(dp: Dispatcher) -> None:
    """Register referral and withdrawal handlers."""
    dp.message.register(refer_command_handler, Command("refer"))
    
    dp.callback_query.register(referral_details_handler, lambda c: c.data == "referral_details")
    dp.callback_query.register(withdraw_earnings_handler, lambda c: c.data == "withdraw_earnings")
    dp.callback_query.register(use_for_premium_handler, lambda c: c.data == "use_for_premium")
    dp.callback_query.register(back_to_refer_handler, lambda c: c.data == "back_to_refer")
    
    dp.callback_query.register(confirm_withdrawal_handler, lambda c: c.data == "confirm_withdrawal")
    dp.callback_query.register(cancel_withdrawal_handler, lambda c: c.data == "cancel_withdrawal")
    
    dp.message.register(account_name_handler, WithdrawalStates.waiting_for_account_name)
    dp.message.register(account_number_handler, WithdrawalStates.waiting_for_account_number)
    dp.message.register(bank_name_handler, WithdrawalStates.waiting_for_bank_name)
