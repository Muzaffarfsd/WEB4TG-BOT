"""A/B Testing for welcome messages and onboarding flows."""
import random
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from src.database import get_connection, is_available as db_available, DATABASE_URL

logger = logging.getLogger(__name__)


@dataclass
class ABTest:
    name: str
    variant_a: str
    variant_b: str
    description: str = ""


WELCOME_TESTS = {
    "welcome_voice": ABTest(
        name="welcome_voice",
        variant_a="short",
        variant_b="detailed",
        description="Voice greeting length: short vs detailed"
    ),
    "welcome_menu": ABTest(
        name="welcome_menu",
        variant_a="buttons_first",
        variant_b="text_first", 
        description="Show inline buttons before or after welcome text"
    ),
    "cta_style": ABTest(
        name="cta_style",
        variant_a="direct",
        variant_b="soft",
        description="Call-to-action style: direct vs soft approach"
    ),
}

WELCOME_VARIANTS = {
    "short": """Привет! Я AI-консультант WEB4TG Studio.

Помогу подобрать приложение для вашего бизнеса и рассчитать стоимость.

Чем могу помочь?""",
    
    "detailed": """Привет! Я AI-консультант WEB4TG Studio — премиальной студии разработки Telegram Mini Apps.

Я помогу вам:
• Подобрать готовое решение или создать уникальное приложение
• Рассчитать стоимость разработки
• Узнать о бонусах и скидках
• Посмотреть примеры наших работ

Задавайте любые вопросы!""",
}


class ABTestingSystem:
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        if not DATABASE_URL:
            return
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS ab_test_assignments (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            test_name VARCHAR(50) NOT NULL,
                            variant VARCHAR(20) NOT NULL,
                            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, test_name)
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS ab_test_events (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            test_name VARCHAR(50) NOT NULL,
                            variant VARCHAR(20) NOT NULL,
                            event_type VARCHAR(50) NOT NULL,
                            event_data JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_ab_assignments_user 
                        ON ab_test_assignments(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_ab_events_test 
                        ON ab_test_events(test_name, variant)
                    """)
            logger.info("A/B testing tables initialized")
        except Exception as e:
            logger.error(f"Failed to init A/B testing tables: {e}")
    
    def get_variant(self, user_id: int, test_name: str) -> str:
        """Get user's variant for a test, or assign one if not exists."""
        if not DATABASE_URL:
            return "a"
        
        test = WELCOME_TESTS.get(test_name)
        if not test:
            return "a"
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT variant FROM ab_test_assignments
                        WHERE user_id = %s AND test_name = %s
                    """, (user_id, test_name))
                    
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    
                    variant = random.choice(["a", "b"])
                    
                    cur.execute("""
                        INSERT INTO ab_test_assignments (user_id, test_name, variant)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, test_name) DO NOTHING
                        RETURNING variant
                    """, (user_id, test_name, variant))
                    
                    inserted = cur.fetchone()
                    return inserted[0] if inserted else variant
                    
        except Exception as e:
            logger.error(f"Failed to get/assign variant: {e}")
            return "a"
    
    def track_event(self, user_id: int, test_name: str, event_type: str, 
                    event_data: Optional[Dict] = None) -> bool:
        """Track an event for A/B testing analytics."""
        if not DATABASE_URL:
            return False
        
        variant = self.get_variant(user_id, test_name)
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    import json
                    cur.execute("""
                        INSERT INTO ab_test_events 
                        (user_id, test_name, variant, event_type, event_data)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, test_name, variant, event_type, 
                          json.dumps(event_data) if event_data else None))
            return True
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return False
    
    def get_welcome_message(self, user_id: int) -> str:
        """Get the appropriate welcome message variant for user."""
        variant = self.get_variant(user_id, "welcome_voice")
        
        if variant == "a":
            return WELCOME_VARIANTS["short"]
        else:
            return WELCOME_VARIANTS["detailed"]
    
    def get_test_stats(self, test_name: str) -> Dict[str, Any]:
        """Get statistics for a specific test."""
        if not DATABASE_URL:
            return {}
        
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            variant,
                            COUNT(DISTINCT user_id) as users,
                            COUNT(*) as total_events
                        FROM ab_test_events
                        WHERE test_name = %s
                        GROUP BY variant
                    """, (test_name,))
                    
                    results = cur.fetchall()
                    
                    stats = {}
                    for row in results:
                        stats[row[0]] = {
                            "users": row[1],
                            "events": row[2]
                        }
                    
                    cur.execute("""
                        SELECT 
                            variant,
                            event_type,
                            COUNT(*) as count
                        FROM ab_test_events
                        WHERE test_name = %s
                        GROUP BY variant, event_type
                        ORDER BY variant, count DESC
                    """, (test_name,))
                    
                    events = cur.fetchall()
                    for row in events:
                        variant, event_type, count = row
                        if variant in stats:
                            if "events_breakdown" not in stats[variant]:
                                stats[variant]["events_breakdown"] = {}
                            stats[variant]["events_breakdown"][event_type] = count
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"Failed to get test stats: {e}")
            return {}
    
    def format_stats_message(self, test_name: str) -> str:
        """Format test statistics as a readable message."""
        stats = self.get_test_stats(test_name)
        
        if not stats:
            return f"Нет данных для теста '{test_name}'"
        
        test = WELCOME_TESTS.get(test_name)
        test_desc = test.description if test else test_name
        
        lines = [f"📊 <b>A/B Тест: {test_name}</b>", f"<i>{test_desc}</i>", ""]
        
        for variant, data in stats.items():
            variant_name = "A" if variant == "a" else "B"
            lines.append(f"<b>Вариант {variant_name}:</b>")
            lines.append(f"  👥 Пользователей: {data.get('users', 0)}")
            lines.append(f"  📈 Всего событий: {data.get('events', 0)}")
            
            if "events_breakdown" in data:
                lines.append("  События:")
                for event, count in data["events_breakdown"].items():
                    lines.append(f"    • {event}: {count}")
            lines.append("")
        
        return "\n".join(lines)


ab_testing = ABTestingSystem()
