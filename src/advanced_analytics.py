"""Advanced analytics: cohort analysis, conversion attribution, LTV, revenue tracking."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


class AdvancedAnalytics:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS revenue_events (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            amount FLOAT NOT NULL,
                            currency VARCHAR(10) DEFAULT 'RUB',
                            event_type VARCHAR(50) NOT NULL,
                            source VARCHAR(100),
                            metadata JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS attribution_events (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            first_touch VARCHAR(100),
                            last_touch VARCHAR(100),
                            conversion_event VARCHAR(100),
                            touchpoints JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_revenue_user ON revenue_events(user_id, created_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_revenue_type ON revenue_events(event_type, created_at)
                    """)
        except Exception as e:
            logger.error(f"Failed to init advanced analytics tables: {e}")

    def track_revenue(self, user_id: int, amount: float, event_type: str, source: str = "", metadata: dict = None):
        if not DATABASE_URL:
            return
        try:
            import json
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO revenue_events (user_id, amount, event_type, source, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, amount, event_type, source, json.dumps(metadata) if metadata else None))
        except Exception as e:
            logger.error(f"Failed to track revenue: {e}")

    def get_cohort_analysis(self, days: int = 90) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        WITH cohorts AS (
                            SELECT
                                user_id,
                                DATE_TRUNC('week', MIN(created_at)) as cohort_week,
                                MIN(created_at) as first_seen
                            FROM funnel_events
                            WHERE created_at > NOW() - %s * INTERVAL '1 day'
                            GROUP BY user_id
                        ),
                        activity AS (
                            SELECT
                                c.user_id,
                                c.cohort_week,
                                DATE_TRUNC('week', fe.created_at) as activity_week
                            FROM cohorts c
                            JOIN funnel_events fe ON fe.user_id = c.user_id
                            WHERE fe.created_at > NOW() - %s * INTERVAL '1 day'
                        )
                        SELECT
                            cohort_week::date,
                            COUNT(DISTINCT user_id) as cohort_size,
                            COUNT(DISTINCT CASE WHEN activity_week = cohort_week THEN user_id END) as week_0,
                            COUNT(DISTINCT CASE WHEN activity_week = cohort_week + INTERVAL '1 week' THEN user_id END) as week_1,
                            COUNT(DISTINCT CASE WHEN activity_week = cohort_week + INTERVAL '2 weeks' THEN user_id END) as week_2,
                            COUNT(DISTINCT CASE WHEN activity_week = cohort_week + INTERVAL '3 weeks' THEN user_id END) as week_3
                        FROM activity
                        GROUP BY cohort_week
                        ORDER BY cohort_week DESC
                        LIMIT 12
                    """, (days, days))
                    rows = cur.fetchall()
                    return {
                        "cohorts": [
                            {
                                "week": str(r[0]),
                                "size": r[1],
                                "retention": [
                                    round(r[2] / r[1] * 100, 1) if r[1] else 0,
                                    round(r[3] / r[1] * 100, 1) if r[1] else 0,
                                    round(r[4] / r[1] * 100, 1) if r[1] else 0,
                                    round(r[5] / r[1] * 100, 1) if r[1] else 0,
                                ]
                            }
                            for r in rows
                        ]
                    }
        except Exception as e:
            logger.error(f"Cohort analysis failed: {e}")
            return {}

    def get_conversion_attribution(self, days: int = 30) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        WITH user_journeys AS (
                            SELECT
                                user_id,
                                ARRAY_AGG(event_name ORDER BY created_at) as journey,
                                MIN(created_at) as first_event,
                                MAX(created_at) as last_event
                            FROM funnel_events
                            WHERE created_at > NOW() - %s * INTERVAL '1 day'
                            GROUP BY user_id
                        )
                        SELECT
                            CASE
                                WHEN 'lead_submit' = ANY(journey) THEN 'converted'
                                WHEN 'calculator_total' = ANY(journey) THEN 'engaged'
                                WHEN 'menu_open' = ANY(journey) THEN 'explored'
                                ELSE 'bounced'
                            END as segment,
                            COUNT(*) as users,
                            AVG(ARRAY_LENGTH(journey, 1)) as avg_touchpoints,
                            AVG(EXTRACT(EPOCH FROM (last_event - first_event)) / 3600) as avg_hours
                        FROM user_journeys
                        GROUP BY segment
                        ORDER BY users DESC
                    """, (days,))
                    rows = cur.fetchall()
                    return {
                        "segments": [
                            {
                                "name": r[0],
                                "users": r[1],
                                "avg_touchpoints": round(float(r[2] or 0), 1),
                                "avg_hours_to_convert": round(float(r[3] or 0), 1)
                            }
                            for r in rows
                        ]
                    }
        except Exception as e:
            logger.error(f"Attribution analysis failed: {e}")
            return {}

    def get_revenue_stats(self, days: int = 30) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COALESCE(SUM(amount), 0) as total_revenue,
                            COUNT(*) as transactions,
                            COUNT(DISTINCT user_id) as paying_users,
                            AVG(amount) as avg_transaction
                        FROM revenue_events
                        WHERE created_at > NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    row = cur.fetchone()
                    if row:
                        return {
                            "total_revenue": float(row[0] or 0),
                            "transactions": row[1] or 0,
                            "paying_users": row[2] or 0,
                            "avg_transaction": round(float(row[3] or 0), 2),
                        }
        except Exception as e:
            logger.error(f"Revenue stats failed: {e}")
        return {}

    def get_ltv_analysis(self) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(DISTINCT user_id) as total_users,
                            COALESCE(SUM(amount), 0) as total_revenue,
                            CASE WHEN COUNT(DISTINCT user_id) > 0
                                THEN COALESCE(SUM(amount), 0) / COUNT(DISTINCT user_id)
                                ELSE 0
                            END as arpu
                        FROM revenue_events
                    """)
                    row = cur.fetchone()
                    if row:
                        return {
                            "total_paying_users": row[0] or 0,
                            "total_revenue": float(row[1] or 0),
                            "arpu": round(float(row[2] or 0), 2),
                        }
        except Exception as e:
            logger.error(f"LTV analysis failed: {e}")
        return {}

    def get_funnel_by_day(self, days: int = 14) -> List[Dict]:
        if not DATABASE_URL:
            return []
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            DATE(created_at) as day,
                            COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'start') as starts,
                            COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'menu_open') as menu,
                            COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'calculator_open') as calc,
                            COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'lead_submit') as leads,
                            COUNT(DISTINCT user_id) FILTER (WHERE event_name = 'payment_view') as payments
                        FROM funnel_events
                        WHERE created_at > NOW() - %s * INTERVAL '1 day'
                        GROUP BY DATE(created_at)
                        ORDER BY day DESC
                    """, (days,))
                    return [
                        {
                            "day": str(r[0]),
                            "starts": r[1],
                            "menu": r[2],
                            "calculator": r[3],
                            "leads": r[4],
                            "payments": r[5],
                        }
                        for r in cur.fetchall()
                    ]
        except Exception as e:
            logger.error(f"Daily funnel failed: {e}")
            return []

    def format_advanced_stats(self, days: int = 30) -> str:
        text = f"📊 <b>Продвинутая аналитика ({days} дн.)</b>\n\n"

        revenue = self.get_revenue_stats(days)
        if revenue:
            text += "<b>💰 Revenue:</b>\n"
            text += f"  Общий доход: {revenue['total_revenue']:,.0f}₽\n"
            text += f"  Транзакций: {revenue['transactions']}\n"
            text += f"  Платящих: {revenue['paying_users']}\n"
            text += f"  Средний чек: {revenue['avg_transaction']:,.0f}₽\n\n"

        attr = self.get_conversion_attribution(days)
        if attr and attr.get("segments"):
            text += "<b>🎯 Конверсионные сегменты:</b>\n"
            for s in attr["segments"]:
                text += f"  {s['name']}: {s['users']} ({s['avg_touchpoints']} точек, {s['avg_hours_to_convert']:.0f}ч)\n"
            text += "\n"

        cohorts = self.get_cohort_analysis(days)
        if cohorts and cohorts.get("cohorts"):
            text += "<b>📈 Когорты (retention %):</b>\n"
            text += "  Неделя | W0 | W1 | W2 | W3\n"
            for c in cohorts["cohorts"][:6]:
                r = c["retention"]
                text += f"  {c['week']} ({c['size']}): {r[0]}% → {r[1]}% → {r[2]}% → {r[3]}%\n"
            text += "\n"

        daily = self.get_funnel_by_day(7)
        if daily:
            text += "<b>📅 Воронка по дням:</b>\n"
            text += "  День | Start→Menu→Calc→Lead→Pay\n"
            for d in daily[:7]:
                text += f"  {d['day']}: {d['starts']}→{d['menu']}→{d['calculator']}→{d['leads']}→{d['payments']}\n"

        return text


advanced_analytics = AdvancedAnalytics()
