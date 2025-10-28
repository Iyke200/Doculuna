import logging
from aiogram import Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import MINIMUM_WITHDRAWAL_AMOUNT, ADMIN_USER_IDS
from database.db import (
    get_or_create_wallet,
    create_withdrawal_request,
    get_withdrawal_requests,
    get_referral_stats,
    create_referral_code,
    get_leaderboard
)
from utils.wallet_utils import format_wallet_message, get_referral_link
from utils.wallet_keyboards import get_wallet_keyboard, get_cancel_keyboard, get_withdrawal_admin_keyboard

logger = logging.getLogger(__name__)

class WithdrawalStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_account_name = State()
    waiting_for_bank_name = State()
    waiting_for_account_number = State()

async def wallet_command(message: types.Message):
    """Show wallet information."""
    try:
        user_id = message.from_user.id
        wallet_message = await format_wallet_message(user_id)
        keyboard = get_wallet_keyboard()
        
        await message.answer(wallet_message, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error showing wallet for user {message.from_user.id}: {e}")
        await message.answer("❌ Error loading wallet. Please try again later.")

async def wallet_callback(callback: types.CallbackQuery):
    """Handle wallet button callback."""
    try:
        user_id = callback.from_user.id
        wallet_message = await format_wallet_message(user_id)
        keyboard = get_wallet_keyboard()
        
        await callback.message.edit_text(wallet_message, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing wallet for user {callback.from_user.id}: {e}")
        await callback.answer("❌ Error loading wallet", show_alert=True)

async def withdraw_callback(callback: types.CallbackQuery, state: FSMContext):
    """Start withdrawal process."""
    try:
        user_id = callback.from_user.id
        wallet = await get_or_create_wallet(user_id)
        
        if wallet["balance"] < MINIMUM_WITHDRAWAL_AMOUNT:
            await callback.answer(
                f"❌ Minimum withdrawal amount is ₦{MINIMUM_WITHDRAWAL_AMOUNT:,}. Your balance: ₦{wallet['balance']:,}",
                show_alert=True
            )
            return
        
        pending = await get_withdrawal_requests(user_id=user_id, status="pending")
        if pending:
            await callback.answer(
                "❌ You already have a pending withdrawal request. Please wait for it to be processed.",
                show_alert=True
            )
            return
        
        await callback.message.edit_text(
            f"💰 <b>Withdrawal Request</b>\n\n"
            f"Available Balance: ₦{wallet['balance']:,}\n"
            f"Minimum Withdrawal: ₦{MINIMUM_WITHDRAWAL_AMOUNT:,}\n\n"
            f"Please enter the amount you want to withdraw:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(WithdrawalStates.waiting_for_amount)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error starting withdrawal for user {callback.from_user.id}: {e}")
        await callback.answer("❌ Error starting withdrawal", show_alert=True)

async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    """Process withdrawal amount input."""
    try:
        try:
            amount = int(message.text.strip().replace(",", "").replace("₦", ""))
        except ValueError:
            await message.answer("❌ Invalid amount. Please enter a valid number.")
            return
        
        wallet = await get_or_create_wallet(message.from_user.id)
        
        if amount < MINIMUM_WITHDRAWAL_AMOUNT:
            await message.answer(f"❌ Minimum withdrawal amount is ₦{MINIMUM_WITHDRAWAL_AMOUNT:,}")
            return
        
        if amount > wallet["balance"]:
            await message.answer(
                f"❌ Insufficient balance. Your balance: ₦{wallet['balance']:,}"
            )
            return
        
        await state.update_data(amount=amount)
        await message.answer(
            f"✅ Amount: ₦{amount:,}\n\n"
            f"Please enter your account name:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(WithdrawalStates.waiting_for_account_name)
    except Exception as e:
        logger.error(f"Error processing withdrawal amount for user {message.from_user.id}: {e}")
        await message.answer("❌ Error processing amount. Please try again.")

async def process_account_name(message: types.Message, state: FSMContext):
    """Process account name input."""
    try:
        account_name = message.text.strip()
        if len(account_name) < 3:
            await message.answer("❌ Please enter a valid account name.")
            return
        
        await state.update_data(account_name=account_name)
        await message.answer(
            f"✅ Account Name: {account_name}\n\n"
            f"Please enter your bank name:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(WithdrawalStates.waiting_for_bank_name)
    except Exception as e:
        logger.error(f"Error processing account name for user {message.from_user.id}: {e}")
        await message.answer("❌ Error processing account name. Please try again.")

async def process_bank_name(message: types.Message, state: FSMContext):
    """Process bank name input."""
    try:
        bank_name = message.text.strip()
        if len(bank_name) < 3:
            await message.answer("❌ Please enter a valid bank name.")
            return
        
        await state.update_data(bank_name=bank_name)
        await message.answer(
            f"✅ Bank: {bank_name}\n\n"
            f"Please enter your account number:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(WithdrawalStates.waiting_for_account_number)
    except Exception as e:
        logger.error(f"Error processing bank name for user {message.from_user.id}: {e}")
        await message.answer("❌ Error processing bank name. Please try again.")

async def process_account_number(message: types.Message, state: FSMContext, bot):
    """Process account number and create withdrawal request."""
    try:
        account_number = message.text.strip().replace(" ", "")
        if not account_number.isdigit() or len(account_number) < 10:
            await message.answer("❌ Please enter a valid account number (at least 10 digits).")
            return
        
        data = await state.get_data()
        user_id = message.from_user.id
        username = message.from_user.username or f"User{user_id}"
        
        withdrawal_id = await create_withdrawal_request(
            user_id=user_id,
            amount=data["amount"],
            account_name=data["account_name"],
            bank_name=data["bank_name"],
            account_number=account_number
        )
        
        if not withdrawal_id:
            await message.answer("❌ Failed to create withdrawal request. Please try again later.")
            await state.clear()
            return
        
        await message.answer(
            "✅ <b>Withdrawal Request Submitted</b>\n\n"
            f"Amount: ₦{data['amount']:,}\n"
            f"Account Name: {data['account_name']}\n"
            f"Bank: {data['bank_name']}\n"
            f"Account Number: {account_number}\n\n"
            "Your request is pending admin review. You'll be notified once it's processed."
        )
        
        for admin_id in ADMIN_USER_IDS:
            try:
                admin_message = (
                    "💸 <b>New Withdrawal Request</b>\n\n"
                    f"User: @{username} (ID: {user_id})\n"
                    f"Amount: ₦{data['amount']:,}\n"
                    f"Account Name: {data['account_name']}\n"
                    f"Bank: {data['bank_name']}\n"
                    f"Account Number: {account_number}\n"
                    f"Request ID: {withdrawal_id}"
                )
                keyboard = get_withdrawal_admin_keyboard(withdrawal_id)
                await bot.send_message(admin_id, admin_message, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await state.clear()
    except Exception as e:
        logger.error(f"Error processing account number for user {message.from_user.id}: {e}")
        await message.answer("❌ Error creating withdrawal request. Please try again.")
        await state.clear()

async def cancel_withdrawal(callback: types.CallbackQuery, state: FSMContext):
    """Cancel withdrawal process."""
    await state.clear()
    await callback.message.edit_text("❌ Withdrawal cancelled.")
    await callback.answer()

async def referral_stats_callback(callback: types.CallbackQuery, bot):
    """Show referral statistics."""
    try:
        user_id = callback.from_user.id
        stats = await get_referral_stats(user_id)
        referral_code = await create_referral_code(user_id)
        bot_info = await bot.get_me()
        referral_link = await get_referral_link(user_id, bot_info.username)
        
        message = (
            "👥 <b>Referral Summary</b>\n\n"
            f"Total Referrals: {stats['total_referrals']}\n"
            f"Completed Referrals: {stats['completed']}\n"
            f"Pending Referrals: {stats['pending']}\n\n"
            f"💸 Total Earned from Referrals: ₦{stats['total_earned']:,}\n\n"
            f"🔗 Your Referral Link:\n<code>{referral_link}</code>\n\n"
            f"Share this link and earn:\n"
            f"• Weekly Plan → ₦150\n"
            f"• Monthly Plan → ₦350"
        )
        
        await callback.message.edit_text(message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing referral stats for user {callback.from_user.id}: {e}")
        await callback.answer("❌ Error loading referral stats", show_alert=True)

async def withdrawal_history_callback(callback: types.CallbackQuery):
    """Show withdrawal history."""
    try:
        user_id = callback.from_user.id
        withdrawals = await get_withdrawal_requests(user_id=user_id)
        
        if not withdrawals:
            await callback.message.edit_text("📜 <b>Your Withdrawal History</b>\n\nYou have no past withdrawals yet.")
            await callback.answer()
            return
        
        message = "📜 <b>Your Withdrawal History</b>\n\n"
        for i, w in enumerate(withdrawals[:10], 1):
            status_emoji = "⏳" if w["status"] == "pending" else "✅" if w["status"] == "approved" else "❌"
            message += f"{i}. ₦{w['amount']:,} - {status_emoji} {w['status'].title()}\n"
        
        await callback.message.edit_text(message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing withdrawal history for user {callback.from_user.id}: {e}")
        await callback.answer("❌ Error loading history", show_alert=True)

async def leaderboard_callback(callback: types.CallbackQuery):
    """Show referral leaderboard."""
    try:
        leaderboard = await get_leaderboard(limit=10)
        
        if not leaderboard:
            await callback.message.edit_text("🏆 <b>Weekly Referral Leaderboard</b>\n\nNo data yet. Be the first to earn!")
            await callback.answer()
            return
        
        message = "🏆 <b>Weekly Referral Leaderboard</b>\n\n"
        medals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, user in enumerate(leaderboard):
            username = user.get("username", f"User{user['user_id']}")
            earned = user.get("total_earned", 0)
            medal = medals[i] if i < len(medals) else f"{i+1}."
            message += f"{medal} @{username} — ₦{earned:,}\n"
        
        message += "\n🔥 Keep referring to reach the top!"
        
        await callback.message.edit_text(message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing leaderboard: {e}")
        await callback.answer("❌ Error loading leaderboard", show_alert=True)

def register_wallet_handlers(dp: Dispatcher):
    """Register wallet-related handlers."""
    from functools import partial
    
    dp.message.register(wallet_command, Command("wallet"))
    dp.callback_query.register(wallet_callback, F.data == "wallet")
    dp.callback_query.register(withdraw_callback, F.data == "withdraw")
    dp.callback_query.register(cancel_withdrawal, F.data == "cancel_withdrawal")
    dp.callback_query.register(referral_stats_callback, F.data == "ref_stats")
    dp.callback_query.register(withdrawal_history_callback, F.data == "withdraw_history")
    dp.callback_query.register(leaderboard_callback, F.data == "leaderboard")
    
    dp.message.register(process_withdrawal_amount, WithdrawalStates.waiting_for_amount)
    dp.message.register(process_account_name, WithdrawalStates.waiting_for_account_name)
    dp.message.register(process_bank_name, WithdrawalStates.waiting_for_bank_name)
    dp.message.register(process_account_number, WithdrawalStates.waiting_for_account_number)
    
    logger.info("Wallet handlers registered")
