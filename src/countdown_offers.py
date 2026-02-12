"""Countdown limited-time offers with urgency mechanics.

Creates time-limited special offers with real countdowns,
scarcity signals, and automatic expiry.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


@dataclass
class SpecialOffer:
    offer_id: str
    title: str
    description: str
    discount_percent: int
    expires_at: float
    max_claims: int = 10
    claimed_by: List[int] = field(default_factory=list)
    active: bool = True


DEFAULT_OFFERS = [
    SpecialOffer(
        offer_id="first_order",
        title="🔥 Скидка на первый заказ",
        description="Специальная скидка для новых клиентов на любой пакет разработки",
        discount_percent=15,
        expires_at=time.time() + 86400 * 3,
        max_claims=20,
    ),
    SpecialOffer(
        offer_id="bundle_deal",
        title="📦 Mini App + Подписка",
        description="Закажите разработку Mini App и получите 3 месяца подписки бесплатно",
        discount_percent=20,
        expires_at=time.time() + 86400 * 7,
        max_claims=10,
    ),
    SpecialOffer(
        offer_id="referral_bonus",
        title="👥 Двойной реферальный бонус",
        description="Пригласите друга сейчас — оба получите удвоенный бонус",
        discount_percent=0,
        expires_at=time.time() + 86400 * 5,
        max_claims=50,
    ),
]


class CountdownManager:
    def __init__(self):
        self._offers: Dict[str, SpecialOffer] = {}
        for offer in DEFAULT_OFFERS:
            self._offers[offer.offer_id] = offer

    def get_active_offers(self) -> List[SpecialOffer]:
        now = time.time()
        return [
            o for o in self._offers.values()
            if o.active and o.expires_at > now and len(o.claimed_by) < o.max_claims
        ]

    def get_offers_menu(self) -> Tuple[str, InlineKeyboardMarkup]:
        offers = self.get_active_offers()

        if not offers:
            text = (
                "🎯 <b>Специальные предложения</b>\n\n"
                "Сейчас нет активных акций, но вы можете:\n"
                "• Использовать промокод (/promo)\n"
                "• Получить скидку через реферальную программу"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎟 Промокод", callback_data="promo_enter")],
                [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
            ])
            return text, keyboard

        text = "🔥 <b>СПЕЦИАЛЬНЫЕ ПРЕДЛОЖЕНИЯ</b>\n\n"

        for offer in offers:
            remaining = offer.expires_at - time.time()
            hours = int(remaining / 3600)
            minutes = int((remaining % 3600) / 60)

            if hours > 24:
                time_str = f"{hours // 24}д {hours % 24}ч"
            elif hours > 0:
                time_str = f"{hours}ч {minutes}мин"
            else:
                time_str = f"{minutes} мин"

            spots_left = offer.max_claims - len(offer.claimed_by)

            text += (
                f"<b>{offer.title}</b>\n"
                f"{offer.description}\n"
            )
            if offer.discount_percent > 0:
                text += f"💰 Скидка: <b>-{offer.discount_percent}%</b>\n"
            text += (
                f"⏰ Осталось: <b>{time_str}</b>\n"
                f"👥 Мест: <b>{spots_left}/{offer.max_claims}</b>\n\n"
            )

        buttons = []
        for offer in offers:
            buttons.append([InlineKeyboardButton(
                f"🎁 {offer.title}", callback_data=f"claim_offer_{offer.offer_id}"
            )])
        buttons.append([InlineKeyboardButton("◀️ Меню", callback_data="menu_back")])

        return text, InlineKeyboardMarkup(buttons)

    def claim_offer(self, user_id: int, offer_id: str) -> Tuple[str, InlineKeyboardMarkup]:
        offer = self._offers.get(offer_id)
        if not offer:
            return "Предложение не найдено", InlineKeyboardMarkup([])

        if not offer.active or offer.expires_at < time.time():
            return (
                "⏰ К сожалению, это предложение уже истекло.",
                InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="offers_menu")]])
            )

        if user_id in offer.claimed_by:
            return (
                "✅ Вы уже воспользовались этим предложением!",
                InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="offers_menu")]])
            )

        if len(offer.claimed_by) >= offer.max_claims:
            return (
                "😔 Все места заняты. Следите за новыми предложениями!",
                InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="offers_menu")]])
            )

        offer.claimed_by.append(user_id)

        text = (
            f"🎉 <b>Предложение активировано!</b>\n\n"
            f"{offer.title}\n"
        )
        if offer.discount_percent > 0:
            text += f"💰 Ваша скидка: <b>-{offer.discount_percent}%</b>\n\n"
        text += "Менеджер учтёт скидку при оформлении заказа."

        try:
            from src.leads import lead_manager
            lead_manager.add_tag(user_id, f"offer_{offer_id}")
            from src.leads import LeadPriority
            lead_manager.update_lead(user_id, priority=LeadPriority.HOT, score=45)
        except Exception as e:
            logger.warning(f"Failed to save offer claim: {e}")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📋 Составить бриф", callback_data="start_brief",
                **styled_button_api_kwargs(style="constructive")
            )],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
        ])

        return text, keyboard

    def get_user_offer_context(self, user_id: int) -> str:
        offers = self.get_active_offers()
        if not offers:
            return ""
        best = offers[0]
        remaining = best.expires_at - time.time()
        hours = int(remaining / 3600)
        if best.discount_percent > 0:
            return f"Сейчас действует {best.title} (-{best.discount_percent}%), осталось {hours}ч!"
        return f"Сейчас действует {best.title}, осталось {hours}ч!"


countdown_manager = CountdownManager()
