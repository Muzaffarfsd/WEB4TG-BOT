"""Consultation booking system with calendar UI.

Interactive booking flow with time slot selection,
manager notifications, and follow-up reminders.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = ["", "янв", "фев", "мар", "апр", "май", "июн",
             "июл", "авг", "сен", "окт", "ноя", "дек"]

TIME_SLOTS = [
    "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00",
]


@dataclass
class Booking:
    user_id: int
    date: str = ""
    time_slot: str = ""
    topic: str = ""
    created_at: float = field(default_factory=time.time)
    confirmed: bool = False


class ConsultationManager:
    def __init__(self):
        self._bookings: Dict[int, Booking] = {}
        self._booked_slots: Dict[str, List[str]] = {}

    def start_booking(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        self._bookings[user_id] = Booking(user_id=user_id)
        return self._get_date_keyboard()

    def get_booking(self, user_id: int) -> Optional[Booking]:
        return self._bookings.get(user_id)

    def set_date(self, user_id: int, date: str) -> Tuple[str, InlineKeyboardMarkup]:
        booking = self._bookings.get(user_id)
        if booking:
            booking.date = date
        return self._get_time_keyboard(date)

    def set_time(self, user_id: int, time_slot: str) -> Tuple[str, InlineKeyboardMarkup]:
        booking = self._bookings.get(user_id)
        if booking:
            booking.time_slot = time_slot
        return self._get_topic_keyboard()

    def set_topic(self, user_id: int, topic: str) -> Tuple[str, InlineKeyboardMarkup]:
        booking = self._bookings.get(user_id)
        if booking:
            booking.topic = topic
            booking.confirmed = True

            if booking.date not in self._booked_slots:
                self._booked_slots[booking.date] = []
            self._booked_slots[booking.date].append(booking.time_slot)

        return self._get_confirmation(user_id)

    def _get_date_keyboard(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            "📅 <b>Запись на консультацию</b>\n\n"
            "Выберите удобную дату:"
        )

        today = datetime.now()
        buttons = []
        row = []
        for i in range(1, 8):
            date = today + timedelta(days=i)
            if date.weekday() >= 6:
                continue
            day_name = WEEKDAYS_RU[date.weekday()]
            date_str = date.strftime("%Y-%m-%d")
            label = f"{day_name}, {date.day} {MONTHS_RU[date.month]}"
            row.append(InlineKeyboardButton(label, callback_data=f"consult_date_{date_str}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="consult_cancel")])
        return text, InlineKeyboardMarkup(buttons)

    def _get_time_keyboard(self, date: str) -> Tuple[str, InlineKeyboardMarkup]:
        booked = self._booked_slots.get(date, [])

        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            day_name = WEEKDAYS_RU[dt.weekday()]
            date_label = f"{day_name}, {dt.day} {MONTHS_RU[dt.month]}"
        except ValueError:
            date_label = date

        text = (
            f"📅 <b>Дата: {date_label}</b>\n\n"
            "⏰ Выберите время (MSK):"
        )

        buttons = []
        row = []
        for slot in TIME_SLOTS:
            if slot in booked:
                continue
            row.append(InlineKeyboardButton(slot, callback_data=f"consult_time_{slot}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("◀️ Назад к датам", callback_data="book_consult")])
        return text, InlineKeyboardMarkup(buttons)

    def _get_topic_keyboard(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = "💬 <b>О чём поговорим?</b>"

        topics = [
            ("🛒 Создание Mini App", "new_app"),
            ("💰 Обсуждение бюджета", "budget"),
            ("🔧 Доработка проекта", "upgrade"),
            ("🤝 Партнёрство", "partner"),
            ("❓ Другое", "other"),
        ]

        buttons = []
        for label, topic_id in topics:
            buttons.append([InlineKeyboardButton(label, callback_data=f"consult_topic_{topic_id}")])

        return text, InlineKeyboardMarkup(buttons)

    def _get_confirmation(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        booking = self._bookings.get(user_id)
        if not booking:
            return "Ошибка", InlineKeyboardMarkup([])

        topic_names = {
            "new_app": "Создание Mini App",
            "budget": "Обсуждение бюджета",
            "upgrade": "Доработка проекта",
            "partner": "Партнёрство",
            "other": "Другое",
        }

        try:
            dt = datetime.strptime(booking.date, "%Y-%m-%d")
            day_name = WEEKDAYS_RU[dt.weekday()]
            date_label = f"{day_name}, {dt.day} {MONTHS_RU[dt.month]}"
        except ValueError:
            date_label = booking.date

        text = (
            "✅ <b>Консультация забронирована!</b>\n\n"
            f"📅 Дата: <b>{date_label}</b>\n"
            f"⏰ Время: <b>{booking.time_slot} MSK</b>\n"
            f"💬 Тема: {topic_names.get(booking.topic, booking.topic)}\n\n"
            "Менеджер свяжется с вами за 30 минут до консультации.\n"
            "Можете написать дополнительные вопросы прямо в чат."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Мой кабинет", callback_data="my_dashboard")],
            [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")],
        ])

        return text, keyboard

    def get_manager_notification(self, user_id: int, username: str = "", first_name: str = "") -> str:
        booking = self._bookings.get(user_id)
        if not booking:
            return ""

        topic_names = {
            "new_app": "Создание Mini App",
            "budget": "Обсуждение бюджета",
            "upgrade": "Доработка проекта",
            "partner": "Партнёрство",
            "other": "Другое",
        }

        return (
            f"📅 <b>Новая запись на консультацию!</b>\n\n"
            f"👤 {first_name} (@{username or 'нет'})\n"
            f"🆔 <code>{user_id}</code>\n"
            f"📅 {booking.date} в {booking.time_slot} MSK\n"
            f"💬 {topic_names.get(booking.topic, booking.topic)}"
        )

    def save_to_lead(self, user_id: int) -> None:
        try:
            from src.leads import lead_manager, LeadPriority
            lead_manager.update_lead(user_id, priority=LeadPriority.HOT, score=55)
            lead_manager.add_tag(user_id, "consultation_booked")
        except Exception as e:
            logger.warning(f"Failed to save consultation to lead: {e}")


consultation_manager = ConsultationManager()
