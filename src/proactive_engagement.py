"""Proactive Engagement Engine — trigger-based dialog initiation, behavioral signals, predictive engagement."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.database import get_connection, DATABASE_URL
from src.leads import lead_manager
from src.config import config
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

TRIGGER_TYPES = {
    "funnel_stall": "Клиент завис на этапе воронки",
    "engagement_drop": "Резкое падение вовлечённости",
    "high_intent_no_action": "Высокий интерес, но нет действия",
    "cart_abandonment": "Калькулятор без заявки",
    "comeback_window": "Оптимальное окно для возврата",
    "optimal_time_window": "Лучшее время для контакта",
    "competitor_research": "Упоминание конкурентов + молчание",
    "warm_reactivation": "Реактивация тёплого лида",
}

MAX_PROACTIVE_PER_4H = 1
MAX_PROACTIVE_PER_DAY = 3
DELIVERY_HOUR_START = 9
DELIVERY_HOUR_END = 20

TRIGGER_PROMPTS = {
    "funnel_stall": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент активно общался, изучал услуги, но внезапно замолчал на этапе "{stage}".
Этап воронки: {stage}
Время молчания: {hours_silent}ч

Контекст:
{context}

{client_signals}

ЗАДАЧА: Мягко вернуть клиента, предложив конкретную помощь по тому, на чём он остановился.

СТРАТЕГИЯ:
- Не спрашивай "всё ли ок" — дай конкретику по теме, на которой клиент застрял
- Если застрял на ценах — предложи расчёт ROI или рассрочку
- Если на портфолио — предложи кейс из его ниши
- Если на консультации — упрости шаг (мини-звонок 5 мин)

ФОРМАТ: 2-3 коротких предложения. Без markdown, без списков. Одно emoji максимум в конце.

Напиши ТОЛЬКО текст.""",

    "engagement_drop": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент был активен (отвечал быстро, использовал инструменты), но скорость ответов резко упала.
Было: {prev_speed} мин/ответ → Стало: {curr_speed} мин/ответ
Последнее действие: {last_action}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Вернуть вовлечённость через микро-ценность, связанную с последним интересом клиента.

СТРАТЕГИЯ:
- Начни с чего-то полезного по теме последнего разговора
- Не упоминай что заметил "снижение активности"
- Предложи быстрый следующий шаг (2 минуты)

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "high_intent_no_action": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент показал высокий интерес (propensity {score}/100), но не сделал ключевое действие.
Propensity score: {score}/100
Использовал: {tools_used}
НЕ сделал: {missing_action}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Подтолкнуть к следующему шагу через снижение барьера.

СТРАТЕГИЯ:
- Покажи что ты УЖЕ подготовил что-то для клиента
- Предложи бесплатный/лёгкий шаг к действию
- Используй принцип "я сделал за тебя" — клиенту остаётся только подтвердить

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "cart_abandonment": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент использовал калькулятор (рассчитал стоимость {cost}₽), но не оставил заявку.
Рассчитанная стоимость: {cost}₽
Выбранные фичи: {features}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Вернуть клиента, обработав потенциальное возражение по цене.

СТРАТЕГИЯ:
- Упомяни конкретную сумму — покажи что помнишь
- Предложи рассрочку или MVP-вариант
- Покажи ROI: "за Xк/мес окупится за Y дней"
- Не давай скидку сразу, только если клиент возражает

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "comeback_window": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент вернулся после паузы {days_away} дней, но ещё ничего не написал. Это окно для инициативы.
Дней отсутствия: {days_away}
Прежний интерес: {prev_interest}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Тёпло поприветствовать и предложить что-то НОВОЕ с момента последнего общения.

СТРАТЕГИЯ:
- Не упоминай что "давно не писал" прямо
- Расскажи о новом кейсе/фиче/акции, которая появилась
- Покажи что помнишь контекст (ниша, задача клиента)

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "optimal_time_window": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Анализ показал, что сейчас лучшее время для контакта с клиентом (он обычно активен в это время).
Обычное время активности: {active_hours}
Текущий этап: {stage}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Отправить ценное сообщение в оптимальный момент.

