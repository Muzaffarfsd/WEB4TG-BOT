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
        "services": "🏷 Услуги и цены",
        "portfolio": "🖼 Портфолио",
        "calculator": "🧮 Калькулятор",
        "ai_agent": "🤖 AI-консультант",
        "payment": "💳 Оплата",
        "bonuses": "🎁 Бонусы",
        "testimonials": "⭐ Отзывы клиентов",
        "contact_manager": "👨‍💼 Связаться с менеджером",
        "welcome": "Привет! 👋 Я Алекс, AI-консультант WEB4TG Studio.\n\nМы создаём Telegram Mini Apps для бизнеса. Чем могу помочь?",
        "rate_limit": "⏳ Пожалуйста, не отправляйте сообщения так быстро.",
        "error": "Произошла ошибка. Попробуйте ещё раз.",
        "handoff_request": "📞 Запрос на связь с менеджером отправлен!",
        "handoff_reason": "Причина",
        "lang_detected": "🌐 Язык определён автоматически: Русский",
        "lang_changed": "🌐 Язык изменён на: ",
    },
    "en": {
        "services": "🏷 Services & Pricing",
        "portfolio": "🖼 Portfolio",
        "calculator": "🧮 Calculator",
        "ai_agent": "🤖 AI Consultant",
        "payment": "💳 Payment",
        "bonuses": "🎁 Bonuses",
        "testimonials": "⭐ Client Reviews",
        "contact_manager": "👨‍💼 Contact Manager",
        "welcome": "Hello! 👋 I'm Alex, AI consultant at WEB4TG Studio.\n\nWe build Telegram Mini Apps for businesses. How can I help?",
        "rate_limit": "⏳ Please don't send messages so quickly.",
        "error": "An error occurred. Please try again.",
        "handoff_request": "📞 Manager contact request sent!",
        "handoff_reason": "Reason",
        "lang_detected": "🌐 Language detected: English",
        "lang_changed": "🌐 Language changed to: ",
    },
    "uz": {
        "services": "🏷 Xizmatlar va narxlar",
        "portfolio": "🖼 Portfolio",
        "calculator": "🧮 Kalkulyator",
        "ai_agent": "🤖 AI maslahatchi",
        "payment": "💳 To'lov",
        "bonuses": "🎁 Bonuslar",
        "testimonials": "⭐ Mijozlar sharhlari",
        "contact_manager": "👨‍💼 Menejer bilan bog'lanish",
        "welcome": "Salom! 👋 Men Alex, WEB4TG Studio AI maslahatchisiman.\n\nBiz biznes uchun Telegram Mini Apps yaratamiz. Qanday yordam bera olaman?",
        "rate_limit": "⏳ Iltimos, xabarlarni tez-tez yubormang.",
        "error": "Xatolik yuz berdi. Qayta urinib ko'ring.",
        "handoff_request": "📞 Menejer bilan bog'lanish so'rovi yuborildi!",
        "handoff_reason": "Sabab",
        "lang_detected": "🌐 Til aniqlandi: O'zbek",
        "lang_changed": "🌐 Til o'zgartirildi: ",
    },
    "kz": {
        "services": "🏷 Қызметтер мен бағалар",
        "portfolio": "🖼 Портфолио",
        "calculator": "🧮 Калькулятор",
        "ai_agent": "🤖 AI кеңесші",
        "payment": "💳 Төлем",
        "bonuses": "🎁 Бонустар",
        "testimonials": "⭐ Клиент пікірлері",
        "contact_manager": "👨‍💼 Менеджермен байланысу",
        "welcome": "Сәлем! 👋 Мен Алекс, WEB4TG Studio AI кеңесшісімін.\n\nБіз бизнес үшін Telegram Mini Apps жасаймыз. Қалай көмектесе аламын?",
        "rate_limit": "⏳ Хабарларды тез жібермеңіз.",
        "error": "Қате орын алды. Қайта көріңіз.",
        "handoff_request": "📞 Менеджермен байланысу сұрауы жіберілді!",
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
