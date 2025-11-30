# profile_handlers.py
"""Integrated handlers for /profile, /recommend, /history commands.

This module integrates gamification, smart recommendations, and history
into the DocuLuna bot with proper Aiogram handlers.
"""

import logging
from datetime import datetime
from typing import Optional

from aiogram import Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.gamification import gamification_engine, GamificationEngine
from handlers.smart_recommendation import smart_recommendation, SmartRecommendation
from handlers.history import (
    get_recent_history, 
    get_history_stats, 
    get_history_count,
    clean_old_history,
    clear_all_history
)

logger = logging.getLogger(__name__)

# Initialize the router
router = Router()


async def format_profile_message(user_id: int, username: str = None) -> str:
    """Format the user profile message with gamification data."""
    profile = await gamification_engine.get_profile(user_id)
    history_count = await get_history_count(user_id)
    
    # Calculate progress bar for XP
    current_xp = profile.get("xp", 0)
    next_level_xp = profile.get("next_level_xp", 100)
    progress = min(current_xp / next_level_xp, 1.0) if next_level_xp > 0 else 1.0
    progress_bar = create_progress_bar(progress)
    
    # Format badges
    badges = profile.get("badges", [])
    badges_text = ""
    if badges:
        badge_names = [b.get("name", b) if isinstance(b, dict) else b for b in badges[:5]]
        badges_text = " | ".join(badge_names)
        if len(badges) > 5:
            badges_text += f" (+{len(badges) - 5} more)"
    else:
        badges_text = "None yet - keep processing documents!"
    
    # Format last activity
    last_activity = profile.get("last_activity")
    if last_activity:
        try:
            last_dt = datetime.fromisoformat(last_activity)
            last_activity_text = last_dt.strftime("%b %d, %Y")
        except:
            last_activity_text = "Recently"
    else:
        last_activity_text = "Just started"
    
    display_name = f"@{username}" if username else f"User {user_id}"
    
    message = f"""🌙 <b>DocuLuna Profile</b>

👤 <b>{display_name}</b>

📊 <b>Stats:</b>
├ {profile.get('rank', '🌑 New Moon')}
├ Level: {profile.get('level', 1)}
├ XP: {current_xp}/{next_level_xp}
│  {progress_bar}
├ 🌙 Moons: {profile.get('moons', 0)}
├ 🔥 Streak: {profile.get('streak', 0)} days
└ 📄 Documents: {history_count}

🏆 <b>Achievements:</b>
{badges_text}

📅 Last active: {last_activity_text}

<i>Use /recommend for personalized tips!</i>"""
    
    return message


