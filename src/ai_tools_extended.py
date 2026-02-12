"""Extended AI tools: case study generator, AI coach, KP generator.

Advanced AI-powered features that leverage Gemini for
generating personalized content and coaching.
"""

import logging
from typing import Optional, Dict, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


def build_case_study_prompt(industry: str, features: str, budget: str) -> str:
    return (
        f"Ты — маркетолог WEB4TG Studio. Создай убедительный кейс-стади для клиента.\n\n"
        f"Отрасль: {industry}\n"
        f"Функции: {features}\n"
        f"Бюджет: {budget}\n\n"
        f"Формат кейса:\n"
        f"1. Название проекта (придумай реалистичное)\n"
        f"2. Проблема клиента (2-3 предложения)\n"
        f"3. Решение WEB4TG Studio (3-4 пункта)\n"
        f"4. Результаты с цифрами (конверсия, заказы, экономия)\n"
        f"5. Цитата довольного клиента\n\n"
        f"Пиши на русском, убедительно, с конкретными цифрами. 250-400 символов."
    )


def build_kp_prompt(
    client_name: str,
    business_type: str,
    features: str,
    budget: str,
    timeline: str,
) -> str:
    return (
        f"Ты — коммерческий директор WEB4TG Studio. Создай краткое коммерческое предложение.\n\n"
        f"Клиент: {client_name}\n"
        f"Тип бизнеса: {business_type}\n"
        f"Требуемые функции: {features}\n"
        f"Бюджет: {budget}\n"
        f"Желаемые сроки: {timeline}\n\n"
        f"Формат КП:\n"
        f"1. Заголовок с названием клиента\n"
        f"2. Понимание задачи (2-3 предложения)\n"
        f"3. Предлагаемое решение (3-5 пунктов)\n"
        f"4. Стоимость и сроки\n"
        f"5. Почему WEB4TG Studio (2-3 преимущества)\n"
        f"6. Следующие шаги\n\n"
        f"Пиши на русском, профессионально, с конкретными цифрами. 400-600 символов."
    )


def build_coach_prompt(user_context: str) -> str:
    return (
        f"Ты — AI-коуч по продажам WEB4TG Studio. Проанализируй диалог с клиентом "
        f"и дай 3 рекомендации менеджеру, как улучшить конверсию.\n\n"
        f"Контекст диалога:\n{user_context}\n\n"
        f"Формат:\n"
        f"1. Оценка текущей ситуации (1-2 предложения)\n"
        f"2. Рекомендация 1 с конкретным действием\n"
        f"3. Рекомендация 2 с конкретным действием\n"
        f"4. Рекомендация 3 с конкретным действием\n\n"
        f"Будь конкретен, давай actionable советы."
    )


def get_ai_coach_view(analysis: str = "") -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        "🧠 <b>AI Sales Coach</b>\n\n"
    )

    if analysis:
        text += analysis
    else:
        text += (
            "AI-коуч анализирует ваши диалоги и даёт рекомендации "
            "по улучшению конверсии.\n\n"
            "Нажмите кнопку для анализа последних диалогов."
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Анализировать диалоги", callback_data="ai_coach_analyze")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])

    return text, keyboard


def get_case_study_result(case_text: str, industry: str) -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        f"📋 <b>AI-сгенерированный кейс</b>\n"
        f"<i>Отрасль: {industry}</i>\n\n"
        f"{case_text}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Сгенерировать ещё", callback_data=f"gen_case_{industry}")],
        [InlineKeyboardButton(
            "📋 Заказать проект", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard
