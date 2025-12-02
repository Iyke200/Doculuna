"""Quick-access command shortcuts for DocuLuna."""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


@router.message(Command("convert"))
async def cmd_convert(message: types.Message):
    """Quick convert command."""
    await message.answer(
        "📄 <b>Quick Convert</b>\n\n"
        "Send a PDF to convert to Word, or a Word file to convert to PDF.\n"
        "I'll detect the format automatically!",
        parse_mode="HTML"
    )


@router.message(Command("compress"))
async def cmd_compress(message: types.Message):
    """Quick compress command."""
    await message.answer(
        "🗜️ <b>Quick Compress</b>\n\n"
        "Send a PDF or Word file to compress.\n"
        "I'll reduce the size by 50-80% while keeping quality!",
        parse_mode="HTML"
    )


@router.message(Command("merge"))
async def cmd_merge(message: types.Message):
    """Quick merge command."""
    await message.answer(
        "🧩 <b>Quick Merge</b>\n\n"
        "Send multiple PDFs to combine them into one file.\n"
        "Just keep sending files and I'll merge them together!",
        parse_mode="HTML"
    )


@router.message(Command("split"))
async def cmd_split(message: types.Message):
    """Quick split command."""
    await message.answer(
        "✂️ <b>Quick Split</b>\n\n"
        "Send a PDF file to extract specific pages.\n"
        "Choose which pages you want to keep!",
        parse_mode="HTML"
    )


@router.message(Command("profile"))
async def cmd_profile_redirect(message: types.Message):
    """Profile command redirect."""
    from handlers.profile_handlers import cmd_profile
    await cmd_profile(message)


@router.message(Command("recommend"))
async def cmd_recommend_redirect(message: types.Message):
    """Recommend command redirect."""
    from handlers.profile_handlers import cmd_recommend
    await cmd_recommend(message)


@router.message(Command("help"))
async def cmd_help_quick(message: types.Message):
    """Quick help command."""
    help_text = """📖 <b>DocuLuna Help</b>

<b>Quick Commands:</b>
/convert - Convert PDF ↔️ Word
/compress - Compress files
/merge - Merge PDFs
/split - Extract pages
/profile - View your profile
/recommend - Get suggestions
/start - Main menu

<b>Features:</b>
✅ 3 free uses/day (Free)
💎 Unlimited (Premium)
🌙 Earn XP & achievements
💰 Referral rewards

<b>Need Help?</b>
Contact @DocuLunaSupport
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Back to Menu", callback_data="back_to_menu")
    await message.answer(help_text, reply_markup=builder.as_markup(), parse_mode="HTML")


def register_shortcuts(dp) -> None:
    """Register all shortcut handlers."""
    dp.include_router(router)
