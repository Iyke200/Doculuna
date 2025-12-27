import logging
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import PREMIUM_PLANS, MANUAL_PAYMENT_DETAILS, ADMIN_USER_IDS
from database.db import DATABASE_PATH
import aiosqlite
import os

logger = logging.getLogger(__name__)
router = Router()

class PaymentStates(StatesGroup):
    selecting_plan = State()
    selecting_method = State()
    awaiting_proof = State()
    awaiting_name = State()
    awaiting_amount = State()
    awaiting_txid = State()

@router.callback_query(F.data == "upgrade")
async def show_plans(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{v['name']} - ₦{v['price']}", callback_data=f"plan_{k}")]
        for k, v in PREMIUM_PLANS.items()
    ])
    await callback.message.edit_text("Select a Premium Plan:", reply_markup=keyboard)
    await state.set_state(PaymentStates.selecting_plan)

@router.callback_query(F.data.startswith("plan_"))
async def select_method(callback: CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]
    await state.update_data(plan=plan)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="OPay", callback_data="method_opay")],
        [InlineKeyboardButton(text="PalmPay", callback_data="method_palmpay")],
        [InlineKeyboardButton(text="USDT (TRC20)", callback_data="method_usdt_trc20")]
    ])
    await callback.message.edit_text("Select Payment Method:", reply_markup=keyboard)
    await state.set_state(PaymentStates.selecting_method)

@router.callback_query(F.data.startswith("method_"))
async def show_details(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2] if "trc20" in callback.data else callback.data.split("_")[1]
    await state.update_data(method=method)
    details = MANUAL_PAYMENT_DETAILS.get(method)
    
    text = f"💳 *Payment Details*\n\n"
    if "address" in details:
        text += f"Address: `{details['address']}`\nNetwork: {details['network']}"
    else:
        text += f"Bank: {details['bank']}\nAccount: `{details['account']}`\nName: {details['name']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have Paid", callback_data="paid")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "paid")
async def ask_proof(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Please upload a screenshot of your payment:")
    await state.set_state(PaymentStates.awaiting_proof)

@router.message(PaymentStates.awaiting_proof, F.photo)
async def process_proof(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_path = f"payments/{message.from_user.id}_{photo.file_id}.jpg"
    await message.bot.download(photo, destination=file_path)
    await state.update_data(screenshot=file_path)
    await message.answer("Enter the name used for payment:")
    await state.set_state(PaymentStates.awaiting_name)

@router.message(PaymentStates.awaiting_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Enter the amount paid:")
    await state.set_state(PaymentStates.awaiting_amount)

@router.message(PaymentStates.awaiting_amount)
async def process_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(amount=message.text)
    if data['method'] == 'usdt_trc20':
        await message.answer("Enter USDT Transaction ID (TxID):")
        await state.set_state(PaymentStates.awaiting_txid)
    else:
        await submit_payment(message, state)

@router.message(PaymentStates.awaiting_txid)
async def process_txid(message: Message, state: FSMContext):
    await state.update_data(txid=message.text)
    await submit_payment(message, state)

async def submit_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO manual_payments (user_id, amount, plan_type, payment_method, payer_name, tx_id, screenshot_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message.from_user.id, data['amount'], data['plan'], data['method'], data['name'], data.get('txid'), data['screenshot'])
        )
        payment_id = cursor.lastrowid
        await db.commit()

    await message.answer("✅ Payment submitted! Waiting for admin approval.")
    
    # Notify Admin
    admin_text = f"🆕 *New Payment Request*\n\nUser: {message.from_user.id}\nPlan: {data['plan']}\nMethod: {data['method']}\nName: {data['name']}\nAmount: {data['amount']}"
    if 'txid' in data: admin_text += f"\nTxID: `{data['txid']}`"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Approve", callback_data=f"approve_{payment_id}_{message.from_user.id}"),
         InlineKeyboardButton(text="Reject", callback_data=f"reject_{payment_id}_{message.from_user.id}")]
    ])
    
    for admin_id in ADMIN_USER_IDS:
        try:
            await message.bot.send_photo(admin_id, photo=FSInputFile(data['screenshot']), caption=admin_text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await state.clear()

@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    _, pid, uid = callback.data.split("_")
    # Logic to update user status and payment status in DB would go here
    # For now, just a placeholder as requested "manual flow"
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ APPROVED")
    await callback.bot.send_message(uid, "🌟 Your payment has been approved! Premium features are now active.")

@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    _, pid, uid = callback.data.split("_")
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ REJECTED")
    await callback.bot.send_message(uid, "❌ Your payment was rejected. Please contact support.")

def register_manual_payment_handlers(dp):
    dp.include_router(router)
