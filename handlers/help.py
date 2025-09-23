# help.py
import logging
import re
from typing import Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.markdown import bold as hbold, code as hcode, link as hlink
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Assuming db.py for role-based help content
from database.db import get_user_role  # type: ignore

load_dotenv()

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - user_id=%(user_id)s - action=%(action)s - query=%(query)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class HelpCategory(Enum):
    """Command categories for organized help display."""
    GENERAL = "General Commands"
    ADMIN = "Admin Commands"
    PAYMENTS = "Payments & Premium"
    REFERRALS = "Referrals"
    SETTINGS = "Settings"

@dataclass
class CommandInfo:
    """Structure for command metadata."""
    name: str
    description: str
    category: HelpCategory
    usage: str
    roles: List[str]  # ['user', 'support', 'moderator', 'superadmin']
    example: Optional[str] = None
    is_hidden: bool = False

# Master command registry - dynamically generates help content
COMMAND_REGISTRY: Dict[str, CommandInfo] = {
    # General Commands
    "start": CommandInfo(
        name="start",
        description="Start the bot and begin your journey",
        category=HelpCategory.GENERAL,
        usage="/start",
        roles=["user", "support", "moderator", "superadmin"],
        example="/start"
    ),
    "help": CommandInfo(
        name="help",
        description="Show this help menu",
        category=HelpCategory.GENERAL,
        usage="/help [search_term]",
        roles=["user", "support", "moderator", "superadmin"],
        example="/help payment"
    ),
    
    # Admin Commands
    "ban": CommandInfo(
        name="ban",
        description="Ban a user from using the bot",
        category=HelpCategory.ADMIN,
        usage="/ban <user_id>",
        roles=["moderator", "superadmin"],
        example="/ban 123456"
    ),
    "unban": CommandInfo(
        name="unban",
        description="Unban a user and restore access",
        category=HelpCategory.ADMIN,
        usage="/unban <user_id>",
        roles=["moderator", "superadmin"],
        example="/unban 123456"
    ),
    "broadcast": CommandInfo(
        name="broadcast",
        description="Send message to all users",
        category=HelpCategory.ADMIN,
        usage="/broadcast <message>",
        roles=["superadmin"],
        example="/broadcast System maintenance scheduled"
    ),
    
    # Payments & Premium
    "premium": CommandInfo(
        name="premium",
        description="Manage your premium subscription",
        category=HelpCategory.PAYMENTS,
        usage="/premium",
        roles=["user", "support", "moderator", "superadmin"],
        example="/premium"
    ),
    "upgrade": CommandInfo(
        name="upgrade",
        description="Upgrade to premium plan",
        category=HelpCategory.PAYMENTS,
        usage="/upgrade",
        roles=["user", "support", "moderator", "superadmin"],
        example="/upgrade"
    ),
    
    # Referrals
    "refer": CommandInfo(
        name="refer",
        description="Generate and share your referral link",
        category=HelpCategory.REFERRALS,
        usage="/refer",
        roles=["user", "support", "moderator", "superadmin"],
        example="/refer"
    ),
    
    # Settings
    "settings": CommandInfo(
        name="settings",
        description="Configure bot preferences",
        category=HelpCategory.SETTINGS,
        usage="/settings",
        roles=["user", "support", "moderator", "superadmin"],
        example="/settings"
    ),
    
    # Hidden commands (internal use only)
    "_stats": CommandInfo(
        name="_stats",
        description="Internal statistics command",
        category=HelpCategory.ADMIN,
        usage="/_stats",
        roles=["superadmin"],
        is_hidden=True
    )
}

def validate_search_query(query: str) -> bool:
    """Validate search query input."""
    if not query:
        return False
    # Basic sanitization - allow alphanumeric, spaces, and common punctuation
    if re.match(r'^[a-zA-Z0-9\s\.\,\!\?\:\-\(\)]+$', query):
        return True
    return False

def get_user_authorized_commands(user_role: str) -> List[CommandInfo]:
    """Filter commands based on user role permissions."""
    return [
        cmd for cmd in COMMAND_REGISTRY.values() 
        if user_role in cmd.roles and not cmd.is_hidden
    ]

def search_commands(search_term: str, user_role: str) -> List[CommandInfo]:
    """Search commands by name, description, or category."""
    search_lower = search_term.lower().strip()
    authorized_cmds = get_user_authorized_commands(user_role)
    
    return [
        cmd for cmd in authorized_cmds
        if (search_lower in cmd.name.lower() or 
            search_lower in cmd.description.lower() or 
            search_lower in cmd.category.value.lower())
    ]

def format_command_help(cmd: CommandInfo, parse_mode: ParseMode = ParseMode.MARKDOWN) -> str:
    """Format individual command help with Markdown/HTML."""
    if parse_mode == ParseMode.MARKDOWN:
        formatted = f"{hbold(cmd.name)}\n"
        formatted += f"{cmd.description}\n\n"
        formatted += f"{hcode(cmd.usage)}\n"
        
        if cmd.example:
            formatted += f"\n{hcode(cmd.example)}\n"
            
        formatted += f"\n*{cmd.category.value}*\n"
        
    else:  # HTML
        formatted = f"<b>{cmd.name}</b>\n"
        formatted += f"{cmd.description}\n\n"
        formatted += f"<code>{cmd.usage}</code>\n"
        
        if cmd.example:
            formatted += f"\n<code>{cmd.example}</code>\n"
            
        formatted += f"\n<i>{cmd.category.value}</i>\n"
    
    return formatted

