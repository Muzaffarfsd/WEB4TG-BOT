"""Self-learning feedback loop system for tracking AI response outcomes."""
import logging
from typing import Optional
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


class FeedbackLoop:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS response_outcomes (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            message_text TEXT,
                            response_text TEXT,
                            response_variant VARCHAR(20),
                            funnel_stage VARCHAR(30),
                            propensity_score INT,
                            outcome_type VARCHAR(30) NULL,
                            outcome_at TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_response_outcomes_user_id
                        ON response_outcomes(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_response_outcomes_outcome_type
                        ON response_outcomes(outcome_type)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_response_outcomes_created_at
                        ON response_outcomes(created_at)
                    """)
            logger.info("Response outcomes table initialized")
        except Exception as e:
            logger.error(f"Failed to init response_outcomes table: {e}")

    def log_response(self, user_id: int, message_text: str, response_text: str,
                     variant: Optional[str] = None, funnel_stage: Optional[str] = None,
                     propensity_score: Optional[int] = None) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO response_outcomes
                        (user_id, message_text, response_text, response_variant, funnel_stage, propensity_score)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user_id, message_text, response_text, variant, funnel_stage, propensity_score))
                    result = cur.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to log response: {e}")
            return 0

    def record_outcome(self, user_id: int, outcome_type: str) -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE response_outcomes
                        SET outcome_type = %s, outcome_at = NOW()
                        WHERE id = (
                            SELECT id FROM response_outcomes
                            WHERE user_id = %s AND outcome_type IS NULL
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                    """, (outcome_type, user_id))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to record outcome for user {user_id}: {e}")
            return False

    def record_outcome_by_id(self, response_id: int, outcome_type: str) -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE response_outcomes
                        SET outcome_type = %s, outcome_at = NOW()
                        WHERE id = %s
                    """, (outcome_type, response_id))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to record outcome for response {response_id}: {e}")
            return False

    def get_successful_patterns(self, outcome_type: str = 'lead_created',
                                limit: int = 20) -> list[dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT message_text, response_text, funnel_stage, response_variant
                        FROM response_outcomes
                        WHERE outcome_type = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (outcome_type, limit))
                    rows = cur.fetchall()
                    return [
                        {
                            "message_text": row[0],
                            "response_text": row[1],
                            "funnel_stage": row[2],
                            "response_variant": row[3],
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Failed to get successful patterns: {e}")
            return []

    def get_conversion_rate(self, days: int = 30) -> dict:
        if not DATABASE_URL:
            return {}

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS with_outcome
                        FROM response_outcomes
                        WHERE created_at >= NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    row = cur.fetchone()
                    total_responses = row[0] if row else 0
                    with_outcome = row[1] if row else 0
                    conversion_rate = round((with_outcome / total_responses * 100), 2) if total_responses > 0 else 0.0

                    cur.execute("""
                        SELECT outcome_type, COUNT(*) AS cnt
                        FROM response_outcomes
                        WHERE outcome_type IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY outcome_type
                    """, (days,))
                    by_outcome = {r[0]: r[1] for r in cur.fetchall()}

                    cur.execute("""
                        SELECT
                            funnel_stage,
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS converted
                        FROM response_outcomes
                        WHERE funnel_stage IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY funnel_stage
                    """, (days,))
                    by_stage = {r[0]: {"total": r[1], "converted": r[2]} for r in cur.fetchall()}

                    cur.execute("""
                        SELECT
                            response_variant,
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS converted
                        FROM response_outcomes
                        WHERE response_variant IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY response_variant
                    """, (days,))
                    by_variant = {r[0]: {"total": r[1], "converted": r[2]} for r in cur.fetchall()}

                    return {
                        "total_responses": total_responses,
                        "with_outcome": with_outcome,
                        "conversion_rate": conversion_rate,
                        "by_outcome": by_outcome,
                        "by_stage": by_stage,
                        "by_variant": by_variant,
                    }
        except Exception as e:
            logger.error(f"Failed to get conversion rate: {e}")
            return {}

    def get_learning_insights(self, limit: int = 10) -> str:
        if not DATABASE_URL:
            return "Database not configured"

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT funnel_stage,
                               COUNT(*) AS total,
                               COUNT(outcome_type) AS converted,
                               ROUND(COUNT(outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_outcomes
                        WHERE funnel_stage IS NOT NULL
                        GROUP BY funnel_stage
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    stage_rows = cur.fetchall()

                    cur.execute("""
                        SELECT response_variant,
                               COUNT(*) AS total,
                               COUNT(outcome_type) AS converted,
                               ROUND(COUNT(outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_outcomes
                        WHERE response_variant IS NOT NULL
                        GROUP BY response_variant
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    variant_rows = cur.fetchall()

                    cur.execute("""
                        SELECT message_text, COUNT(*) AS cnt
                        FROM response_outcomes
                        WHERE outcome_type IS NOT NULL
                          AND message_text IS NOT NULL
                        GROUP BY message_text
                        ORDER BY cnt DESC
                        LIMIT %s
                    """, (limit,))
                    message_rows = cur.fetchall()

            lines = ["📊 Learning Insights\n"]

            lines.append("🏆 Best converting funnel stages:")
            if stage_rows:
                for row in stage_rows:
                    lines.append(f"  • {row[0]}: {row[2]}/{row[1]} ({row[3]}%)")
            else:
                lines.append("  No data yet")

            lines.append("\n🔬 Best converting A/B variants:")
            if variant_rows:
                for row in variant_rows:
                    lines.append(f"  • Variant {row[0]}: {row[2]}/{row[1]} ({row[3]}%)")
            else:
                lines.append("  No data yet")

            lines.append("\n💬 Most common converting messages:")
            if message_rows:
                for row in message_rows:
                    msg_preview = (row[0][:60] + "...") if row[0] and len(row[0]) > 60 else row[0]
                    lines.append(f"  • \"{msg_preview}\" — {row[1]}x")
            else:
                lines.append("  No data yet")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get learning insights: {e}")
            return "Error generating insights"

    def cleanup_old(self, days: int = 90) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM response_outcomes
                        WHERE created_at < NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    deleted = cur.rowcount
                    logger.info(f"Cleaned up {deleted} old response outcomes (older than {days} days)")
                    return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old response outcomes: {e}")
            return 0


feedback_loop = FeedbackLoop()