СТРАТЕГИЯ:
- Начни с микро-пользы: факт, совет, кейс из его ниши
- Привяжи к нерешённой задаче клиента
- Предложи лёгкий следующий шаг

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "competitor_research": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Клиент упоминал конкурентов/альтернативы ("{competitor_mention}"), потом замолчал — вероятно сравнивает.
Упомянутые альтернативы: {competitor_mention}
Молчит: {hours_silent}ч

Контекст:
{context}

{client_signals}

ЗАДАЧА: Помочь клиенту сравнить, не критикуя конкурентов.

СТРАТЕГИЯ:
- Предложи объективное сравнение ("составил таблицу плюсов и минусов")
- Подчеркни уникальные преимущества WEB4TG (специализация, сроки 7-15 дней, договор)
- Не критикуй альтернативы, вопросами подведи к выводу

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",

    "warm_reactivation": """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

СИТУАЦИЯ: Тёплый лид (score {score}/100) не проявлял активность {days_inactive} дней. Пора реактивировать.
Score: {score}/100
Дней неактивности: {days_inactive}
Последнее действие: {last_action}

Контекст:
{context}

{client_signals}

ЗАДАЧА: Реактивировать тёплый лид через новую ценность.

СТРАТЕГИЯ:
- Предложи что-то новое, чего не было раньше (свежий кейс, новая фича, акция)
- Упомяни конкретную выгоду для его бизнеса
- Снизь барьер входа максимально ("просто глянь 2 мин")

ФОРМАТ: 2-3 коротких предложения. Без markdown. Одно emoji максимум.

Напиши ТОЛЬКО текст.""",
}


def _build_client_signals(user_id: int) -> str:
    signals = []
    try:
        lead = lead_manager.get_lead(user_id)
        if lead:
            if lead.score and lead.score >= 50:
                signals.append("СИГНАЛ: Горячий лид")
            elif lead.score and lead.score >= 25:
                signals.append("СИГНАЛ: Тёплый лид")
            if lead.business_type:
                signals.append(f"НИША: {lead.business_type}")
            if lead.budget:
                signals.append(f"БЮДЖЕТ: {lead.budget}")
    except Exception:
        pass

    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile:
            if profile.get("business_type"):
                signals.append(f"БИЗНЕС: {profile['business_type']}")
            if profile.get("pain_points"):
                signals.append(f"БОЛИ: {profile['pain_points']}")
    except Exception:
        pass

    try:
        from src.propensity import propensity_scorer
        score = propensity_scorer.calculate_score(user_id)
        if score:
            signals.append(f"PROPENSITY: {score}/100")
    except Exception:
        pass

    return "\n".join(signals) if signals else "Нет данных о клиенте"


