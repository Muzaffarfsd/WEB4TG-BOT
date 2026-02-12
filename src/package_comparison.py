"""Visual package comparison with feature matrix.

Side-by-side comparison of service packages,
payment calculator with discount application,
and timeline visualization.
"""

import logging
from typing import Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


PACKAGES = {
    "starter": {
        "name": "🚀 Стартер",
        "price": 150000,
        "timeline": "7-10 дней",
        "description": "Быстрый запуск Mini App",
        "features": {
            "catalog": True,
            "cart": True,
            "payments": True,
            "auth": True,
            "push": False,
            "loyalty": False,
            "analytics": False,
            "ai_bot": False,
            "crm": False,
            "custom_design": False,
        },
        "support": "30 дней",
        "updates": "3 месяца",
    },
    "business": {
        "name": "💼 Бизнес",
        "price": 250000,
        "timeline": "14-21 день",
        "description": "Полноценное приложение для бизнеса",
        "features": {
            "catalog": True,
            "cart": True,
            "payments": True,
            "auth": True,
            "push": True,
            "loyalty": True,
            "analytics": True,
            "ai_bot": False,
            "crm": False,
            "custom_design": True,
        },
        "support": "90 дней",
        "updates": "6 месяцев",
    },
    "premium": {
        "name": "👑 Премиум",
        "price": 400000,
        "timeline": "21-30 дней",
        "description": "Максимальные возможности и индивидуальный подход",
        "features": {
            "catalog": True,
            "cart": True,
            "payments": True,
            "auth": True,
            "push": True,
            "loyalty": True,
            "analytics": True,
            "ai_bot": True,
            "crm": True,
            "custom_design": True,
        },
        "support": "12 месяцев",
        "updates": "12 месяцев",
    },
}

FEATURE_NAMES = {
    "catalog": "📦 Каталог товаров",
    "cart": "🛒 Корзина",
    "payments": "💳 Онлайн-оплата",
    "auth": "🔐 Авторизация",
    "push": "🔔 Push-уведомления",
    "loyalty": "❤️ Программа лояльности",
    "analytics": "📊 Аналитика",
    "ai_bot": "🤖 AI чат-бот",
    "crm": "👥 CRM-система",
    "custom_design": "🎨 Кастомный дизайн",
}


def get_comparison_view() -> Tuple[str, InlineKeyboardMarkup]:
    text = "📦 <b>СРАВНЕНИЕ ПАКЕТОВ</b>\n\n"

    for pkg_id, pkg in PACKAGES.items():
        text += f"<b>{pkg['name']}</b>\n"
        text += f"💰 {pkg['price']:,} ₽ • ⏱ {pkg['timeline']}\n".replace(",", " ")
        text += f"📝 {pkg['description']}\n\n"

        for feat_id, feat_name in FEATURE_NAMES.items():
            has = pkg["features"].get(feat_id, False)
            mark = "✅" if has else "—"
            text += f"  {mark} {feat_name}\n"

        text += f"\n🛡 Поддержка: {pkg['support']}\n"
        text += f"🔄 Обновления: {pkg['updates']}\n"
        text += "━━━━━━━━━━━━━━━\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Стартер", callback_data="pkg_starter"),
         InlineKeyboardButton("💼 Бизнес", callback_data="pkg_business"),
         InlineKeyboardButton("👑 Премиум", callback_data="pkg_premium")],
        [InlineKeyboardButton(
            "📋 Составить бриф", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])

    return text, keyboard


def get_package_detail(pkg_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    pkg = PACKAGES.get(pkg_id)
    if not pkg:
        return "Пакет не найден", InlineKeyboardMarkup([])

    text = (
        f"{pkg['name']}\n\n"
        f"💰 <b>Стоимость: {pkg['price']:,} ₽</b>\n"
        f"⏱ Срок: {pkg['timeline']}\n"
        f"📝 {pkg['description']}\n\n"
        f"<b>Что входит:</b>\n"
    ).replace(",", " ")

    for feat_id, feat_name in FEATURE_NAMES.items():
        has = pkg["features"].get(feat_id, False)
        if has:
            text += f"  ✅ {feat_name}\n"

    text += (
        f"\n🛡 Поддержка: {pkg['support']}\n"
        f"🔄 Обновления: {pkg['updates']}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Заказать этот пакет", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("📦 Все пакеты", callback_data="compare_packages")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard


def calculate_with_discount(pkg_id: str, discount_percent: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    pkg = PACKAGES.get(pkg_id)
    if not pkg:
        return "Пакет не найден", InlineKeyboardMarkup([])

    original = pkg["price"]
    discount_amount = int(original * discount_percent / 100)
    final = original - discount_amount

    installment_3 = int(final / 3)
    installment_6 = int(final / 6)

    text = (
        f"💰 <b>Расчёт стоимости: {pkg['name']}</b>\n\n"
        f"Базовая цена: {original:,} ₽\n"
    ).replace(",", " ")

    if discount_percent > 0:
        text += f"🎯 Ваша скидка: -{discount_percent}% (-{discount_amount:,} ₽)\n".replace(",", " ")
        text += f"<b>Итого: {final:,} ₽</b>\n\n".replace(",", " ")
    else:
        text += f"<b>Итого: {final:,} ₽</b>\n\n".replace(",", " ")

    text += (
        f"📅 <b>Варианты оплаты:</b>\n"
        f"  💳 Полная оплата: {final:,} ₽\n"
        f"  📆 Рассрочка 3 мес: {installment_3:,} ₽/мес\n"
        f"  📆 Рассрочка 6 мес: {installment_6:,} ₽/мес\n\n"
        f"50% предоплата + 50% после сдачи"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "💳 Оплатить", callback_data="smart_payment",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("📄 Договор", callback_data="smart_contract")],
        [InlineKeyboardButton("◀️ Назад", callback_data="compare_packages")],
    ])

    return text, keyboard


def get_timeline_view(pkg_id: str = "business") -> Tuple[str, InlineKeyboardMarkup]:
    timelines = {
        "starter": [
            ("1-2", "📋 Сбор требований и утверждение ТЗ"),
            ("3-5", "🎨 Дизайн и прототип"),
            ("6-8", "💻 Разработка"),
            ("9-10", "🧪 Тестирование и запуск"),
        ],
        "business": [
            ("1-3", "📋 Аналитика и проектирование"),
            ("4-7", "🎨 UI/UX дизайн"),
            ("8-14", "💻 Разработка основного функционала"),
            ("15-18", "🔗 Интеграции и настройка"),
            ("19-21", "🧪 Тестирование и деплой"),
        ],
        "premium": [
            ("1-5", "📋 Глубокая аналитика и стратегия"),
            ("6-10", "🎨 Индивидуальный дизайн"),
            ("11-20", "💻 Full-stack разработка"),
            ("21-25", "🤖 AI-интеграции и автоматизация"),
            ("26-28", "🧪 QA и оптимизация"),
            ("29-30", "🚀 Деплой и обучение"),
        ],
    }

    stages = timelines.get(pkg_id, timelines["business"])
    pkg = PACKAGES.get(pkg_id, PACKAGES["business"])

    text = f"⏱ <b>Таймлайн: {pkg['name']}</b>\n\n"

    for i, (days, desc) in enumerate(stages):
        connector = "┣" if i < len(stages) - 1 else "┗"
        text += f"  {connector}━ <b>Дни {days}</b>\n"
        text += f"  ┃  {desc}\n"

    text += f"\n📅 Общий срок: <b>{pkg['timeline']}</b>"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Начать проект", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("📦 Пакеты", callback_data="compare_packages")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard
