import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.database import get_connection, DATABASE_URL
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class BroadcastManager:
    def __init__(self):
        self._init_db()

    def _get_connection(self):
        return get_connection()

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, broadcast will not work")
            return

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bot_users (
                            user_id BIGINT PRIMARY KEY,
                            username VARCHAR(255),
                            first_name VARCHAR(255),
                            is_blocked BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS broadcasts (
                            id SERIAL PRIMARY KEY,
                            admin_id BIGINT NOT NULL,
                            content_type VARCHAR(20) DEFAULT 'text',
                            text_content TEXT,
                            media_file_id TEXT,
                            caption TEXT,
                            parse_mode VARCHAR(20),
                            target_audience VARCHAR(50) DEFAULT 'all',
                            status VARCHAR(20) DEFAULT 'draft',
                            total_users INTEGER DEFAULT 0,
                            sent_count INTEGER DEFAULT 0,
                            failed_count INTEGER DEFAULT 0,
                            blocked_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            completed_at TIMESTAMP
                        )
                    """)

                    try:
                        cur.execute("""
                            INSERT INTO bot_users (user_id, username, first_name)
                            SELECT user_id, username, first_name FROM leads
                            ON CONFLICT (user_id) DO NOTHING
                        """)
                    except Exception as e:
                        logger.debug(f"Backfill from leads: {e}")

                    try:
                        cur.execute("""
                            INSERT INTO bot_users (user_id, username, first_name)
                            SELECT telegram_id, username, first_name FROM referral_users
                            ON CONFLICT (user_id) DO NOTHING
                        """)
                    except Exception as e:
                        logger.debug(f"Backfill from referral_users: {e}")

                logger.info("Broadcast tables initialized")
        except Exception as e:
            logger.error(f"Failed to init broadcast tables: {e}")

    def register_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        if not DATABASE_URL:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO bot_users (user_id, username, first_name, last_seen)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (user_id) DO UPDATE SET
                            username = COALESCE(EXCLUDED.username, bot_users.username),
                            first_name = COALESCE(EXCLUDED.first_name, bot_users.first_name),
                            last_seen = CURRENT_TIMESTAMP
                    """, (user_id, username, first_name))
        except Exception as e:
            logger.error(f"Failed to register user {user_id}: {e}")

    def mark_blocked(self, user_id: int):
        if not DATABASE_URL:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE bot_users SET is_blocked = TRUE WHERE user_id = %s",
                        (user_id,)
                    )
        except Exception as e:
            logger.error(f"Failed to mark user {user_id} as blocked: {e}")

    def get_user_ids(self, audience: str = 'all', priority: Optional[str] = None) -> List[int]:
        if not DATABASE_URL:
            return []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if audience == 'all':
                        cur.execute(
                            "SELECT user_id FROM bot_users WHERE is_blocked = FALSE"
                        )
                    elif audience == 'priority' and priority:
                        cur.execute("""
                            SELECT bu.user_id FROM bot_users bu
                            JOIN leads l ON bu.user_id = l.user_id
                            WHERE bu.is_blocked = FALSE AND l.priority = %s
                        """, (priority,))
                    else:
                        cur.execute(
                            "SELECT user_id FROM bot_users WHERE is_blocked = FALSE"
                        )
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user ids: {e}")
            return []

    def get_audience_counts(self) -> Dict[str, int]:
        if not DATABASE_URL:
            return {'all': 0, 'hot': 0, 'warm': 0, 'cold': 0}
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM bot_users WHERE is_blocked = FALSE"
                    )
                    all_count = cur.fetchone()[0]

                    counts = {'all': all_count, 'hot': 0, 'warm': 0, 'cold': 0}

                    for p in ('hot', 'warm', 'cold'):
                        cur.execute("""
                            SELECT COUNT(*) FROM bot_users bu
                            JOIN leads l ON bu.user_id = l.user_id
                            WHERE bu.is_blocked = FALSE AND l.priority = %s
                        """, (p,))
                        counts[p] = cur.fetchone()[0]

                    return counts
        except Exception as e:
            logger.error(f"Failed to get audience counts: {e}")
            return {'all': 0, 'hot': 0, 'warm': 0, 'cold': 0}

    def create_broadcast(self, admin_id: int, content_type: str,
                         text_content: Optional[str] = None,
                         media_file_id: Optional[str] = None,
                         caption: Optional[str] = None,
                         parse_mode: Optional[str] = None,
                         target_audience: str = 'all') -> Optional[int]:
        if not DATABASE_URL:
            return None
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if target_audience == 'all':
                        user_ids = self.get_user_ids('all')
                    else:
                        user_ids = self.get_user_ids('priority', priority=target_audience)
                    total = len(user_ids)

                    cur.execute("""
                        INSERT INTO broadcasts
                            (admin_id, content_type, text_content, media_file_id, caption,
                             parse_mode, target_audience, status, total_users)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'sending', %s)
                        RETURNING id
                    """, (admin_id, content_type, text_content, media_file_id,
                          caption, parse_mode, target_audience, total))
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to create broadcast: {e}")
            return None

    def update_broadcast(self, broadcast_id: int, **kwargs):
        if not DATABASE_URL:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    set_parts = []
                    values = []
                    for key, value in kwargs.items():
                        set_parts.append(f"{key} = %s")
                        values.append(value)
                    if not set_parts:
                        return
                    values.append(broadcast_id)
                    cur.execute(
                        f"UPDATE broadcasts SET {', '.join(set_parts)} WHERE id = %s",
                        tuple(values)
                    )
        except Exception as e:
            logger.error(f"Failed to update broadcast {broadcast_id}: {e}")

    def complete_broadcast(self, broadcast_id: int, sent: int, failed: int, blocked: int):
        if not DATABASE_URL:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE broadcasts SET
                            status = 'completed',
                            sent_count = %s,
                            failed_count = %s,
                            blocked_count = %s,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (sent, failed, blocked, broadcast_id))
        except Exception as e:
            logger.error(f"Failed to complete broadcast {broadcast_id}: {e}")

    def get_recent_broadcasts(self, limit: int = 5) -> List[Dict]:
        if not DATABASE_URL:
            return []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT %s",
                        (limit,)
                    )
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get recent broadcasts: {e}")
            return []

    def get_broadcast(self, broadcast_id: int) -> Optional[Dict]:
        if not DATABASE_URL:
            return None
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM broadcasts WHERE id = %s", (broadcast_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get broadcast {broadcast_id}: {e}")
            return None

    def format_broadcast_stats(self) -> str:
        recent = self.get_recent_broadcasts(5)
        counts = self.get_audience_counts()

        text = "📡 <b>Система рассылок</b>\n\n"
        text += f"👥 <b>Аудитория:</b>\n"
        text += f"  Всего: {counts.get('all', 0)}\n"
        text += f"  🔥 Горячие: {counts.get('hot', 0)}\n"
        text += f"  🌡 Тёплые: {counts.get('warm', 0)}\n"
        text += f"  ❄️ Холодные: {counts.get('cold', 0)}\n"

        if recent:
            text += "\n📋 <b>Последние рассылки:</b>\n"
            for bc in recent:
                status_emoji = {
                    'draft': '📝', 'sending': '📤', 'completed': '✅', 'failed': '❌'
                }.get(bc.get('status', ''), '❓')
                date_str = bc['created_at'].strftime('%d.%m %H:%M') if bc.get('created_at') else ''
                audience_names = {'all': 'все', 'hot': '🔥', 'warm': '🌡', 'cold': '❄️'}
                audience = audience_names.get(bc.get('target_audience', 'all'), bc.get('target_audience', ''))
                text += (
                    f"\n{status_emoji} {date_str} — {audience}\n"
                    f"   👥 {bc.get('total_users', 0)} | "
                    f"✅ {bc.get('sent_count', 0)} | "
                    f"❌ {bc.get('failed_count', 0)} | "
                    f"🚫 {bc.get('blocked_count', 0)}"
                )
        else:
            text += "\n<i>Рассылок пока не было</i>"

        return text

    async def send_broadcast(self, bot, broadcast_id: int, progress_callback=None):
        from telegram.error import Forbidden, BadRequest

        bc = self.get_broadcast(broadcast_id)
        if not bc:
            logger.error(f"Broadcast {broadcast_id} not found")
            return

        target_audience = bc.get('target_audience', 'all')
        if target_audience == 'all':
            user_ids = self.get_user_ids('all')
        else:
            user_ids = self.get_user_ids('priority', priority=target_audience)

        total = len(user_ids)
        self.update_broadcast(broadcast_id, total_users=total)

        sent = 0
        failed = 0
        blocked = 0
        content_type = bc.get('content_type', 'text')

        for i, user_id in enumerate(user_ids):
            try:
                if content_type == 'text':
                    await bot.send_message(
                        chat_id=user_id,
                        text=bc.get('text_content', '')
                    )
                elif content_type == 'photo':
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=bc.get('media_file_id'),
                        caption=bc.get('caption') or None
                    )
                elif content_type == 'video':
                    await bot.send_video(
                        chat_id=user_id,
                        video=bc.get('media_file_id'),
                        caption=bc.get('caption') or None
                    )
                sent += 1
            except Forbidden:
                self.mark_blocked(user_id)
                blocked += 1
            except BadRequest:
                failed += 1
            except Exception as e:
                logger.error(f"Broadcast send error to {user_id}: {e}")
                failed += 1

            if (i + 1) % 25 == 0:
                await asyncio.sleep(1.1)

            if progress_callback and (i + 1) % 50 == 0:
                await progress_callback(sent, failed, blocked, total)

        self.complete_broadcast(broadcast_id, sent, failed, blocked)

        if progress_callback:
            await progress_callback(sent, failed, blocked, total)

        return {'sent': sent, 'failed': failed, 'blocked': blocked, 'total': total}


broadcast_manager = BroadcastManager()