def generate_category_help(categories: Dict[HelpCategory, List[CommandInfo]], 
                         parse_mode: ParseMode = ParseMode.MARKDOWN) -> str:
    """Generate organized help by category."""
    help_text = "📖 *Bot Commands*\n\n" if parse_mode == ParseMode.MARKDOWN else "<b>📖 Bot Commands</b>\n\n"
    
    for category, commands in categories.items():
        if not commands:
            continue
            
        if parse_mode == ParseMode.MARKDOWN:
            help_text += f"*{category.value}*\n"
        else:
            help_text += f"<i>{category.value}</i>\n"
            
        for cmd in commands:
            help_text += f"• {format_command_help(cmd, parse_mode)}"
            help_text += "─" * 40 + "\n\n"
        
        help_text += "\n"
    
    return help_text

async def help_command_handler(message: types.Message) -> None:
    """Main /help command handler with search capability."""
    user_id = message.from_user.id
    user_role = get_user_role(user_id)
    
    # Input validation and parsing
    text_parts = message.text.split(maxsplit=1)
    search_query = text_parts[1].strip() if len(text_parts) > 1 else ""
    
    try:
        if search_query and not validate_search_query(search_query):
            await message.reply(
                "❌ Invalid search query. Please use letters, numbers, and basic punctuation.",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.warning("Invalid search query", extra={
                'user_id': user_id, 
                'action': 'help_search', 
                'query': search_query
            })
            return
        
        # Generate appropriate help content
        if search_query:
            # Search mode
            results = search_commands(search_query, user_role)
            
            if not results:
                response = f"🔍 *No results found for* `{search_query}`\n\n"
                response += "Try searching for:\n"
                response += "• payment, premium, upgrade\n• refer, referral\n• ban, broadcast\n• settings"
                logger.info("No search results", extra={
                    'user_id': user_id, 
                    'action': 'help_search', 
                    'query': search_query
                })
            else:
                response = f"🔍 *Search results for* `{search_query}`:\n\n"
                for cmd in results[:5]:  # Limit to 5 results
                    response += format_command_help(cmd, ParseMode.MARKDOWN)
                    response += "─" * 30 + "\n\n"
                
                if len(results) > 5:
                    response += f"*...and {len(results) - 5} more results*\n"
                
                logger.info("Search successful", extra={
                    'user_id': user_id, 
                    'action': 'help_search', 
                    'query': search_query, 
                    'results': len(results)
                })
                
        else:
            # Full help by category
            authorized_commands = get_user_authorized_commands(user_role)
            
            # Group by category
            categories = {}
            for cmd in authorized_commands:
                cat = cmd.category
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(cmd)
            
            # Sort categories and commands
            sorted_categories = sorted(categories.items(), key=lambda x: x[0].value)
            response = generate_category_help(dict(sorted_categories), ParseMode.MARKDOWN)
            
            logger.info("Full help requested", extra={
                'user_id': user_id, 
                'action': 'help_full', 
                'total_commands': len(authorized_commands)
            })
        
        # Send response with character limit handling
        if len(response) > 4096:  # Telegram limit
            # Split into multiple messages
            messages = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for i, msg in enumerate(messages):
                await message.reply(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            await message.reply(response, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            
    except Exception as e:
        # Error isolation
        logger.error("Help command error", exc_info=True, extra={
            'user_id': user_id, 
            'action': 'help', 
            'query': search_query
        })
        await message.reply(
            "❌ An error occurred while generating help. Please try again.",
            parse_mode=ParseMode.MARKDOWN
        )

async def command_details_handler(message: types.Message) -> None:
    """Handle detailed command information requests."""
    user_id = message.from_user.id
    user_role = get_user_role(user_id)
    
    # Extract command name from message
    command_name = message.text.replace("/help", "").strip().lstrip("/")
    
    if not command_name or len(command_name) > 20:
        await message.reply(
            "Usage: Send `/command_name` for detailed help\n\n"
            "Examples:\n"
            f"{hcode('/premium')}\n"
            f"{hcode('/ban')}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Find command
    command_info = COMMAND_REGISTRY.get(command_name.lower())
    
    if not command_info:
        await message.reply(
            f"❌ Command `{command_name}` not found.\n\n"
            "Use `/help` to see all available commands.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.warning("Unknown command requested", extra={
            'user_id': user_id, 
            'action': 'command_details', 
            'command': command_name
        })
        return
    
    # Check authorization
    if user_role not in command_info.roles:
        await message.reply(
            f"❌ You don't have permission to use `{command_name}`.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.warning("Unauthorized command access", extra={
            'user_id': user_id, 
            'action': 'command_details', 
            'command': command_name, 
            'role': user_role
        })
        return
    
    # Generate detailed help
    detailed_help = f"{hbold(command_info.name.upper())}\n\n"
    detailed_help += f"{command_info.description}\n\n"
    detailed_help += f"{hbold('Usage:')}\n{hcode(command_info.usage)}\n\n"
    
    if command_info.example:
        detailed_help += f"{hbold('Example:')}\n{hcode(command_info.example)}\n\n"
    
    detailed_help += f"{hbold('Category:')} {command_info.category.value}\n"
    detailed_help += f"{hbold('Required Role:')} {', '.join(command_info.roles)}\n"
    
    await message.reply(detailed_help, parse_mode=ParseMode.MARKDOWN)
    logger.info("Command details requested", extra={
        'user_id': user_id, 
        'action': 'command_details', 
        'command': command_name
    })

def register_help_handlers(dp: Dispatcher) -> None:
    """Register all help-related handlers."""
    # Main help command with optional search
    dp.register_message_handler(
        help_command_handler, 
        Command("help"),
        state="*"
    )
    
    # Detailed command help
    dp.register_message_handler(
        command_details_handler,
        Text(startswith=["/help "], ignore_case=True),
        state="*"
    )
    
    # Legacy command pattern support
    dp.register_message_handler(
        command_details_handler,
        lambda message: message.text and message.text.startswith("/"),
        state="*"
    )
