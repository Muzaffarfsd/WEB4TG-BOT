import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

DATABASE_URL = None
try:
    import os
    DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")
except Exception:
    pass


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


SUMMARIZATION_THRESHOLD = 20
KEEP_RECENT = 10


@dataclass
class UserSession:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    messages: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    _loaded_from_db: bool = False
    _summary: Optional[str] = None
    _needs_summarization: bool = False
    
    def add_message(self, role: str, content: str, max_history: int = 30) -> None:
        if role == "user":
            self.messages.append({
                "role": "user",
                "parts": [{"text": content}]
            })
        else:
            self.messages.append({
                "role": "model",
                "parts": [{"text": content}]
            })
        
        if len(self.messages) > max_history:
            if len(self.messages) >= SUMMARIZATION_THRESHOLD and not self._needs_summarization:
                self._needs_summarization = True
            self.messages = self.messages[-max_history:]
        
        self.last_activity = time.time()
        self.message_count += 1

        _save_message_to_db(self.user_id, role, content)
    
    def get_history(self) -> List[Dict]:
        result = []
        if self._summary:
            result.append({
                "role": "user",
                "parts": [{"text": f"[РЕЗЮМЕ ПРЕДЫДУЩЕГО ДИАЛОГА]\n{self._summary}"}]
            })
            result.append({
                "role": "model",
                "parts": [{"text": "Понял контекст из предыдущего диалога, продолжаю."}]
            })
        result.extend(self.messages)
        return result
    
    def set_summary(self, summary: str) -> None:
        self._summary = summary
        self._needs_summarization = False
        _save_summary_to_db(self.user_id, summary)
    
    def clear_history(self) -> None:
        self.messages = []
        self._summary = None
        self._needs_summarization = False
        self.last_activity = time.time()
        _clear_history_db(self.user_id)


def _save_message_to_db(user_id: int, role: str, content: str):
    if not DATABASE_URL:
        return
    try:
        from src.database import execute_query
        execute_query(
            "INSERT INTO conversation_history (telegram_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content)
        )
    except Exception as e:
        logger.debug(f"Failed to save message to DB: {e}")


def _clear_history_db(user_id: int):
    if not DATABASE_URL:
        return
    try:
        from src.database import execute_query
        execute_query("DELETE FROM conversation_history WHERE telegram_id = %s", (user_id,))
    except Exception as e:
        logger.debug(f"Failed to clear history from DB: {e}")


def _save_summary_to_db(user_id: int, summary: str):
    if not DATABASE_URL:
        return
    try:
        from src.database import execute_query
        execute_query(
            """INSERT INTO conversation_summaries (telegram_id, summary)
               VALUES (%s, %s)
               ON CONFLICT (telegram_id) DO UPDATE SET summary = %s, updated_at = NOW()""",
            (user_id, summary, summary)
        )
    except Exception as e:
        logger.debug(f"Failed to save summary to DB: {e}")


def _load_summary_from_db(user_id: int) -> Optional[str]:
    if not DATABASE_URL:
        return None
    try:
        from src.database import execute_one
        row = execute_one(
            "SELECT summary FROM conversation_summaries WHERE telegram_id = %s",
            (user_id,), dict_cursor=True
        )
        if row:
            return row["summary"]
    except Exception as e:
        logger.debug(f"Failed to load summary from DB: {e}")
    return None


def _load_history_from_db(user_id: int, limit: int = 20) -> List[Dict]:
    if not DATABASE_URL:
        return []
    try:
        from src.database import execute_query
        rows = execute_query(
            """SELECT role, content FROM conversation_history 
               WHERE telegram_id = %s 
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit),
            fetch=True, dict_cursor=True
        )
        if not rows:
            return []
        
        messages = []
        for row in reversed(rows):
            gemini_role = "user" if row["role"] == "user" else "model"
            messages.append({
                "role": gemini_role,
                "parts": [{"text": row["content"]}]
            })
        return messages
    except Exception as e:
        logger.debug(f"Failed to load history from DB: {e}")
        return []


def _init_conversation_table():
    if not DATABASE_URL:
        return
    try:
        from src.database import execute_query
        execute_query("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        execute_query(
            "CREATE INDEX IF NOT EXISTS idx_conv_history_tid ON conversation_history(telegram_id)"
        )
        execute_query("""
            DELETE FROM conversation_history 
            WHERE created_at < NOW() - INTERVAL '7 days'
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                telegram_id BIGINT PRIMARY KEY,
                summary TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("Conversation history + summaries tables initialized")
    except Exception as e:
        logger.warning(f"Failed to init conversation_history table: {e}")


class SessionManager:
    def __init__(self, max_sessions: int = 10000, session_ttl: int = 86400):
        self._sessions: OrderedDict[int, UserSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl
        _init_conversation_table()
    
    def get_session(self, user_id: int, username: Optional[str] = None, 
                    first_name: Optional[str] = None) -> UserSession:
        self._cleanup_expired()
        
        if user_id in self._sessions:
            session = self._sessions[user_id]
            session.last_activity = time.time()
            self._sessions.move_to_end(user_id)
            return session
        
        db_messages = _load_history_from_db(user_id)
        db_summary = _load_summary_from_db(user_id)
        
        session = UserSession(
            user_id=user_id,
            username=username,
            first_name=first_name,
            messages=db_messages,
            _loaded_from_db=bool(db_messages),
            _summary=db_summary
        )
        self._sessions[user_id] = session
        
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)
        
        return session
    
    def clear_session(self, user_id: int) -> None:
        if user_id in self._sessions:
            self._sessions[user_id].clear_history()
    
    def _cleanup_expired(self) -> None:
        current_time = time.time()
        expired = [
            uid for uid, session in self._sessions.items()
            if current_time - session.last_activity > self._session_ttl
        ]
        for uid in expired:
            del self._sessions[uid]
    
    def get_stats(self) -> Dict:
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions
        }


session_manager = SessionManager()
