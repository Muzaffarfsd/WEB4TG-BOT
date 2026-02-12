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

    def get_dropoff_analysis(self, days: int = 30) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        WITH user_stages AS (
                            SELECT
                                user_id,
                                ARRAY_AGG(DISTINCT event_name ORDER BY event_name) as stages,
                                COUNT(*) as total_events
                            FROM funnel_events
                            WHERE created_at > NOW() - %s * INTERVAL '1 day'
                            GROUP BY user_id
                        ),
                        stage_counts AS (
                            SELECT
                                unnest(ARRAY['start', 'menu_open', 'calculator_open', 'lead_submit', 'payment_view']) as stage,
                                0 as sort_order
                        )
                        SELECT
                            fe.event_name as stage,
                            COUNT(DISTINCT fe.user_id) as users_at_stage
                        FROM funnel_events fe
                        WHERE fe.created_at > NOW() - %s * INTERVAL '1 day'
                        GROUP BY fe.event_name
                        ORDER BY users_at_stage DESC
                    """, (days, days))
                    rows = cur.fetchall()

                    if not rows:
                        return {}

                    stages = [(r[0], r[1]) for r in rows]
                    dropoffs = []
                    for i in range(len(stages) - 1):
                        current_users = stages[i][1]
                        next_users = stages[i + 1][1]
                        if current_users > 0:
                            dropoff_rate = round((1 - next_users / current_users) * 100, 1)
                            dropoffs.append({
                                "from_stage": stages[i][0],
                                "to_stage": stages[i + 1][0],
                                "dropoff_rate": dropoff_rate,
                                "users_lost": current_users - next_users
                            })

                    highest_dropoff = max(dropoffs, key=lambda x: x["dropoff_rate"]) if dropoffs else None

                    cur.execute("""
                        SELECT AVG(msg_count)
                        FROM (
                            SELECT user_id, COUNT(*) as msg_count
                            FROM funnel_events
                            WHERE created_at > NOW() - %s * INTERVAL '1 day'
                            GROUP BY user_id
                            HAVING COUNT(DISTINCT event_name) = 1
                        ) as single_stage_users
                    """, (days,))
                    avg_row = cur.fetchone()
                    avg_messages_before_dropoff = round(float(avg_row[0] or 1), 1) if avg_row and avg_row[0] else 1.0

                    cur.execute("""
                        SELECT event_name, COUNT(*) as cnt
                        FROM funnel_events fe
                        WHERE fe.created_at > NOW() - %s * INTERVAL '1 day'
                          AND fe.user_id NOT IN (
                              SELECT DISTINCT user_id FROM funnel_events
                              WHERE event_name = 'lead_submit'
                              AND created_at > NOW() - %s * INTERVAL '1 day'
                          )
                        GROUP BY event_name
                        ORDER BY cnt DESC
                        LIMIT 1
                    """, (days, days))
                    last_type_row = cur.fetchone()
                    most_common_last_type = last_type_row[0] if last_type_row else "unknown"

                    return {
                        "stages": stages,
                        "dropoffs": dropoffs,
                        "highest_dropoff": highest_dropoff,
                        "avg_messages_before_dropoff": avg_messages_before_dropoff,
                        "most_common_last_type": most_common_last_type
                    }
        except Exception as e:
            logger.error(f"Drop-off analysis failed: {e}")
            return {}

    def get_tool_conversion_attribution(self, days: int = 30) -> Dict:
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            im.tool_name,
                            COUNT(DISTINCT im.user_id) as total_users,
                            COUNT(DISTINCT CASE WHEN fe.event_name = 'lead_submit' THEN im.user_id END) as converted_users
                        FROM interaction_metrics im
                        LEFT JOIN funnel_events fe ON im.user_id = fe.user_id AND fe.event_name = 'lead_submit'
                        WHERE im.created_at > NOW() - %s * INTERVAL '1 day'
                          AND im.tool_name IS NOT NULL
                        GROUP BY im.tool_name
                        ORDER BY converted_users DESC
                        LIMIT 10
                    """, (days,))
                    tool_rows = cur.fetchall()

                    cur.execute("""
                        SELECT
                            fe.event_name as stage,
                            COUNT(DISTINCT fe.user_id) as total_users,
                            COUNT(DISTINCT CASE WHEN fe2.event_name = 'lead_submit' THEN fe.user_id END) as converted
                        FROM funnel_events fe
                        LEFT JOIN funnel_events fe2 ON fe.user_id = fe2.user_id AND fe2.event_name = 'lead_submit'
                        WHERE fe.created_at > NOW() - %s * INTERVAL '1 day'
                        GROUP BY fe.event_name
                        ORDER BY converted DESC
                        LIMIT 10
                    """, (days,))
                    stage_rows = cur.fetchall()

                    cur.execute("""
                        SELECT AVG(ps.score)
                        FROM propensity_scores ps
                        JOIN funnel_events fe ON ps.user_id = fe.user_id AND fe.event_name = 'lead_submit'
                        WHERE ps.created_at > NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    avg_score_row = cur.fetchone()
                    avg_propensity = round(float(avg_score_row[0] or 0), 2) if avg_score_row and avg_score_row[0] else 0

                    return {
                        "top_converting_tools": [
                            {"tool": r[0], "total_users": r[1], "converted": r[2],
                             "rate": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0}
                            for r in tool_rows
                        ],
                        "top_converting_stages": [
                            {"stage": r[0], "total_users": r[1], "converted": r[2],
                             "rate": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0}
                            for r in stage_rows
                        ],
                        "avg_propensity_at_conversion": avg_propensity
                    }
        except Exception as e:
            logger.error(f"Tool conversion attribution failed: {e}")
            return {}

    def predict_ltv(self, user_id: int) -> Dict:
        if not DATABASE_URL:
            return {"category": "low", "estimated_value": 0, "factors": {}}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    lead_score = 0
                    try:
                        cur.execute("""
                            SELECT score FROM leads WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1
                        """, (user_id,))
                        row = cur.fetchone()
                        if row:
                            lead_score = row[0] or 0
                    except Exception:
                        pass

                    tools_used = 0
                    try:
                        cur.execute("""
                            SELECT COUNT(DISTINCT tool_name) FROM interaction_metrics
                            WHERE user_id = %s AND tool_name IS NOT NULL
                        """, (user_id,))
                        row = cur.fetchone()
                        if row:
                            tools_used = row[0] or 0
                    except Exception:
                        pass

                    session_count = 0
                    try:
                        cur.execute("""
                            SELECT COUNT(DISTINCT DATE(created_at)) FROM funnel_events
                            WHERE user_id = %s
                        """, (user_id,))
                        row = cur.fetchone()
                        if row:
                            session_count = row[0] or 0
                    except Exception:
                        pass

                    score = (lead_score * 0.4) + (tools_used * 15) + (session_count * 10)

                    if score > 80:
                        category = "high"
                        estimated_value = 300000
                    elif score > 40:
                        category = "medium"
                        estimated_value = 200000
                    else:
                        category = "low"
                        estimated_value = 100000

                    return {
                        "category": category,
                        "estimated_value": estimated_value,
                        "factors": {
                            "lead_score": lead_score,
                            "tools_used": tools_used,
                            "session_count": session_count,
                            "composite_score": round(score, 1)
                        }
                    }
        except Exception as e:
            logger.error(f"LTV prediction failed for user {user_id}: {e}")
            return {"category": "low", "estimated_value": 0, "factors": {}}

    def predict_churn_risk(self, user_id: int) -> Dict:
        if not DATABASE_URL:
            return {"risk": "unknown", "factors": {}}
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            EXTRACT(DAY FROM NOW() - MAX(created_at)) as days_since_last,
                            COUNT(*) as total_events
                        FROM funnel_events
                        WHERE user_id = %s
                    """, (user_id,))
                    row = cur.fetchone()

                    if not row or row[1] == 0:
                        return {"risk": "high", "factors": {"reason": "no_activity"}}

                    days_since_last = float(row[0] or 0)
                    total_events = row[1]

                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as recent,
                            COUNT(*) FILTER (WHERE created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days') as previous
                        FROM funnel_events
                        WHERE user_id = %s
                    """, (user_id,))
                    trend_row = cur.fetchone()
                    recent = trend_row[0] if trend_row else 0
                    previous = trend_row[1] if trend_row else 0

                    if previous > 0:
                        trend = "increasing" if recent > previous else "decreasing" if recent < previous else "stable"
                    else:
                        trend = "new" if recent > 0 else "inactive"

                    if days_since_last > 14 or trend == "inactive":
                        risk = "high"
                    elif days_since_last > 7 or trend == "decreasing":
                        risk = "medium"
                    else:
                        risk = "low"

                    return {
                        "risk": risk,
                        "factors": {
                            "days_since_last_interaction": round(days_since_last, 1),
                            "total_events": total_events,
                            "engagement_trend": trend,
                            "recent_7d_events": recent,
                            "previous_7d_events": previous
                        }
                    }
        except Exception as e:
            logger.error(f"Churn risk prediction failed for user {user_id}: {e}")
            return {"risk": "unknown", "factors": {}}

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
