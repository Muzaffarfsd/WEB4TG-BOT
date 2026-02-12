"""Client dashboard — /mystatus command.

Shows comprehensive client status: coins, tier, discount,
referrals, funnel stage, propensity score, activity summary.
"""

import logging
import time
from typing import Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


TIER_THRESHOLDS = [
    (2500, "💎 Бриллиант", "diamond"),
    (2000, "👑 Платина", "platinum"),
    (1500, "🥇 Золото", "gold"),
    (1000, "🥈 Серебро", "silver"),
    (500, "🥉 Бронза", "bronze"),
    (0, "🌱 Новичок", "starter"),
]

FUNNEL_STAGE_NAMES = {
    "awareness": "🔍 Знакомство",
    "interest": "💡 Интерес",
    "consideration": "🤔 Рассмотрение",
    "decision": "🎯 Решение",
    "converted": "✅ Клиент",
}

PROPENSITY_LABELS = {
    (80, 101): ("🔥 Горячий", "Высокая вероятность покупки"),
    (50, 80): ("🟠 Тёплый", "Есть интерес, нужен толчок"),
    (20, 50): ("🟡 Умеренный", "Изучает варианты"),
    (0, 20): ("🔵 Холодный", "Начальная стадия"),
}


def get_tier(coins: int) -> tuple:
    for threshold, name, key in TIER_THRESHOLDS:
        if coins >= threshold:
            return name, key
    return "🌱 Новичок", "starter"


def get_propensity_label(score: int) -> tuple:
    for (low, high), (label, desc) in PROPENSITY_LABELS.items():
        if low <= score < high:
            return label, desc
    return "🔵 Холодный", "Начальная стадия"


def get_next_tier_info(coins: int) -> Optional[str]:
    for threshold, name, _ in TIER_THRESHOLDS:
        if coins < threshold:
            remaining = threshold - coins
            return f"До уровня {name}: ещё {remaining} монет"
    return None


def build_dashboard(user_id: int, username: str = "", first_name: str = "") -> tuple:
    coins = 0
    discount = 0
    referral_count = 0
    referral_earnings = 0
    funnel_stage = "awareness"
    propensity_score = 0
    message_count = 0
    days_active = 0
    tasks_completed = 0

    try:
        from src.tasks_tracker import tasks_tracker
        progress = tasks_tracker.get_user_progress(user_id)
        coins = progress.total_coins
        discount = progress.get_discount_percent()
        tasks_completed = progress.completed_count
    except Exception as e:
        logger.debug(f"Tasks data unavailable: {e}")

    try:
        from src.referrals import referral_manager
        ref_stats = referral_manager.get_user_stats(user_id)
        referral_count = ref_stats.get("referral_count", 0)
        referral_earnings = ref_stats.get("total_earned", 0)
    except Exception as e:
        logger.debug(f"Referral data unavailable: {e}")

    try:
        from src.session import session_manager
        session = session_manager.get_session(user_id)
        message_count = session.message_count
        if session.created_at:
            days_active = max(1, int((time.time() - session.created_at) / 86400))
    except Exception as e:
        logger.debug(f"Session data unavailable: {e}")

    try:
        from src.propensity import propensity_scorer
        score_data = propensity_scorer.get_score(user_id)
        if isinstance(score_data, dict):
            propensity_score = score_data.get("score", 0)
        else:
            propensity_score = int(score_data) if score_data else 0
    except Exception as e:
        logger.debug(f"Propensity data unavailable: {e}")

    try:
        from src.analytics import analytics
        stage = analytics.get_user_funnel_stage(user_id)
        if stage:
            funnel_stage = stage
    except Exception as e:
        logger.debug(f"Funnel stage unavailable: {e}")

    tier_name, tier_key = get_tier(coins)
    prop_label, prop_desc = get_propensity_label(propensity_score)
    stage_name = FUNNEL_STAGE_NAMES.get(funnel_stage, "🔍 Знакомство")
    next_tier = get_next_tier_info(coins)

    display_name = first_name or username or f"User #{user_id}"

    progress_bar = _make_progress_bar(coins, 2500)

    text = (
        f"📊 <b>Ваш личный кабинет</b>\n"
        f"👤 {display_name}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🏆 <b>Уровень:</b> {tier_name}\n"
        f"💰 <b>Монеты:</b> {coins}\n"
        f"{progress_bar}\n"
    )

    if next_tier:
        text += f"<i>{next_tier}</i>\n"

    text += (
        f"\n🎯 <b>Скидка:</b> {discount}%\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📈 <b>Активность</b>\n"
        f"💬 Сообщений: {message_count}\n"
        f"📅 Дней с нами: {days_active}\n"
        f"✅ Заданий выполнено: {tasks_completed}\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Рефералы</b>\n"
        f"🔗 Приглашено друзей: {referral_count}\n"
        f"💎 Заработано от рефералов: {referral_earnings} монет\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🔍 <b>Статус</b>\n"
        f"📌 Стадия: {stage_name}\n"
        f"🌡 Интерес: {prop_label}\n"
        f"<i>{prop_desc}</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧮 Калькулятор", callback_data="menu_calculator"),
         InlineKeyboardButton("🎁 Бонусы", callback_data="loyalty_menu")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referral_info")],
        [InlineKeyboardButton(
            "📝 Оставить заявку", callback_data="menu_lead",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")],
    ])

    return text, keyboard


def _make_progress_bar(current: int, max_val: int) -> str:
    filled = min(10, int(current / max(1, max_val) * 10))
    empty = 10 - filled
    bar = "▓" * filled + "░" * empty
    pct = min(100, int(current / max(1, max_val) * 100))
    return f"[{bar}] {pct}%"
