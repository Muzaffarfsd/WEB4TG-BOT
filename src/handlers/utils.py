import asyncio
import logging
import os
from telegram import Update
from telegram.constants import ChatAction

from src.leads import lead_manager
from src.loyalty import LoyaltySystem

logger = logging.getLogger(__name__)

loyalty_system = LoyaltySystem()

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")
if MANAGER_CHAT_ID:
    lead_manager.set_manager_chat_id(int(MANAGER_CHAT_ID))


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


WELCOME_MESSAGES = {
    "ru": """Привет{name}! Меня зовут Алекс, работаю консультантом в WEB4TG Studio.

Мы делаем Telegram Mini Apps для бизнеса — интернет-магазины, рестораны, салоны красоты и многое другое.

Кстати, можем общаться как удобно — текстом или голосовыми, мне без разницы)

Расскажите, чем занимаетесь? Посмотрим, чем можем быть полезны.""",
    "en": """Hey{name}! I'm Alex, consultant at WEB4TG Studio.

We build Telegram Mini Apps for businesses — online stores, restaurants, beauty salons and more.

By the way, feel free to text or send voice messages — whatever works for you)

So what's your business about? Let's see how we can help.""",
    "uk": """Привіт{name}! Мене звати Алекс, працюю консультантом у WEB4TG Studio.

Ми робимо Telegram Mini Apps для бізнесу — інтернет-магазини, ресторани, салони краси та багато іншого.

До речі, можемо спілкуватися як зручно — текстом або голосовими, мені без різниці)

Розкажіть, чим займаєтесь? Подивимось, чим можемо бути корисні.""",
}


STRESS_DICTIONARY = {
    "разработка": "разрабо́тка",
    "приложение": "приложе́ние",
    "приложения": "приложе́ния",
    "стоимость": "сто́имость",
    "договор": "догово́р",
    "звонит": "звони́т",
    "каталог": "катало́г",
    "маркетинг": "ма́ркетинг",
    "обеспечение": "обеспе́чение",
    "средства": "сре́дства",
    "процент": "проце́нт",
    "квартал": "кварта́л",
    "эксперт": "экспе́рт",
    "оптовый": "опто́вый",
    "украинский": "украи́нский",
    "красивее": "краси́вее",
    "мастерски": "мастерски́",
    "включит": "включи́т",
    "облегчить": "облегчи́ть",
    "углубить": "углуби́ть",
    "баловать": "балова́ть",
    "досуг": "досу́г",
    "жалюзи": "жалюзи́",
    "торты": "то́рты",
    "банты": "ба́нты",
    "шарфы": "ша́рфы",
    "порты": "по́рты",
    "склады": "скла́ды",
    "telegram": "телегра́м",
    "функционал": "функциона́л",
    "интерфейс": "интерфе́йс",
    "дизайн": "диза́йн",
    "контент": "конте́нт",
    "проект": "прое́кт",
    "клиент": "клие́нт",
    "сервис": "се́рвис",
    "бизнес": "би́знес",
    "менеджер": "ме́неджер",
    "маркетплейс": "маркетпле́йс",
}


def apply_stress_marks(text: str) -> str:
    import re
    result = text
    for word, stressed in STRESS_DICTIONARY.items():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub(stressed, result)
    return result


def get_broadcast_audience_keyboard(counts: dict):
    """Build broadcast audience selection keyboard."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📤 Всем ({counts.get('all', 0)})", callback_data="bc_audience_all")],
        [InlineKeyboardButton(f"🔥 Горячим ({counts.get('hot', 0)})", callback_data="bc_audience_hot"),
         InlineKeyboardButton(f"🌡 Тёплым ({counts.get('warm', 0)})", callback_data="bc_audience_warm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bc_cancel")]
    ])
