import asyncio
import logging
from telegram import Update
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)


async def send_typing_action(update: Update, duration: float = 4.0):
    try:
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Typing action error: {e}")


def detect_language(text: str) -> str:
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    latin_count = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    
    if cyrillic_count > latin_count:
        ukrainian_chars = sum(1 for c in text if c in 'їієґІЇЄҐ')
        if ukrainian_chars > 0:
            return 'uk'
        return 'ru'
    return 'en'


def escape_markdown(text: str) -> str:
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text
