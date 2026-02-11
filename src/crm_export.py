"""CRM integration and data export: webhooks, CSV/JSON export, auto-sync."""

import csv
import io
import json
import time
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


class CRMExporter:
    def __init__(self):
        self._webhook_url = None
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_webhooks (
                            id SERIAL PRIMARY KEY,
                            event_type VARCHAR(100) NOT NULL,
                            webhook_url TEXT NOT NULL,
                            active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_export_log (
                            id SERIAL PRIMARY KEY,
                            export_type VARCHAR(50) NOT NULL,
                            records_count INT NOT NULL,
                            status VARCHAR(20) DEFAULT 'completed',
                            metadata JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
        except Exception as e:
            logger.error(f"Failed to init CRM tables: {e}")

    def export_leads_csv(self, days: int = 30) -> Optional[str]:
        if not DATABASE_URL:
            return None
        try:
            from psycopg2.extras import RealDictCursor
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            user_id, username, first_name, phone,
                            business_type, budget, estimated_cost,
                            status, priority, score,
                            message_count, tags,
                            created_at, last_activity
                        FROM leads
                        WHERE created_at > NOW() - %s * INTERVAL '1 day'
                        ORDER BY created_at DESC
                    """, (days,))
                    rows = cur.fetchall()

            if not rows:
                return None

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                clean_row = {}
                for k, v in row.items():
                    if isinstance(v, (list, dict)):
                        clean_row[k] = json.dumps(v, ensure_ascii=False)
                    elif isinstance(v, datetime):
                        clean_row[k] = v.isoformat()
                    else:
                        clean_row[k] = v
                writer.writerow(clean_row)

            self._log_export("csv", len(rows))
            return output.getvalue()
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return None

    def export_leads_json(self, days: int = 30) -> Optional[str]:
        if not DATABASE_URL:
            return None
        try:
            from psycopg2.extras import RealDictCursor
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            user_id, username, first_name, phone,
                            business_type, budget, estimated_cost,
                            status, priority, score,
                            message_count, tags,
                            created_at, last_activity
                        FROM leads
                        WHERE created_at > NOW() - %s * INTERVAL '1 day'
                        ORDER BY created_at DESC
                    """, (days,))
                    rows = cur.fetchall()

            if not rows:
                return None

            data = []
            for row in rows:
                item = {}
                for k, v in row.items():
                    if isinstance(v, datetime):
                        item[k] = v.isoformat()
                    else:
                        item[k] = v
                data.append(item)

            self._log_export("json", len(data))
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return None

    def export_analytics_json(self, days: int = 30) -> Optional[str]:
        if not DATABASE_URL:
            return None
        try:
            from src.analytics import analytics
            from src.advanced_analytics import advanced_analytics

            data = {
                "period_days": days,
                "exported_at": datetime.now().isoformat(),
                "funnel": analytics.get_funnel_stats(days),
                "daily_funnel": advanced_analytics.get_funnel_by_day(days),
                "revenue": advanced_analytics.get_revenue_stats(days),
                "segments": advanced_analytics.get_conversion_attribution(days),
                "cohorts": advanced_analytics.get_cohort_analysis(days),
            }
            self._log_export("analytics_json", 1)
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Analytics export failed: {e}")
            return None

    async def send_webhook(self, event_type: str, data: dict):
        webhooks = self._get_active_webhooks(event_type)
        if not webhooks:
            return

        import aiohttp
        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }

        async with aiohttp.ClientSession() as session:
            for wh in webhooks:
                try:
                    async with session.post(
                        wh["webhook_url"],
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status >= 400:
                            logger.warning(f"Webhook {event_type} to {wh['webhook_url']} returned {resp.status}")
                except Exception as e:
                    logger.error(f"Webhook {event_type} failed: {e}")

    async def on_new_lead(self, lead_data: dict):
        await self.send_webhook("new_lead", lead_data)

    async def on_payment(self, payment_data: dict):
        await self.send_webhook("payment", payment_data)

    def add_webhook(self, event_type: str, url: str) -> bool:
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO crm_webhooks (event_type, webhook_url)
                        VALUES (%s, %s)
                    """, (event_type, url))
            return True
        except Exception as e:
            logger.error(f"Failed to add webhook: {e}")
            return False

    def remove_webhook(self, webhook_id: int) -> bool:
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE crm_webhooks SET active = FALSE WHERE id = %s",
                        (webhook_id,)
                    )
            return True
        except Exception:
            return False

    def _get_active_webhooks(self, event_type: str) -> list:
        if not DATABASE_URL:
            return []
        try:
            from psycopg2.extras import RealDictCursor
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM crm_webhooks
                        WHERE event_type = %s AND active = TRUE
                    """, (event_type,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    def _log_export(self, export_type: str, count: int):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO crm_export_log (export_type, records_count)
                        VALUES (%s, %s)
                    """, (export_type, count))
        except Exception:
            pass

    def get_export_history(self, limit: int = 20) -> list:
        if not DATABASE_URL:
            return []
        try:
            from psycopg2.extras import RealDictCursor
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM crm_export_log
                        ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                    return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []


crm_exporter = CRMExporter()
