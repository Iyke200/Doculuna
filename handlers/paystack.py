# handlers/paystack.py - Production Payment System
import logging
import requests
import json
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import (
    PAYSTACK_SECRET_KEY, PAYSTACK_INITIALIZE_URL, PAYSTACK_VERIFY_URL,
    PREMIUM_PLANS, REFERRAL_REWARDS
)
from database.db import update_user_premium_status, add_payment_log, get_user_by_id
from utils.referral_utils import process_referral_reward

logger = logging.getLogger(__name__)

class PaystackPayment:
    def __init__(self):
        self.secret_key = PAYSTACK_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    async def initialize_payment(self, email: str, amount: int, reference: str, plan: str):
        """Initialize Paystack payment."""
        try:
            data = {
                'email': email,
                'amount': amount * 100,  # Convert to kobo
                'reference': reference,
                'metadata': {
                    'plan': plan,
                    'custom_fields': [
                        {
                            'display_name': 'Plan Type',
                            'variable_name': 'plan_type',
                            'value': plan
                        }
                    ]
                }
            }
            
            response = requests.post(PAYSTACK_INITIALIZE_URL, 
                                   headers=self.headers, 
                                   data=json.dumps(data))
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Paystack initialization failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error initializing Paystack payment: {e}")
            return None
    
    async def verify_payment(self, reference: str):
        """Verify Paystack payment."""
        try:
            response = requests.get(f"{PAYSTACK_VERIFY_URL}{reference}", 
                                  headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Paystack verification failed: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error verifying Paystack payment: {e}")
            return None

paystack = PaystackPayment()

async def initiate_premium_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize premium payment with Paystack."""
    try:
        query = update.callback_query
        plan_type = query.data.split('_')[-1]  # Extract plan from callback data
        if not update.effective_user:
            await query.edit_message_text("❌ User information not available.")
            return
        user_id = update.effective_user.id
        user = get_user_by_id(user_id)
        
        if not user:
            await query.edit_message_text("❌ User not found. Please use /start first.")
            return
            
        if plan_type not in PREMIUM_PLANS:
            await query.edit_message_text("❌ Invalid plan selected.")
            return
            
        plan = PREMIUM_PLANS[plan_type]
        reference = f"docuLuna_{user_id}_{uuid.uuid4().hex[:8]}"
        
        # Store payment info in context
        context.user_data['payment_reference'] = reference
        context.user_data['selected_plan'] = plan_type
        
        # For now, create a manual payment message since we need email
        payment_message = (
            f"💳 **{plan['name']} - ₦{plan['price']:,}**\n\n"
            f"✨ {plan['description']}\n"
            f"⏰ Valid for {plan['duration_days']} days\n\n"
            f"**What you get:**\n"
            f"✅ Unlimited conversions\n"
            f"✅ No watermarks\n"
            f"✅ Priority processing\n"
            f"✅ Large file support (up to 50MB)\n\n"
            f"Click below to proceed with payment:"
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Card", callback_data=f"pay_card_{plan_type}")],
            [InlineKeyboardButton("🏦 Bank Transfer", callback_data=f"pay_bank_{plan_type}")],
            [InlineKeyboardButton("🔙 Back", callback_data="premium_menu")]
        ]
        
        await query.edit_message_text(
            payment_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error initiating premium payment: {e}")
        await query.edit_message_text("❌ Payment initialization failed. Please try again.")

async def handle_card_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle card payment flow."""
    try:
        query = update.callback_query
        plan_type = query.data.split('_')[-1]
        user_id = update.effective_user.id
        plan = PREMIUM_PLANS[plan_type]
        
        # Request email for Paystack
        await query.edit_message_text(
            f"📧 **Card Payment Setup**\n\n"
            f"Plan: {plan['name']} - ₦{plan['price']:,}\n\n"
            f"Please reply with your email address to receive the secure payment link.\n\n"
            f"Format: your.email@example.com"
        )
        
        # Set state for email collection
        context.user_data['awaiting_email'] = True
        context.user_data['payment_plan'] = plan_type
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error handling card payment: {e}")

async def handle_bank_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bank transfer payment."""
    try:
        query = update.callback_query
        plan_type = query.data.split('_')[-1]
        plan = PREMIUM_PLANS[plan_type]
        
        bank_message = (
            f"🏦 **Bank Transfer Details**\n\n"
            f"Plan: {plan['name']} - ₦{plan['price']:,}\n\n"
            f"**Transfer to:**\n"
            f"🏦 Bank: Moniepoint\n"
            f"🔢 Account: 9057203030\n"
            f"👤 Name: Ebere Nwankwo\n"
            f"💰 Amount: ₦{plan['price']:,}\n\n"
            f"**After payment:**\n"
            f"📸 Send screenshot of payment\n"
            f"⏰ Processing time: 5-10 minutes\n\n"
            f"🔒 Your premium access will be activated immediately after verification."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ I've Made Payment", callback_data=f"payment_sent_{plan_type}")],
            [InlineKeyboardButton("🔙 Back", callback_data="premium_menu")]
        ]
        
        await query.edit_message_text(
            bank_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error handling bank payment: {e}")

async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment confirmation from user."""
    try:
        query = update.callback_query
        plan_type = query.data.split('_')[-1]
        user_id = update.effective_user.id
        
        # Notify admin about payment
        username = update.effective_user.username if update.effective_user else 'N/A'
        admin_message = (
            f"💰 **New Payment Notification**\n\n"
            f"User ID: {user_id}\n"
            f"Username: @{username}\n"
            f"Plan: {PREMIUM_PLANS[plan_type]['name']}\n"
            f"Amount: ₦{PREMIUM_PLANS[plan_type]['price']:,}\n\n"
            f"Please verify and activate premium access."
        )
        
        # Send to admin
        from config import ADMIN_USER_IDS
        for admin_id in ADMIN_USER_IDS:
            try:
                keyboard = [[InlineKeyboardButton("✅ Activate Premium", 
                                                callback_data=f"activate_{user_id}_{plan_type}")]]
                await context.bot.send_message(
                    admin_id,
                    admin_message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        await query.edit_message_text(
            "✅ **Payment Confirmation Received!**\n\n"
            "Your payment is being processed. You'll receive confirmation within 5-10 minutes.\n\n"
            "Thank you for choosing DocuLuna Pro! 🚀"
        )
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error handling payment confirmation: {e}")

async def activate_premium_by_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin function to activate premium."""
    try:
        query = update.callback_query
        data_parts = query.data.split('_')
        target_user_id = int(data_parts[1])
        plan_type = data_parts[2]
        if not update.effective_user:
            await query.answer("❌ User information not available", show_alert=True)
            return
        admin_id = update.effective_user.id
        
        from config import ADMIN_USER_IDS
        if admin_id not in ADMIN_USER_IDS:
            await query.answer("❌ Unauthorized", show_alert=True)
            return
            
        plan = PREMIUM_PLANS[plan_type]
        
        # Activate premium
        update_user_premium_status(target_user_id, plan['duration_days'])
        
        # Log payment
        add_payment_log(target_user_id, plan['price'], plan_type, "manual_activation")
        
        # Notify user
        try:
            await context.bot.send_message(
                target_user_id,
                f"🎉 **Premium Activated!**\n\n"
                f"Welcome to DocuLuna Pro!\n"
                f"Plan: {plan['name']}\n"
                f"Valid for: {plan['duration_days']} days\n\n"
                f"✨ Enjoy unlimited, watermark-free conversions!"
            )
        except:
            pass
        
        await query.edit_message_text(
            f"✅ Premium activated for user {target_user_id}\n"
            f"Plan: {plan['name']}\n"
            f"Duration: {plan['duration_days']} days"
        )
        
    except Exception as e:
        logger.error(f"Error activating premium by admin: {e}")
        await query.answer("❌ Error activating premium", show_alert=True)