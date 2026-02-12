"""Interactive onboarding quiz with guided selling flow.

World-class onboarding: qualifies client in 4 steps,
then delivers personalized recommendation with matching
template, case study, ROI estimate, and next action.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot_api import styled_button_api_kwargs

logger = logging.getLogger(__name__)


BUSINESS_TYPES = {
    "shop": {"name": "Интернет-магазин", "icon": "🛒", "template": "ecommerce"},
    "restaurant": {"name": "Ресторан / Доставка", "icon": "🍽", "template": "restaurant"},
    "beauty": {"name": "Салон красоты", "icon": "💇‍♀️", "template": "services"},
    "fitness": {"name": "Фитнес-клуб", "icon": "🏋️", "template": "fitness"},
    "medical": {"name": "Медицина", "icon": "🏥", "template": "services"},
    "education": {"name": "Образование", "icon": "📚", "template": "services"},
    "services": {"name": "Услуги / Сервис", "icon": "🔧", "template": "services"},
    "other": {"name": "Другое", "icon": "💼", "template": "services"},
}

PROBLEMS = {
    "more_clients": {"name": "Привлечь больше клиентов", "icon": "📈", "weight": 3},
    "automate": {"name": "Автоматизировать процессы", "icon": "⚙️", "weight": 2},
    "online_pay": {"name": "Принимать оплату онлайн", "icon": "💳", "weight": 3},
    "mobile_app": {"name": "Запустить мобильное приложение", "icon": "📱", "weight": 2},
    "compete": {"name": "Обойти конкурентов", "icon": "🚀", "weight": 3},
    "loyalty": {"name": "Удержать клиентов", "icon": "❤️", "weight": 2},
}

BUDGETS = {
    "low": {"name": "До 100 000 ₽", "icon": "💰", "range": (0, 100000)},
    "medium": {"name": "100 000 — 200 000 ₽", "icon": "💰💰", "range": (100000, 200000)},
    "high": {"name": "200 000 — 400 000 ₽", "icon": "💰💰💰", "range": (200000, 400000)},
    "premium": {"name": "400 000 ₽ и выше", "icon": "💎", "range": (400000, 999999)},
    "unsure": {"name": "Пока не определился", "icon": "🤔", "range": (0, 200000)},
}

TIMELINES = {
    "asap": {"name": "Как можно скорее", "icon": "⚡", "days": "7-14", "urgency": "high"},
    "month": {"name": "В ближайший месяц", "icon": "📅", "days": "14-21", "urgency": "medium"},
    "quarter": {"name": "В течение 3 месяцев", "icon": "🗓", "days": "21-30", "urgency": "low"},
    "exploring": {"name": "Просто изучаю", "icon": "🔍", "days": "гибкие", "urgency": "low"},
}

ROI_DATA = {
    "shop": {
        "avg_check": 3500, "orders_day": 15, "conversion_boost": 0.35,
        "case": "Radiance (магазин одежды) — +40% онлайн-заказов за 3 месяца",
        "recommended_features": ["catalog", "cart", "payments", "push", "loyalty"],
    },
    "restaurant": {
        "avg_check": 1800, "orders_day": 40, "conversion_boost": 0.25,
        "case": "Fresh Kitchen — +30% заказов на доставку, время обработки -60%",
        "recommended_features": ["catalog", "cart", "payments", "delivery", "booking"],
    },
    "beauty": {
        "avg_check": 2500, "orders_day": 12, "conversion_boost": 0.30,
        "case": "GlowUp Studio — онлайн-запись снизила no-show на 45%",
        "recommended_features": ["booking", "auth", "push", "loyalty", "reviews"],
    },
    "fitness": {
        "avg_check": 5000, "orders_day": 8, "conversion_boost": 0.20,
        "case": "FitLife — удержание клиентов +60% с трекингом прогресса",
        "recommended_features": ["booking", "auth", "push", "progress", "subscriptions"],
    },
    "medical": {
        "avg_check": 3000, "orders_day": 20, "conversion_boost": 0.25,
        "case": "МедЦентр Плюс — сокращение звонков на 70% с онлайн-записью",
        "recommended_features": ["booking", "auth", "push", "calendar", "chat"],
    },
    "education": {
        "avg_check": 4000, "orders_day": 10, "conversion_boost": 0.30,
        "case": "SkillHub — доходимость курсов +40% с геймификацией",
        "recommended_features": ["auth", "progress", "push", "subscriptions", "chat"],
    },
    "services": {
        "avg_check": 4000, "orders_day": 10, "conversion_boost": 0.25,
        "case": "ServicePro — автозапись заменила 3 администраторов",
        "recommended_features": ["booking", "auth", "payments", "push", "reviews"],
    },
    "other": {
        "avg_check": 3000, "orders_day": 10, "conversion_boost": 0.20,
        "case": "Более 50 успешных проектов в разных нишах",
        "recommended_features": ["auth", "catalog", "payments", "push", "analytics"],
    },
}


@dataclass
class QuizState:
    user_id: int
    step: int = 0
    business_type: Optional[str] = None
    problem: Optional[str] = None
    budget: Optional[str] = None
    timeline: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed: bool = False


class OnboardingManager:
    def __init__(self):
        self._states: Dict[int, QuizState] = {}

    def start_quiz(self, user_id: int) -> QuizState:
        self._states[user_id] = QuizState(user_id=user_id)
        return self._states[user_id]

    def get_state(self, user_id: int) -> Optional[QuizState]:
        return self._states.get(user_id)

    def clear_state(self, user_id: int) -> None:
        self._states.pop(user_id, None)

    def get_step_keyboard(self, step: int) -> Tuple[str, InlineKeyboardMarkup]:
        if step == 0:
            return self._business_type_step()
        elif step == 1:
            return self._problem_step()
        elif step == 2:
            return self._budget_step()
        elif step == 3:
            return self._timeline_step()
        return ("", InlineKeyboardMarkup([]))

    def process_answer(self, user_id: int, answer: str) -> Optional[QuizState]:
        state = self._states.get(user_id)
        if not state:
            return None

        if state.step == 0:
            state.business_type = answer
        elif state.step == 1:
            state.problem = answer
        elif state.step == 2:
            state.budget = answer
        elif state.step == 3:
            state.timeline = answer
            state.completed = True

        state.step += 1
        return state

    def generate_recommendation(self, user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
        state = self._states.get(user_id)
        if not state or not state.completed:
            return ("Квиз не завершён", InlineKeyboardMarkup([]))

        btype = state.business_type or "other"
        roi = ROI_DATA.get(btype, ROI_DATA["other"])
        biz = BUSINESS_TYPES.get(btype, BUSINESS_TYPES["other"])
        budget_info = BUDGETS.get(state.budget or "medium", BUDGETS["medium"])
        timeline_info = TIMELINES.get(state.timeline or "month", TIMELINES["month"])

        avg_check = roi["avg_check"]
        orders = roi["orders_day"]
        boost = roi["conversion_boost"]
        monthly_extra = int(avg_check * orders * 30 * boost)
        yearly_extra = monthly_extra * 12
        app_cost = budget_info["range"][1] if budget_info["range"][1] <= 200000 else 200000
        if app_cost == 0:
            app_cost = 150000
        payback_months = max(1, round(app_cost / monthly_extra, 1)) if monthly_extra > 0 else 12
        roi_percent = int((yearly_extra - app_cost) / app_cost * 100) if app_cost > 0 else 0

        from src.calculator import FEATURES as CALC_FEATURES
        recommended_cost = sum(
            CALC_FEATURES[f]["price"] for f in roi["recommended_features"]
            if f in CALC_FEATURES
        )

        features_list = []
        for f_id in roi["recommended_features"]:
            if f_id in CALC_FEATURES:
                features_list.append(f"  ✓ {CALC_FEATURES[f_id]['name']}")

        problem_name = PROBLEMS.get(state.problem, {}).get("name", "развитие бизнеса")

        text = (
            f"🎯 <b>Персональная рекомендация для вашего бизнеса</b>\n\n"
            f"{biz['icon']} <b>Ваш бизнес:</b> {biz['name']}\n"
            f"🎯 <b>Цель:</b> {problem_name}\n"
            f"💰 <b>Бюджет:</b> {budget_info['name']}\n"
            f"⏱ <b>Сроки:</b> {timeline_info['name']}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Расчёт окупаемости (ROI)</b>\n\n"
            f"📈 Дополнительный доход: <b>+{monthly_extra:,} ₽/мес</b>\n"
            f"💵 За год: <b>+{yearly_extra:,} ₽</b>\n"
            f"⏱ Окупаемость: <b>{payback_months} мес.</b>\n"
            f"📊 ROI: <b>+{roi_percent}%</b>\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"✅ <b>Рекомендуемый набор функций:</b>\n"
        ).replace(",", " ")

        text += "\n".join(features_list)

        text += (
            f"\n\n💵 <b>Ориентировочная стоимость: {recommended_cost:,} ₽</b>\n"
            f"⏱ <b>Срок разработки: {timeline_info['days']} дней</b>\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"🏆 <b>Успешный кейс:</b>\n"
            f"<i>{roi['case']}</i>"
        ).replace(",", " ")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📋 Составить бриф проекта", callback_data="start_brief",
                **styled_button_api_kwargs(style="constructive")
            )],
            [InlineKeyboardButton("🧮 Калькулятор стоимости", callback_data="menu_calculator")],
            [InlineKeyboardButton("💬 Обсудить с AI-консультантом", callback_data="quiz_to_ai")],
            [InlineKeyboardButton("👨‍💼 Связаться с менеджером", callback_data="request_manager")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="menu_back")],
        ])

        return text, keyboard

    def _business_type_step(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            "👋 <b>Добро пожаловать в WEB4TG Studio!</b>\n\n"
            "Я помогу подобрать идеальное решение для вашего бизнеса.\n"
            "Ответьте на 4 быстрых вопроса — и получите персональную рекомендацию "
            "с расчётом окупаемости.\n\n"
            "📌 <b>Шаг 1 из 4:</b> Какой у вас бизнес?"
        )
        buttons = []
        items = list(BUSINESS_TYPES.items())
        for i in range(0, len(items), 2):
            row = []
            for key, val in items[i:i+2]:
                row.append(InlineKeyboardButton(
                    f"{val['icon']} {val['name']}", callback_data=f"quiz_biz_{key}"
                ))
            buttons.append(row)
        buttons.append([InlineKeyboardButton("⏭ Пропустить квиз", callback_data="quiz_skip")])
        return text, InlineKeyboardMarkup(buttons)

    def _problem_step(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            "🎯 <b>Шаг 2 из 4:</b> Какая главная задача?\n\n"
            "Выберите то, что для вас сейчас важнее всего:"
        )
        buttons = []
        for key, val in PROBLEMS.items():
            buttons.append([InlineKeyboardButton(
                f"{val['icon']} {val['name']}", callback_data=f"quiz_prob_{key}"
            )])
        return text, InlineKeyboardMarkup(buttons)

    def _budget_step(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            "💰 <b>Шаг 3 из 4:</b> Какой примерный бюджет?\n\n"
            "Это поможет подобрать оптимальное решение:"
        )
        buttons = []
        for key, val in BUDGETS.items():
            buttons.append([InlineKeyboardButton(
                f"{val['icon']} {val['name']}", callback_data=f"quiz_bud_{key}"
            )])
        return text, InlineKeyboardMarkup(buttons)

    def _timeline_step(self) -> Tuple[str, InlineKeyboardMarkup]:
        text = (
            "⏱ <b>Шаг 4 из 4:</b> Когда хотите запустить?\n\n"
            "Это определит приоритет и план работы:"
        )
        buttons = []
        for key, val in TIMELINES.items():
            buttons.append([InlineKeyboardButton(
                f"{val['icon']} {val['name']}", callback_data=f"quiz_time_{key}"
            )])
        return text, InlineKeyboardMarkup(buttons)

    def save_to_lead(self, user_id: int) -> None:
        state = self._states.get(user_id)
        if not state:
            return
        try:
            from src.leads import lead_manager
            biz = BUSINESS_TYPES.get(state.business_type or "", {})
            lead_manager.update_lead(
                user_id,
                business_type=biz.get("name", ""),
                budget=BUDGETS.get(state.budget or "", {}).get("name", ""),
            )
            if state.timeline in ("asap", "month"):
                from src.leads import LeadPriority
                lead_manager.update_lead(user_id, priority=LeadPriority.HOT, score=50)
            elif state.timeline == "quarter":
                from src.leads import LeadPriority
                lead_manager.update_lead(user_id, priority=LeadPriority.WARM, score=30)
        except Exception as e:
            logger.warning(f"Failed to save quiz to lead: {e}")


onboarding_manager = OnboardingManager()
