import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.database import get_connection, DATABASE_URL
from src.leads import lead_manager
from src.config import config
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

FOLLOW_UP_SCHEDULES = {
    "hot": [
        timedelta(hours=2),
        timedelta(hours=12),
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
    ],
    "warm": [
        timedelta(hours=6),
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
        timedelta(days=30),
    ],
    "cold": [
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
        timedelta(days=30),
        timedelta(days=45),
    ],
}

FOLLOW_UP_PROMPTS = {
    1: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Micro-value check-in (первое касание после молчания)
Клиент перестал отвечать. Твоя задача — дать МИКРО-ПОЛЬЗУ и мягко напомнить о себе.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Начни с конкретной пользы по теме клиента (совет, факт, идея)
- Не спрашивай "остались ли вопросы" — это клише
- Покажи экспертизу в одном предложении
- Закончи открытым вопросом

ФОРМАТ:
- 2-3 коротких предложения
- Как сообщение от знакомого эксперта
- Без "Привет!" в начале (используй имя или начни с сути)
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ:
"Кстати, по поводу твоего ресторана — я тут посчитал, мини-апп в среднем увеличивает средний чек на 23%. Если интересно, могу показать как это работает"
"Забыл упомянуть — для салонов красоты есть фича с автоматической записью, экономит 2-3 часа в день администратору. Актуально для тебя?"

Напиши ТОЛЬКО текст, без кавычек.""",

    2: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Social proof (второе касание — доказательство через других)
Первое сообщение осталось без ответа. Задача — показать результат похожего клиента.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Расскажи про КОНКРЕТНЫЙ кейс из похожей ниши клиента
- Используй точные цифры (конверсии, заказы, рост)
- Свяжи кейс с задачей клиента
- Не напоминай что писал раньше

ФОРМАТ:
- 2-4 коротких предложения
- Конкретные цифры и факты
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ:
"Слушай, вспомнил про тебя — мы тут доделали мини-апп для кофейни, у них за первый месяц +38 заказов через приложение. Похожая ситуация как у тебя. Если хочешь, покажу как устроено"
"У нас свежий результат — фитнес-клуб запустил мини-апп, записи через бот выросли на 56%. Подумал, тебе может быть полезно взглянуть"

Напиши ТОЛЬКО текст, без кавычек.""",

    3: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Value bomb (третье касание — бесплатная ценность)
Два сообщения без ответа. Задача — дать что-то бесплатно, снизить барьер.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Предложи что-то БЕСПЛАТНОЕ и конкретное (аудит, расчёт, консультация 15 мин)
- Покажи что ты вложился: "я тут посчитал для тебя", "подготовил"
- Без давления — чисто полезность
- Привяжи к бизнесу клиента

ФОРМАТ:
- 2-3 предложения
- Конкретное предложение с low commitment
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ:
"Я тут прикинул примерный план для твоего проекта — получилось интересно. Могу скинуть, если хочешь глянуть? Займёт 2 минуты"
"Подготовил тебе мини-аудит — посмотрел как конкуренты в твоей нише используют мини-аппы. Есть пара идей. Скинуть?"

Напиши ТОЛЬКО текст, без кавычек.""",

    4: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Scarcity / Urgency (четвёртое касание — ограниченное предложение)
Три сообщения без ответа. Задача — создать мягкую срочность.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Предложи что-то с дедлайном (скидка до конца недели, свободный слот, акция)
- Обоснуй срочность логично (не "последний шанс!")
- Свяжи с конкретной выгодой для клиента
- Формулировка мягкая, не агрессивная

ФОРМАТ:
- 2-3 предложения
- Конкретное предложение с временным ограничением
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ:
"Слушай, у нас сейчас освободился слот на разработку — можем взять проект без очереди. Обычно ждут 2-3 недели. Если тебе актуально — дай знать до пятницы"
"Кстати, до конца месяца действует скидка 15% на запуск нового проекта. Подумал, может тебе пригодится — ты же как раз думал про приложение"

Напиши ТОЛЬКО текст, без кавычек.""",

    5: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Perspective shift (пятое касание — новый угол)
Четыре сообщения без ответа. Задача — зайти с другой стороны, изменить фрейм.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Покажи проблему с НОВОЙ стороны, о которой клиент не думал
- Используй "потери" — сколько клиент теряет БЕЗ приложения
- Или расскажи тренд в его индустрии
- Не упоминай предыдущие сообщения

ФОРМАТ:
- 2-3 предложения
- Свежий взгляд, неочевидный инсайт
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ:
"Интересная статистика — 73% клиентов ресторанов предпочитают заказывать через приложение, а не звонить. Ты уже ловишь этот трафик или он уходит конкурентам?"
"Знаешь что самое дорогое в бизнесе? Не ошибки, а упущенные возможности. Один наш клиент подсчитал, что терял 340 тысяч в месяц просто потому, что у него не было удобного приложения для записи"

Напиши ТОЛЬКО текст, без кавычек.""",

    6: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Soft breakup (шестое касание — мягкое прощание)
Пять сообщений без ответа. Задача — "психология обратного хода".

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Скажи что не будешь больше беспокоить
- Оставь дверь открытой
- Покажи уважение к времени клиента
- Парадоксально — breakup-сообщения получают самый высокий % ответов (25-40%)

ФОРМАТ:
- 2 предложения максимум
- Уважительный, тёплый тон
- Без markdown, emoji, списков
- Без обиды или пассивной агрессии

ПРИМЕРЫ СТИЛЯ:
"Понимаю, сейчас наверное не до этого. Если когда-нибудь вернёшься к идее с приложением — просто напиши, я помогу разобраться"
"Не хочу надоедать, так что оставлю в покое. Но если вдруг появятся вопросы — я тут, пиши в любое время"

Напиши ТОЛЬКО текст, без кавычек.""",

    7: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Win-back (седьмое касание через 3-6 недель — возвращение)
Все предыдущие follow-up без ответа. Задача — вернуть интерес НОВОЙ ценностью.

Контекст разговора:
{context}

{client_signals}

СТРАТЕГИЯ:
- Пиши как будто с нуля, без отсылок к прошлым сообщениям
- Предложи НОВУЮ ценность: свежий кейс, новая фича, отраслевой тренд
- Минимальный commitment: "посмотри 2 минуты"
- Если не ответит — это последнее сообщение

ФОРМАТ:
- 2-3 предложения
- Свежий тон, как будто давно не общались
- Без markdown, emoji (кроме одного в конце), списков
- Без упоминания прошлых сообщений

ПРИМЕРЫ СТИЛЯ:
"Давно не общались! У нас тут появилась новая фишка — делаем мини-аппы с AI-ассистентом внутри. Буквально за неделю. Если интересно — покажу демо, займёт 3 минуты)"
"Привет! Вспомнил про тебя — мы запустили новый формат: MVP за 7 дней. Один клиент уже окупил за первую неделю. Если хочешь подробности — напиши)"

Напиши ТОЛЬКО текст, без кавычек.""",
}


def _build_client_signals(user_id: int) -> str:
    signals = []

    try:
        lead = lead_manager.get_lead(user_id)
        if lead:
            if lead.score and lead.score >= 50:
                signals.append("СИГНАЛ: Горячий лид (высокий интерес)")
            elif lead.score and lead.score >= 25:
                signals.append("СИГНАЛ: Тёплый лид (средний интерес)")

            if lead.industry:
                signals.append(f"НИША клиента: {lead.industry}")

            if lead.budget_range:
                signals.append(f"БЮДЖЕТ: {lead.budget_range}")

            tags = getattr(lead, 'tags', None)
            if tags:
                signals.append(f"ТЕГИ: {tags}")
    except Exception:
        pass

    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile:
            if profile.get("business_type"):
                signals.append(f"ТИП БИЗНЕСА: {profile['business_type']}")
            if profile.get("pain_points"):
                signals.append(f"БОЛИ: {profile['pain_points']}")
            if profile.get("communication_style"):
                signals.append(f"СТИЛЬ ОБЩЕНИЯ: {profile['communication_style']}")
    except Exception:
        pass

    try:
        from src.propensity import propensity_scorer
        score_data = propensity_scorer.calculate_score(user_id)
        if score_data and score_data.get("score"):
            signals.append(f"PROPENSITY SCORE: {score_data['score']}/100")
    except Exception:
        pass

    if signals:
        return "Сигналы о клиенте:\n" + "\n".join(signals)
    return "Сигналы о клиенте: нет данных (используй общий подход)"


class FollowUpManager:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, follow-ups disabled")
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS follow_ups (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            follow_up_number INTEGER DEFAULT 1,
                            status VARCHAR(20) DEFAULT 'scheduled',
                            scheduled_at TIMESTAMP NOT NULL,
                            sent_at TIMESTAMP,
                            message_text TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_user_id ON follow_ups(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_status ON follow_ups(status)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_scheduled ON follow_ups(scheduled_at)
                    """)
            logger.info("Follow-up table initialized")
        except Exception as e:
            logger.error(f"Failed to init follow-up table: {e}")

    def schedule_follow_up(self, user_id: int) -> bool:
        if not DATABASE_URL:
            return False

        try:
            lead = lead_manager.get_lead(user_id)
            if not lead:
                return False

            if lead.message_count < 2:
                return False

            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id FROM follow_ups 
                        WHERE user_id = %s AND status = 'paused'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

                    sent_count = 0
                    cur.execute("""
                        SELECT COUNT(*) as cnt FROM follow_ups 
                        WHERE user_id = %s AND status = 'sent'
                    """, (user_id,))
                    sent_row = cur.fetchone()
                    if sent_row:
                        sent_count = sent_row['cnt']

                    next_number = sent_count + 1

                    score = lead.score or 0
                    if score >= 50:
                        priority = "hot"
                    elif score >= 25:
                        priority = "warm"
                    else:
                        priority = "cold"

                    schedule = FOLLOW_UP_SCHEDULES.get(priority, FOLLOW_UP_SCHEDULES["cold"])

                    if next_number > len(schedule):
                        return False

                    if next_number > 7:
                        return False

                    delay = schedule[next_number - 1]
                    scheduled_at = datetime.now() + delay

                    try:
                        from src.session import get_client_profile
                        profile = get_client_profile(user_id)
                        if profile and profile.get("timezone_offset") is not None:
                            tz_offset = profile["timezone_offset"]
                            client_hour = (scheduled_at.hour + tz_offset) % 24
                            if client_hour < 9:
                                scheduled_at += timedelta(hours=(9 - client_hour))
                            elif client_hour > 20:
                                scheduled_at += timedelta(hours=(24 - client_hour + 9))
                    except Exception:
                        pass

                    cur.execute("""
                        SELECT id FROM follow_ups 
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

                    cur.execute("""
                        INSERT INTO follow_ups (user_id, follow_up_number, status, scheduled_at)
                        VALUES (%s, %s, 'scheduled', %s)
                    """, (user_id, next_number, scheduled_at))

            logger.info(f"Scheduled follow-up #{next_number} for user {user_id} at {scheduled_at} (priority: {priority})")
            return True
        except Exception as e:
            logger.error(f"Failed to schedule follow-up for user {user_id}: {e}")
            return False

    def cancel_follow_ups(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'cancelled'
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    cancelled = cur.rowcount

            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} follow-ups for user {user_id}")

            self.mark_responded(user_id)
            return cancelled
        except Exception as e:
            logger.error(f"Failed to cancel follow-ups for user {user_id}: {e}")
            return 0

    def cancel_for_blocked_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'cancelled'
                        WHERE user_id = %s AND status IN ('scheduled', 'paused')
                    """, (user_id,))
                    cancelled = cur.rowcount
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} follow-ups for blocked user {user_id}")
            return cancelled
        except Exception as e:
            logger.error(f"Failed to cancel follow-ups for blocked user {user_id}: {e}")
            return 0

    def get_due_follow_ups(self) -> List[Dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT f.id, f.user_id, f.follow_up_number, f.scheduled_at
                        FROM follow_ups f
                        JOIN leads l ON f.user_id = l.user_id
                        LEFT JOIN bot_users bu ON f.user_id = bu.user_id
                        WHERE f.status = 'scheduled'
                          AND f.scheduled_at <= NOW()
                          AND (l.last_activity IS NULL OR l.last_activity < NOW() - INTERVAL '2 hours')
                          AND (bu.is_blocked IS NULL OR bu.is_blocked = FALSE)
                        ORDER BY f.scheduled_at ASC
                        LIMIT 20
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get due follow-ups: {e}")
            return []

    def mark_sent(self, follow_up_id: int, message_text: str) -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'sent', sent_at = NOW(), message_text = %s
                        WHERE id = %s
                    """, (message_text, follow_up_id))
            return True
        except Exception as e:
            logger.error(f"Failed to mark follow-up {follow_up_id} as sent: {e}")
            return False

    def mark_responded(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'responded'
                        WHERE user_id = %s AND status = 'sent'
                    """, (user_id,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Failed to mark responded for user {user_id}: {e}")
            return 0

    async def generate_follow_up_message(self, user_id: int, follow_up_number: int) -> str:
        try:
            messages = lead_manager.get_conversation_history(user_id, limit=10)

            context_parts = []
            for msg in messages[-8:]:
                role_label = "Клиент" if msg.role == "user" else "Алекс"
                context_parts.append(f"{role_label}: {msg.content[:300]}")

            context = "\n".join(context_parts) if context_parts else "Клиент начал диалог, но разговор был коротким."

            client_signals = _build_client_signals(user_id)

            prompt_template = FOLLOW_UP_PROMPTS.get(follow_up_number, FOLLOW_UP_PROMPTS[1])
            prompt = prompt_template.format(context=context, client_signals=client_signals)

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
            logger.error(f"Failed to generate follow-up message for user {user_id}: {e}")

        fallback_messages = {
            1: "Кстати, по поводу твоего проекта — мини-аппы в среднем увеличивают конверсию на 35%. Если интересно, могу показать как это работает для твоей ниши",
            2: "У нас свежий результат — сделали Mini App для похожего бизнеса, +47 заказов за первый месяц. Подумал, тебе может быть полезно",
            3: "Подготовил примерный план для твоего проекта. Могу скинуть? Займёт 2 минуты глянуть",
            4: "У нас сейчас освободился слот — можем взять проект без очереди. Обычно ждут 2-3 недели. Актуально до конца недели",
            5: "73% клиентов предпочитают заказывать через приложение. Интересно, ты уже ловишь этот трафик?",
            6: "Не хочу надоедать, так что оставлю в покое. Но если появятся вопросы — просто напиши, я тут",
            7: "Давно не общались! У нас появился новый формат — MVP за 7 дней. Один клиент окупил за первую неделю. Если хочешь подробности — напиши)",
        }
        return fallback_messages.get(follow_up_number, fallback_messages[1])

    def pause_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'paused'
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Failed to pause follow-ups for user {user_id}: {e}")
            return 0

    def resume_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'scheduled'
                        WHERE user_id = %s AND status = 'paused'
                    """, (user_id,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Failed to resume follow-ups for user {user_id}: {e}")
            return 0

    def get_user_follow_up_stats(self) -> List[Dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            f.user_id,
                            l.first_name,
                            l.username,
                            COUNT(*) FILTER (WHERE f.status = 'scheduled') as pending,
                            COUNT(*) FILTER (WHERE f.status = 'sent') as sent,
                            COUNT(*) FILTER (WHERE f.status = 'responded') as responded,
                            COUNT(*) FILTER (WHERE f.status = 'paused') as paused,
                            MAX(f.follow_up_number) as max_followup
                        FROM follow_ups f
                        LEFT JOIN leads l ON f.user_id = l.user_id
                        GROUP BY f.user_id, l.first_name, l.username
                        ORDER BY pending DESC, sent DESC
                        LIMIT 20
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user follow-up stats: {e}")
            return []

    def get_stats(self) -> Dict:
        if not DATABASE_URL:
            return {
                "total": 0, "scheduled": 0, "sent": 0,
                "responded": 0, "cancelled": 0, "paused": 0,
                "sent_today": 0
            }

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE status = 'scheduled') as scheduled,
                            COUNT(*) FILTER (WHERE status = 'sent') as sent,
                            COUNT(*) FILTER (WHERE status = 'responded') as responded,
                            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                            COUNT(*) FILTER (WHERE status = 'paused') as paused,
                            COUNT(*) FILTER (WHERE status = 'sent' AND sent_at >= CURRENT_DATE) as sent_today
                        FROM follow_ups
                    """)
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            logger.error(f"Failed to get follow-up stats: {e}")

        return {
            "total": 0, "scheduled": 0, "sent": 0,
            "responded": 0, "cancelled": 0, "paused": 0,
            "sent_today": 0
        }


follow_up_manager = FollowUpManager()
