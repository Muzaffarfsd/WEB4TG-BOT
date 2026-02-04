"""Analytics and funnel tracking for WEB4TG bot."""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


class FunnelEvent(Enum):
    START = "start"
    MENU_OPEN = "menu_open"
    SERVICES_VIEW = "services_view"
    PORTFOLIO_VIEW = "portfolio_view"
    CALCULATOR_OPEN = "calculator_open"
    CALCULATOR_FEATURE_ADD = "calculator_feature_add"
    CALCULATOR_TOTAL = "calculator_total"
    LEAD_FORM_OPEN = "lead_form_open"
    LEAD_SUBMIT = "lead_submit"
    PAYMENT_VIEW = "payment_view"
    PAYMENT_CARD = "payment_card"
    PAYMENT_BANK = "payment_bank"
    PAYMENT_CONFIRM = "payment_confirm"
    REFERRAL_VIEW = "referral_view"
    REFERRAL_SHARE = "referral_share"
    TASK_COMPLETE = "task_complete"
    REVIEW_SUBMIT = "review_submit"
    VOICE_SENT = "voice_sent"
    AI_RESPONSE = "ai_response"


class Analytics:
    """Analytics tracking for funnel and user behavior."""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize analytics tables."""
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, analytics disabled")
            return
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS funnel_events (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            event_name VARCHAR(100) NOT NULL,
                            event_data JSONB,
                            session_id VARCHAR(100),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_funnel_user_id ON funnel_events(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_funnel_event_name ON funnel_events(event_name)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_funnel_created_at ON funnel_events(created_at)
                    """)
                    
            logger.info("Analytics tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize analytics: {e}")
    
    def track(
        self,
        user_id: int,
        event: FunnelEvent,
        data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """Track a funnel event."""
        if not DATABASE_URL:
            return False
        
        try:
            import json
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO funnel_events (user_id, event_name, event_data, session_id)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, event.value, json.dumps(data) if data else None, session_id))
            return True
        except Exception as e:
            logger.error(f"Failed to track event {event.value}: {e}")
            return False
    
    def get_funnel_stats(self, days: int = 30) -> Dict[str, int]:
        """Get funnel conversion stats for the last N days."""
        if not DATABASE_URL:
            return {}
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT event_name, COUNT(DISTINCT user_id) as users
                        FROM funnel_events
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        GROUP BY event_name
                        ORDER BY users DESC
                    """, (days,))
                    rows = cur.fetchall()
                    return {row[0]: row[1] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get funnel stats: {e}")
            return {}
    
    def get_conversion_rate(self, from_event: FunnelEvent, to_event: FunnelEvent, days: int = 30) -> float:
        """Calculate conversion rate between two events."""
        if not DATABASE_URL:
            return 0.0
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) FROM funnel_events
                        WHERE event_name = %s AND created_at > NOW() - INTERVAL '%s days'
                    """, (from_event.value, days))
                    from_count = cur.fetchone()[0] or 0
                    
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) FROM funnel_events
                        WHERE event_name = %s AND created_at > NOW() - INTERVAL '%s days'
                    """, (to_event.value, days))
                    to_count = cur.fetchone()[0] or 0
                    
                    if from_count == 0:
                        return 0.0
                    return round(to_count / from_count * 100, 2)
        except Exception as e:
            logger.error(f"Failed to get conversion rate: {e}")
            return 0.0
    
    def get_daily_stats(self, days: int = 7) -> list:
        """Get daily event counts."""
        if not DATABASE_URL:
            return []
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DATE(created_at) as day, 
                               COUNT(*) as events,
                               COUNT(DISTINCT user_id) as users
                        FROM funnel_events
                        WHERE created_at > NOW() - INTERVAL '%s days'
                        GROUP BY DATE(created_at)
                        ORDER BY day DESC
                    """, (days,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get daily stats: {e}")
            return []
    
    def format_stats_message(self, days: int = 30) -> str:
        """Format analytics stats as a message."""
        stats = self.get_funnel_stats(days)
        daily = self.get_daily_stats(7)
        
        if not stats:
            return "📊 Нет данных аналитики"
        
        text = f"📊 <b>Аналитика воронки ({days} дней)</b>\n\n"
        
        funnel_order = [
            ("start", "🚀 Старт"),
            ("menu_open", "📱 Меню"),
            ("calculator_open", "🧮 Калькулятор"),
            ("lead_form_open", "📝 Форма заявки"),
            ("lead_submit", "✅ Заявка"),
            ("payment_view", "💳 Оплата"),
            ("payment_confirm", "💰 Оплачено"),
        ]
        
        text += "<b>Воронка:</b>\n"
        for event_name, label in funnel_order:
            count = stats.get(event_name, 0)
            text += f"{label}: {count}\n"
        
        start_count = stats.get("start", 0)
        lead_count = stats.get("lead_submit", 0)
        if start_count > 0:
            conversion = round(lead_count / start_count * 100, 1)
            text += f"\n<b>Конверсия в заявку:</b> {conversion}%"
        
        if daily:
            text += "\n\n<b>По дням:</b>\n"
            for day, events, users in daily[:5]:
                text += f"📅 {day}: {users} юзеров, {events} событий\n"
        
        return text


analytics = Analytics()
