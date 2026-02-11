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
    "response_style": ABTest(
        name="response_style",
        variant_a="formal",
        variant_b="casual",
        description="Dialog response style: formal professional vs casual friendly"
    ),
    "objection_handling": ABTest(
        name="objection_handling",
        variant_a="empathy_first",
        variant_b="data_first",
        description="Objection handling: empathy-led vs data-led approach"
    ),
    "pricing_reveal": ABTest(
        name="pricing_reveal",
        variant_a="upfront",
        variant_b="value_first",
        description="Pricing: show price immediately vs build value first"
    ),
    "followup_tone": ABTest(
        name="followup_tone",
        variant_a="professional",
        variant_b="friendly",
        description="Follow-up message tone: professional vs friendly"
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
    
    def get_conversion_stats(self, test_name: str) -> dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            a.variant,
                            COUNT(DISTINCT a.user_id) AS users,
                            COUNT(DISTINCT CASE WHEN ro.outcome_type IS NOT NULL THEN a.user_id END) AS converted
                        FROM ab_test_assignments a
                        LEFT JOIN response_outcomes ro ON a.user_id = ro.user_id
                            AND ro.response_variant = a.variant
                            AND ro.outcome_type IS NOT NULL
                        WHERE a.test_name = %s
                        GROUP BY a.variant
                    """, (test_name,))
                    result = {}
                    for row in cur.fetchall():
                        result[row[0]] = {"users": row[1], "converted": row[2]}
                    return result
        except Exception as e:
            logger.error(f"Failed to get conversion stats for {test_name}: {e}")
            return {}

    def chi_square_significance(self, test_name: str) -> dict:
        stats = self.get_conversion_stats(test_name)
        if "a" not in stats or "b" not in stats:
            return {"significant": False, "reason": "insufficient_data", "p_value": None, "winner": None}

        a_users = stats["a"]["users"]
        b_users = stats["b"]["users"]
        a_conv = stats["a"]["converted"]
        b_conv = stats["b"]["converted"]

        min_sample = 30
        if a_users < min_sample or b_users < min_sample:
            return {
                "significant": False,
                "reason": f"need_{min_sample}_users_per_variant",
                "a_rate": round(a_conv / a_users * 100, 1) if a_users else 0,
                "b_rate": round(b_conv / b_users * 100, 1) if b_users else 0,
                "a_users": a_users, "b_users": b_users,
                "p_value": None, "winner": None
            }

        a_no = a_users - a_conv
        b_no = b_users - b_conv
        total = a_users + b_users
        total_conv = a_conv + b_conv
        total_no = a_no + b_no

        if total_conv == 0 or total_no == 0:
            return {
                "significant": False, "reason": "no_variance",
                "a_rate": 0, "b_rate": 0, "p_value": None, "winner": None
            }

        e_a_conv = a_users * total_conv / total
        e_a_no = a_users * total_no / total
        e_b_conv = b_users * total_conv / total
        e_b_no = b_users * total_no / total

        chi2 = 0
        for obs, exp in [(a_conv, e_a_conv), (a_no, e_a_no), (b_conv, e_b_conv), (b_no, e_b_no)]:
            if exp > 0:
                chi2 += (obs - exp) ** 2 / exp

        critical_values = {0.05: 3.841, 0.01: 6.635, 0.001: 10.828}
        p_value_approx = None
        significant = False
        if chi2 >= critical_values[0.001]:
            p_value_approx = 0.001
            significant = True
        elif chi2 >= critical_values[0.01]:
            p_value_approx = 0.01
            significant = True
        elif chi2 >= critical_values[0.05]:
            p_value_approx = 0.05
            significant = True

        a_rate = round(a_conv / a_users * 100, 1) if a_users else 0
        b_rate = round(b_conv / b_users * 100, 1) if b_users else 0
        winner = "a" if a_rate > b_rate else "b" if b_rate > a_rate else None

        return {
            "significant": significant,
            "chi2": round(chi2, 3),
            "p_value": p_value_approx,
            "a_rate": a_rate, "b_rate": b_rate,
            "a_users": a_users, "b_users": b_users,
            "a_converted": a_conv, "b_converted": b_conv,
            "winner": winner if significant else None,
            "confidence": f"{100 - int(p_value_approx * 100)}%" if p_value_approx else None
        }

    def format_stats_message(self, test_name: str) -> str:
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

        sig = self.chi_square_significance(test_name)
        if sig.get("a_rate") is not None:
            lines.append("<b>Конверсия:</b>")
            lines.append(f"  A: {sig['a_rate']}% ({sig.get('a_converted', 0)}/{sig.get('a_users', 0)})")
            lines.append(f"  B: {sig['b_rate']}% ({sig.get('b_converted', 0)}/{sig.get('b_users', 0)})")
            if sig["significant"]:
                lines.append(f"\n✅ <b>Статистически значимо!</b> (p < {sig['p_value']}, {sig['confidence']})")
                lines.append(f"🏆 Победитель: Вариант {'A' if sig['winner'] == 'a' else 'B'}")
            elif sig.get("reason") and "need" in sig["reason"]:
                lines.append(f"\n⏳ Недостаточно данных (нужно 30+ пользователей на вариант)")
            else:
                lines.append(f"\n🔄 Разница не значима. Продолжаем тест.")

        return "\n".join(lines)

    def format_all_tests_summary(self) -> str:
        lines = ["📊 <b>Сводка по всем A/B тестам</b>\n"]
        for test_name, test in WELCOME_TESTS.items():
            sig = self.chi_square_significance(test_name)
            status = "⏳"
            if sig.get("significant"):
                status = f"✅ Winner: {'A' if sig['winner'] == 'a' else 'B'}"
            elif sig.get("a_users", 0) >= 30:
                status = "🔄 Нет разницы"
            lines.append(f"<b>{test_name}</b>: {status}")
            if sig.get("a_rate") is not None:
                lines.append(f"  A: {sig['a_rate']}% | B: {sig['b_rate']}%")
        return "\n".join(lines)


ab_testing = ABTestingSystem()
