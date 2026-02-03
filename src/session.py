import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import OrderedDict


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class UserSession:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    messages: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    
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
            self.messages = self.messages[-max_history:]
        
        self.last_activity = time.time()
        self.message_count += 1
    
    def get_history(self) -> List[Dict]:
        return self.messages.copy()
    
    def clear_history(self) -> None:
        self.messages = []
        self.last_activity = time.time()


class SessionManager:
    def __init__(self, max_sessions: int = 10000, session_ttl: int = 86400):
        self._sessions: OrderedDict[int, UserSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl
    
    def get_session(self, user_id: int, username: Optional[str] = None, 
                    first_name: Optional[str] = None) -> UserSession:
        self._cleanup_expired()
        
        if user_id in self._sessions:
            session = self._sessions[user_id]
            session.last_activity = time.time()
            self._sessions.move_to_end(user_id)
            return session
        
        session = UserSession(
            user_id=user_id,
            username=username,
            first_name=first_name
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
