"""Enterprise-grade monitoring, health checks, and alerting system."""

import time
import logging
import asyncio
import os
from collections import defaultdict
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")


@dataclass
class MetricPoint:
    count: int = 0
    total_time: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None


class PerformanceMonitor:
    def __init__(self):
        self._metrics: Dict[str, MetricPoint] = defaultdict(MetricPoint)
        self._start_time = time.time()
        self._message_count = 0
        self._ai_latencies = []
        self._error_log = []
        self._alert_cooldowns: Dict[str, float] = {}
        self._health_status = {
            "database": True,
            "ai_service": True,
            "telegram_api": True,
        }
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bot_metrics (
                            id SERIAL PRIMARY KEY,
                            metric_name VARCHAR(100) NOT NULL,
                            metric_value FLOAT NOT NULL,
                            metadata JSONB,
                            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bot_alerts (
                            id SERIAL PRIMARY KEY,
                            alert_type VARCHAR(100) NOT NULL,
                            severity VARCHAR(20) NOT NULL,
                            message TEXT NOT NULL,
                            resolved BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            resolved_at TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
                        ON bot_metrics(metric_name, recorded_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_type 
                        ON bot_alerts(alert_type, created_at)
                    """)
        except Exception as e:
            logger.error(f"Failed to init monitoring tables: {e}")

    def track_request(self, operation: str, duration: float, success: bool = True, error: str = None):
        m = self._metrics[operation]
        m.count += 1
        m.total_time += duration
        if not success:
            m.errors += 1
            m.last_error = error
            m.last_error_time = time.time()
            self._error_log.append({
                "operation": operation,
                "error": error,
                "time": time.time()
            })
            if len(self._error_log) > 1000:
                self._error_log = self._error_log[-500:]

    def track_ai_latency(self, latency: float, model: str = "gemini"):
        self._ai_latencies.append({"latency": latency, "model": model, "time": time.time()})
        if len(self._ai_latencies) > 500:
            self._ai_latencies = self._ai_latencies[-250:]

    def track_message(self):
        self._message_count += 1

    def update_health(self, service: str, healthy: bool):
        prev = self._health_status.get(service)
        self._health_status[service] = healthy
        if prev is True and not healthy:
            self._record_alert(
                alert_type=f"{service}_down",
                severity="critical",
                message=f"Service {service} is unhealthy"
            )
        elif prev is False and healthy:
            self._resolve_alert(f"{service}_down")

    def _record_alert(self, alert_type: str, severity: str, message: str):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_alerts (alert_type, severity, message)
                        VALUES (%s, %s, %s)
                    """, (alert_type, severity, message))
        except Exception:
            pass

    def _resolve_alert(self, alert_type: str):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE bot_alerts SET resolved = TRUE, resolved_at = NOW()
                        WHERE alert_type = %s AND resolved = FALSE
                    """, (alert_type,))
        except Exception:
            pass

    def save_metrics_snapshot(self):
        if not DATABASE_URL:
            return
        try:
            import json
            with get_connection() as conn:
                with conn.cursor() as cur:
                    for op, m in self._metrics.items():
                        avg_time = m.total_time / m.count if m.count > 0 else 0
                        cur.execute("""
                            INSERT INTO bot_metrics (metric_name, metric_value, metadata)
                            VALUES (%s, %s, %s)
                        """, (
                            f"op_{op}",
                            avg_time,
                            json.dumps({
                                "count": m.count,
                                "errors": m.errors,
                                "total_time": round(m.total_time, 3)
                            })
                        ))

                    recent_ai = [x for x in self._ai_latencies if time.time() - x["time"] < 3600]
                    if recent_ai:
                        avg_latency = sum(x["latency"] for x in recent_ai) / len(recent_ai)
                        p95 = sorted([x["latency"] for x in recent_ai])[int(len(recent_ai) * 0.95)] if len(recent_ai) > 1 else avg_latency
                        cur.execute("""
                            INSERT INTO bot_metrics (metric_name, metric_value, metadata)
                            VALUES (%s, %s, %s)
                        """, (
                            "ai_latency",
                            avg_latency,
                            json.dumps({"p95": round(p95, 3), "samples": len(recent_ai)})
                        ))
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def get_health_report(self) -> Dict[str, Any]:
        uptime = time.time() - self._start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)

        recent_errors = [e for e in self._error_log if time.time() - e["time"] < 3600]
        error_rate = len(recent_errors) / max(self._message_count, 1) * 100

        recent_ai = [x for x in self._ai_latencies if time.time() - x["time"] < 3600]
        avg_ai_latency = sum(x["latency"] for x in recent_ai) / len(recent_ai) if recent_ai else 0

        return {
            "uptime": f"{hours}h {minutes}m",
            "uptime_seconds": uptime,
            "messages_processed": self._message_count,
            "health_status": dict(self._health_status),
            "all_healthy": all(self._health_status.values()),
            "error_rate_1h": round(error_rate, 2),
            "errors_1h": len(recent_errors),
            "ai_avg_latency": round(avg_ai_latency, 3),
            "ai_samples_1h": len(recent_ai),
            "operations": {
                op: {
                    "count": m.count,
                    "avg_time": round(m.total_time / m.count, 3) if m.count > 0 else 0,
                    "errors": m.errors,
                    "error_rate": round(m.errors / m.count * 100, 1) if m.count > 0 else 0
                }
                for op, m in self._metrics.items()
            }
        }

    def format_health_message(self) -> str:
        report = self.get_health_report()
        health_icons = {True: "🟢", False: "🔴"}

        text = f"🏥 <b>Health Report</b>\n\n"
        text += f"⏱ Аптайм: {report['uptime']}\n"
        text += f"📨 Обработано сообщений: {report['messages_processed']}\n\n"

        text += "<b>Сервисы:</b>\n"
        for service, healthy in report['health_status'].items():
            text += f"{health_icons[healthy]} {service}\n"

        text += f"\n<b>За последний час:</b>\n"
        text += f"❌ Ошибок: {report['errors_1h']}\n"
        text += f"📊 Error rate: {report['error_rate_1h']}%\n"
        text += f"🤖 AI latency: {report['ai_avg_latency']}s (n={report['ai_samples_1h']})\n"

        if report['operations']:
            text += "\n<b>Операции:</b>\n"
            top_ops = sorted(
                report['operations'].items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:8]
            for op, stats in top_ops:
                text += f"• {op}: {stats['count']}x, {stats['avg_time']}s avg"
                if stats['errors'] > 0:
                    text += f" ⚠️{stats['errors']} err"
                text += "\n"

        return text

    async def check_and_alert(self, bot):
        if not MANAGER_CHAT_ID:
            return

        report = self.get_health_report()
        alerts = []

        if not report['all_healthy']:
            down = [s for s, h in report['health_status'].items() if not h]
            alerts.append(f"🔴 Сервисы недоступны: {', '.join(down)}")

        if report['error_rate_1h'] > 10:
            alerts.append(f"⚠️ Высокий error rate: {report['error_rate_1h']}% ({report['errors_1h']} ошибок/час)")

        if report['ai_avg_latency'] > 15 and report['ai_samples_1h'] > 5:
            alerts.append(f"🐌 Высокая задержка AI: {report['ai_avg_latency']}s")

        if not alerts:
            return

        now = time.time()
        alert_key = "|".join(alerts)
        if now - self._alert_cooldowns.get(alert_key, 0) < 1800:
            return
        self._alert_cooldowns[alert_key] = now

        text = "🚨 <b>Bot Alert</b>\n\n" + "\n".join(alerts)
        try:
            await bot.send_message(int(MANAGER_CHAT_ID), text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")


class HealthChecker:
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor

    async def check_database(self) -> bool:
        if not DATABASE_URL:
            return True
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            self.monitor.update_health("database", True)
            return True
        except Exception:
            self.monitor.update_health("database", False)
            return False

    async def check_ai_service(self) -> bool:
        try:
            from src.ai_client import ai_client
            start = time.time()
            result = await ai_client.quick_response("ping")
            latency = time.time() - start
            healthy = bool(result) and latency < 30
            self.monitor.update_health("ai_service", healthy)
            self.monitor.track_ai_latency(latency)
            return healthy
        except Exception:
            self.monitor.update_health("ai_service", False)
            return False

    async def run_all_checks(self) -> Dict[str, bool]:
        db_ok = await self.check_database()
        return {
            "database": db_ok,
            "ai_service": self.monitor._health_status.get("ai_service", True),
            "telegram_api": self.monitor._health_status.get("telegram_api", True),
        }


monitor = PerformanceMonitor()
health_checker = HealthChecker(monitor)


async def periodic_health_check(context):
    try:
        await health_checker.run_all_checks()
        monitor.save_metrics_snapshot()
        await monitor.check_and_alert(context.bot)
    except Exception as e:
        logger.error(f"Health check failed: {e}")


async def periodic_metrics_save(context):
    try:
        monitor.save_metrics_snapshot()
    except Exception as e:
        logger.error(f"Metrics save failed: {e}")