class ProactiveEngagementEngine:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, proactive engagement disabled")
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS behavioral_signals (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            avg_response_speed_min FLOAT DEFAULT 0,
                            prev_response_speed_min FLOAT DEFAULT 0,
                            session_frequency_days FLOAT DEFAULT 0,
                            last_active_hour INTEGER,
                            peak_active_hours VARCHAR(50),
                            engagement_velocity FLOAT DEFAULT 0,
                            prev_engagement_velocity FLOAT DEFAULT 0,
                            last_funnel_stage VARCHAR(50),
                            funnel_stage_entered_at TIMESTAMP,
                            competitor_mentioned BOOLEAN DEFAULT FALSE,
                            competitor_context TEXT,
                            last_tool_used VARCHAR(50),
                            calculator_result INTEGER,
                            calculator_features TEXT,
                            days_since_last_activity FLOAT DEFAULT 0,
                            total_sessions INTEGER DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id)
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_behavioral_user
                        ON behavioral_signals(user_id)
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS trigger_history (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            trigger_type VARCHAR(50) NOT NULL,
                            trigger_score FLOAT DEFAULT 0,
                            message_text TEXT,
                            status VARCHAR(20) DEFAULT 'sent',
                            responded BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trigger_user_created
                        ON trigger_history(user_id, created_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trigger_status
                        ON trigger_history(status, created_at)
                    """)
            logger.info("Proactive engagement tables initialized")
        except Exception as e:
            logger.error(f"Failed to init proactive engagement tables: {e}")

    def update_behavioral_signals(self, user_id: int, event_type: str = "message", **kwargs):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO behavioral_signals (user_id)
                        VALUES (%s)
                        ON CONFLICT (user_id) DO NOTHING
                    """, (user_id,))

                    updates = ["updated_at = CURRENT_TIMESTAMP"]
                    params = []

                    if event_type == "message":
                        cur.execute("""
                            SELECT avg_response_speed_min FROM behavioral_signals WHERE user_id = %s
                        """, (user_id,))
                        row = cur.fetchone()
                        old_speed = row[0] if row and row[0] else 0
                        new_speed = kwargs.get("response_speed_min", 0)
                        if new_speed > 0:
                            updates.append("prev_response_speed_min = avg_response_speed_min")
                            avg = (old_speed * 0.7 + new_speed * 0.3) if old_speed > 0 else new_speed
                            updates.append("avg_response_speed_min = %s")
                            params.append(avg)

                        now_hour = datetime.utcnow().hour
                        tz_offset = kwargs.get("tz_offset", 0)
                        local_hour = (now_hour + tz_offset) % 24
                        updates.append("last_active_hour = %s")
                        params.append(local_hour)

                    if event_type == "funnel_stage":
                        stage = kwargs.get("stage", "")
                        if stage:
                            updates.append("last_funnel_stage = %s")
                            params.append(stage)
                            updates.append("funnel_stage_entered_at = CURRENT_TIMESTAMP")

                    if event_type == "competitor_mention":
                        updates.append("competitor_mentioned = TRUE")
                        mention = kwargs.get("competitor_context", "")
                        if mention:
                            updates.append("competitor_context = %s")
                            params.append(mention[:500])

                    if event_type == "calculator_used":
                        result = kwargs.get("cost", 0)
                        features = kwargs.get("features", "")
                        if result:
                            updates.append("calculator_result = %s")
                            params.append(result)
                        if features:
                            updates.append("calculator_features = %s")
                            params.append(features[:500])
                        updates.append("last_tool_used = 'calculator'")

                    if event_type in ("tool_portfolio", "tool_pricing", "tool_brief", "tool_consultation"):
                        updates.append("last_tool_used = %s")
                        params.append(event_type)

                    cur.execute("""
                        SELECT engagement_velocity FROM behavioral_signals WHERE user_id = %s
                    """, (user_id,))
                    ev_row = cur.fetchone()
                    old_ev = ev_row[0] if ev_row and ev_row[0] else 0

                    try:
                        from src.propensity import propensity_scorer
                        new_score = propensity_scorer.calculate_score(user_id)
                        if new_score is not None:
                            updates.append("prev_engagement_velocity = engagement_velocity")
                            updates.append("engagement_velocity = %s")
                            params.append(float(new_score))
                    except Exception:
                        pass

                    updates.append("days_since_last_activity = 0")

                    params.append(user_id)
                    cur.execute(
                        f"UPDATE behavioral_signals SET {', '.join(updates)} WHERE user_id = %s",
                        params
                    )
        except Exception as e:
            logger.error(f"Failed to update behavioral signals for {user_id}: {e}")

    def _check_anti_spam(self, user_id: int) -> bool:
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM trigger_history
                        WHERE user_id = %s AND created_at > NOW() - INTERVAL '4 hours'
                        AND status = 'sent'
                    """, (user_id,))
                    count_4h = cur.fetchone()[0]
                    if count_4h >= MAX_PROACTIVE_PER_4H:
                        return False

                    cur.execute("""
                        SELECT COUNT(*) FROM trigger_history
                        WHERE user_id = %s AND created_at > NOW() - INTERVAL '24 hours'
                        AND status = 'sent'
                    """, (user_id,))
                    count_24h = cur.fetchone()[0]
                    if count_24h >= MAX_PROACTIVE_PER_DAY:
                        return False

                    return True
        except Exception as e:
            logger.error(f"Anti-spam check failed for {user_id}: {e}")
            return False

    def _is_delivery_window(self, user_id: int) -> bool:
        try:
            from src.session import get_client_profile
            profile = get_client_profile(user_id)
            tz_offset = 0
            if profile and profile.get("timezone_offset") is not None:
                tz_offset = profile["timezone_offset"]
            local_hour = (datetime.utcnow().hour + tz_offset) % 24
            return DELIVERY_HOUR_START <= local_hour < DELIVERY_HOUR_END
        except Exception:
            current_hour = datetime.utcnow().hour
            return 6 <= current_hour < 18

    def _is_user_eligible(self, user_id: int) -> bool:
        try:
            from src.followup import follow_up_manager
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM follow_ups
                        WHERE user_id = %s AND status = 'paused'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

                    cur.execute("""
                        SELECT is_blocked FROM bot_users
                        WHERE user_id = %s
                    """, (user_id,))
                    row = cur.fetchone()
                    if row and row[0]:
                        return False

                    cur.execute("""
                        SELECT id FROM follow_ups
                        WHERE user_id = %s AND status = 'scheduled'
                        AND scheduled_at <= NOW() + INTERVAL '2 hours'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

            return True
        except Exception:
            return True

    def _calculate_predictive_score(self, signals: Dict) -> float:
        score = 0.0

        response_speed = signals.get("avg_response_speed_min", 0) or 0
        prev_speed = signals.get("prev_response_speed_min", 0) or 0
        if prev_speed > 0 and response_speed > 0:
            speed_ratio = response_speed / prev_speed
            if speed_ratio > 2.0:
                score += 15
            elif speed_ratio > 1.5:
                score += 10
            elif speed_ratio < 0.8:
                score += 5

        velocity = signals.get("engagement_velocity", 0) or 0
        prev_velocity = signals.get("prev_engagement_velocity", 0) or 0
        if prev_velocity > 0:
            velocity_change = (velocity - prev_velocity) / prev_velocity
            if velocity_change < -0.3:
                score += 15
            elif velocity_change < -0.1:
                score += 8

        days_inactive = signals.get("days_since_last_activity", 0) or 0
        if 1 <= days_inactive <= 3:
            score += 20
        elif 3 < days_inactive <= 7:
            score += 15
        elif 7 < days_inactive <= 14:
            score += 10
        elif days_inactive > 14:
            score += 5

        sessions = signals.get("total_sessions", 0) or 0
        if sessions >= 3:
            score += 10
        elif sessions >= 2:
            score += 5

        tool = signals.get("last_tool_used", "") or ""
        if tool in ("calculator", "tool_brief"):
            score += 15
        elif tool in ("tool_consultation", "tool_pricing"):
            score += 10
        elif tool in ("tool_portfolio",):
            score += 5

        if signals.get("calculator_result"):
            score += 10
        if signals.get("competitor_mentioned"):
            score += 10

        return min(score, 100)

    def evaluate_triggers(self) -> List[Dict]:
        if not DATABASE_URL:
            return []

        triggered = []
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT bs.*,
                               im.total_messages, im.last_interaction, im.tools_used,
                               im.calculator_uses, im.portfolio_views, im.pricing_views,
                               im.lead_submitted, im.consultation_requested, im.payment_viewed,
                               im.last_score as propensity_score,
                               im.brief_uses, im.compare_uses
                        FROM behavioral_signals bs
                        LEFT JOIN interaction_metrics im ON bs.user_id = im.user_id
                        WHERE bs.updated_at > NOW() - INTERVAL '30 days'
                    """)
                    users = cur.fetchall()

            for u in users:
                user_id = u["user_id"]

                if not self._is_user_eligible(user_id):
                    continue
                if not self._check_anti_spam(user_id):
                    continue
                if not self._is_delivery_window(user_id):
                    continue

                triggers = self._detect_triggers(u)
                if triggers:
                    best = max(triggers, key=lambda t: t["score"])
                    triggered.append(best)

        except Exception as e:
            logger.error(f"Failed to evaluate triggers: {e}")

        triggered.sort(key=lambda t: t["score"], reverse=True)
        return triggered[:20]

    def _detect_triggers(self, u: Dict) -> List[Dict]:
        triggers = []
        user_id = u["user_id"]
        last_interaction = u.get("last_interaction")
        propensity = u.get("propensity_score", 0) or 0

        if last_interaction:
            hours_since = (datetime.utcnow() - last_interaction).total_seconds() / 3600
        else:
            hours_since = 999

        stage = u.get("last_funnel_stage", "") or ""
        stage_entered = u.get("funnel_stage_entered_at")
        if stage and stage_entered:
            stage_hours = (datetime.utcnow() - stage_entered).total_seconds() / 3600
            if stage_hours >= 6 and hours_since >= 4:
                score = self._calculate_predictive_score(u)
                if score >= 25:
                    triggers.append({
                        "user_id": user_id,
                        "trigger_type": "funnel_stall",
                        "score": score,
                        "params": {
                            "stage": stage,
                            "hours_silent": int(hours_since),
                        }
                    })

        avg_speed = u.get("avg_response_speed_min", 0) or 0
        prev_speed = u.get("prev_response_speed_min", 0) or 0
        if prev_speed > 0 and avg_speed > 0:
            ratio = avg_speed / prev_speed
            if ratio > 2.0 and hours_since >= 3:
                score = self._calculate_predictive_score(u)
                if score >= 20:
                    triggers.append({
                        "user_id": user_id,
                        "trigger_type": "engagement_drop",
                        "score": score + 5,
                        "params": {
                            "prev_speed": round(prev_speed, 1),
                            "curr_speed": round(avg_speed, 1),
                            "last_action": u.get("last_tool_used", "сообщение"),
                        }
                    })

        if propensity >= 40:
            lead_submitted = u.get("lead_submitted", False)
            consultation = u.get("consultation_requested", False)
            if not lead_submitted and not consultation and hours_since >= 6:
                tools = []
                if u.get("calculator_uses", 0) > 0:
                    tools.append("калькулятор")
                if u.get("portfolio_views", 0) > 0:
                    tools.append("портфолио")
                if u.get("pricing_views", 0) > 0:
                    tools.append("цены")
                if u.get("brief_uses", 0) > 0:
                    tools.append("бриф")

                missing = "заявка/консультация"
                if not lead_submitted:
                    missing = "заявка"
                if not consultation:
                    missing = "запись на консультацию"

                score = self._calculate_predictive_score(u)
                if score >= 30:
                    triggers.append({
                        "user_id": user_id,
                        "trigger_type": "high_intent_no_action",
                        "score": score + 10,
                        "params": {
                            "score": propensity,
                            "tools_used": ", ".join(tools) if tools else "нет",
                            "missing_action": missing,
                        }
                    })

        calc_uses = u.get("calculator_uses", 0) or 0
        calc_result = u.get("calculator_result", 0) or 0
        lead_submitted = u.get("lead_submitted", False)
        if calc_uses > 0 and calc_result > 0 and not lead_submitted and hours_since >= 4:
            score = self._calculate_predictive_score(u)
            if score >= 20:
                triggers.append({
                    "user_id": user_id,
                    "trigger_type": "cart_abandonment",
                    "score": score + 15,
                    "params": {
                        "cost": calc_result,
                        "features": u.get("calculator_features", ""),
                    }
                })

        days_inactive = hours_since / 24
        if 3 <= days_inactive <= 14 and propensity >= 20:
            score = self._calculate_predictive_score(u)
            if score >= 20:
                triggers.append({
                    "user_id": user_id,
                    "trigger_type": "comeback_window",
                    "score": score,
                    "params": {
                        "days_away": int(days_inactive),
                        "prev_interest": stage or "общий интерес",
                    }
                })

        peak_hours = u.get("peak_active_hours", "") or ""
        last_hour = u.get("last_active_hour")
        if last_hour is not None:
            try:
                from src.session import get_client_profile
                profile = get_client_profile(user_id)
                tz_offset = 0
                if profile and profile.get("timezone_offset") is not None:
                    tz_offset = profile["timezone_offset"]
                local_hour = (datetime.utcnow().hour + tz_offset) % 24
                if abs(local_hour - last_hour) <= 1 and hours_since >= 12 and propensity >= 30:
                    score = self._calculate_predictive_score(u)
                    triggers.append({
                        "user_id": user_id,
                        "trigger_type": "optimal_time_window",
                        "score": score + 5,
                        "params": {
                            "active_hours": f"{last_hour}:00",
                            "stage": stage or "интерес",
                        }
                    })
            except Exception:
                pass

        if u.get("competitor_mentioned") and hours_since >= 6 and hours_since <= 72:
            score = self._calculate_predictive_score(u)
            if score >= 15:
                triggers.append({
                    "user_id": user_id,
                    "trigger_type": "competitor_research",
                    "score": score + 10,
                    "params": {
                        "competitor_mention": u.get("competitor_context", "конкуренты")[:200],
                        "hours_silent": int(hours_since),
                    }
                })

        if 7 <= days_inactive <= 30 and 25 <= propensity <= 60:
            score = self._calculate_predictive_score(u)
            if score >= 15:
                triggers.append({
                    "user_id": user_id,
                    "trigger_type": "warm_reactivation",
                    "score": score,
                    "params": {
                        "score": propensity,
                        "days_inactive": int(days_inactive),
                        "last_action": u.get("last_tool_used", "сообщение"),
                    }
                })

        return triggers

    async def generate_trigger_message(self, trigger: Dict) -> str:
        trigger_type = trigger["trigger_type"]
        user_id = trigger["user_id"]
        params = trigger.get("params", {})

        try:
            messages = lead_manager.get_conversation_history(user_id, limit=8)
            context_parts = []
            for msg in messages[-6:]:
                role_label = "Клиент" if msg.role == "user" else "Алекс"
                context_parts.append(f"{role_label}: {msg.content[:250]}")
            context = "\n".join(context_parts) if context_parts else "Контекст диалога минимален."

            client_signals = _build_client_signals(user_id)

            prompt_template = TRIGGER_PROMPTS.get(trigger_type, TRIGGER_PROMPTS["funnel_stall"])
            format_params = {
                "context": context,
                "client_signals": client_signals,
                **params,
            }
            for key in ("stage", "hours_silent", "prev_speed", "curr_speed",
                         "last_action", "score", "tools_used", "missing_action",
                         "cost", "features", "days_away", "prev_interest",
                         "active_hours", "competitor_mention", "days_inactive"):
                if key not in format_params:
                    format_params[key] = ""

            prompt = prompt_template.format(**format_params)

            from src.ai_client import ai_client
            result = await ai_client.generate_response(
                messages=[{"role": "user", "parts": [{"text": prompt}]}],
                thinking_level="low"
            )

            if result:
                text = result.strip().strip('"').strip("'")
                if len(text) > 20:
                    return text

        except Exception as e:
            logger.error(f"Failed to generate trigger message for {user_id} ({trigger_type}): {e}")

        return self._get_fallback_message(trigger_type, params)

    def _get_fallback_message(self, trigger_type: str, params: Dict) -> str:
        fallbacks = {
            "funnel_stall": "Кстати, по поводу твоего проекта — подготовил примерный план. Могу скинуть? Займёт 2 минуты глянуть 😊",
            "engagement_drop": "Вспомнил про тебя — у нас свежий кейс из похожей ниши, +47 заказов за месяц. Интересно?",
            "high_intent_no_action": "Я тут прикинул примерный ROI для твоего проекта — цифры интересные получились. Скинуть?",
            "cart_abandonment": f"По твоему расчёту на {params.get('cost', '')}₽ — кстати, есть рассрочка от 35% предоплаты. Это меньше, чем зарплата стажёра за месяц)",
            "comeback_window": "У нас появилась новая фишка — MVP за 7 дней. Один клиент окупил за первую неделю. Если хочешь подробности — напиши)",
            "optimal_time_window": "Мини-аппы в среднем увеличивают конверсию на 35%. Могу показать как это работает для твоей ниши",
            "competitor_research": "Составил сравнительную таблицу — мини-апп vs другие решения. Там видно разницу в сроках и стоимости. Скинуть?",
            "warm_reactivation": "Давно не общались! У нас тут появились новые кейсы — думаю, тебе будет полезно глянуть)",
        }
        return fallbacks.get(trigger_type, fallbacks["funnel_stall"])

    def record_trigger_sent(self, user_id: int, trigger_type: str, score: float, message: str):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trigger_history (user_id, trigger_type, trigger_score, message_text, status)
                        VALUES (%s, %s, %s, %s, 'sent')
                    """, (user_id, trigger_type, score, message[:2000]))
        except Exception as e:
            logger.error(f"Failed to record trigger for {user_id}: {e}")

    def mark_trigger_responded(self, user_id: int):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trigger_history
                        SET responded = TRUE
                        WHERE user_id = %s AND status = 'sent' AND responded = FALSE
                        AND created_at > NOW() - INTERVAL '7 days'
                    """, (user_id,))
        except Exception as e:
            logger.error(f"Failed to mark trigger responded for {user_id}: {e}")

    def get_trigger_stats(self) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            trigger_type,
                            COUNT(*) as total_sent,
                            COUNT(*) FILTER (WHERE responded = TRUE) as responded,
                            ROUND(AVG(trigger_score)::numeric, 1) as avg_score,
                            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as sent_today,
                            COUNT(*) FILTER (WHERE responded = TRUE AND created_at > NOW() - INTERVAL '7 days') as responded_week
                        FROM trigger_history
                        WHERE status = 'sent'
                        GROUP BY trigger_type
                        ORDER BY total_sent DESC
                    """)
                    results = {}
                    for row in cur.fetchall():
                        tt = row["trigger_type"]
                        total = row["total_sent"] or 1
                        results[tt] = {
                            "total": row["total_sent"],
                            "responded": row["responded"],
                            "response_rate": round(row["responded"] / total * 100, 1),
                            "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
                            "today": row["sent_today"],
                            "responded_week": row["responded_week"],
                        }
                    return results
        except Exception as e:
            logger.error(f"Failed to get trigger stats: {e}")
            return {}

    def get_pending_triggers_count(self) -> int:
        if not DATABASE_URL:
            return 0
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) FROM behavioral_signals
                        WHERE updated_at > NOW() - INTERVAL '30 days'
                    """)
                    return cur.fetchone()[0]
        except Exception:
            return 0

    def get_recent_triggers(self, limit: int = 10) -> List[Dict]:
        if not DATABASE_URL:
            return []
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT th.user_id, th.trigger_type, th.trigger_score,
                               th.responded, th.created_at,
                               l.first_name, l.username
                        FROM trigger_history th
                        LEFT JOIN leads l ON th.user_id = l.user_id
                        WHERE th.status = 'sent'
                        ORDER BY th.created_at DESC
                        LIMIT %s
                    """, (limit,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    def get_conversion_metrics(self) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_triggers,
                            COUNT(*) FILTER (WHERE responded = TRUE) as total_responded,
                            COUNT(DISTINCT user_id) as unique_users,
                            COUNT(DISTINCT user_id) FILTER (WHERE responded = TRUE) as responded_users,
                            ROUND(AVG(trigger_score)::numeric, 1) as avg_trigger_score,
                            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as week_triggers,
                            COUNT(*) FILTER (WHERE responded = TRUE AND created_at > NOW() - INTERVAL '7 days') as week_responded
                        FROM trigger_history
                        WHERE status = 'sent'
                    """)
                    row = cur.fetchone()
                    if row:
                        total = row["total_triggers"] or 1
                        week_total = row["week_triggers"] or 1
                        return {
                            "total_triggers": row["total_triggers"],
                            "total_responded": row["total_responded"],
                            "overall_response_rate": round(row["total_responded"] / total * 100, 1),
                            "unique_users": row["unique_users"],
                            "responded_users": row["responded_users"],
                            "avg_score": float(row["avg_trigger_score"]) if row["avg_trigger_score"] else 0,
                            "week_triggers": row["week_triggers"],
                            "week_responded": row["week_responded"],
                            "week_response_rate": round(row["week_responded"] / week_total * 100, 1),
                        }
        except Exception as e:
            logger.error(f"Failed to get conversion metrics: {e}")
        return {}


proactive_engine = ProactiveEngagementEngine()
