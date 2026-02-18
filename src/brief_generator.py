"""Interactive brief generator wizard.

Step-by-step project brief creation with 6 questions,
auto-formatting, and lead creation.
Persists state to PostgreSQL so briefs survive bot restarts.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


BRIEF_STEPS = [
    {
        "id": "project_type",
        "question": "📋 <b>Шаг 1/6: Тип проекта</b>\n\nКакое приложение вам нужно?",
        "options": {
            "shop": "🛒 Интернет-магазин",
            "restaurant": "🍽 Ресторан/Доставка",
            "beauty": "💇‍♀️ Салон красоты",
            "fitness": "🏋️ Фитнес-клуб",
            "medical": "🏥 Медицина",
            "education": "📚 Образование",
            "services": "🔧 Услуги",
            "custom": "✨ Кастомный проект",
        },
    },
    {
        "id": "audience",
        "question": "👥 <b>Шаг 2/6: Целевая аудитория</b>\n\nКто ваши клиенты?",
        "options": {
            "b2c_young": "🧑 Молодёжь 18-35",
            "b2c_adult": "👨‍👩‍👧 Семейные 25-45",
            "b2c_premium": "💎 Премиум-сегмент",
            "b2c_mass": "🌍 Массовый рынок",
            "b2b": "🏢 Бизнес (B2B)",
            "mixed": "🔀 Смешанная аудитория",
        },
    },
    {
        "id": "key_features",
        "question": "⚡ <b>Шаг 3/6: Ключевые функции</b>\n\nЧто обязательно должно быть? (выберите главное)",
        "options": {
            "catalog_cart": "🛒 Каталог + Корзина",
            "booking": "📅 Бронирование/Запись",
            "payments": "💳 Онлайн-оплата",
            "loyalty": "❤️ Программа лояльности",
            "ai_bot": "🤖 AI чат-бот",
            "delivery": "🚚 Доставка",
            "analytics": "📊 Аналитика",
            "crm": "👥 CRM-система",
        },
    },
    {
        "id": "design_pref",
        "question": "🎨 <b>Шаг 4/6: Дизайн</b>\n\nКакой стиль вам ближе?",
        "options": {
            "minimal": "⬜ Минимализм",
            "modern": "🔷 Современный",
            "premium": "🖤 Премиум/Люкс",
            "bright": "🌈 Яркий/Молодёжный",
            "corporate": "📐 Корпоративный",
            "custom_design": "🎨 У меня есть макет",
        },
    },
    {
        "id": "integrations",
        "question": "🔗 <b>Шаг 5/6: Интеграции</b>\n\nЧто нужно подключить?",
        "options": {
            "tg_payments": "⭐ Telegram Stars",
            "bank_cards": "💳 Банковские карты",
            "1c": "📦 1C / МойСклад",
            "crm_ext": "📋 CRM (Bitrix/AmoCRM)",
            "maps": "🗺 Google Maps",
            "sms_email": "📧 SMS/Email",
            "none": "❌ Пока не нужны",
        },
    },
    {
        "id": "budget_timeline",
        "question": "💰 <b>Шаг 6/6: Бюджет и сроки</b>\n\nВаш приоритет?",
        "options": {
            "fast_cheap": "⚡ Быстро и бюджетно",
            "balanced": "⚖️ Баланс цены и качества",
            "quality": "🏆 Максимальное качество",
            "mvp_first": "🚀 Сначала MVP, потом доработки",
        },
    },
]


@dataclass
class BriefState:
    user_id: int
    step: int = 0
    answers: Dict[str, str] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed: bool = False


class BriefGenerator:
    def __init__(self):
        self._states: Dict[int, BriefState] = {}
        self._init_db()

    def _init_db(self):
        try:
            from src.database import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS brief_states (
                            user_id BIGINT PRIMARY KEY,
                            step INTEGER DEFAULT 0,
                            answers JSONB DEFAULT '{}',
                            completed BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Brief states DB init failed (will use in-memory): {e}")

    def _save_to_db(self, state: BriefState):
        try:
            from src.database import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO brief_states (user_id, step, answers, completed, updated_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (user_id)
                        DO UPDATE SET step = EXCLUDED.step,
                                      answers = EXCLUDED.answers,
                                      completed = EXCLUDED.completed,
                                      updated_at = NOW()
                    """, (state.user_id, state.step, json.dumps(state.answers), state.completed))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save brief state to DB: {e}")

    def _load_from_db(self, user_id: int) -> Optional[BriefState]:
        try:
            from src.database import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT step, answers, completed FROM brief_states
                        WHERE user_id = %s
                    """, (user_id,))
                    row = cur.fetchone()
                    if row:
                        answers = row[1] if isinstance(row[1], dict) else json.loads(row[1]) if row[1] else {}
                        state = BriefState(
                            user_id=user_id,
                            step=row[0],
                            answers=answers,
                            completed=row[2],
                        )
                        self._states[user_id] = state
                        return state
        except Exception as e:
            logger.warning(f"Failed to load brief state from DB: {e}")
        return None

    def _delete_from_db(self, user_id: int):
        try:
            from src.database import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM brief_states WHERE user_id = %s", (user_id,))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to delete brief state from DB: {e}")

    def start_brief(self, user_id: int) -> BriefState:
        state = BriefState(user_id=user_id)
        self._states[user_id] = state
        self._save_to_db(state)
        return state

    def get_state(self, user_id: int) -> Optional[BriefState]:
        state = self._states.get(user_id)
        if state:
            return state
        return self._load_from_db(user_id)

    def clear_state(self, user_id: int) -> None:
        self._states.pop(user_id, None)
        self._delete_from_db(user_id)

    def get_current_step(self, user_id: int) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
        state = self.get_state(user_id)
        if not state or state.step >= len(BRIEF_STEPS):
            return None

        step_data = BRIEF_STEPS[state.step]
        buttons = []
        items = list(step_data["options"].items())
        for i in range(0, len(items), 2):
            row = []
            for key, label in items[i:i+2]:
                row.append(InlineKeyboardButton(
                    label, callback_data=f"brief_{step_data['id']}_{key}"
                ))
            buttons.append(row)
        buttons.append([InlineKeyboardButton("❌ Отменить", callback_data="brief_cancel")])

        return step_data["question"], InlineKeyboardMarkup(buttons)

    def process_answer(self, user_id: int, step_id: str, answer: str) -> Optional[BriefState]:
        state = self.get_state(user_id)
        if not state:
            return None

        state.answers[step_id] = answer
        state.step += 1

        if state.step >= len(BRIEF_STEPS):
            state.completed = True

        self._save_to_db(state)
        return state

    def format_brief(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        state = self.get_state(user_id)
        if not state or not state.completed:
            return "Бриф не завершён", InlineKeyboardMarkup([])

        labels = {}
        for step in BRIEF_STEPS:
            answer = state.answers.get(step["id"], "")
            labels[step["id"]] = step["options"].get(answer, answer)

        dash = "—"
        pt = labels.get("project_type", dash)
        au = labels.get("audience", dash)
        kf = labels.get("key_features", dash)
        dp = labels.get("design_pref", dash)
        ig = labels.get("integrations", dash)
        bt = labels.get("budget_timeline", dash)
        text = (
            "📋 <b>ВАШ БРИФ ПРОЕКТА</b>\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"📌 <b>Тип проекта:</b> {pt}\n"
            f"👥 <b>Аудитория:</b> {au}\n"
            f"⚡ <b>Ключевые функции:</b> {kf}\n"
            f"🎨 <b>Дизайн:</b> {dp}\n"
            f"🔗 <b>Интеграции:</b> {ig}\n"
            f"💰 <b>Приоритет:</b> {bt}\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "✅ <b>Бриф сохранён!</b>\n\n"
            "Нажмите кнопку ниже — AI мгновенно сформирует "
            "персональное коммерческое предложение в формате PDF."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📄 Получить PDF-предложение", callback_data="generate_kp",
                **styled_button_api_kwargs(style="constructive")
            )],
            [InlineKeyboardButton(
                "👨‍💼 Отправить менеджеру", callback_data="brief_send_manager",
            )],
            [InlineKeyboardButton("🧮 Рассчитать стоимость", callback_data="menu_calculator")],
            [InlineKeyboardButton("💬 Обсудить с AI", callback_data="quiz_to_ai")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="menu_back")],
        ])

        return text, keyboard

    def save_to_lead(self, user_id: int, username: str = "", first_name: str = "") -> None:
        state = self.get_state(user_id)
        if not state:
            return
        try:
            from src.leads import lead_manager, LeadPriority
            lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)

            brief_text = []
            for step in BRIEF_STEPS:
                answer = state.answers.get(step["id"], "")
                label = step["options"].get(answer, answer)
                brief_text.append(f"{step['id']}: {label}")

            lead_manager.update_lead(
                user_id,
                message="; ".join(brief_text),
                priority=LeadPriority.HOT,
                score=60,
            )
            lead_manager.add_tag(user_id, "brief_completed")
        except Exception as e:
            logger.warning(f"Failed to save brief to lead: {e}")

    def get_brief_summary_for_manager(self, user_id: int) -> str:
        state = self.get_state(user_id)
        if not state:
            return "Бриф не найден"

        lines = ["📋 БРИФ ПРОЕКТА\n"]
        for step in BRIEF_STEPS:
            answer = state.answers.get(step["id"], "")
            label = step["options"].get(answer, answer)
            step_name = step["question"].split(":")[0].replace("<b>", "").replace("</b>", "").strip()
            step_name = step_name.split("/6")[-1].strip(": ")
            lines.append(f"• {step_name}: {label}")

        return "\n".join(lines)


brief_generator = BriefGenerator()
