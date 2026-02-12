"""Portfolio showcase with before/after metrics and ROI data.

World-class portfolio presentation with real business metrics,
interactive case selection, and industry filtering.
"""

import logging
from typing import List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


PORTFOLIO_CASES = [
    {
        "id": "ecommerce_radiance",
        "name": "Radiance — Магазин одежды",
        "industry": "shop",
        "icon": "🛒",
        "description": "Mini App для бренда одежды с каталогом 500+ товаров",
        "features": ["Каталог", "Корзина", "Оплата", "Push", "Избранное"],
        "timeline": "14 дней",
        "before": {"orders_day": 10, "avg_check": 3200, "conversion": 1.8},
        "after": {"orders_day": 14, "avg_check": 3800, "conversion": 2.5},
        "roi_months": 2.5,
        "testimonial": "Заказы выросли на 40%, а средний чек — на 18%. Окупили за 2.5 месяца.",
    },
    {
        "id": "restaurant_fresh",
        "name": "Fresh Kitchen — Доставка еды",
        "industry": "restaurant",
        "icon": "🍽",
        "description": "Система онлайн-заказов с доставкой и трекингом",
        "features": ["Меню", "Корзина", "Оплата", "Доставка", "Push"],
        "timeline": "10 дней",
        "before": {"orders_day": 30, "avg_check": 1600, "conversion": 2.0},
        "after": {"orders_day": 42, "avg_check": 1900, "conversion": 3.1},
        "roi_months": 1.8,
        "testimonial": "+40% заказов и -60% времени обработки. Клиенты довольны быстрой доставкой.",
    },
    {
        "id": "beauty_glowup",
        "name": "GlowUp Studio — Салон красоты",
        "industry": "beauty",
        "icon": "💇‍♀️",
        "description": "Онлайн-запись с автоматическими напоминаниями",
        "features": ["Запись", "Авторизация", "Push", "Лояльность", "Отзывы"],
        "timeline": "12 дней",
        "before": {"orders_day": 8, "avg_check": 2200, "conversion": 3.0},
        "after": {"orders_day": 12, "avg_check": 2600, "conversion": 4.2},
        "roi_months": 2.0,
        "testimonial": "No-show снизился на 45%. Клиенты сами записываются через Telegram.",
    },
    {
        "id": "fitness_fitlife",
        "name": "FitLife — Фитнес-клуб",
        "industry": "fitness",
        "icon": "🏋️",
        "description": "Подписки, расписание и трекинг прогресса",
        "features": ["Подписки", "Расписание", "Прогресс", "Push", "Авторизация"],
        "timeline": "16 дней",
        "before": {"orders_day": 5, "avg_check": 4500, "conversion": 2.5},
        "after": {"orders_day": 8, "avg_check": 5200, "conversion": 3.8},
        "roi_months": 2.2,
        "testimonial": "Удержание клиентов +60%. Трекинг прогресса мотивирует людей продолжать.",
    },
    {
        "id": "medical_medplus",
        "name": "МедЦентр Плюс — Клиника",
        "industry": "medical",
        "icon": "🏥",
        "description": "Онлайн-запись и управление расписанием врачей",
        "features": ["Запись", "Расписание", "Push", "Авторизация", "Чат"],
        "timeline": "18 дней",
        "before": {"orders_day": 15, "avg_check": 2800, "conversion": 1.5},
        "after": {"orders_day": 22, "avg_check": 3100, "conversion": 2.8},
        "roi_months": 2.5,
        "testimonial": "Сократили звонки на 70%. Пациенты записываются за 30 секунд.",
    },
    {
        "id": "education_skillhub",
        "name": "SkillHub — Онлайн-школа",
        "industry": "education",
        "icon": "📚",
        "description": "Платформа курсов с геймификацией",
        "features": ["Курсы", "Прогресс", "Геймификация", "Подписки", "Push"],
        "timeline": "20 дней",
        "before": {"orders_day": 8, "avg_check": 3500, "conversion": 2.0},
        "after": {"orders_day": 13, "avg_check": 4200, "conversion": 3.5},
        "roi_months": 1.5,
        "testimonial": "Доходимость курсов +40%. Геймификация удерживает учеников.",
    },
]


def get_portfolio_menu() -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        "🎨 <b>Портфолио WEB4TG Studio</b>\n\n"
        "Более 50 успешных проектов.\n"
        "Выберите кейс для подробностей с реальными метриками:\n"
    )

    buttons = []
    for case in PORTFOLIO_CASES:
        buttons.append([InlineKeyboardButton(
            f"{case['icon']} {case['name']}", callback_data=f"pcase_{case['id']}"
        )])

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="menu_back")])

    return text, InlineKeyboardMarkup(buttons)


def get_case_detail(case_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    case = None
    for c in PORTFOLIO_CASES:
        if c["id"] == case_id:
            case = c
            break

    if not case:
        return "Кейс не найден", InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="menu_portfolio")
        ]])

    b = case["before"]
    a = case["after"]

    orders_change = int((a["orders_day"] - b["orders_day"]) / b["orders_day"] * 100)
    check_change = int((a["avg_check"] - b["avg_check"]) / b["avg_check"] * 100)
    conv_change = round((a["conversion"] - b["conversion"]) / b["conversion"] * 100)

    features_str = " • ".join(case["features"])

    text = (
        f"{case['icon']} <b>{case['name']}</b>\n\n"
        f"📝 {case['description']}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Метрики ДО → ПОСЛЕ</b>\n\n"
        f"🛒 Заказов/день: {b['orders_day']} → <b>{a['orders_day']}</b> (+{orders_change}%)\n"
        f"💰 Средний чек: {b['avg_check']:,}₽ → <b>{a['avg_check']:,}₽</b> (+{check_change}%)\n"
        f"📈 Конверсия: {b['conversion']}% → <b>{a['conversion']}%</b> (+{conv_change}%)\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"⏱ <b>Срок:</b> {case['timeline']}\n"
        f"💵 <b>Окупаемость:</b> {case['roi_months']} мес.\n"
        f"⚡ <b>Функции:</b> {features_str}\n\n"
        f"💬 <i>«{case['testimonial']}»</i>"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Хочу такой же!", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("🧮 Калькулятор", callback_data="menu_calculator")],
        [InlineKeyboardButton("◀️ Все кейсы", callback_data="menu_portfolio")],
    ])

    return text, keyboard


def get_case_by_industry(industry: str) -> Optional[dict]:
    for case in PORTFOLIO_CASES:
        if case["industry"] == industry:
            return case
    return None
