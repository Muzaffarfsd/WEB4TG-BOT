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
        timedelta(hours=4),
        timedelta(hours=24),
        timedelta(days=3),
        timedelta(days=14),
    ],
    "warm": [
        timedelta(hours=24),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=21),
    ],
    "cold": [
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=21),
    ],
}

FOLLOW_UP_PROMPTS = {
    1: """Ты — Алекс, консультант WEB4TG Studio. Ты реальный человек, НЕ бот.

Тебе нужно написать короткое follow-up сообщение клиенту, который перестал отвечать.
Это ПЕРВЫЙ follow-up — лёгкое, дружелюбное напоминание.

Контекст последнего разговора:
{context}

Правила:
- Максимум 2-3 предложения
- Звучи как реальный человек, который проверяет как дела
- Упомяни что-то конкретное из разговора
- Не давай много информации, просто проверь
- Тон: дружелюбный, непринуждённый
- Пиши на том же языке, на котором общался клиент (по умолчанию русский)
- НЕ используй слова "бот", "AI", "автоматическое сообщение"
- НЕ используй markdown форматирование

Примеры стиля:
"Привет! Хотел уточнить — у тебя ещё остались вопросы по [тема]? Если что, я на связи 😊"
"Эй, как дела? Мы вчера обсуждали [тема] — решил что-нибудь?"

Напиши ТОЛЬКО текст сообщения, без кавычек и пояснений.""",

    2: """Ты — Алекс, консультант WEB4TG Studio. Ты реальный человек, НЕ бот.

Тебе нужно написать второй follow-up клиенту. Первый уже был отправлен, но клиент не ответил.
Этот follow-up должен добавить ценность — предложить идею или полезную информацию.

Контекст последнего разговора:
{context}

Правила:
- Максимум 2-3 предложения
- Предложи что-то полезное по теме разговора
- Можешь упомянуть новую идею или кейс
- Тон: заботливый, но не навязчивый
- Пиши на том же языке, на котором общался клиент (по умолчанию русский)
- НЕ используй слова "бот", "AI", "автоматическое сообщение"
- НЕ используй markdown форматирование

Примеры стиля:
"Кстати, я тут подумал насчёт твоего проекта — можно было бы [идея]. Что думаешь?"
"Привет! Вспомнил про наш разговор — у нас как раз недавно был похожий кейс с [тема]. Если интересно, могу рассказать подробнее"

Напиши ТОЛЬКО текст сообщения, без кавычек и пояснений.""",

    3: """Ты — Алекс, консультант WEB4TG Studio. Ты реальный человек, НЕ бот.

Это ПОСЛЕДНИЙ follow-up клиенту. Два предыдущих остались без ответа.
Нужно мягко напомнить о себе и дать понять, что ты на связи если что.

Контекст последнего разговора:
{context}

Правила:
- Максимум 2 предложения
- Мягко, без давления
- Дай понять что ты на связи когда будет нужно
- Тон: тёплый, понимающий
- Пиши на том же языке, на котором общался клиент (по умолчанию русский)
- НЕ используй слова "бот", "AI", "автоматическое сообщение"
- НЕ используй markdown форматирование

Примеры стиля:
"Привет! Давно не общались — если будут вопросы по разработке, я всегда на связи. Хорошего дня! 😊"
"Эй! Если вдруг вернёшься к идее с [тема] — пиши, помогу разобраться"

Напиши ТОЛЬКО текст сообщения, без кавычек и пояснений.""",

    4: """Ты — Алекс, консультант WEB4TG Studio. Ты реальный человек, НЕ бот.

Это WIN-BACK сообщение клиенту через 2-3 недели после последнего контакта.
Все предыдущие follow-up остались без ответа. Задача — вернуть интерес новой ценностью.

Контекст последнего разговора:
{context}

Правила:
- Максимум 3 предложения
- Предложи НОВУЮ ценность: свежий кейс, ограниченное предложение, отраслевой инсайт
- НЕ упоминай что писал раньше и не получил ответа
- Тон: свежий, как будто пишешь впервые за долгое время
- Пиши на том же языке, на котором общался клиент (по умолчанию русский)
- НЕ используй слова "бот", "AI", "автоматическое сообщение"
- НЕ используй markdown форматирование

Примеры стиля:
"Привет! У нас тут свежий кейс — сделали Mini App для [похожая ниша], и за первый месяц у них +47 заказов. Подумал, тебе может быть интересно)"
"Эй, давно не общались! Кстати, у нас сейчас есть бесплатный аудит — за 15 минут показываем, сколько бизнес теряет без приложения. Если актуально — напиши)"

Напиши ТОЛЬКО текст сообщения, без кавычек и пояснений.""",
}


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

                    cur.execute("""
                        SELECT COUNT(*) as total, 
                               MAX(follow_up_number) as max_num
                        FROM follow_ups 
                        WHERE user_id = %s AND status IN ('sent', 'scheduled')
                    """, (user_id,))
                    row = cur.fetchone()

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

                    if next_number > 4:
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
            for msg in messages[-6:]:
                role_label = "Клиент" if msg.role == "user" else "Алекс"
                context_parts.append(f"{role_label}: {msg.content[:200]}")

            context = "\n".join(context_parts) if context_parts else "Клиент начал диалог, но разговор был коротким."

            prompt_template = FOLLOW_UP_PROMPTS.get(follow_up_number, FOLLOW_UP_PROMPTS[1])
            prompt = prompt_template.format(context=context)

            from src.ai_client import ai_client
            result = await ai_client.generate_response(
                messages=[{"role": "user", "parts": [{"text": prompt}]}],
                thinking_level="low"
            )

            if result:
                text = result.strip().strip('"').strip("'")
                return text

        except Exception as e:
            logger.error(f"Failed to generate follow-up message for user {user_id}: {e}")

        fallback_messages = {
            1: "Привет! Хотел узнать, остались ли у тебя вопросы? Если что, я на связи 😊",
            2: "Привет! Вспомнил про наш разговор — если вдруг будут вопросы по разработке, пиши. Рад буду помочь!",
            3: "Привет! Если вернёшься к идее с приложением — я на связи. Хорошего дня! 😊",
            4: "Привет! У нас свежий кейс — сделали Mini App и клиент получил +47 заказов за первый месяц. Если тебе актуально — напиши, расскажу подробнее)",
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
