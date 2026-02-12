"""Achievements, leaderboard, VIP program, and seasonal promos.

Gamification layer: achievements with unlock conditions,
referral leaderboard, VIP tiers, and seasonal promotions.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


ACHIEVEMENTS = [
    {"id": "first_message", "name": "💬 Первое сообщение", "desc": "Отправьте первое сообщение", "coins": 50, "condition": "messages >= 1"},
    {"id": "explorer", "name": "🔍 Исследователь", "desc": "Изучите 3 раздела меню", "coins": 100, "condition": "sections >= 3"},
    {"id": "calculator_user", "name": "🧮 Калькулятор", "desc": "Воспользуйтесь калькулятором", "coins": 75, "condition": "calc_used"},
    {"id": "brief_master", "name": "📋 Мастер брифа", "desc": "Заполните бриф проекта", "coins": 150, "condition": "brief_completed"},
    {"id": "quiz_complete", "name": "🎯 Квиз пройден", "desc": "Пройдите квиз подбора решения", "coins": 100, "condition": "quiz_completed"},
    {"id": "social_butterfly", "name": "🦋 Социальная бабочка", "desc": "Пригласите 3 друзей", "coins": 200, "condition": "referrals >= 3"},
    {"id": "loyal_customer", "name": "❤️ Лояльный клиент", "desc": "Взаимодействуйте 7 дней подряд", "coins": 300, "condition": "streak >= 7"},
    {"id": "voice_user", "name": "🎤 Голос", "desc": "Отправьте голосовое сообщение", "coins": 75, "condition": "voice_sent"},
    {"id": "portfolio_viewer", "name": "🎨 Ценитель", "desc": "Просмотрите 3 кейса", "coins": 100, "condition": "cases_viewed >= 3"},
    {"id": "vip_tier", "name": "👑 VIP", "desc": "Достигните уровня Золото", "coins": 500, "condition": "tier >= gold"},
]


VIP_TIERS = {
    "bronze": {"name": "🥉 Бронза", "min_coins": 500, "discount": 3, "perks": ["Базовая скидка 3%"]},
    "silver": {"name": "🥈 Серебро", "min_coins": 1000, "discount": 5, "perks": ["Скидка 5%", "Приоритетная поддержка"]},
    "gold": {"name": "🥇 Золото", "min_coins": 1500, "discount": 10, "perks": ["Скидка 10%", "VIP поддержка", "Ранний доступ"]},
    "platinum": {"name": "👑 Платина", "min_coins": 2000, "discount": 15, "perks": ["Скидка 15%", "Персональный менеджер", "Ранний доступ", "Бесплатные консультации"]},
    "diamond": {"name": "💎 Бриллиант", "min_coins": 2500, "discount": 20, "perks": ["Скидка 20%", "Все привилегии Платины", "Индивидуальные условия"]},
}


class AchievementManager:
    def __init__(self):
        self._unlocked: Dict[int, List[str]] = {}

    def get_user_achievements(self, user_id: int) -> List[dict]:
        unlocked = self._unlocked.get(user_id, [])
        result = []
        for ach in ACHIEVEMENTS:
            a = ach.copy()
            a["unlocked"] = ach["id"] in unlocked
            result.append(a)
        return result

    def unlock(self, user_id: int, achievement_id: str) -> Optional[dict]:
        if user_id not in self._unlocked:
            self._unlocked[user_id] = []
        if achievement_id in self._unlocked[user_id]:
            return None
        self._unlocked[user_id].append(achievement_id)
        for ach in ACHIEVEMENTS:
            if ach["id"] == achievement_id:
                try:
                    from src.tasks_tracker import tasks_tracker
                    tasks_tracker.add_coins(user_id, ach["coins"], f"achievement_{achievement_id}")
                except Exception:
                    pass
                return ach
        return None

    def check_and_unlock(self, user_id: int, event: str, value: int = 1) -> List[dict]:
        newly_unlocked = []
        event_checks = {
            "messages": ["first_message"],
            "calc_used": ["calculator_user"],
            "brief_completed": ["brief_master"],
            "quiz_completed": ["quiz_complete"],
            "voice_sent": ["voice_user"],
        }

        for ach_id in event_checks.get(event, []):
            result = self.unlock(user_id, ach_id)
            if result:
                newly_unlocked.append(result)

        if event == "referrals" and value >= 3:
            result = self.unlock(user_id, "social_butterfly")
            if result:
                newly_unlocked.append(result)

        return newly_unlocked

    def get_achievements_view(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        achievements = self.get_user_achievements(user_id)
        unlocked_count = sum(1 for a in achievements if a["unlocked"])
        total = len(achievements)

        text = (
            f"🏆 <b>Достижения</b> ({unlocked_count}/{total})\n\n"
        )

        for ach in achievements:
            status = "✅" if ach["unlocked"] else "🔒"
            text += f"{status} <b>{ach['name']}</b> — +{ach['coins']} монет\n"
            text += f"    <i>{ach['desc']}</i>\n\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Мой кабинет", callback_data="my_dashboard")],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
        ])

        return text, keyboard


def get_vip_view(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    coins = 0
    try:
        from src.tasks_tracker import tasks_tracker
        progress = tasks_tracker.get_user_progress(user_id)
        coins = progress.total_coins
    except Exception:
        pass

    current_tier = None
    next_tier = None
    for tier_id in ["diamond", "platinum", "gold", "silver", "bronze"]:
        tier = VIP_TIERS[tier_id]
        if coins >= tier["min_coins"]:
            current_tier = (tier_id, tier)
            break

    if current_tier:
        tier_keys = list(VIP_TIERS.keys())
        idx = tier_keys.index(current_tier[0])
        if idx > 0:
            next_key = tier_keys[idx - 1]
            next_tier = (next_key, VIP_TIERS[next_key])
    else:
        current_tier = ("none", {"name": "🌱 Новичок", "discount": 0, "perks": ["Базовый доступ"]})
        next_tier = ("bronze", VIP_TIERS["bronze"])

    text = (
        f"👑 <b>VIP-программа</b>\n\n"
        f"💰 Ваши монеты: <b>{coins}</b>\n"
        f"🏆 Текущий уровень: <b>{current_tier[1]['name']}</b>\n"
        f"🎯 Скидка: <b>{current_tier[1]['discount']}%</b>\n\n"
        f"<b>Ваши привилегии:</b>\n"
    )

    for perk in current_tier[1]["perks"]:
        text += f"  ✓ {perk}\n"

    if next_tier:
        remaining = next_tier[1]["min_coins"] - coins
        text += (
            f"\n━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>До {next_tier[1]['name']}:</b> ещё {remaining} монет\n"
            f"  Бонус: скидка {next_tier[1]['discount']}%"
        )

    text += "\n\n━━━━━━━━━━━━━━━\n\n<b>Все уровни:</b>\n"
    for tier_id, tier in VIP_TIERS.items():
        marker = "👉" if current_tier and tier_id == current_tier[0] else "  "
        text += f"{marker} {tier['name']} — от {tier['min_coins']} монет (скидка {tier['discount']}%)\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Достижения", callback_data="achievements_view")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="my_dashboard")],
    ])

    return text, keyboard


def get_leaderboard() -> Tuple[str, InlineKeyboardMarkup]:
    text = "🏆 <b>Топ рефереров</b>\n\n"

    try:
        from src.referrals import referral_manager
        top = referral_manager.get_top_referrers(10) if hasattr(referral_manager, 'get_top_referrers') else []
        if not top:
            text += "Пока никто не пригласил друзей. Будьте первым!"
        else:
            medals = ["🥇", "🥈", "🥉"] + ["  " + str(i) + "." for i in range(4, 11)]
            for i, entry in enumerate(top):
                name = entry.get("name", f"User")
                count = entry.get("count", 0)
                text += f"{medals[i]} {name} — {count} рефералов\n"
    except Exception:
        text += "Данные недоступны."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="referral_info")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])

    return text, keyboard


SEASONAL_PROMOS = {
    "new_year": {
        "name": "🎄 Новогодняя акция",
        "description": "Закажите Mini App до 31 декабря — получите скидку 20% и бесплатный месяц поддержки",
        "discount": 20,
        "months": [12, 1],
    },
    "spring": {
        "name": "🌸 Весенний старт",
        "description": "Весна — время запускать новое! Скидка 10% на все пакеты",
        "discount": 10,
        "months": [3, 4, 5],
    },
    "summer": {
        "name": "☀️ Летнее предложение",
        "description": "Летняя скидка 15% + бесплатная интеграция Push-уведомлений",
        "discount": 15,
        "months": [6, 7, 8],
    },
    "black_friday": {
        "name": "🖤 Black Friday",
        "description": "Максимальная скидка 25% на все услуги. Только до конца ноября!",
        "discount": 25,
        "months": [11],
    },
}


def get_current_seasonal_promo() -> Optional[dict]:
    import datetime
    current_month = datetime.datetime.now().month
    for promo_id, promo in SEASONAL_PROMOS.items():
        if current_month in promo["months"]:
            return promo
    return None


def get_seasonal_promo_view() -> Tuple[str, InlineKeyboardMarkup]:
    promo = get_current_seasonal_promo()

    if not promo:
        text = (
            "🎯 <b>Специальные предложения</b>\n\n"
            "Сейчас нет сезонных акций, но вы можете:\n"
            "• Использовать промокод (/promo)\n"
            "• Получить скидку через реферальную программу"
        )
    else:
        text = (
            f"{promo['name']}\n\n"
            f"{promo['description']}\n\n"
            f"💰 Скидка: <b>-{promo['discount']}%</b>"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Воспользоваться", callback_data="start_brief",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("🔥 Все предложения", callback_data="offers_menu")],
        [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
    ])

    return text, keyboard


achievement_manager = AchievementManager()
