"""RAG on Successful Dialogs — learn from conversations that led to conversions."""
import logging
import json
import time
from typing import Optional, List, Dict
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

class DialogRAG:
    def __init__(self):
        self._init_tables()
    
    def _init_tables(self):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS successful_dialogs (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT,
                            niche VARCHAR(50),
                            scenario VARCHAR(50),
                            funnel_stage VARCHAR(30),
                            user_message TEXT,
                            bot_response TEXT,
                            methodology_used VARCHAR(50),
                            outcome VARCHAR(30),
                            quality_score FLOAT DEFAULT 0,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dialog_rag_scenario 
                        ON successful_dialogs(scenario, quality_score DESC)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dialog_rag_niche
                        ON successful_dialogs(niche, scenario)
                    """)
        except Exception as e:
            logger.error(f"Failed to init dialog RAG tables: {e}")
    
    def save_successful_exchange(
        self, user_id: int, user_message: str, bot_response: str,
        niche: str = "", scenario: str = "", funnel_stage: str = "",
        methodology: str = "", outcome: str = "conversion",
        quality_score: float = 0.8
    ):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM successful_dialogs")
                    count = cur.fetchone()[0]
                    if count > 500:
                        cur.execute("""
                            DELETE FROM successful_dialogs 
                            WHERE id IN (
                                SELECT id FROM successful_dialogs 
                                ORDER BY quality_score ASC, created_at ASC 
                                LIMIT %s
                            )
                        """, (count - 450,))
                    
                    cur.execute("""
                        INSERT INTO successful_dialogs 
                        (user_id, niche, scenario, funnel_stage, user_message, bot_response, methodology_used, outcome, quality_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, niche[:50], scenario[:50], funnel_stage[:30],
                          user_message[:500], bot_response[:1000], methodology[:50], 
                          outcome[:30], quality_score))
        except Exception as e:
            logger.debug(f"Failed to save successful dialog: {e}")
    
    def get_similar_examples(
        self, scenario: str = "", niche: str = "", limit: int = 2
    ) -> Optional[str]:
        if not DATABASE_URL:
            return None
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if niche and scenario:
                        cur.execute("""
                            SELECT user_message, bot_response, methodology_used, outcome
                            FROM successful_dialogs
                            WHERE niche = %s AND scenario = %s AND quality_score >= 0.7
                            ORDER BY quality_score DESC, created_at DESC
                            LIMIT %s
                        """, (niche, scenario, limit))
                        rows = cur.fetchall()
                        if rows:
                            return self._format_examples(rows, f"нише '{niche}' + сценарию '{scenario}'")
                    
                    if scenario:
                        cur.execute("""
                            SELECT user_message, bot_response, methodology_used, outcome
                            FROM successful_dialogs
                            WHERE scenario = %s AND quality_score >= 0.7
                            ORDER BY quality_score DESC, created_at DESC
                            LIMIT %s
                        """, (scenario, limit))
                        rows = cur.fetchall()
                        if rows:
                            return self._format_examples(rows, f"сценарию '{scenario}'")
                    
                    if niche:
                        cur.execute("""
                            SELECT user_message, bot_response, methodology_used, outcome
                            FROM successful_dialogs
                            WHERE niche = %s AND quality_score >= 0.7
                            ORDER BY quality_score DESC, created_at DESC
                            LIMIT %s
                        """, (niche, limit))
                        rows = cur.fetchall()
                        if rows:
                            return self._format_examples(rows, f"нише '{niche}'")
                    
            return None
        except Exception as e:
            logger.debug(f"Failed to get dialog examples: {e}")
            return None
    
    def _format_examples(self, rows, match_type: str) -> str:
        parts = [f"## УСПЕШНЫЕ ДИАЛОГИ (совпадение по {match_type})"]
        for i, (user_msg, bot_resp, method, outcome) in enumerate(rows, 1):
            parts.append(f"\n### Реальный пример {i} (метод: {method or 'авто'}, результат: {outcome})")
            parts.append(f"Клиент: \"{user_msg[:200]}\"")
            parts.append(f"Алекс: \"{bot_resp[:400]}\"")
        return "\n".join(parts)
    
    def mark_session_successful(self, user_id: int, outcome: str = "conversion"):
        if not DATABASE_URL:
            return
        try:
            from src.session import session_manager
            if user_id in session_manager._sessions:
                session = session_manager._sessions[user_id]
                messages = session.get_history()
                
                pairs = []
                for i in range(len(messages) - 1):
                    if messages[i].get("role") == "user" and messages[i+1].get("role") in ("assistant", "model"):
                        user_msg = ""
                        bot_resp = ""
                        parts = messages[i].get("parts", [])
                        if parts:
                            user_msg = parts[0].get("text", "") if isinstance(parts[0], dict) else str(parts[0])
                        parts_bot = messages[i+1].get("parts", [])
                        if parts_bot:
                            bot_resp = parts_bot[0].get("text", "") if isinstance(parts_bot[0], dict) else str(parts_bot[0])
                        if user_msg and bot_resp and len(bot_resp) > 30:
                            pairs.append((user_msg, bot_resp))
                
                for user_msg, bot_resp in pairs[-3:]:
                    self.save_successful_exchange(
                        user_id=user_id,
                        user_message=user_msg,
                        bot_response=bot_resp,
                        outcome=outcome,
                        quality_score=0.85
                    )
                    
                logger.info(f"Marked {len(pairs[-3:])} exchanges as successful for user {user_id}")
        except Exception as e:
            logger.debug(f"Failed to mark session successful: {e}")

dialog_rag = DialogRAG()
