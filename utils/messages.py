# messages.py
"""Module containing all message templates for DocuLuna bot.

This module provides lists and dictionaries of themed messages for various
events in the bot, ensuring consistent lunar-themed communication.
"""

import random
from typing import List, Dict

WELCOME_MESSAGES: List[str] = [
    "🌙 Welcome back, Lunar Traveler! Ready to transform another document?",
    "✨ Luna beams shine on you! Let's turn your files into magic.",
    "🌑 Hello, Moon Wanderer! What document adventure awaits today?",
    "🌓 Greetings from the lunar side! DocuLuna at your service.",
    "🌕 Full moon vibes! Let's illuminate your files.",
    "🌔 Step into the moonlight. How can I assist with your docs?",
    "🌒 Crescent cheers! Ready to convert and conquer?",
    "✨ Sparkling stars and lunar glow — welcome aboard!",
    "🌙 Lunar landing successful! Documents incoming?",
    "🪐 Orbiting around your needs. Welcome!",
    "🌟 New moon rising! Let's start your document quest.",
    "🚀 Launch into lunar docs! What's on the agenda?"
]

WELCOME_MSG = """🌙 <b>Welcome to DocuLuna</b>

I'm Luna, your document transformation assistant! Here's what I can do:

📄 <b>PDF & Document Tools:</b>
• Convert between PDF ↔️ Word
• Merge multiple PDFs together
• Split pages from PDFs
• Compress PDFs to save space

🖼️ <b>Smart Tools:</b>
• Convert images to PDF
• Extract text with OCR
• Get personalized recommendations

📊 <b>Your Profile:</b>
• Track your progress with XP & levels
• Earn moons and achievements
• View operation history

<b>Choose an option below to get started!</b>"""

PROCESSING_MSG = """⏳ <b>Processing your file...</b>

🌙 Luna is working her magic on your document.
Please wait, this typically takes just a few seconds.
"""

LEVEL_UP_MESSAGES: List[str] = [
    "⚡ Boom! Level {level} → {rank} | +{moons} moons",
    "🌕 Your lunar glow intensifies! Welcome to Level {level}",
    "✨ Level {level} unlocked! You are now a {rank} | +{moons} moons reward!",
    "🌑 From new moon to {rank}! Level {level} achieved | {moons} moons gifted.",
    "🌓 Waxing strong! Level {level} → {rank} | {moons} moons added.",
    "🪐 Celestial leap! Level {level} as {rank} | {moons} moons orbit you.",
    "🌙 Overlord in sight? Level {level} unlocked! {rank} | +{moons} moons.",
    "🔥 Level up alert! {level} reached – {rank} status | Bonus: {moons} moons.",
    "⭐ Shining brighter! Level {level} as {rank} | Collect {moons} moons."
]

ACHIEVEMENT_MESSAGES: Dict[str, str] = {
    "First Document": "⭐ First step on the moon: 'First Document' badge earned!",
    "Speedster": "🚀 Blasting off with 'Speedster'! Quick as lunar light.",
    "Streak Lord": "🔥 On fire! 'Streak Lord' for unbreakable 7-day dedication.",
    "Scholar": "📚 Lunar library built: 'Scholar' achievement unlocked!",
    "Moon Collector": "🌙 Hoarding moons? 'Moon Collector' badge shines bright.",
    "Smart Worker": "🧠 Brainy moves: 'Smart Worker' badge unlocked — you followed Luna’s wisdom!",
    "Document Master": "🛡️ Document Master unlocked! 50 conversions mastered.",
    "Lunar Legend": "🌌 Lunar Legend! Reached level 50 with style."
}

STREAK_MESSAGES: List[str] = [
    "🔥 You're on a {streak}-day streak! Luna is proud!",
    "✨ {streak} days strong! Keep the lunar momentum.",
    "🌓 Streak at {streak}! The moon bows to your consistency.",
    "🌕 Full power streak: {streak} days. Legendary!",
    "🌔 Waxing streak to {streak}! More moons await.",
    "🌒 Building momentum: {streak}-day streak unlocked!",
    "🪐 Orbital consistency: {streak} days in a row!"
]

ERROR_MESSAGES: List[str] = [
    "🌑 Oops! Something slipped in the lunar shadows. Try again?",
    "✨ Luna hiccup! Invalid file — please check and retry.",
    "🌓 File too heavy for moon gravity!",
    "🌔 No document received. Send one to continue your journey!",
    "🌒 Unsupported format. Try PDF, Word, or images?",
    "🪐 Connection lost to the lunar base. Reconnect?",
    "⚡ Premium feature — spend moons or upgrade to unlock!",
    "🌙 Database eclipse! Retrying in a moment.",
    "🚀 Command misfire! Check /help for guidance."
]

RECOMMENDATION_MESSAGES: List[str] = [
    "🌙 Tip: Compress large files to save space and time!",
    "✨ Suggestion: Split big PDFs for easier sharing.",
    "🌓 Recommend: Use OCR on scanned documents for searchable text.",
    "🌕 Smart move: Add timestamps and versions to avoid confusion.",
    "🌔 Pro tip: Clean old history weekly to keep things tidy.",
    "🌒 Idea: Group similar operations into projects.",
    "🪐 Following tips earns XP and the Smart Worker badge!",
    "⚡ Compress images before converting to PDF for smaller files.",
    "🚀 Split long docs into chapters for mobile reading.",
    "⭐ Sanitize filenames — remove special characters for safety.",
    "🧠 Quick win: Use bulk operations for multiple files.",
    "📚 Scholar hint: Merge related PDFs into one master doc."
]

def get_random_welcome() -> str:
    """Get a random welcome message."""
    return random.choice(WELCOME_MESSAGES)

def get_random_level_up(level: int, rank: str, moons: int) -> str:
    """Format a random level up message."""
    return random.choice(LEVEL_UP_MESSAGES).format(level=level, rank=rank, moons=moons)

def get_random_streak(streak: int) -> str:
    """Format a random streak message."""
    return random.choice(STREAK_MESSAGES).format(streak=streak)

def get_random_error() -> str:
    """Get a random error message."""
    return random.choice(ERROR_MESSAGES)

def get_random_recommendation() -> str:
    """Get a random recommendation message."""
    return random.choice(RECOMMENDATION_MESSAGES)
