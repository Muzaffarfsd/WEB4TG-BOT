"""Context-aware smart buttons after AI responses.

Generates dynamic action buttons based on conversation context,
funnel stage, detected intents, and propensity score.
"""

import logging
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


BUTTON_SETS = {
    "awareness": [
        ("🎯 Подобрать решение", "start_quiz"),
        ("📊 Примеры работ", "menu_portfolio"),
        ("💰 Цены", "menu_calculator"),
    ],
    "interest": [
        ("🧮 Рассчитать стоимость", "menu_calculator"),
        ("📋 Составить бриф", "start_brief"),
        ("⭐ Отзывы клиентов", "menu_testimonials"),
    ],
    "consideration": [
        ("📋 Составить бриф", "start_brief"),
        ("📦 Сравнить пакеты", "compare_packages"),
        ("👨‍💼 Связаться с менеджером", "request_manager"),
    ],
    "decision": [
        ("💳 Оплатить", "smart_payment"),
        ("📄 Договор", "smart_contract"),
        ("👨‍💼 Менеджер", "request_manager"),
    ],
    "converted": [
        ("📊 Мой кабинет", "my_dashboard"),
        ("👥 Пригласить друга", "referral_info"),
        ("🎁 Бонусы", "loyalty_menu"),
    ],
}

INTENT_BUTTONS = {
    "price_inquiry": [("🧮 Калькулятор", "menu_calculator"), ("📦 Пакеты", "compare_packages")],
    "portfolio_request": [("📊 Портфолио", "menu_portfolio"), ("⭐ Отзывы", "menu_testimonials")],
    "ready_to_buy": [("💳 Оплата", "smart_payment"), ("📋 Бриф", "start_brief")],
    "objection": [("📊 Кейсы", "menu_portfolio"), ("💬 Подробнее", "quiz_to_ai")],
    "booking": [("📅 Консультация", "book_consult"), ("👨‍💼 Менеджер", "request_manager")],
    "competitor": [("📊 Сравнение пакетов", "compare_packages"), ("⭐ Отзывы", "menu_testimonials")],
}


def get_context_buttons(
    user_id: int,
    ai_response: str = "",
    funnel_stage: str = "awareness",
    detected_intents: Optional[List[str]] = None,
    propensity_score: int = 0,
) -> Optional[InlineKeyboardMarkup]:
    try:
        return _build_context_buttons(user_id, ai_response, funnel_stage, detected_intents, propensity_score)
    except Exception as e:
        logger.error(f"Smart buttons error for user {user_id}: {e}")
        return None


def _build_context_buttons(
    user_id: int,
    ai_response: str,
    funnel_stage: str,
    detected_intents: Optional[List[str]],
    propensity_score: int,
) -> Optional[InlineKeyboardMarkup]:
    buttons = []

    if detected_intents:
        for intent in detected_intents[:2]:
            if intent in INTENT_BUTTONS:
                for label, data in INTENT_BUTTONS[intent]:
                    btn = InlineKeyboardButton(label, callback_data=data)
                    buttons.append(btn)
                break

    if not buttons:
        stage_buttons = BUTTON_SETS.get(funnel_stage, BUTTON_SETS["awareness"])
        for label, data in stage_buttons[:3]:
            buttons.append(InlineKeyboardButton(label, callback_data=data))

    if propensity_score >= 70 and funnel_stage not in ("decision", "converted"):
        buttons = [
            InlineKeyboardButton(
                "🔥 Оставить заявку", callback_data="menu_lead",
                **styled_button_api_kwargs(style="constructive")
            )
        ] + buttons[:2]

    rows = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i+2])

    return InlineKeyboardMarkup(rows) if rows else None


def detect_response_intents(ai_response: str) -> List[str]:
    intents = []
    lower = ai_response.lower()

    if any(w in lower for w in ["цен", "стоим", "бюджет", "₽", "рублей", "тариф"]):
        intents.append("price_inquiry")
    if any(w in lower for w in ["портфол", "кейс", "пример", "работ"]):
        intents.append("portfolio_request")
    if any(w in lower for w in ["заказ", "оплат", "купи", "оформ"]):
        intents.append("ready_to_buy")
    if any(w in lower for w in ["конкурент", "фрилансер", "агентств", "сравни"]):
        intents.append("competitor")
    if any(w in lower for w in ["встреч", "консультац", "созвон", "звонок"]):
        intents.append("booking")
    if any(w in lower for w in ["дорого", "сомне", "не увер", "гарант"]):
        intents.append("objection")

    return intents
