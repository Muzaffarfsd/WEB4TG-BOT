import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

SESSION_GAP_MINUTES = 30


class PropensityScorer:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, propensity scoring disabled")
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS interaction_metrics (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT UNIQUE NOT NULL,
                            first_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            total_messages INT DEFAULT 0,
                            session_count INT DEFAULT 0,
                            avg_response_time_sec FLOAT DEFAULT 0,
                            tools_used INT DEFAULT 0,
                            features_explored INT DEFAULT 0,
                            pricing_views INT DEFAULT 0,
                            portfolio_views INT DEFAULT 0,
                            calculator_uses INT DEFAULT 0,
                            roi_uses INT DEFAULT 0,
                            brief_uses INT DEFAULT 0,
                            compare_uses INT DEFAULT 0,
                            lead_submitted BOOLEAN DEFAULT FALSE,
                            consultation_requested BOOLEAN DEFAULT FALSE,
                            payment_viewed BOOLEAN DEFAULT FALSE,
                            last_score INT DEFAULT 0,
                            score_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
            logger.info("interaction_metrics table initialized")
        except Exception as e:
            logger.error(f"Failed to init interaction_metrics table: {e}")

    def record_interaction(self, user_id: int, event_type: str = 'message') -> None:
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO interaction_metrics (user_id, session_count)
                        VALUES (%s, 1)
                        ON CONFLICT (user_id) DO NOTHING
                    """, (user_id,))

                    cur.execute(
                        "SELECT last_interaction FROM interaction_metrics WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    last_interaction = row[0] if row else None

                    new_session = False
                    if last_interaction:
                        gap = datetime.utcnow() - last_interaction
                        if gap > timedelta(minutes=SESSION_GAP_MINUTES):
                            new_session = True

                    updates = ["last_interaction = CURRENT_TIMESTAMP"]
                    params: list = []

                    if event_type == 'message':
                        updates.append("total_messages = total_messages + 1")

                    if event_type == 'tool_calculator':
                        updates.append("calculator_uses = calculator_uses + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_portfolio':
                        updates.append("portfolio_views = portfolio_views + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_pricing':
                        updates.append("pricing_views = pricing_views + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_payment':
                        updates.append("payment_viewed = TRUE")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_lead':
                        updates.append("lead_submitted = TRUE")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_consultation':
                        updates.append("consultation_requested = TRUE")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_roi':
                        updates.append("roi_uses = roi_uses + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_brief':
                        updates.append("brief_uses = brief_uses + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_compare':
                        updates.append("compare_uses = compare_uses + 1")
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_discount':
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_calendar':
                        updates.append("tools_used = tools_used + 1")
                        updates.append("features_explored = features_explored + 1")
                    elif event_type == 'tool_social':
                        updates.append("tools_used = tools_used + 1")

                    if new_session:
                        updates.append("session_count = session_count + 1")

                    params.append(user_id)

                    cur.execute(
                        f"UPDATE interaction_metrics SET {', '.join(updates)} WHERE user_id = %s",
                        params
                    )

            score = self.calculate_score(user_id)
            if score is not None:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE interaction_metrics SET last_score = %s, score_updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                            (score, user_id)
                        )
        except Exception as e:
            logger.error(f"Failed to record interaction for user {user_id}: {e}")

    def calculate_score(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT first_interaction, last_interaction, total_messages,
                               session_count, calculator_uses, portfolio_views,
                               pricing_views, lead_submitted, consultation_requested,
                               payment_viewed, roi_uses, brief_uses, compare_uses
                        FROM interaction_metrics WHERE user_id = %s
                    """, (user_id,))
                    row = cur.fetchone()
                    if not row:
                        return 0

                    (first_interaction, last_interaction, total_messages,
                     session_count, calculator_uses, portfolio_views,
                     pricing_views, lead_submitted, consultation_requested,
                     payment_viewed, roi_uses, brief_uses, compare_uses) = row

                    days_active = max((datetime.utcnow() - first_interaction).total_seconds() / 86400, 0.1)
                    messages_per_day = total_messages / days_active
                    engagement_velocity = min(messages_per_day * 3, 15)

                    session_depth = min(total_messages / 3, 15)

                    multi_session = min(session_count * 5, 15)

                    tool_engagement = min(
                        calculator_uses * 8
                        + portfolio_views * 5
                        + pricing_views * 3
                        + roi_uses * 5
                        + brief_uses * 8
                        + compare_uses * 3,
                        25
                    )

                    buying_signals = min(
                        (15 if lead_submitted else 0)
                        + (10 if consultation_requested else 0)
                        + (15 if payment_viewed else 0),
                        25
                    )

                    days_since_last = (datetime.utcnow() - last_interaction).total_seconds() / 86400
                    if days_since_last <= 1:
                        decay = 1.0
                    elif days_since_last <= 3:
                        decay = 0.9
                    elif days_since_last <= 7:
                        decay = 0.7
                    elif days_since_last <= 14:
                        decay = 0.5
                    elif days_since_last <= 30:
                        decay = 0.3
                    else:
                        decay = 0.1

                    raw_score = engagement_velocity + session_depth + multi_session + tool_engagement + buying_signals
                    final_score = min(100, int(raw_score * decay))
                    return final_score
        except Exception as e:
            logger.error(f"Failed to calculate score for user {user_id}: {e}")
            return 0

    def get_score(self, user_id: int) -> Optional[int]:
        if not DATABASE_URL:
            return None

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT last_score FROM interaction_metrics WHERE user_id = %s",
                        (user_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0]
        except Exception as e:
            logger.error(f"Failed to get score for user {user_id}: {e}")
        return None

    def boost_score(self, user_id: int, boost: int, reason: str = "") -> None:
        if not DATABASE_URL or boost <= 0:
            return
        try:
            current = self.get_score(user_id)
            if current is None:
                self.record_interaction(user_id, "message")
                current = 0
            new_score = min(100, current + boost)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE interaction_metrics SET last_score = %s, score_updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                        (new_score, user_id)
                    )
            logger.info(f"Propensity boost for user {user_id}: +{boost} ({reason}), {current}->{new_score}")
        except Exception as e:
            logger.error(f"Failed to boost score for user {user_id}: {e}")

    def get_top_prospects(self, limit: int = 10) -> List[Dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id, last_score, total_messages, last_interaction, lead_submitted
                        FROM interaction_metrics
                        ORDER BY last_score DESC
                        LIMIT %s
                    """, (limit,))
                    results = []
                    for row in cur.fetchall():
                        results.append({
                            "user_id": row[0],
                            "score": row[1],
                            "total_messages": row[2],
                            "last_interaction": row[3].isoformat() if row[3] else None,
                            "lead_submitted": row[4]
                        })
                    return results
        except Exception as e:
            logger.error(f"Failed to get top prospects: {e}")
        return []

    def get_score_distribution(self) -> Dict:
        if not DATABASE_URL:
            return {"hot_70_100": 0, "warm_40_69": 0, "cool_20_39": 0, "cold_0_19": 0}

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE last_score >= 70) AS hot_70_100,
                            COUNT(*) FILTER (WHERE last_score >= 40 AND last_score < 70) AS warm_40_69,
                            COUNT(*) FILTER (WHERE last_score >= 20 AND last_score < 40) AS cool_20_39,
                            COUNT(*) FILTER (WHERE last_score < 20) AS cold_0_19
                        FROM interaction_metrics
                    """)
                    row = cur.fetchone()
                    if row:
                        return {
                            "hot_70_100": row[0],
                            "warm_40_69": row[1],
                            "cool_20_39": row[2],
                            "cold_0_19": row[3]
                        }
        except Exception as e:
            logger.error(f"Failed to get score distribution: {e}")
        return {"hot_70_100": 0, "warm_40_69": 0, "cool_20_39": 0, "cold_0_19": 0}


propensity_scorer = PropensityScorer()
