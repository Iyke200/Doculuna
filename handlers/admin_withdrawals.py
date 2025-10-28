import logging
from aiogram import Dispatcher, types, F
from config import ADMIN_USER_IDS
from database.db import process_withdrawal, get_withdrawal_requests

logger = logging.getLogger(__name__)

async def approve_withdrawal(callback: types.CallbackQuery, bot):
    """Approve a withdrawal request."""
    try:
        if callback.from_user.id not in ADMIN_USER_IDS:
            await callback.answer("❌ Unauthorized", show_alert=True)
            return
        
        withdrawal_id = int(callback.data.split("_")[1])
        
        requests = await get_withdrawal_requests()
        withdrawal = next((w for w in requests if w["id"] == withdrawal_id), None)
        
        if not withdrawal:
            await callback.answer("❌ Withdrawal request not found", show_alert=True)
            return
        
        if withdrawal["status"] != "pending":
            await callback.answer(f"❌ Already {withdrawal['status']}", show_alert=True)
            return
        
        success = await process_withdrawal(
            withdrawal_id=withdrawal_id,
            admin_id=callback.from_user.id,
            approved=True,
            notes="Approved by admin"
        )
        
        if success:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n"
                f"✅ <b>APPROVED</b> by @{callback.from_user.username}"
            )
            
            try:
                await bot.send_message(
                    withdrawal["user_id"],
                    f"✅ <b>Withdrawal Approved</b>\n\n"
                    f"Your ₦{withdrawal['amount']:,} withdrawal has been approved and will be processed shortly."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {withdrawal['user_id']}: {e}")
            
            await callback.answer("✅ Withdrawal approved", show_alert=True)
        else:
            await callback.answer("❌ Failed to approve withdrawal", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error approving withdrawal: {e}")
        await callback.answer("❌ Error processing approval", show_alert=True)

async def reject_withdrawal(callback: types.CallbackQuery, bot):
    """Reject a withdrawal request."""
    try:
        if callback.from_user.id not in ADMIN_USER_IDS:
            await callback.answer("❌ Unauthorized", show_alert=True)
            return
        
        withdrawal_id = int(callback.data.split("_")[1])
        
        requests = await get_withdrawal_requests()
        withdrawal = next((w for w in requests if w["id"] == withdrawal_id), None)
        
        if not withdrawal:
            await callback.answer("❌ Withdrawal request not found", show_alert=True)
            return
        
        if withdrawal["status"] != "pending":
            await callback.answer(f"❌ Already {withdrawal['status']}", show_alert=True)
            return
        
        success = await process_withdrawal(
            withdrawal_id=withdrawal_id,
            admin_id=callback.from_user.id,
            approved=False,
            notes="Rejected by admin"
        )
        
        if success:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n"
                f"❌ <b>REJECTED</b> by @{callback.from_user.username}"
            )
            
            try:
                await bot.send_message(
                    withdrawal["user_id"],
                    f"❌ <b>Withdrawal Rejected</b>\n\n"
                    f"Your ₦{withdrawal['amount']:,} withdrawal request has been rejected.\n"
                    f"Please contact support if you have questions."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {withdrawal['user_id']}: {e}")
            
            await callback.answer("❌ Withdrawal rejected", show_alert=True)
        else:
            await callback.answer("❌ Failed to reject withdrawal", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error rejecting withdrawal: {e}")
        await callback.answer("❌ Error processing rejection", show_alert=True)

def register_admin_withdrawal_handlers(dp: Dispatcher):
    """Register admin withdrawal handlers."""
    dp.callback_query.register(approve_withdrawal, F.data.startswith("approve_"))
    dp.callback_query.register(reject_withdrawal, F.data.startswith("reject_"))
    logger.info("Admin withdrawal handlers registered")
