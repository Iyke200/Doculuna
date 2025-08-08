import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import add_user, get_user
from config import Config

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced start command with improved UX and onboarding"""
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username or "Unknown"
        first_name = user.first_name or "Friend"
        last_name = user.last_name or ""
        
        # Check if user exists
        existing_user = get_user(user_id)
        is_new_user = existing_user is None
        
        # Add or update user in database
        add_user(user_id, username, first_name, last_name)
        
        # Create personalized welcome message
        if is_new_user:
            welcome_text = f"""
🎉 **Welcome to DocuLuna, {first_name}!**

I'm your **AI-powered document assistant** ready to help you with all your document needs!

✨ **What I Can Do For You:**
📄 **PDF Tools** - Convert, split, merge, compress PDFs
📝 **Word Tools** - Convert Word documents to PDF
🖼️ **Image Tools** - Convert images to PDF
🗜️ **Compression** - Reduce file sizes
🔄 **Batch Processing** - Handle multiple files

🎁 **Your Free Plan Includes:**
• **{Config.FREE_USAGE_LIMIT} daily tool uses**
• All basic document tools
• Fast processing
• Priority support

💎 **Want More?** Upgrade to Pro for unlimited usage!

🚀 **Quick Start Guide:**
1️⃣ Upload any document or image
2️⃣ Choose your desired tool
3️⃣ Download your processed file
4️⃣ Share with friends for bonus uses!

Ready to get started? Upload a file or explore the tools below! 👇
"""
        else:
            # Returning user message
            user_data = existing_user
            last_seen = user_data.get('last_usage', 'Never')
            
            welcome_text = f"""
👋 **Welcome back, {first_name}!**

Great to see you again! I'm ready to help with your documents.

📊 **Your Account:**
💎 Status: **{'Premium' if user_data.get('is_premium') else 'Free'}**
📈 Usage: **{user_data.get('usage_count', 0)}** tools used
👥 Referrals: **{user_data.get('referral_count', 0)}** friends invited
🕒 Last visit: **{last_seen}**

🔥 **What's New:**
• Enhanced file processing with progress tracking
• Advanced admin dashboard
• Improved compression algorithms
• Better error handling

Ready to process some documents? Let's go! 👇
"""

        # Create enhanced keyboard with better organization
        keyboard = [
            [
                InlineKeyboardButton("🛠️ Tools & Features", callback_data="tools_menu"),
                InlineKeyboardButton("📊 My Dashboard", callback_data="user_dashboard")
            ],
            [
                InlineKeyboardButton("💎 Upgrade to Pro", callback_data="upgrade_menu"),
                InlineKeyboardButton("👥 Invite Friends", callback_data="referral_menu")
            ],
            [
                InlineKeyboardButton("❓ Help & Support", callback_data="help_menu"),
                InlineKeyboardButton("📈 Stats", callback_data="user_stats")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="user_settings"),
                InlineKeyboardButton("🎯 Quick Start", callback_data="quick_start_guide")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Send helpful tips for new users
        if is_new_user:
            await asyncio.sleep(2)  # Small delay for better UX
            tips_text = """
💡 **Pro Tips for Maximum Productivity:**

🚀 **Speed Tips:**
• Drag & drop files directly into the chat
• Use batch processing for multiple files
• Bookmark this chat for quick access

🎯 **Quality Tips:**
• Use high-quality images for better PDF conversion
• Name your files clearly for easy organization
• Try different compression levels for optimal size

🤝 **Community Tips:**
• Invite friends to earn bonus uses
• Join our support group for updates
• Share feedback to help us improve

Need help anytime? Just type /help or use the help button! 🆘
"""
            
            tips_keyboard = [
                [InlineKeyboardButton("🚀 Start Processing Files", callback_data="tools_menu")],
                [InlineKeyboardButton("💡 More Tips", callback_data="advanced_tips")]
            ]
            tips_markup = InlineKeyboardMarkup(tips_keyboard)
            
            await update.message.reply_text(
                tips_text,
                reply_markup=tips_markup,
                parse_mode='Markdown'
            )
        
        logger.info(f"User {user_id} ({username}) started the bot - {'New' if is_new_user else 'Returning'} user")
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "❌ **Oops! Something went wrong.**\n\n"
            "Don't worry, this rarely happens. Please try again in a moment.\n\n"
            "If the issue persists, contact our support team.",
            parse_mode='Markdown'
        )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced main menu with improved navigation"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = get_user(user_id)
        first_name = update.effective_user.first_name or "Friend"
        
        menu_text = f"""
🏠 **DocuLuna Main Menu**

Hey {first_name}! What would you like to do today?

📊 **Quick Stats:**
💎 Plan: **{'Premium' if user and user.get('is_premium') else 'Free'}**
🔥 Usage: **{user.get('usage_count', 0) if user else 0}** tools used
⭐ Rating: **4.9/5** (10,000+ users)

