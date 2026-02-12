"""Trial/Demo access and savings calculator.

Provides demo links, trial descriptions,
and ROI/savings calculator for clients.
"""

import logging
from typing import Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


DEMO_APPS = [
    {
        "id": "shop_demo",
        "name": "🛒 Интернет-магазин",
        "description": "Полнофункциональный демо-магазин с каталогом, корзиной и оплатой",
        "url": "https://t.me/web4tg_shop_demo_bot",
        "features": ["Каталог 50+ товаров", "Корзина", "Telegram Stars оплата", "Push"],
    },
    {
        "id": "booking_demo",
        "name": "📅 Система записи",
        "description": "Демо онлайн-записи для салонов и клиник",
        "url": "https://t.me/web4tg_booking_demo_bot",
        "features": ["Выбор мастера", "Выбор услуги", "Выбор времени", "Напоминания"],
    },
    {
        "id": "restaurant_demo",
        "name": "🍽 Ресторан/Доставка",
        "description": "Демо системы заказов с доставкой",
        "url": "https://t.me/web4tg_restaurant_demo_bot",
        "features": ["Меню с фото", "Корзина", "Адрес доставки", "Трекинг заказа"],
    },
]


def get_demo_menu() -> Tuple[str, InlineKeyboardMarkup]:
    try:
        return _build_demo_menu()
    except Exception as e:
        logger.error(f"Demo menu error: {e}")
        return "Ошибка загрузки демо. Попробуйте позже.", InlineKeyboardMarkup([])


def _build_demo_menu() -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        "🎮 <b>Попробуйте наши демо-приложения!</b>\n\n"
        "Протестируйте работающие Mini Apps прямо сейчас. "
        "Каждое демо — это полноценное приложение:\n\n"
    )

    for demo in DEMO_APPS:
        features = ", ".join(demo["features"][:3])
        text += (
            f"{demo['name']}\n"
            f"  {demo['description']}\n"
            f"  ⚡ {features}\n\n"
        )

    text += "<i>Нажмите на демо, чтобы попробовать</i>"

    buttons = []
    for demo in DEMO_APPS:
        buttons.append([InlineKeyboardButton(
            f"▶️ {demo['name']}", url=demo["url"]
        )])
    buttons.append([InlineKeyboardButton(
        "📋 Хочу такое же!", callback_data="start_brief",
        **styled_button_api_kwargs(style="constructive")
    )])
    buttons.append([InlineKeyboardButton("◀️ Меню", callback_data="menu_back")])

    return text, InlineKeyboardMarkup(buttons)


def calculate_savings(
    business_type: str = "shop",
    current_method: str = "manual",
    monthly_orders: int = 300,
    avg_check: int = 3000,
) -> Tuple[str, InlineKeyboardMarkup]:
    savings_data = {
        "shop": {
            "manual": {"time_saved_hours": 40, "error_rate_reduction": 0.15, "conversion_boost": 0.25},
            "website": {"time_saved_hours": 15, "error_rate_reduction": 0.05, "conversion_boost": 0.15},
        },
        "restaurant": {
            "manual": {"time_saved_hours": 60, "error_rate_reduction": 0.20, "conversion_boost": 0.30},
            "website": {"time_saved_hours": 20, "error_rate_reduction": 0.08, "conversion_boost": 0.18},
        },
        "beauty": {
            "manual": {"time_saved_hours": 30, "error_rate_reduction": 0.25, "conversion_boost": 0.35},
            "website": {"time_saved_hours": 10, "error_rate_reduction": 0.10, "conversion_boost": 0.20},
        },
    }

    biz_data = savings_data.get(business_type, savings_data["shop"])
    method_data = biz_data.get(current_method, biz_data["manual"])

    time_saved = method_data["time_saved_hours"]
    extra_revenue_monthly = int(monthly_orders * avg_check * method_data["conversion_boost"])
    error_savings = int(monthly_orders * avg_check * method_data["error_rate_reduction"])
    total_monthly = extra_revenue_monthly + error_savings
    total_yearly = total_monthly * 12

    employee_cost = time_saved * 500
    total_with_employee = total_monthly + employee_cost

    text = (
        "📊 <b>Калькулятор экономии</b>\n\n"
        f"📈 Дополнительный доход: <b>+{extra_revenue_monthly:,} ₽/мес</b>\n"
        f"🛡 Экономия на ошибках: <b>+{error_savings:,} ₽/мес</b>\n"
        f"⏱ Экономия времени: <b>{time_saved} часов/мес</b>\n"
        f"👤 Экономия на сотрудниках: <b>{employee_cost:,} ₽/мес</b>\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Итого выгода: +{total_with_employee:,} ₽/мес</b>\n"
        f"💵 <b>За год: +{total_yearly:,} ₽</b>\n\n"
        f"<i>При {monthly_orders} заказах/мес и среднем чеке {avg_check:,} ₽</i>"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Заказать разработку", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("🧮 Калькулятор стоимости", callback_data="menu_calculator")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard
