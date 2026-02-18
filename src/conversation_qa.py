"""Conversation quality scoring, human handoff triggers, and QA analytics."""

import time
import logging
import os
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")

HANDOFF_TRIGGERS = {
    "explicit_request": [
        "менеджер", "оператор", "человек", "живой", "хочу поговорить",
        "позовите менеджера", "manager", "human", "real person",
        "оператору", "к менеджеру", "с менеджером", "переключи",
    ],
    "frustration": [
        "не понимаешь", "тупой бот", "бесполезн", "не помогаешь",
        "ничего не понимаешь", "дурак", "тупица", "useless", "stupid bot",
        "опять не то", "снова не так", "не то предлагаешь",
    ],
    "complex_request": [
        "юридический вопрос", "индивидуальные условия", "специальное предложение",
        "нестандартный проект", "корпоративный", "b2b", "enterprise",
        "тендер", "госзаказ", "тех поддержк", "техническая проблема",
    ],
    "high_value": [
        "большой проект", "крупный заказ", "от 500", "от миллиона",
        "несколько приложений", "сеть магазинов", "франшиза",
    ],
}


@dataclass
class ConversationQuality:
    response_relevance: float = 0.0
    user_satisfaction: float = 0.0
    resolution_progress: float = 0.0
    engagement_level: float = 0.0
    overall_score: float = 0.0


class ConversationQAManager:
    def __init__(self):
        self._session_scores: Dict[int, List[float]] = {}
        self._handoff_queue: Dict[int, dict] = {}
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_quality (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            score FLOAT NOT NULL,
                            factors JSONB,
                            handoff_triggered BOOLEAN DEFAULT FALSE,
                            handoff_reason VARCHAR(200),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS handoff_requests (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            reason VARCHAR(200) NOT NULL,
                            trigger_type VARCHAR(50),
                            context_summary TEXT,
                            status VARCHAR(20) DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            resolved_at TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_qa_user ON conversation_quality(user_id, created_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_handoff_status ON handoff_requests(status, created_at)
                    """)
        except Exception as e:
            logger.error(f"Failed to init QA tables: {e}")

    def score_conversation(
        self,
        user_id: int,
        user_message: str,
        ai_response: str,
        message_count: int,
        session_messages: int
    ) -> ConversationQuality:
        quality = ConversationQuality()

        ai_len = len(ai_response) if ai_response else 0
        user_len = len(user_message) if user_message else 0

        if ai_len > 50:
            quality.response_relevance = min(1.0, ai_len / 300)
        if ai_len < 20 or ai_response in ["Извините", "Ошибка", "Не удалось"]:
            quality.response_relevance = 0.2

        satisfaction_signals = {
            "positive": ["спасибо", "отлично", "круто", "понял", "ясно", "класс", "thanks", "great", "good", "ok"],
            "negative": ["не понимаю", "не то", "опять", "не помогает", "ерунда", "плохо", "wrong", "bad"],
        }

        user_lower = user_message.lower() if user_message else ""
        pos_count = sum(1 for w in satisfaction_signals["positive"] if w in user_lower)
        neg_count = sum(1 for w in satisfaction_signals["negative"] if w in user_lower)
        quality.user_satisfaction = min(1.0, 0.5 + pos_count * 0.15 - neg_count * 0.2)

        if session_messages > 3:
            quality.engagement_level = min(1.0, session_messages / 15)
        else:
            quality.engagement_level = 0.3

        action_keywords = ["калькулятор", "портфолио", "заявк", "оплат", "записат", "calculate", "portfolio", "lead"]
        has_action = any(k in user_lower for k in action_keywords)
        quality.resolution_progress = 0.7 if has_action else 0.4

        quality.overall_score = (
            quality.response_relevance * 0.3 +
            quality.user_satisfaction * 0.3 +
            quality.resolution_progress * 0.2 +
            quality.engagement_level * 0.2
        )

        if user_id not in self._session_scores:
            self._session_scores[user_id] = []
        self._session_scores[user_id].append(quality.overall_score)
        if len(self._session_scores[user_id]) > 50:
            self._session_scores[user_id] = self._session_scores[user_id][-25:]

        self._save_score(user_id, quality)
        return quality

    def _save_score(self, user_id: int, quality: ConversationQuality):
        if not DATABASE_URL:
            return
        try:
            import json
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversation_quality (user_id, score, factors)
                        VALUES (%s, %s, %s)
                    """, (
                        user_id,
                        quality.overall_score,
                        json.dumps({
                            "relevance": round(quality.response_relevance, 3),
                            "satisfaction": round(quality.user_satisfaction, 3),
                            "resolution": round(quality.resolution_progress, 3),
                            "engagement": round(quality.engagement_level, 3),
                        })
                    ))
        except Exception:
            pass

    def check_handoff_triggers(self, user_id: int, message: str) -> Optional[Tuple[str, str]]:
        if not message:
            return None
        msg_lower = message.lower()

        for trigger_type, keywords in HANDOFF_TRIGGERS.items():
            for kw in keywords:
                if kw in msg_lower:
                    return trigger_type, kw

        scores = self._session_scores.get(user_id, [])
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            if recent_avg < 0.3:
                return "low_quality", f"avg_score={recent_avg:.2f}"

        return None

    def create_handoff_request(
        self,
        user_id: int,
        reason: str,
        trigger_type: str,
        context_summary: str = ""
    ) -> Optional[int]:
        if not DATABASE_URL:
            return None
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM handoff_requests
                        WHERE user_id = %s AND status = 'pending'
                        AND created_at > NOW() - INTERVAL '1 hour'
                    """, (user_id,))
                    if cur.fetchone()[0] > 0:
                        return None

                    cur.execute("""
                        INSERT INTO handoff_requests (user_id, reason, trigger_type, context_summary)
                        VALUES (%s, %s, %s, %s) RETURNING id
                    """, (user_id, reason, trigger_type, context_summary[:500]))
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to create handoff request: {e}")
            return None

    def resolve_handoff(self, request_id: int):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE handoff_requests SET status = 'resolved', resolved_at = NOW()
                        WHERE id = %s
                    """, (request_id,))
        except Exception:
            pass

    def get_pending_handoffs(self) -> list:
        if not DATABASE_URL:
            return []
        try:
            from psycopg2.extras import RealDictCursor
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM handoff_requests
                        WHERE status = 'pending'
                        ORDER BY created_at DESC LIMIT 20
                    """)
                    return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    def get_qa_stats(self, days: int = 7) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total,
                            AVG(score) as avg_score,
                            COUNT(*) FILTER (WHERE score >= 0.7) as high_quality,
                            COUNT(*) FILTER (WHERE score < 0.3) as low_quality,
                            COUNT(*) FILTER (WHERE handoff_triggered) as handoffs
                        FROM conversation_quality
                        WHERE created_at > NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    row = cur.fetchone()
                    if row:
                        total = row[0] or 0
                        return {
                            "total_scored": total,
                            "avg_score": round(float(row[1] or 0), 3),
                            "high_quality_pct": round(row[2] / total * 100, 1) if total else 0,
                            "low_quality_pct": round(row[3] / total * 100, 1) if total else 0,
                            "handoffs": row[4] or 0,
                        }
        except Exception as e:
            logger.error(f"Failed to get QA stats: {e}")
        return {}

    async def notify_manager_handoff(self, bot, user_id: int, reason: str, trigger_type: str, user_name: str = ""):
        if not MANAGER_CHAT_ID:
            return
        trigger_labels = {
            "explicit_request": "👤 Запрос клиента",
            "frustration": "😤 Фрустрация клиента",
            "complex_request": "🏢 Сложный запрос",
            "high_value": "💎 Крупный клиент",
            "low_quality": "📉 Низкое качество диалога",
        }
        label = trigger_labels.get(trigger_type, trigger_type)
        text = (
            f"🔔 <b>Требуется менеджер!</b>\n\n"
            f"👤 Клиент: {user_name} (ID: {user_id})\n"
            f"📌 Триггер: {label}\n"
            f"💬 Причина: {reason}\n\n"
            f"Используйте /history {user_id} для просмотра диалога."
        )
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Взять в работу", callback_data=f"handoff_resolve_{user_id}")]
            ])
            await bot.send_message(int(MANAGER_CHAT_ID), text, parse_mode="HTML", reply_markup=keyboard)

            try:
                from src.manager_coaching import generate_coaching_briefing
                briefing = generate_coaching_briefing(
                    user_id=user_id,
                    trigger_type=trigger_type,
                    trigger_reason=reason,
                )
                if briefing:
                    await bot.send_message(int(MANAGER_CHAT_ID), briefing, parse_mode="HTML")
            except Exception as coaching_err:
                logger.debug(f"Coaching briefing skipped: {coaching_err}")
        except Exception as e:
            logger.error(f"Failed to notify manager about handoff: {e}")


qa_manager = ConversationQAManager()