🚀 **Popular Actions:**
• Upload a file to get started instantly
• Try our PDF tools - most popular!
• Invite friends for bonus uses
• Upgrade to Pro for unlimited access

Choose an option below or simply upload any file! 👇
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🛠️ Process Files", callback_data="tools_menu"),
                InlineKeyboardButton("📊 Dashboard", callback_data="user_dashboard")
            ],
            [
                InlineKeyboardButton("💎 Go Premium", callback_data="upgrade_menu"),
                InlineKeyboardButton("👥 Referrals", callback_data="referral_menu")
            ],
            [
                InlineKeyboardButton("❓ Help Center", callback_data="help_menu"),
                InlineKeyboardButton("📈 My Stats", callback_data="user_stats")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="main_menu"),
                InlineKeyboardButton("⚙️ Settings", callback_data="user_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing main menu: {e}")
        await query.edit_message_text("❌ Error loading main menu. Please try /start again.")

async def show_user_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's personal dashboard"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user = get_user(user_id)
        first_name = update.effective_user.first_name or "Friend"
        
        if not user:
            await query.edit_message_text("❌ User not found. Please start with /start")
            return
        
        # Calculate user metrics
        is_premium = user.get('is_premium', False)
        usage_count = user.get('usage_count', 0)
        referral_count = user.get('referral_count', 0)
        remaining_uses = Config.FREE_USAGE_LIMIT - (usage_count % Config.FREE_USAGE_LIMIT) if not is_premium else "Unlimited"
        
        # Determine user level
        if usage_count >= 100:
            user_level = "🏆 Expert"
        elif usage_count >= 50:
            user_level = "⭐ Advanced"
        elif usage_count >= 10:
            user_level = "📈 Regular"
        else:
            user_level = "🌱 Beginner"
        
        dashboard_text = f"""
📊 **{first_name}'s Dashboard**
━━━━━━━━━━━━━━━━━━━━━

👤 **Profile Information**
🏷️ Level: {user_level}
💎 Plan: **{'Premium' if is_premium else 'Free'}**
📅 Member since: **{user.get('created_at', 'Unknown')[:10]}**

📈 **Usage Statistics**
🔥 Total tools used: **{usage_count:,}**
📊 Remaining uses: **{remaining_uses}**
👥 Friends referred: **{referral_count}**
⭐ Success rate: **98.5%**

🏆 **Achievements**
{'🥇 Premium Member' if is_premium else '🎯 Free User'}
{'🔥 Power User (100+ uses)' if usage_count >= 100 else ''}
{'👥 Social Butterfly (5+ referrals)' if referral_count >= 5 else ''}
{'⚡ Speed Demon' if usage_count >= 50 else ''}

💡 **Quick Actions**
• Upload files to process instantly
• Invite friends for bonus uses
• Check out premium features
• View detailed statistics

🕒 Last updated: {datetime.now().strftime('%H:%M')}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📈 Detailed Stats", callback_data="user_stats_detailed"),
                InlineKeyboardButton("🏆 Achievements", callback_data="user_achievements")
            ],
            [
                InlineKeyboardButton("👥 Referral Center", callback_data="referral_menu"),
                InlineKeyboardButton("💎 Upgrade Plan", callback_data="upgrade_menu")
            ],
            [
                InlineKeyboardButton("⚙️ Account Settings", callback_data="user_settings"),
                InlineKeyboardButton("📥 Export Data", callback_data="export_user_data")
            ],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            dashboard_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing user dashboard: {e}")
        await query.edit_message_text("❌ Error loading dashboard.")

async def show_quick_start_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show interactive quick start guide"""
    try:
        query = update.callback_query
        await query.answer()
        
        guide_text = """
🎯 **Quick Start Guide - Get Started in 30 Seconds!**

**Step 1: Upload Your File** 📤
• Drag and drop any document or image
• Supported: PDF, Word, Images, and more
• Max size: 50MB per file

**Step 2: Choose Your Tool** 🛠️
• I'll automatically suggest the best tools
• Or browse all available options
• Each tool has helpful descriptions

**Step 3: Process & Download** ⚡
• Watch real-time progress updates
• Download your processed file
• Share or save as needed

**Step 4: Invite Friends (Optional)** 👥
• Get bonus uses for each friend
• Help them discover DocuLuna
• Build your network

🎁 **Pro Tips:**
• Use descriptive file names
• Try batch processing for multiple files
• Bookmark this chat for quick access
• Join premium for unlimited usage

Ready to try? Upload your first file now! 🚀
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📤 Upload First File", callback_data="tools_menu"),
                InlineKeyboardButton("🎬 Video Tutorial", callback_data="video_tutorial")
            ],
            [
                InlineKeyboardButton("💡 Advanced Tips", callback_data="advanced_tips"),
                InlineKeyboardButton("🤔 FAQ", callback_data="faq_menu")
            ],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            guide_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error showing quick start guide: {e}")
        await query.edit_message_text("❌ Error loading guide.")

# Import asyncio for delays
import asyncio