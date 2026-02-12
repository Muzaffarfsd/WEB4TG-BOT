"""CRM dashboard for admins with revenue forecasting and client health.

Provides admin-facing analytics: lead pipeline, revenue forecasting,
client health scores, and actionable insights.
"""

import logging
import time
from typing import Tuple, Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def get_crm_dashboard() -> Tuple[str, InlineKeyboardMarkup]:
    total_leads = 0
    hot_leads = 0
    warm_leads = 0
    cold_leads = 0
    converted = 0
    total_revenue = 0
    avg_score = 0

    try:
        from src.leads import lead_manager
        all_leads = lead_manager.get_all_leads() if hasattr(lead_manager, 'get_all_leads') else []
        total_leads = len(all_leads)

        for lead in all_leads:
            p = getattr(lead, 'priority', None)
            if p:
                p_val = p.value if hasattr(p, 'value') else str(p)
                if p_val == 'hot':
                    hot_leads += 1
                elif p_val == 'warm':
                    warm_leads += 1
                elif p_val == 'cold':
                    cold_leads += 1
            s = getattr(lead, 'status', '')
            if s == 'converted':
                converted += 1
    except Exception as e:
        logger.debug(f"CRM leads data unavailable: {e}")

    conversion_rate = (converted / max(1, total_leads)) * 100

    projected_revenue = int(hot_leads * 200000 * 0.6 + warm_leads * 150000 * 0.3 + cold_leads * 100000 * 0.05)

    text = (
        "📊 <b>CRM ДАШБОРД</b>\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "👥 <b>Лиды</b>\n"
        f"  📋 Всего: {total_leads}\n"
        f"  🔥 Горячие: {hot_leads}\n"
        f"  🟠 Тёплые: {warm_leads}\n"
        f"  🔵 Холодные: {cold_leads}\n"
        f"  ✅ Конвертировано: {converted}\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📈 <b>Конверсия</b>\n"
        f"  📊 Общая: {conversion_rate:.1f}%\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Прогноз выручки</b>\n"
        f"  📈 Ожидаемая: {projected_revenue:,} ₽\n".replace(",", " ") +
        f"  🔥 От горячих: {int(hot_leads * 200000 * 0.6):,} ₽\n".replace(",", " ") +
        f"  🟠 От тёплых: {int(warm_leads * 150000 * 0.3):,} ₽\n".replace(",", " ")
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Горячие лиды", callback_data="crm_hot"),
         InlineKeyboardButton("📊 Аналитика", callback_data="crm_analytics")],
        [InlineKeyboardButton("🏥 Health Score", callback_data="crm_health")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])

    return text, keyboard


def get_hot_leads_view() -> Tuple[str, InlineKeyboardMarkup]:
    text = "🔥 <b>Горячие лиды</b>\n\n"

    try:
        from src.leads import lead_manager
        hot = lead_manager.get_hot_leads() if hasattr(lead_manager, 'get_hot_leads') else []
        if not hot:
            text += "Нет горячих лидов."
        else:
            for i, lead in enumerate(hot[:10], 1):
                name = getattr(lead, 'first_name', '') or f"User#{getattr(lead, 'user_id', '?')}"
                username = getattr(lead, 'username', '')
                score = getattr(lead, 'score', 0)
                text += f"{i}. {name} (@{username or 'нет'}) — Score: {score}\n"
    except Exception:
        text += "Данные недоступны."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ CRM", callback_data="crm_dashboard")],
    ])

    return text, keyboard


def get_client_health_view() -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        "🏥 <b>Client Health Score</b>\n\n"
        "Оценка вовлечённости клиентов:\n\n"
    )

    try:
        from src.leads import lead_manager
        all_leads = lead_manager.get_all_leads() if hasattr(lead_manager, 'get_all_leads') else []
        healthy = 0
        at_risk = 0
        churning = 0

        for lead in all_leads:
            score = getattr(lead, 'score', 0)
            if score >= 50:
                healthy += 1
            elif score >= 20:
                at_risk += 1
            else:
                churning += 1

        total = max(1, len(all_leads))
        text += (
            f"✅ Здоровые (score≥50): {healthy} ({healthy/total*100:.0f}%)\n"
            f"⚠️ В зоне риска (20-49): {at_risk} ({at_risk/total*100:.0f}%)\n"
            f"🔴 Уходящие (<20): {churning} ({churning/total*100:.0f}%)\n"
        )
    except Exception:
        text += "Данные недоступны."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ CRM", callback_data="crm_dashboard")],
    ])

    return text, keyboard
