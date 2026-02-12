"""Social features: story sharing, gift system, success story rotator.

Social engagement features to increase virality and retention.
"""

import logging
import time
import random
from typing import Tuple, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


SUCCESS_STORIES = [
    {
        "title": "Radiance — Магазин одежды",
        "quote": "За 3 месяца заказы выросли на 40%. Mini App стал основным каналом продаж.",
        "metric": "+40% заказов",
        "icon": "🛒",
    },
    {
        "title": "Fresh Kitchen — Доставка еды",
        "quote": "Время обработки заказа сократилось на 60%. Клиенты счастливы.",
        "metric": "-60% время обработки",
        "icon": "🍽",
    },
    {
        "title": "GlowUp Studio — Салон красоты",
        "quote": "No-show снизился на 45%. Клиенты записываются сами через Telegram.",
        "metric": "-45% no-show",
        "icon": "💇‍♀️",
    },
    {
        "title": "FitLife — Фитнес-клуб",
        "quote": "Удержание клиентов выросло на 60%. Геймификация работает.",
        "metric": "+60% удержание",
        "icon": "🏋️",
    },
    {
        "title": "МедЦентр Плюс — Клиника",
        "quote": "Звонки сократились на 70%. Экономия на call-центре — 200 000 ₽/мес.",
        "metric": "-70% звонков",
        "icon": "🏥",
    },
    {
        "title": "SkillHub — Онлайн-школа",
        "quote": "Доходимость курсов выросла на 40%. Геймификация мотивирует учиться.",
        "metric": "+40% доходимость",
        "icon": "📚",
    },
]


class SuccessStoryRotator:
    def __init__(self):
        self._shown: dict = {}

    def get_story(self, user_id: int) -> dict:
        shown = self._shown.get(user_id, [])
        available = [s for i, s in enumerate(SUCCESS_STORIES) if i not in shown]
        if not available:
            self._shown[user_id] = []
            available = SUCCESS_STORIES

        story = random.choice(available)
        idx = SUCCESS_STORIES.index(story)
        if user_id not in self._shown:
            self._shown[user_id] = []
        self._shown[user_id].append(idx)

        return story

    def get_story_view(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        story = self.get_story(user_id)

        text = (
            f"{story['icon']} <b>{story['title']}</b>\n\n"
            f"💬 <i>«{story['quote']}»</i>\n\n"
            f"📊 Результат: <b>{story['metric']}</b>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ещё история", callback_data="next_story")],
            [InlineKeyboardButton(
                "📋 Хочу так же!", callback_data="start_brief",
                **styled_button_api_kwargs(style="constructive")
            )],
            [InlineKeyboardButton("📊 Все кейсы", callback_data="menu_portfolio")],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
        ])

        return text, keyboard


def get_share_text(user_id: int, ref_code: str = "") -> Tuple[str, InlineKeyboardMarkup]:
    share_message = (
        "🚀 Рекомендую WEB4TG Studio!\n\n"
        "Они делают крутые Mini Apps для Telegram — "
        "магазины, рестораны, записи на приём.\n"
        "Быстро, качественно, с окупаемостью от 2 месяцев."
    )

    if ref_code:
        share_message += f"\n\nМоя реферальная ссылка: https://t.me/web4tg_bot?start=ref_{ref_code}"

    text = (
        "📢 <b>Поделитесь с друзьями!</b>\n\n"
        "Скопируйте текст ниже и отправьте друзьям:\n\n"
        f"<code>{share_message}</code>\n\n"
        "За каждого приглашённого друга вы получите бонусные монеты!"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="referral_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])

    return text, keyboard


GIFT_CATALOG = [
    {"id": "free_consult", "name": "🎁 Бесплатная консультация", "cost": 500, "desc": "30-минутная консультация с менеджером"},
    {"id": "design_bonus", "name": "🎨 Бонус на дизайн", "cost": 1000, "desc": "Бесплатная разработка UI/UX одного экрана"},
    {"id": "month_support", "name": "🛡 Месяц поддержки", "cost": 1500, "desc": "Дополнительный месяц бесплатной поддержки"},
    {"id": "priority_dev", "name": "⚡ Приоритетная разработка", "cost": 2000, "desc": "Ваш проект — в приоритете очереди"},
]


def get_gift_catalog(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    coins = 0
    try:
        from src.tasks_tracker import tasks_tracker
        progress = tasks_tracker.get_user_progress(user_id)
        coins = progress.total_coins
    except Exception:
        pass

    text = (
        f"🎁 <b>Магазин бонусов</b>\n"
        f"💰 Ваш баланс: <b>{coins} монет</b>\n\n"
    )

    for gift in GIFT_CATALOG:
        can_buy = "✅" if coins >= gift["cost"] else "🔒"
        text += (
            f"{can_buy} <b>{gift['name']}</b> — {gift['cost']} монет\n"
            f"   {gift['desc']}\n\n"
        )

    buttons = []
    for gift in GIFT_CATALOG:
        if coins >= gift["cost"]:
            buttons.append([InlineKeyboardButton(
                f"🎁 {gift['name']}", callback_data=f"buy_gift_{gift['id']}"
            )])

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="my_dashboard")])

    return text, InlineKeyboardMarkup(buttons)


def buy_gift(user_id: int, gift_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    gift = None
    for g in GIFT_CATALOG:
        if g["id"] == gift_id:
            gift = g
            break

    if not gift:
        return "Бонус не найден", InlineKeyboardMarkup([])

    coins = 0
    try:
        from src.tasks_tracker import tasks_tracker
        progress = tasks_tracker.get_user_progress(user_id)
        coins = progress.total_coins
    except Exception:
        pass

    if coins < gift["cost"]:
        return (
            f"❌ Недостаточно монет. Нужно {gift['cost']}, у вас {coins}.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="gift_catalog")]])
        )

    try:
        from src.tasks_tracker import tasks_tracker
        tasks_tracker.add_coins(user_id, -gift["cost"], f"gift_purchase_{gift_id}")
    except Exception:
        pass

    try:
        from src.leads import lead_manager
        lead_manager.add_tag(user_id, f"gift_{gift_id}")
    except Exception:
        pass

    text = (
        f"✅ <b>Бонус активирован!</b>\n\n"
        f"{gift['name']}\n"
        f"{gift['desc']}\n\n"
        f"Списано: {gift['cost']} монет\n"
        "Менеджер учтёт бонус при работе над вашим проектом."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Магазин бонусов", callback_data="gift_catalog")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard


story_rotator = SuccessStoryRotator()
