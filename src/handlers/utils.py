import asyncio
import logging
import os
import re
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
            await asyncio.sleep(3.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Typing action error: {e}")


async def send_record_voice_action(chat, duration: float = 60.0):
    try:
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await chat.send_action(ChatAction.RECORD_VOICE)
            await asyncio.sleep(3.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Record voice action error: {e}")


def _get_time_greeting() -> dict:
    from datetime import datetime, timezone, timedelta
    moscow_tz = timezone(timedelta(hours=3))
    hour = datetime.now(moscow_tz).hour
    if 5 <= hour < 12:
        return {"ru": "Доброе утро", "en": "Good morning", "uk": "Доброго ранку", "period": "morning"}
    elif 12 <= hour < 18:
        return {"ru": "Добрый день", "en": "Good afternoon", "uk": "Добрий день", "period": "afternoon"}
    elif 18 <= hour < 23:
        return {"ru": "Добрый вечер", "en": "Good evening", "uk": "Добрий вечір", "period": "evening"}
    else:
        return {"ru": "Доброй ночи", "en": "Hey there", "uk": "Доброї ночі", "period": "night"}


def get_welcome_message(lang: str, name: str, is_returning: bool = False, returning_context: str = None) -> str:
    tg = _get_time_greeting()

    if is_returning:
        if lang == "uk":
            ctx = returning_context or "Є кілька свіжих кейсів, які можуть вас зацікавити 👀"
            return (
                f"{tg['uk']}{name}! Як я радий вас бачити знову 🤝\n\n"
                f"{ctx}\n\n"
                f"Що нового у вашому бізнесі? Може, час масштабуватись?"
            )
        elif lang == "en":
            ctx = returning_context or "We've shipped some exciting projects since your last visit 👀"
            return (
                f"{tg['en']}{name}! So good to see you back 🤝\n\n"
                f"{ctx}\n\n"
                f"What's new on your end? Maybe it's time to level up?"
            )
        else:
            ctx = returning_context or "У нас тут пара свежих кейсов, которые могут вас заинтересовать 👀"
            return (
                f"{tg['ru']}{name}! Как же рад вас снова видеть 🤝\n\n"
                f"{ctx}\n\n"
                f"Что нового в вашем бизнесе? Может, пора масштабироваться?"
            )

    if lang == "uk":
        return (
            f"{tg['uk']}{name}! Я Алекс із WEB4TG Studio — ми запустили 200+ Mini Apps для бізнесу з 15 країн.\n\n"
            f"Наші клієнти збільшують продажі в Telegram у середньому на 40% за перший місяць.\n\n"
            f"Пишіть текстом або надсилайте голосові — спілкуємось як вам зручно)\n\n"
            f"Цікаво дізнатись, чим ви займаєтесь — розкажете?"
        )
    elif lang == "en":
        return (
            f"{tg['en']}{name}! I'm Alex from WEB4TG Studio — we've launched 200+ Mini Apps for businesses across 15 countries.\n\n"
            f"Our clients typically see a 40% sales boost in Telegram within the first month.\n\n"
            f"Feel free to type or send voice messages — whatever's comfortable)\n\n"
            f"I'd love to hear about your business — what do you do?"
        )
    else:
        return (
            f"{tg['ru']}{name}! Я Алекс из WEB4TG Studio — мы запустили 200+ Mini Apps для бизнеса из 15 стран.\n\n"
            f"Наши клиенты в среднем увеличивают продажи в Telegram на 40% за первый месяц.\n\n"
            f"Пишите текстом или голосовыми — общаемся как вам удобно)\n\n"
            f"Интересно узнать, чем вы занимаетесь — расскажете?"
        )


WELCOME_MESSAGES = {
    "ru": """Привет{name}! Я Алекс из WEB4TG Studio — мы запустили 200+ Mini Apps для бизнеса из 15 стран.

Наши клиенты в среднем увеличивают продажи в Telegram на 40% за первый месяц.

Пишите текстом или голосовыми — общаемся как вам удобно)

Интересно узнать, чем вы занимаетесь — расскажете?""",
    "en": """Hey{name}! I'm Alex from WEB4TG Studio — we've launched 200+ Mini Apps for businesses across 15 countries.

Our clients typically see a 40% sales boost in Telegram within the first month.

Feel free to type or send voice messages — whatever's comfortable)

I'd love to hear about your business — what do you do?""",
    "uk": """Привіт{name}! Я Алекс із WEB4TG Studio — ми запустили 200+ Mini Apps для бізнесу з 15 країн.

Наші клієнти збільшують продажі в Telegram у середньому на 40% за перший місяць.

Пишіть текстом або надсилайте голосові — спілкуємось як вам зручно)

Цікаво дізнатись, чим ви займаєтесь — розкажете?""",
}


ABBREVIATION_MAP = {
    "ROI": "ар-о-ай",
    "CRM": "си-ар-эм",
    "UX": "ю-экс",
    "UI": "ю-ай",
    "UX/UI": "ю-экс ю-ай",
    "API": "эй-пи-ай",
    "SaaS": "сас",
    "MVP": "эм-ви-пи",
    "KPI": "кей-пи-ай",
    "SEO": "сео",
    "SMM": "эс-эм-эм",
    "B2B": "би-ту-би",
    "B2C": "би-ту-си",
    "IT": "ай-ти",
    "FAQ": "эф-эй-кью",
    "PDF": "пи-ди-эф",
    "AI": "эй-ай",
    "TG": "тэ-гэ",
    "Mini App": "мини-апп",
    "Mini Apps": "мини-аппс",
    "Web App": "веб-апп",
    "WEB4TG": "WEB4TG",
    "HTML": "эйч-ти-эм-эл",
    "CSS": "си-эс-эс",
    "JS": "джей-эс",
    "QR": "кью-ар",
    "NDA": "эн-ди-эй",
    "ТЗ": "тэ-зэ",
    "CMS": "си-эм-эс",
    "SDK": "эс-ди-кей",
    "ERP": "и-ар-пи",
    "PR": "пи-ар",
    "HR": "эйч-ар",
    "ИП": "ай-пи",
    "ООО": "о-о-о",
    "ИНН": "и-эн-эн",
    "CDEK": "сдэк",
    "Telegram": "Телегра́м",
    "WhatsApp": "Вотсапп",
    "Instagram": "Инстаграм",
    "YouTube": "Ютуб",
    "Google": "Гугл",
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
    "подписка": "подпи́ска",
    "интеграция": "интегра́ция",
    "аналитика": "анали́тика",
    "монетизация": "монетиза́ция",
    "конверсия": "конве́рсия",
    "шаблон": "шабло́н",
    "платёж": "платёж",
    "оплата": "опла́та",
    "скидка": "ски́дка",
    "тариф": "тари́ф",
    "портфолио": "портфо́лио",
    "калькулятор": "калькуля́тор",
    "консультант": "консульта́нт",
    "автоматизация": "автоматиза́ция",
    "уведомление": "уведомле́ние",
    "бронирование": "брони́рование",
    "доставка": "доста́вка",
    "ресторан": "рестора́н",
    "фитнес": "фи́тнес",
    "продвижение": "продвиже́ние",
    "сообщество": "соо́бщество",
    "преимущество": "преиму́щество",
    "обслуживание": "обслу́живание",
    "предложение": "предложе́ние",
    "приветствие": "приве́тствие",
    "потенциал": "потенциа́л",
    "программист": "программи́ст",
    "разработчик": "разрабо́тчик",
    "технология": "техноло́гия",
    "платформа": "платфо́рма",
    "инструмент": "инструме́нт",
    "обновление": "обновле́ние",
    "функциональность": "функциона́льность",
    "архитектура": "архитекту́ра",
    "производительность": "производи́тельность",
    "масштабирование": "масштаби́рование",
    "рентабельность": "рента́бельность",
    "окупаемость": "окупа́емость",
}


ONES = {
    0: '', 1: 'одна', 2: 'две', 3: 'три', 4: 'четыре', 5: 'пять',
    6: 'шесть', 7: 'семь', 8: 'восемь', 9: 'девять', 10: 'десять',
    11: 'одиннадцать', 12: 'двенадцать', 13: 'тринадцать', 14: 'четырнадцать',
    15: 'пятнадцать', 16: 'шестнадцать', 17: 'семнадцать', 18: 'восемнадцать', 19: 'девятнадцать',
}
ONES_MASC = {1: 'один', 2: 'два'}
TENS = {
    2: 'двадцать', 3: 'тридцать', 4: 'сорок', 5: 'пятьдесят',
    6: 'шестьдесят', 7: 'семьдесят', 8: 'восемьдесят', 9: 'девяносто',
}
HUNDREDS = {
    1: 'сто', 2: 'двести', 3: 'триста', 4: 'четыреста', 5: 'пятьсот',
    6: 'шестьсот', 7: 'семьсот', 8: 'восемьсот', 9: 'девятьсот',
}


def _number_to_words_russian(n: int) -> str:
    if n == 0:
        return 'ноль'
    if n < 0:
        return 'минус ' + _number_to_words_russian(-n)

    parts = []

    if n >= 1_000_000:
        millions = n // 1_000_000
        n %= 1_000_000
        m_word = _small_number_to_words(millions, masculine=True)
        if millions % 10 == 1 and millions % 100 != 11:
            parts.append(m_word + ' миллион')
        elif 2 <= millions % 10 <= 4 and not (12 <= millions % 100 <= 14):
            parts.append(m_word + ' миллиона')
        else:
            parts.append(m_word + ' миллионов')

    if n >= 1000:
        thousands = n // 1000
        n %= 1000
        t_word = _small_number_to_words(thousands, masculine=False)
        if thousands % 10 == 1 and thousands % 100 != 11:
            parts.append(t_word + ' тысяча')
        elif 2 <= thousands % 10 <= 4 and not (12 <= thousands % 100 <= 14):
            parts.append(t_word + ' тысячи')
        else:
            parts.append(t_word + ' тысяч')

    if n > 0:
        parts.append(_small_number_to_words(n, masculine=True))

    return ' '.join(parts).strip()


def _small_number_to_words(n: int, masculine: bool = True) -> str:
    if n == 0:
        return ''
    parts = []
    if n >= 100:
        parts.append(HUNDREDS[n // 100])
        n %= 100
    if 10 <= n <= 19:
        parts.append(ONES[n])
        return ' '.join(parts)
    if n >= 20:
        parts.append(TENS[n // 10])
        n %= 10
    if 1 <= n <= 9:
        if masculine and n in ONES_MASC:
            parts.append(ONES_MASC[n])
        else:
            parts.append(ONES[n])
    return ' '.join(parts)


def numbers_to_words(text: str) -> str:
    def replace_number(match):
        num_str = match.group(0).replace(' ', '').replace('\u00a0', '')
        try:
            n = int(num_str)
            if n > 10_000_000 or n < 0:
                return match.group(0)
            return _number_to_words_russian(n)
        except ValueError:
            return match.group(0)

    result = re.sub(r'\d[\d\s\u00a0]*\d', replace_number, text)
    result = re.sub(r'(?<!\w)\d+(?!\w)', replace_number, result)
    return result


def naturalize_speech(text: str) -> str:
    result = text
    result = re.sub(r'(\d+)\s*₽', lambda m: m.group(1) + ' рублей', result)
    result = re.sub(r'(\d+)\s*%', lambda m: m.group(1) + ' процентов', result)
    result = re.sub(r'\+\s*(\d)', lambda m: 'плюс ' + m.group(1), result)
    result = result.replace(' / ', ' или ')
    result = re.sub(r'(\d+)-(\d+)', lambda m: m.group(1) + ' — ' + m.group(2), result)
    result = re.sub(r'\bтел\.', 'телефон', result)
    result = re.sub(r'\bдоп\.', 'дополнительный', result)
    result = re.sub(r'\bнапр\.', 'например', result)
    result = re.sub(r'\bт\.д\.', 'так далее', result)
    result = re.sub(r'\bт\.п\.', 'тому подобное', result)
    result = re.sub(r'\bи т\.д\.', 'и так далее', result)
    result = re.sub(r'\bи т\.п\.', 'и тому подобное', result)
    result = re.sub(r'\bруб\.', 'рублей', result)
    result = re.sub(r'\bмес\.', 'месяц', result)
    result = re.sub(r'\bмин\.', 'минут', result)
    return result


def expand_abbreviations(text: str) -> str:
    result = text
    for abbr, pronunciation in sorted(ABBREVIATION_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.compile(r'\b' + re.escape(abbr) + r'\b')
        result = pattern.sub(pronunciation, result)
    return result


def apply_stress_marks(text: str) -> str:
    result = text
    for word, stressed in STRESS_DICTIONARY.items():
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub(stressed, result)
    return result


def get_broadcast_audience_keyboard(counts: dict):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📤 Всем ({counts.get('all', 0)})", callback_data="bc_audience_all")],
        [InlineKeyboardButton(f"🔥 Горячим ({counts.get('hot', 0)})", callback_data="bc_audience_hot"),
         InlineKeyboardButton(f"🌡 Тёплым ({counts.get('warm', 0)})", callback_data="bc_audience_warm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="bc_cancel")]
    ])
