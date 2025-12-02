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

ERROR_CORRUPTED = """❌ File appears corrupted

This file might be damaged or incomplete.

Try:
• Re-download from source
• Send a fresh copy
• Use a different file

"""

ERROR_UNSUPPORTED = """🚫 Format not supported

I work with: PDF • Word • Images (JPG, PNG, GIF)

Try:
• Save as .pdf and send again
• Check the file extension

"""

ERROR_OVERSIZED = """⚠️ File too large

Free limit: 50 MB | Premium: 500 MB

Solutions:
• Upgrade to Premium for unlimited
• Split into smaller parts
• Compress before uploading

"""

ERROR_CORRUPTED_PDF = """🔐 This file is password-protected

I can't convert locked documents.

Fix it:
1. Open in Word/PDF reader
2. Remove password protection
3. Send unprotected version

"""

ERROR_TIMEOUT = """⏱️ Processing took too long

Your file might be:
• Too complex to convert
• Corrupted during upload
• Temporarily unavailable

Retry:
• Wait 30 seconds and try again
• Try a smaller file first

"""

ERROR_QUOTA = """📊 Daily limit reached

You've used 3/3 free conversions today.

Options:
• Premium = Unlimited access
• Wait until tomorrow (resets midnight)

"""

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

SUCCESS_CONVERSION = """✅ Conversion complete!

📊 Conversion Details:
├ Type: {operation_type}
├ File: {filename}
├ Time: {duration}s
└ Size: {size_info}

🎯 Luna suggests:
• 🗜️ Compress to save space
• ✂️ Split if it's too long
• 📊 View statistics

"""

SUCCESS_COMPRESSION = """✅ Compressed!

💾 Space Saved:
├ Original: {original_size}
├ Compressed: {new_size}
└ Saved: {percent_saved}%

Quality: High ✓

Next steps:
• 📤 Share online
• ✂️ Split pages
• 📊 Your stats

"""

SUCCESS_MERGE = """✅ PDFs merged!

📄 Merged File:
├ Pages: {page_count}
├ Size: {file_size}
└ Time: {duration}s

Next actions:
• 🗜️ Compress this file
• ✂️ Split specific pages
• 📊 View progress

"""

SUCCESS_SPLIT = """✅ PDF split!

📄 Your pages:
{page_info}

Ready to download or continue editing!

"""

SUCCESS_IMAGE_PDF = """✅ PDF created!

📖 PDF Details:
├ Pages: {page_count}
├ Format: Standard letter
├ Size: {file_size}
└ Time: {duration}s

What now?
• 🗜️ Make it smaller
• ✂️ Rearrange pages
• 📊 View stats

"""

TOOL_INSTRUCTION_PDF_WORD = """📄 PDF to Word Conversion

Send any PDF file. I'll convert it to an editable Word document.

Size limit: 50 MB (free) / Unlimited (premium)
Time: Usually 5-10 seconds
Quality: Layout preserved ✓

Send your PDF or [⬅️ Back]
"""

TOOL_INSTRUCTION_WORD_PDF = """📝 Word to PDF

Send any Word document (.docx or .doc). I'll convert it to PDF.

Size limit: 50 MB (free) / Unlimited (premium)
Time: Usually 3-8 seconds
Quality: Formatting preserved ✓

Send your file or [⬅️ Back]
"""

TOOL_INSTRUCTION_IMAGE_PDF = """🖼️ Images to PDF

Send 1-20 images. I'll combine them into a single PDF.

Supported: JPG, PNG, GIF, WebP
Size limit: 50 MB total (free)
Time: 5-15 seconds per image

Send your images or [⬅️ Back]
"""

TOOL_INSTRUCTION_MERGE = """🧩 Merge PDFs

Send multiple PDFs to combine them.

How it works:
1. Send first PDF
2. Send 2nd, 3rd, etc.
3. Tap "Done" when finished
4. I'll merge them instantly

Send first PDF or [⬅️ Back]
"""

TOOL_INSTRUCTION_SPLIT = """✂️ Split PDF

Send a PDF. Choose which pages to extract.

Options:
• All pages (full copy)
• Specific range (pages 1-5)
• Custom selection

Send your PDF or [⬅️ Back]
"""

TOOL_INSTRUCTION_COMPRESS = """🗜️ Compress PDF

Send a PDF. I'll shrink it by 50-80%.

• Keeps high quality ✓
• Perfect for sharing
• Reduces storage space

Send your PDF or [⬅️ Back]
"""

FEATURE_SUGGESTION_AFTER_CONVERT = """💡 What's next?

🗜️ Compress (save 70%)  •  ✂️ Split pages  •  📤 Share online

[  🗜️ Compress  ]  [  ↩️ Again  ]  [  ❌ Skip  ]
"""

FEATURE_SUGGESTION_AFTER_COMPRESS = """💡 Perfect for sharing!

📤 It's way smaller now!
Ideal for: Email • Chat • Cloud • Sharing

[  📤 Share  ]  [  📥 Download  ]  [  🏠 Done  ]
"""

FEATURE_SUGGESTION_AFTER_MERGE = """💡 Merged successfully!

What's next?
🗜️ Compress  •  ✂️ Rearrange  •  🏠 Done

[  🗜️ Compress  ]  [  ↩️ Merge Again  ]  [  🏠 Menu  ]
"""

FEATURE_SUGGESTION_AFTER_SPLIT = """💡 Pages extracted!

Ready to:
📥 Download all  •  ✂️ Split more  •  🏠 Done

[  📥 Download  ]  [  ↩️ Split Again  ]  [  🏠 Back  ]
"""

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
