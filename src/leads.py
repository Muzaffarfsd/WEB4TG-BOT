import os
import time
import logging
import csv
import io
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta
from src.database import get_connection, is_available as db_available, DATABASE_URL
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class LeadStatus(Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"


class LeadPriority(Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"


@dataclass
class Lead:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    phone: Optional[str] = None
    business_type: Optional[str] = None
    budget: Optional[str] = None
    message: Optional[str] = None
    status: LeadStatus = LeadStatus.NEW
    created_at: float = field(default_factory=time.time)
    selected_features: List[str] = field(default_factory=list)
    estimated_cost: int = 0
    id: Optional[int] = None
    priority: LeadPriority = LeadPriority.COLD
    tags: List[str] = field(default_factory=list)
    score: int = 0
    last_activity: Optional[float] = None
    message_count: int = 0


@dataclass
class Message:
    id: Optional[int]
    user_id: int
    role: str
    content: str
    created_at: float


class LeadManager:
    def __init__(self):
        self._manager_chat_id: Optional[int] = None
        self._init_db()
    
    def _get_connection(self):
        return get_connection()
    
    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, leads will not be persisted")
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS leads (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT UNIQUE NOT NULL,
                            username VARCHAR(255),
                            first_name VARCHAR(255),
                            phone VARCHAR(50),
                            business_type VARCHAR(255),
                            budget VARCHAR(100),
                            message TEXT,
                            status VARCHAR(20) DEFAULT 'new',
                            selected_features TEXT[],
                            estimated_cost INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            priority VARCHAR(20) DEFAULT 'cold',
                            tags TEXT[] DEFAULT '{}',
                            score INTEGER DEFAULT 0,
                            last_activity TIMESTAMP,
                            message_count INTEGER DEFAULT 0
                        )
                    """)
                    
                    for col, col_def in [
                        ("priority", "VARCHAR(20) DEFAULT 'cold'"),
                        ("tags", "TEXT[] DEFAULT '{}'"),
                        ("score", "INTEGER DEFAULT 0"),
                        ("last_activity", "TIMESTAMP"),
                        ("message_count", "INTEGER DEFAULT 0")
                    ]:
                        try:
                            cur.execute(f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {col} {col_def}")
                        except Exception:
                            pass
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS conversations (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            role VARCHAR(20) NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS analytics (
                            id SERIAL PRIMARY KEY,
                            event_type VARCHAR(50) NOT NULL,
                            user_id BIGINT,
                            data JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics(event_type)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics(created_at)
                    """)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Failed to init database: {e}")
    
    def set_manager_chat_id(self, chat_id: int) -> None:
        self._manager_chat_id = chat_id
        logger.info(f"Manager chat ID set to {chat_id}")
    
    def get_manager_chat_id(self) -> Optional[int]:
        return self._manager_chat_id
    
    def save_message(self, user_id: int, role: str, content: str) -> None:
        if not DATABASE_URL:
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversations (user_id, role, content)
                        VALUES (%s, %s, %s)
                    """, (user_id, role, content[:10000]))
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
    
    def get_conversation_history(self, user_id: int, limit: int = 50) -> List[Message]:
        if not DATABASE_URL:
            return []
        
        messages = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM conversations 
                        WHERE user_id = %s 
                        ORDER BY created_at DESC 
                        LIMIT %s
                    """, (user_id, limit))
                    for row in cur.fetchall():
                        messages.append(Message(
                            id=row['id'],
                            user_id=row['user_id'],
                            role=row['role'],
                            content=row['content'],
                            created_at=row['created_at'].timestamp() if row['created_at'] else time.time()
                        ))
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
        return list(reversed(messages))
    
    def log_event(self, event_type: str, user_id: Optional[int] = None, data: Optional[Dict] = None) -> None:
        if not DATABASE_URL:
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    import json
                    cur.execute("""
                        INSERT INTO analytics (event_type, user_id, data)
                        VALUES (%s, %s, %s)
                    """, (event_type, user_id, json.dumps(data) if data else None))
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    def create_lead(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> Lead:
        lead = Lead(
            user_id=user_id,
            username=username,
            first_name=first_name
        )
        
        if DATABASE_URL:
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO leads (user_id, username, first_name, status)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (user_id) DO UPDATE SET
                                username = EXCLUDED.username,
                                first_name = EXCLUDED.first_name,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING id
                        """, (user_id, username, first_name, lead.status.value))
                        result = cur.fetchone()
                        if result:
                            lead.id = result[0]
                
                self.log_event("lead_created", user_id, {"username": username})
            except Exception as e:
                logger.error(f"Failed to create lead: {e}")
        
        return lead
    
    def _row_to_lead(self, row: dict) -> Lead:
        priority = LeadPriority.COLD
        try:
            priority = LeadPriority(row.get('priority', 'cold') or 'cold')
        except ValueError:
            pass
        
        return Lead(
            id=row['id'],
            user_id=row['user_id'],
            username=row['username'],
            first_name=row['first_name'],
            phone=row['phone'],
            business_type=row['business_type'],
            budget=row['budget'],
            message=row['message'],
            status=LeadStatus(row['status']),
            selected_features=row['selected_features'] or [],
            estimated_cost=row['estimated_cost'] or 0,
            created_at=row['created_at'].timestamp() if row['created_at'] else time.time(),
            priority=priority,
            tags=row.get('tags') or [],
            score=row.get('score') or 0,
            last_activity=row['last_activity'].timestamp() if row.get('last_activity') else None,
            message_count=row.get('message_count') or 0
        )
    
    def get_lead(self, user_id: int) -> Optional[Lead]:
        if not DATABASE_URL:
            return None
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM leads WHERE user_id = %s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        return self._row_to_lead(row)
        except Exception as e:
            logger.error(f"Failed to get lead: {e}")
        return None
    
    def update_lead(
        self,
        user_id: int,
        phone: Optional[str] = None,
        business_type: Optional[str] = None,
        budget: Optional[str] = None,
        message: Optional[str] = None,
        selected_features: Optional[List[str]] = None,
        estimated_cost: Optional[int] = None,
        status: Optional[LeadStatus] = None,
        priority: Optional[LeadPriority] = None,
        tags: Optional[List[str]] = None,
        score: Optional[int] = None
    ) -> Optional[Lead]:
        if not DATABASE_URL:
            return None
        
        updates = []
        values = []
        
        if phone is not None:
            updates.append("phone = %s")
            values.append(phone)
        if business_type is not None:
            updates.append("business_type = %s")
            values.append(business_type)
        if budget is not None:
            updates.append("budget = %s")
            values.append(budget)
        if message is not None:
            updates.append("message = %s")
            values.append(message)
        if selected_features is not None:
            updates.append("selected_features = %s")
            values.append(selected_features)
        if estimated_cost is not None:
            updates.append("estimated_cost = %s")
            values.append(estimated_cost)
        if status is not None:
            updates.append("status = %s")
            values.append(status.value)
        if priority is not None:
            updates.append("priority = %s")
            values.append(priority.value)
        if tags is not None:
            updates.append("tags = %s")
            values.append(tags)
        if score is not None:
            updates.append("score = %s")
            values.append(score)
        
        if not updates:
            return self.get_lead(user_id)
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE leads SET {', '.join(updates)} WHERE user_id = %s",
                        values
                    )
            return self.get_lead(user_id)
        except Exception as e:
            logger.error(f"Failed to update lead: {e}")
        return None
    
    def format_lead_notification(self, lead: Lead) -> str:
        lines = [
            "🔔 **Новая заявка!**\n",
            f"👤 Имя: {lead.first_name or 'Не указано'}",
            f"📱 Username: @{lead.username}" if lead.username else "📱 Username: Нет",
            f"🆔 ID: {lead.user_id}",
        ]
        
        if lead.phone:
            lines.append(f"📞 Телефон: {lead.phone}")
        if lead.business_type:
            lines.append(f"🏢 Тип бизнеса: {lead.business_type}")
        if lead.budget:
            lines.append(f"💰 Бюджет: {lead.budget}")
        if lead.estimated_cost:
            lines.append(f"📊 Расчёт: {lead.estimated_cost:,}₽".replace(",", " "))
        if lead.selected_features:
            lines.append(f"⚙️ Функции: {', '.join(lead.selected_features)}")
        if lead.message:
            lines.append(f"\n💬 Сообщение:\n{lead.message}")
        
        return "\n".join(lines)
    
    def calculate_score(self, user_id: int) -> int:
        score = 0
        lead = self.get_lead(user_id)
        if not lead:
            return 0
        
        if lead.phone:
            score += 20
        if lead.business_type:
            score += 15
        if lead.budget:
            score += 15
        if lead.estimated_cost > 0:
            score += 10
        if lead.selected_features:
            score += min(len(lead.selected_features) * 5, 20)
        if lead.message_count >= 5:
            score += 10
        elif lead.message_count >= 2:
            score += 5
        
        if lead.last_activity:
            hours_since = (time.time() - lead.last_activity) / 3600
            if hours_since < 24:
                score += 10
            elif hours_since < 72:
                score += 5
        
        return min(score, 100)
    
    def update_activity(self, user_id: int) -> None:
        if not DATABASE_URL:
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        UPDATE leads SET 
                            last_activity = CURRENT_TIMESTAMP,
                            message_count = COALESCE(message_count, 0) + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                        RETURNING *
                    """, (user_id,))
                    row = cur.fetchone()
                    if not row:
                        return
                    
                    lead = self._row_to_lead(row)
                    score = self._calculate_score_from_lead(lead)
                    
                    priority_val = lead.priority.value if lead.priority else "cold"
                    if score >= 50:
                        priority_val = LeadPriority.HOT.value
                    elif score >= 25:
                        priority_val = LeadPriority.WARM.value
                    
                    cur.execute("""
                        UPDATE leads SET score = %s, priority = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                    """, (score, priority_val, user_id))
        except Exception as e:
            logger.error(f"Failed to update activity: {e}")
    
    def _calculate_score_from_lead(self, lead) -> int:
        score = 0
        if lead.phone:
            score += 20
        if lead.business_type:
            score += 15
        if lead.budget:
            score += 15
        if lead.estimated_cost > 0:
            score += 10
        if lead.selected_features:
            score += min(len(lead.selected_features) * 5, 20)
        if lead.message_count >= 5:
            score += 10
        elif lead.message_count >= 2:
            score += 5
        if lead.last_activity:
            hours_since = (time.time() - lead.last_activity) / 3600
            if hours_since < 24:
                score += 10
            elif hours_since < 72:
                score += 5
        return min(score, 100)
    
    def add_tag(self, user_id: int, tag: str) -> Optional[Lead]:
        lead = self.get_lead(user_id)
        if not lead:
            return None
        
        tags = list(lead.tags)
        if tag not in tags:
            tags.append(tag)
            return self.update_lead(user_id, tags=tags)
        return lead
    
    def remove_tag(self, user_id: int, tag: str) -> Optional[Lead]:
        lead = self.get_lead(user_id)
        if not lead:
            return None
        
        tags = [t for t in lead.tags if t != tag]
        return self.update_lead(user_id, tags=tags)
    
    def get_leads_by_priority(self, priority: LeadPriority, limit: int = 50) -> List[Lead]:
        if not DATABASE_URL:
            return []
        
        leads = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM leads WHERE priority = %s ORDER BY score DESC LIMIT %s",
                        (priority.value, limit)
                    )
                    for row in cur.fetchall():
                        leads.append(self._row_to_lead(row))
        except Exception as e:
            logger.error(f"Failed to get leads by priority: {e}")
        return leads
    
    def get_leads_by_tag(self, tag: str, limit: int = 50) -> List[Lead]:
        if not DATABASE_URL:
            return []
        
        leads = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM leads WHERE %s = ANY(tags) ORDER BY score DESC LIMIT %s",
                        (tag, limit)
                    )
                    for row in cur.fetchall():
                        leads.append(self._row_to_lead(row))
        except Exception as e:
            logger.error(f"Failed to get leads by tag: {e}")
        return leads
    
    def get_lead_history(self, user_id: int, limit: int = 100) -> List[Dict]:
        if not DATABASE_URL:
            return []
        
        history = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 'message' as type, role, content, created_at
                        FROM conversations WHERE user_id = %s
                        UNION ALL
                        SELECT 'event' as type, event_type as role, 
                               COALESCE(data::text, '') as content, created_at
                        FROM analytics WHERE user_id = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, user_id, limit))
                    for row in cur.fetchall():
                        history.append({
                            'type': row['type'],
                            'role': row['role'],
                            'content': row['content'][:200] if row['content'] else '',
                            'created_at': row['created_at']
                        })
        except Exception as e:
            logger.error(f"Failed to get lead history: {e}")
        return list(reversed(history))
    
    def get_all_leads(self, limit: int = 100) -> List[Lead]:
        if not DATABASE_URL:
            return []
        
        leads = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM leads ORDER BY score DESC, created_at DESC LIMIT %s", (limit,))
                    for row in cur.fetchall():
                        leads.append(self._row_to_lead(row))
        except Exception as e:
            logger.error(f"Failed to get leads: {e}")
        return leads
    
    def get_stats(self) -> Dict:
        if not DATABASE_URL:
            return {"total": 0, "new": 0, "contacted": 0, "qualified": 0, "converted": 0}
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE status = 'new') as new,
                            COUNT(*) FILTER (WHERE status = 'contacted') as contacted,
                            COUNT(*) FILTER (WHERE status = 'qualified') as qualified,
                            COUNT(*) FILTER (WHERE status = 'converted') as converted
                        FROM leads
                    """)
                    row = cur.fetchone()
                    return dict(row) if row else {"total": 0, "new": 0, "contacted": 0, "qualified": 0, "converted": 0}
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
        return {"total": 0, "new": 0, "contacted": 0, "qualified": 0, "converted": 0}
    
    def get_analytics_stats(self) -> Dict:
        if not DATABASE_URL:
            return {}
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) FILTER (WHERE event_type = 'message') as total_messages,
                            COUNT(*) FILTER (WHERE event_type = 'voice_message') as voice_messages,
                            COUNT(*) FILTER (WHERE event_type = 'calculator_used') as calculator_uses,
                            COUNT(*) FILTER (WHERE event_type = 'lead_created') as leads_created,
                            COUNT(DISTINCT user_id) as unique_users
                        FROM analytics
                    """)
                    row = cur.fetchone()
                    
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as today_users
                        FROM analytics 
                        WHERE created_at >= CURRENT_DATE
                    """)
                    today = cur.fetchone()
                    
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as week_users
                        FROM analytics 
                        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                    """)
                    week = cur.fetchone()
                    
                    result = dict(row) if row else {}
                    result['today_users'] = today['today_users'] if today else 0
                    result['week_users'] = week['week_users'] if week else 0
                    return result
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
        return {}
    
    def get_popular_topics(self, limit: int = 10) -> List[Dict]:
        if not DATABASE_URL:
            return []
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT data->>'topic' as topic, COUNT(*) as count
                        FROM analytics 
                        WHERE event_type = 'message' AND data->>'topic' IS NOT NULL
                        GROUP BY data->>'topic'
                        ORDER BY count DESC
                        LIMIT %s
                    """, (limit,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get popular topics: {e}")
        return []
    
    def export_leads_csv(self) -> str:
        leads = self.get_all_leads(limit=1000)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'ID', 'User ID', 'Username', 'Имя', 'Телефон', 
            'Тип бизнеса', 'Бюджет', 'Расчёт', 'Статус', 
            'Функции', 'Сообщение', 'Дата создания'
        ])
        
        for lead in leads:
            writer.writerow([
                lead.id,
                lead.user_id,
                f"@{lead.username}" if lead.username else "",
                lead.first_name or "",
                lead.phone or "",
                lead.business_type or "",
                lead.budget or "",
                lead.estimated_cost,
                lead.status.value,
                ", ".join(lead.selected_features),
                lead.message or "",
                datetime.fromtimestamp(lead.created_at).strftime("%Y-%m-%d %H:%M")
            ])
        
        return output.getvalue()


lead_manager = LeadManager()
