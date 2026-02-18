"""Multi-language support: auto-detection, localized prompts and buttons."""

import re
import logging
from typing import Optional, Dict

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"ru", "en", "uz", "kz"}
DEFAULT_LANGUAGE = "ru"

LANGUAGE_MARKERS = {
    "en": [
        r'\b(hello|hi|hey|how|what|where|when|why|please|thank|thanks|want|need|can|could|would|price|cost|app|website|help|great|good|ok|yes|no)\b',
    ],
    "uz": [
        r'\b(salom|rahmat|narx|qancha|kerak|dastur|ilova|men|biz|qilish|yordam|ha|yoq|yaxshi|keling)\b',
    ],
    "kz": [
        r"[\u04d8\u04e8\u04b0\u04a2\u0492\u049a\u04ae\u04ba\u04d9\u04e9\u04b1\u04a3\u0493\u049b\u04af\u04bb]",
        r'\b(сәлем|рахмет|баға|қанша|керек|бағдарлама|қосымша|мен|біз|жасау|көмек|иә|жоқ|жақсы)\b',
    ],
}

UI_STRINGS = {
    "ru": {
        "services": "💡 Что мы делаем",
        "portfolio": "📊 Кейсы с результатами",
        "calculator": "💰 Рассчитать стоимость",
        "ai_agent": "🤖 Спросить AI",
        "payment": "💳 Оплата",
        "bonuses": "🎁 Мои привилегии",
        "testimonials": "🏆 Что говорят клиенты",
        "contact_manager": "💬 Написать менеджеру",
        "welcome": "Привет! 👋 Я Алекс из WEB4TG Studio — 200+ запущенных Mini Apps, клиенты из 15 стран.\n\nРасскажите о вашем бизнесе — подберём решение.",
        "rate_limit": "⏳ Секундочку — обрабатываю ваш предыдущий запрос. Скоро отвечу!",
        "error": "Упс, что-то пошло не так. Попробуйте ещё раз или напишите менеджеру — мы поможем.",
        "handoff_request": "✅ Готово! Менеджер получил ваш запрос и скоро свяжется с вами.",
        "handoff_reason": "Причина",
        "lang_detected": "🌐 Язык определён автоматически: Русский",
        "lang_changed": "🌐 Язык изменён на: ",
    },
    "en": {
        "services": "💡 What We Build",
        "portfolio": "📊 Case Studies",
        "calculator": "💰 Get a Quote",
        "ai_agent": "🤖 Ask AI",
        "payment": "💳 Payment",
        "bonuses": "🎁 My Perks",
        "testimonials": "🏆 Client Success Stories",
        "contact_manager": "💬 Message a Manager",
        "welcome": "Hey! 👋 I'm Alex from WEB4TG Studio — 200+ Mini Apps launched for businesses in 15 countries.\n\nTell me about your business and I'll find the right solution.",
        "rate_limit": "⏳ One moment — I'm processing your previous request. I'll reply shortly!",
        "error": "Oops, something went wrong. Please try again or reach out to a manager — we'll help.",
        "handoff_request": "✅ Done! A manager received your request and will reach out shortly.",
        "handoff_reason": "Reason",
        "lang_detected": "🌐 Language detected: English",
        "lang_changed": "🌐 Language changed to: ",
    },
    "uz": {
        "services": "💡 Biz nima qilamiz",
        "portfolio": "📊 Natijali loyihalar",
        "calculator": "💰 Narxni hisoblash",
        "ai_agent": "🤖 AI dan so'rash",
        "payment": "💳 To'lov",
        "bonuses": "🎁 Mening imtiyozlarim",
        "testimonials": "🏆 Mijozlar fikrlari",
        "contact_manager": "💬 Menejerga yozish",
        "welcome": "Salom! 👋 Men Alex, WEB4TG Studio — 15 mamlakatdan 200+ Mini Apps ishga tushirganmiz.\n\nBiznesingiz haqida ayting — yechim topamiz.",
        "rate_limit": "⏳ Bir daqiqa — oldingi so'rovingizni qayta ishlamoqdaman. Tez orada javob beraman!",
        "error": "Xatolik yuz berdi. Qayta urinib ko'ring yoki menejerga yozing — yordam beramiz.",
        "handoff_request": "✅ Tayyor! Menejer so'rovingizni oldi va tez orada bog'lanadi.",
        "handoff_reason": "Sabab",
        "lang_detected": "🌐 Til aniqlandi: O'zbek",
        "lang_changed": "🌐 Til o'zgartirildi: ",
    },
    "kz": {
        "services": "💡 Біз не жасаймыз",
        "portfolio": "📊 Нәтижелі кейстер",
        "calculator": "💰 Бағаны есептеу",
        "ai_agent": "🤖 AI-дан сұрау",
        "payment": "💳 Төлем",
        "bonuses": "🎁 Менің артықшылықтарым",
        "testimonials": "🏆 Клиенттер не дейді",
        "contact_manager": "💬 Менеджерге жазу",
        "welcome": "Сәлем! 👋 Мен Алекс, WEB4TG Studio — 15 елден 200+ Mini Apps іске қостық.\n\nБизнесіңіз туралы айтыңыз — шешім табамыз.",
        "rate_limit": "⏳ Бір сәт — алдыңғы сұрауыңызды өңдеп жатырмын. Жақында жауап беремін!",
        "error": "Қателік орын алды. Қайта көріңіз немесе менеджерге жазыңыз — көмектесеміз.",
        "handoff_request": "✅ Дайын! Менеджер сұрауыңызды алды және жақында хабарласады.",
        "handoff_reason": "Себеп",
        "lang_detected": "🌐 Тіл анықталды: Қазақ",
        "lang_changed": "🌐 Тіл өзгертілді: ",
    },
}