def create_progress_bar(progress: float, length: int = 10) -> str:
    """Create a visual progress bar."""
    filled = int(progress * length)
    empty = length - filled
    return "▓" * filled + "░" * empty + f" {int(progress * 100)}%"


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Handle /profile command - show user's gamification profile."""
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        # Ensure user exists and update streak
        await gamification_engine.ensure_user(user_id)
        streak_result = await gamification_engine.update_streak(user_id)
        
        # Format and send profile
        profile_text = await format_profile_message(user_id, username)
        
        # Add inline buttons
        builder = InlineKeyboardBuilder()
        builder.button(text="📊 View Stats", callback_data="profile_stats")
        builder.button(text="🏆 Leaderboard", callback_data="profile_leaderboard")
        builder.button(text="📜 History", callback_data="profile_history")
        builder.adjust(2, 1)
        
        await message.answer(profile_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
        # Show streak message if increased
        if streak_result.get("message"):
            await message.answer(streak_result["message"])
            
    except Exception as e:
        logger.error(f"Error in /profile command: {e}", exc_info=True)
        await message.answer("❌ Could not load profile. Please try again later.")


@router.message(Command("recommend"))
async def cmd_recommend(message: Message):
    """Handle /recommend command - show personalized recommendations."""
    try:
        user_id = message.from_user.id
        
        # Get user history for analysis
        history = await get_recent_history(user_id, limit=20)
        
        # Ensure gamification engine is linked
        smart_recommendation.set_gamification(gamification_engine)
        
        # Get personalized recommendation
        result = await smart_recommendation.analyze_and_suggest(user_id, history)
        
        confidence_emoji = "🎯" if result["confidence"] > 0.8 else "💡" if result["confidence"] > 0.6 else "✨"
        
        message_text = f"""🌙 <b>DocuLuna Recommendation</b>

{confidence_emoji} <b>Personalized Tip:</b>
{result['message']}

<i>Category: {result['category'].title()}</i>

💡 <b>Why this tip?</b>
{result.get('reason', 'Based on your usage patterns')}

<i>Following recommendations earns +75 XP and may unlock the 'Smart Worker' badge!</i>"""

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ I'll try it!", callback_data=f"follow_rec_{result['category']}")
        builder.button(text="🔄 Another tip", callback_data="new_recommendation")
        builder.button(text="📊 My Profile", callback_data="show_profile")
        builder.adjust(2, 1)
        
        await message.answer(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in /recommend command: {e}", exc_info=True)
        await message.answer("❌ Could not generate recommendation. Please try again later.")


@router.message(Command("history"))
async def cmd_history(message: Message):
    """Handle /history command - show user's operation history."""
    try:
        user_id = message.from_user.id
        
        # Get recent history
        history = await get_recent_history(user_id, limit=10)
        stats = await get_history_stats(user_id)
        
        if not history:
            await message.answer(
                "📜 <b>Your History</b>\n\n"
                "No operations yet! Start processing documents to build your history.\n\n"
                "Just send me a PDF, Word document, or image to get started!",
                parse_mode="HTML"
            )
            return
        
        # Format history entries
        history_lines = []
        for i, entry in enumerate(history[:10], 1):
            status_emoji = "✅" if entry["status"] == "success" else "❌"
            op_emoji = {
                "convert": "🔁",
                "compress": "🗜️",
                "merge": "📊",
                "split": "✂️",
                "ocr": "📷",
                "image_to_pdf": "📄"
            }.get(entry["operation_type"], "📄")
            
            history_lines.append(
                f"{i}. {status_emoji} {op_emoji} <code>{entry['filename'][:25]}{'...' if len(entry['filename']) > 25 else ''}</code>\n"
                f"   └ {entry['operation_type']} | {entry['formatted_time']}"
            )
        
        history_text = "\n".join(history_lines)
        
        # Format stats
        most_used = list(stats.get("by_type", {}).items())[:3]
        most_used_text = ", ".join([f"{k}: {v}" for k, v in most_used]) if most_used else "N/A"
        
        message_text = f"""📜 <b>Your DocuLuna History</b>

<b>Recent Operations:</b>
{history_text}

<b>📊 Statistics:</b>
├ Total operations: {stats['total_operations']}
├ Success rate: {stats['success_rate']}%
├ Avg. processing time: {stats['avg_duration']}s
└ Most used: {most_used_text}

<i>Use /profile to see your full stats!</i>"""

        builder = InlineKeyboardBuilder()
        builder.button(text="📊 Full Stats", callback_data="history_full_stats")
        builder.button(text="🧹 Clean Old (30d)", callback_data="history_clean_30")
        builder.button(text="🗑️ Clear All", callback_data="history_clear_confirm")
        builder.adjust(2, 1)
        
        await message.answer(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in /history command: {e}", exc_info=True)
        await message.answer("❌ Could not load history. Please try again later.")


@router.callback_query(lambda c: c.data == "profile_stats")
async def callback_profile_stats(callback: CallbackQuery):
    """Show detailed profile stats."""
    try:
        user_id = callback.from_user.id
        profile = await gamification_engine.get_profile(user_id)
        stats = await get_history_stats(user_id)
        
        by_type = stats.get("by_type", {})
        ops_breakdown = "\n".join([f"  • {k}: {v}" for k, v in list(by_type.items())[:5]]) or "  No operations yet"
        
        file_types = stats.get("file_types", {})
        types_breakdown = "\n".join([f"  • {k}: {v}" for k, v in list(file_types.items())[:5]]) or "  No files yet"
        
        stats_text = f"""📊 <b>Detailed Statistics</b>

<b>🎮 Gamification:</b>
├ Total XP: {profile.get('xp', 0)}
├ Current Level: {profile.get('level', 1)}
├ Rank: {profile.get('rank', 'New Moon')}
├ Moons earned: {profile.get('moons', 0)}
└ Streak: {profile.get('streak', 0)} days

<b>📄 Operations:</b>
├ Total: {stats['total_operations']}
├ Success rate: {stats['success_rate']}%
└ By type:
{ops_breakdown}

<b>📁 File Types Used:</b>
{types_breakdown}

<b>🏆 Badges: {len(profile.get('badges', []))}</b>"""

        await callback.message.edit_text(stats_text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in profile_stats callback: {e}", exc_info=True)
        await callback.answer("Error loading stats", show_alert=True)


@router.callback_query(lambda c: c.data == "profile_leaderboard")
async def callback_leaderboard(callback: CallbackQuery):
    """Show the XP leaderboard."""
    try:
        leaders = await gamification_engine.get_leaderboard(limit=10)
        user_id = callback.from_user.id
        
        if not leaders:
            await callback.message.edit_text(
                "🏆 <b>Leaderboard</b>\n\nNo users on the leaderboard yet. Be the first!",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        user_rank = None
        
        for i, leader in enumerate(leaders, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            is_you = leader["user_id"] == user_id
            if is_you:
                user_rank = i
            
            lines.append(
                f"{medal} {'<b>YOU</b>' if is_you else f'User {leader[\"user_id\"]}'} "
                f"| Level {leader['level']} | {leader['xp']} XP | {leader['moons']} 🌙"
            )
        
        position_text = f"\n\n📍 Your position: #{user_rank}" if user_rank else ""
        
        leaderboard_text = f"""🏆 <b>DocuLuna Leaderboard</b>

{chr(10).join(lines)}{position_text}

<i>Keep processing documents to climb the ranks!</i>"""

        await callback.message.edit_text(leaderboard_text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in leaderboard callback: {e}", exc_info=True)
        await callback.answer("Error loading leaderboard", show_alert=True)


@router.callback_query(lambda c: c.data == "profile_history")
async def callback_profile_history(callback: CallbackQuery):
    """Redirect to history view."""
    try:
        # Create a fake message to reuse the history command
        await callback.message.delete()
        await cmd_history(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in profile_history callback: {e}", exc_info=True)
        await callback.answer("Error loading history", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("follow_rec_"))
async def callback_follow_recommendation(callback: CallbackQuery):
    """Handle when user follows a recommendation."""
    try:
        user_id = callback.from_user.id
        category = callback.data.replace("follow_rec_", "")
        
        # Ensure gamification is linked
        smart_recommendation.set_gamification(gamification_engine)
        
        # Reward the user
        result = await smart_recommendation.reward_followed_recommendation(user_id, category)
        
        reward_text = f"✨ Great choice!\n\n+{result.get('xp_gained', 75)} XP earned!"
        
        if result.get("achievement_unlocked"):
            reward_text += f"\n\n🏆 Achievement unlocked: {result['achievement_unlocked']}!"
        
        if result.get("leveled_up"):
            reward_text += "\n\n⚡ Level up!"
        
        reward_text += "\n\n<i>Keep following tips to maximize your progress!</i>"
        
        await callback.message.edit_text(reward_text, parse_mode="HTML")
        await callback.answer("Reward granted! 🎉")
        
    except Exception as e:
        logger.error(f"Error in follow_recommendation callback: {e}", exc_info=True)
        await callback.answer("Error processing reward", show_alert=True)


@router.callback_query(lambda c: c.data == "new_recommendation")
async def callback_new_recommendation(callback: CallbackQuery):
    """Generate a new recommendation."""
    try:
        user_id = callback.from_user.id
        history = await get_recent_history(user_id, limit=20)
        
        smart_recommendation.set_gamification(gamification_engine)
        result = await smart_recommendation.analyze_and_suggest(user_id, history)
        
        confidence_emoji = "🎯" if result["confidence"] > 0.8 else "💡" if result["confidence"] > 0.6 else "✨"
        
        message_text = f"""🌙 <b>New Recommendation</b>

{confidence_emoji} <b>Tip:</b>
{result['message']}

<i>Category: {result['category'].title()}</i>"""

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ I'll try it!", callback_data=f"follow_rec_{result['category']}")
        builder.button(text="🔄 Another tip", callback_data="new_recommendation")
        builder.adjust(2)
        
        await callback.message.edit_text(message_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in new_recommendation callback: {e}", exc_info=True)
        await callback.answer("Error generating recommendation", show_alert=True)


@router.callback_query(lambda c: c.data == "show_profile")
async def callback_show_profile(callback: CallbackQuery):
    """Show user profile from callback."""
    try:
        user_id = callback.from_user.id
        username = callback.from_user.username
        
        profile_text = await format_profile_message(user_id, username)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📊 View Stats", callback_data="profile_stats")
        builder.button(text="🏆 Leaderboard", callback_data="profile_leaderboard")
        builder.adjust(2)
        
        await callback.message.edit_text(profile_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in show_profile callback: {e}", exc_info=True)
        await callback.answer("Error loading profile", show_alert=True)


@router.callback_query(lambda c: c.data == "history_full_stats")
async def callback_history_full_stats(callback: CallbackQuery):
    """Show full history statistics."""
    await callback_profile_stats(callback)


@router.callback_query(lambda c: c.data == "history_clean_30")
async def callback_clean_history(callback: CallbackQuery):
    """Clean history older than 30 days."""
    try:
        user_id = callback.from_user.id
        deleted = await clean_old_history(user_id, days_old=30)
        
        await callback.answer(f"🧹 Cleaned {deleted} old entries!", show_alert=True)
        
        # Refresh history view
        history = await get_recent_history(user_id, limit=10)
        if history:
            # Simplified refresh
            await callback.message.edit_text(
                f"✅ Cleaned {deleted} entries older than 30 days.\n\n"
                f"Remaining: {await get_history_count(user_id)} entries.\n\n"
                "Use /history to see updated list.",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "📜 History cleared! No entries remaining.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Error in clean_history callback: {e}", exc_info=True)
        await callback.answer("Error cleaning history", show_alert=True)


@router.callback_query(lambda c: c.data == "history_clear_confirm")
async def callback_clear_history_confirm(callback: CallbackQuery):
    """Confirm clearing all history."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ Yes, clear all", callback_data="history_clear_all")
    builder.button(text="❌ Cancel", callback_data="history_cancel")
    builder.adjust(2)
    
    await callback.message.edit_text(
        "⚠️ <b>Clear All History?</b>\n\n"
        "This will permanently delete ALL your operation history.\n"
        "This action cannot be undone.\n\n"
        "Are you sure?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "history_clear_all")
async def callback_clear_all_history(callback: CallbackQuery):
    """Clear all history for user."""
    try:
        user_id = callback.from_user.id
        deleted = await clear_all_history(user_id)
        
        await callback.message.edit_text(
            f"🗑️ <b>History Cleared</b>\n\n"
            f"Deleted {deleted} entries.\n\n"
            "Start fresh by processing new documents!",
            parse_mode="HTML"
        )
        await callback.answer("History cleared! ✅")
        
    except Exception as e:
        logger.error(f"Error in clear_all_history callback: {e}", exc_info=True)
        await callback.answer("Error clearing history", show_alert=True)


@router.callback_query(lambda c: c.data == "history_cancel")
async def callback_cancel(callback: CallbackQuery):
    """Cancel the operation."""
    await callback.message.edit_text(
        "✅ Operation cancelled.\n\nUse /history to view your history.",
        parse_mode="HTML"
    )
    await callback.answer("Cancelled")


def register_profile_handlers(dp: Dispatcher):
    """Register all profile-related handlers with the dispatcher."""
    dp.include_router(router)
    logger.info("✓ Profile, recommend, and history handlers registered")
