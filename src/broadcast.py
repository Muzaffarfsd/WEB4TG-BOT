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

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS broadcast_deliveries (
                            broadcast_id INTEGER REFERENCES broadcasts(id),
                            user_id BIGINT NOT NULL,
                            status VARCHAR(20) DEFAULT 'pending',
                            sent_at TIMESTAMP,
                            PRIMARY KEY (broadcast_id, user_id)
                        )
                    """)

                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_bc_deliveries_status
                        ON broadcast_deliveries(broadcast_id, status)
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
                    broadcast_id = row[0] if row else None

                    if broadcast_id:
                        for uid in user_ids:
                            cur.execute("""
                                INSERT INTO broadcast_deliveries (broadcast_id, user_id, status)
                                VALUES (%s, %s, 'pending') ON CONFLICT DO NOTHING
                            """, (broadcast_id, uid))

                    return broadcast_id
        except Exception as e:
            logger.error(f"Failed to create broadcast: {e}")
            return None

    ALLOWED_BROADCAST_COLUMNS = {
        "status", "total_users", "sent_count", "failed_count",
        "blocked_count", "completed_at", "text_content", "media_file_id",
        "caption", "parse_mode", "target_audience"
    }

    def update_broadcast(self, broadcast_id: int, **kwargs):
        if not DATABASE_URL:
            return
        safe_kwargs = {k: v for k, v in kwargs.items() if k in self.ALLOWED_BROADCAST_COLUMNS}
        if not safe_kwargs:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    set_parts = []
                    values = []
                    for key, value in safe_kwargs.items():
                        set_parts.append(f"{key} = %s")
                        values.append(value)
                    values.append(broadcast_id)
                    cur.execute(
                        f"UPDATE broadcasts SET {', '.join(set_parts)} WHERE id = %s",
                        tuple(values)
                    )
        except Exception as e:
            logger.error(f"Failed to update broadcast {broadcast_id}: {e}")

    def _update_delivery_status(self, broadcast_id: int, user_id: int, status: str):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE broadcast_deliveries
                        SET status = %s, sent_at = CURRENT_TIMESTAMP
                        WHERE broadcast_id = %s AND user_id = %s
                    """, (status, broadcast_id, user_id))
        except Exception as e:
            logger.error(f"Failed to update delivery status for broadcast {broadcast_id}, user {user_id}: {e}")

    def complete_broadcast(self, broadcast_id: int, sent: int, failed: int, blocked: int):
        if not DATABASE_URL:
            return
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'sent') as sent,
                            COUNT(*) FILTER (WHERE status = 'failed') as failed,
                            COUNT(*) FILTER (WHERE status = 'blocked') as blocked
                        FROM broadcast_deliveries WHERE broadcast_id = %s
                    """, (broadcast_id,))
                    row = cur.fetchone()
                    if row:
                        actual_sent, actual_failed, actual_blocked = row
                    else:
                        actual_sent, actual_failed, actual_blocked = sent, failed, blocked

                    cur.execute("""
                        UPDATE broadcasts SET
                            status = 'completed',
                            sent_count = %s,
                            failed_count = %s,
                            blocked_count = %s,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (actual_sent, actual_failed, actual_blocked, broadcast_id))
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

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT user_id FROM broadcast_deliveries
                        WHERE broadcast_id = %s AND status = 'pending'
                        ORDER BY user_id
                    """, (broadcast_id,))
                    user_ids = [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get pending deliveries for broadcast {broadcast_id}: {e}")
            return

        total = len(user_ids)
        self.update_broadcast(broadcast_id, total_users=bc.get('total_users', total))

        sent = 0
        failed = 0
        blocked = 0
        content_type = bc.get('content_type', 'text')

        voice_supplement_audio = None
        try:
            from src.config import config as app_config
            if app_config.elevenlabs_api_key:
                broadcast_text = bc.get('text_content') or bc.get('caption') or ''
                if broadcast_text:
                    voice_text = await _generate_broadcast_voice_supplement(broadcast_text)
                    if voice_text:
                        from src.handlers.media import generate_voice_response
                        voice_supplement_audio = await generate_voice_response(voice_text, voice_profile="greeting")
        except Exception as e:
            logger.warning(f"Broadcast voice supplement pre-generation failed: {e}")

        for i, user_id in enumerate(user_ids):
            try:
                pm = bc.get('parse_mode') or None
                if content_type == 'text':
                    await bot.send_message(
                        chat_id=user_id,
                        text=bc.get('text_content', ''),
                        parse_mode=pm
                    )
                elif content_type == 'photo':
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=bc.get('media_file_id'),
                        caption=bc.get('caption') or None,
                        parse_mode=pm
                    )
                elif content_type == 'video':
                    await bot.send_video(
                        chat_id=user_id,
                        video=bc.get('media_file_id'),
                        caption=bc.get('caption') or None,
                        parse_mode=pm
                    )

                if voice_supplement_audio:
                    try:
                        await bot.send_voice(chat_id=user_id, voice=voice_supplement_audio)
                    except Exception as ve:
                        logger.debug(f"Voice supplement to {user_id} failed: {ve}")

                sent += 1
                self._update_delivery_status(broadcast_id, user_id, 'sent')
            except Forbidden:
                self.mark_blocked(user_id)
                self._update_delivery_status(broadcast_id, user_id, 'blocked')
                blocked += 1
            except BadRequest:
                self._update_delivery_status(broadcast_id, user_id, 'failed')
                failed += 1
            except Exception as e:
                logger.error(f"Broadcast send error to {user_id}: {e}")
                self._update_delivery_status(broadcast_id, user_id, 'failed')
                failed += 1

            if (i + 1) % 25 == 0:
                await asyncio.sleep(1.1)

            if progress_callback and (i + 1) % 50 == 0:
                await progress_callback(sent, failed, blocked, total)

        self.complete_broadcast(broadcast_id, sent, failed, blocked)

        if progress_callback:
            await progress_callback(sent, failed, blocked, total)

        return {'sent': sent, 'failed': failed, 'blocked': blocked, 'total': total}

    async def resume_broadcast(self, bot, progress_callback=None) -> List[Dict]:
        results = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id FROM broadcasts
                        WHERE status = 'sending'
                        ORDER BY created_at ASC
                    """)
                    pending_broadcasts = [row['id'] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to find broadcasts to resume: {e}")
            return results

        for broadcast_id in pending_broadcasts:
            logger.info(f"Resuming broadcast {broadcast_id}")
            result = await self.send_broadcast(bot, broadcast_id, progress_callback)
            if result:
                results.append({'broadcast_id': broadcast_id, **result})

        return results


_BC_VALID_TAGS = {"warm", "excited", "curious", "confident", "whispers", "friendly"}
_BC_CTA_WORDS = {"напиши", "глянь", "ответь", "обсудим", "покажу", "расскажу", "скину", "давай"}


def _validate_bc_voice(raw_text: str, _re=None) -> str:
    """Hard validation: single tag, CTA present, 35-90 chars clean text."""
    if _re is None:
        import re as _re

    result = raw_text.strip().strip('"').strip("'").strip('\u201c').strip('\u201d')
    result = _re.sub(r'\*+', '', result)
    result = _re.sub(r'#+\s*', '', result)
    result = _re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+', '', result)
    result = result.strip()

    tags_found = _re.findall(r'\[(\w+)\]', result)
    if len(tags_found) > 1:
        first_tag = tags_found[0]
        result = _re.sub(r'\[\w+\]\s*', '', result)
        if first_tag in _BC_VALID_TAGS:
            result = f"[{first_tag}] {result.strip()}"
        tags_found = [first_tag] if first_tag in _BC_VALID_TAGS else []

    if tags_found and tags_found[0] not in _BC_VALID_TAGS:
        result = _re.sub(r'\[\w+\]\s*', '', result).strip()

    clean = _re.sub(r'\[\w[\w\s]*?\]\s*', '', result).strip()
    if not (35 <= len(clean) <= 90):
        return ""

    if not any(w in clean.lower() for w in _BC_CTA_WORDS):
        return ""

    return result


async def _generate_broadcast_voice_supplement(text_message: str) -> str:
    """Generate short voice hook for broadcast — must feel personal, not mass, and pull into dialog about Telegram Mini App."""
    import re as _re

    safe_text = (text_message or "").strip()
    if len(safe_text) < 10:
        safe_text = "рассылка о возможностях Telegram Mini App для бизнеса"
    elif len(safe_text) > 500:
        safe_text = safe_text[:500] + "..."

    try:
        from google.genai import types as genai_types
        from src.config import config as app_config, get_gemini_client

        client = get_gemini_client()

        prompt = (
            "Ты — Алекс, живой консультант WEB4TG Studio. Записываешь КОРОТКОЕ голосовое к рассылке.\n\n"
            f"ТЕКСТ РАССЫЛКИ:\n{safe_text}\n\n"
            "КОНТЕКСТ: Рассылка идёт МНОГИМ людям, но голосовое должно звучать как ЛИЧНОЕ сообщение.\n"
            "Цель — вернуть человека в диалог и начать обсуждение разработки Telegram Mini App.\n"
            "Человек видит текст, потом слышит голос — и думает 'мне лично записали, надо ответить'.\n\n"
            "ОБЯЗАТЕЛЬНО используй ОДИН психологический триггер:\n"
            "1. CURIOSITY GAP — 'у меня тут кое-что... напиши, расскажу'\n"
            "2. SOCIAL PROOF — 'похожие бизнесы уже запустили и результат — wow'\n"
            "3. FOMO — 'это ненадолго', 'скоро закроем набор'\n"
            "4. SCARCITY — 'берём 3 проекта в месяц', 'пока есть окно'\n"
            "5. RECIPROCITY — 'подготовил кое-что для тебя', 'сделал подборку'\n\n"
            "СТРАТЕГИЧЕСКОЕ ИСПОЛЬЗОВАНИЕ ТЕГОВ (выбери ОДИН):\n"
            "- [whispers] — эксклюзивность: 'между нами...', 'тебе первому'\n"
            "- [excited] — срочность и wow: 'это реально крутая штука'\n"
            "- [curious] — незавершённая мысль: 'я тут подумал...'\n"
            "- [warm] — личное: 'серьёзно, мне не всё равно'\n"
            "- [confident] — экспертность: 'я знаю как это сработает'\n"
            "- [friendly] — лёгкость: 'глянь, без обязательств'\n\n"
            "ЗАПРЕЩЕНО:\n"
            "- Повторять текст рассылки\n"
            "- Банальности: 'это интересно', 'стоит внимания', 'не пропусти'\n"
            "- Звучать как бот или спам\n"
            "- Больше одного тега\n\n"
            "ФОРМАТ: [тег] текст\n"
            "ДЛИНА: 40-80 символов чистого текста (без тега)\n"
            "ОБЯЗАТЕЛЬНО мини-CTA в конце: 'напиши', 'ответь', 'глянь', 'давай обсудим'\n"
            "НЕТ markdown, emoji, кавычек. WEB4TG Studio — по-английски.\n"
            "Верни ТОЛЬКО текст для озвучки."
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=app_config.model_name,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                max_output_tokens=120,
                temperature=0.7
            )
        )

        if response.text:
            result = _validate_bc_voice(response.text, _re)
            if result:
                return result

    except Exception as e:
        logger.warning(f"Broadcast voice supplement gen failed: {e}")

    import random
    _bc_fallbacks = [
        "[curious] Я тут записал это лично для тебя... просто глянь и напиши что думаешь",
        "[whispers] Между нами — сейчас самое удачное время зайти, напиши пока открыто",
        "[warm] Один бизнес как твой недавно запустился и окупился за месяц — покажу, ответь",
        "[excited] Тут кое-что новое для таких проектов как твой — давай обсудим",
        "[confident] Я точно знаю как это можно сделать в твоём случае — напиши, расскажу",
        "[friendly] Сделал подборку идей под твою нишу, бесплатно — глянь, просто ответь",
    ]
    return random.choice(_bc_fallbacks)


broadcast_manager = BroadcastManager()