LANG_PROMPT_SUFFIXES = {
    "ru": "",
    "en": "\n\n[IMPORTANT: The client speaks English. Respond in English. Keep your sales expertise but communicate in English.]",
    "uz": "\n\n[IMPORTANT: The client speaks Uzbek. Respond in Uzbek (O'zbek tili). Keep your sales expertise but communicate in Uzbek.]",
    "kz": "\n\n[IMPORTANT: The client speaks Kazakh. Respond in Kazakh (Қазақ тілі). Keep your sales expertise but communicate in Kazakh.]",
}


def detect_language(text: str) -> str:
    if not text or len(text.strip()) < 3:
        return DEFAULT_LANGUAGE

    text_lower = text.lower().strip()

    for lang in ["kz", "uz", "en"]:
        for pattern in LANGUAGE_MARKERS[lang]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return lang

    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))

    if has_cyrillic and not has_latin:
        return "ru"
    if has_latin and not has_cyrillic:
        return "en"

    return DEFAULT_LANGUAGE


def get_user_language(user_id: int) -> str:
    if not DATABASE_URL:
        return DEFAULT_LANGUAGE
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT language FROM client_profiles WHERE telegram_id = %s",
                    (user_id,)
                )
                row = cur.fetchone()
                if row and row[0] and row[0] in SUPPORTED_LANGUAGES:
                    return row[0]
    except Exception:
        pass
    return DEFAULT_LANGUAGE


def set_user_language(user_id: int, language: str):
    if language not in SUPPORTED_LANGUAGES:
        return
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO client_profiles (telegram_id, language)
                    VALUES (%s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE SET language = %s
                """, (user_id, language, language))
    except Exception as e:
        logger.debug(f"Failed to set user language: {e}")


def get_string(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    lang_strings = UI_STRINGS.get(language, UI_STRINGS[DEFAULT_LANGUAGE])
    return lang_strings.get(key, UI_STRINGS[DEFAULT_LANGUAGE].get(key, key))


def get_prompt_suffix(language: str) -> str:
    return LANG_PROMPT_SUFFIXES.get(language, "")


def detect_and_remember_language(user_id: int, text: str) -> str:
    detected = detect_language(text)
    current = get_user_language(user_id)

    if detected != current and detected != DEFAULT_LANGUAGE:
        set_user_language(user_id, detected)
        return detected

    return current
