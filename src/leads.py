import os
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")


class LeadStatus(Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"


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


class LeadManager:
    def __init__(self):
        self._manager_chat_id: Optional[int] = None
        self._init_db()
    
    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)
    
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
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    conn.commit()
            logger.info("Leads table initialized")
        except Exception as e:
            logger.error(f"Failed to init leads table: {e}")
    
    def set_manager_chat_id(self, chat_id: int) -> None:
        self._manager_chat_id = chat_id
        logger.info(f"Manager chat ID set to {chat_id}")
    
    def get_manager_chat_id(self) -> Optional[int]:
        return self._manager_chat_id
    
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
                        conn.commit()
            except Exception as e:
                logger.error(f"Failed to create lead: {e}")
        
        return lead
    
    def get_lead(self, user_id: int) -> Optional[Lead]:
        if not DATABASE_URL:
            return None
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM leads WHERE user_id = %s", (user_id,))
                    row = cur.fetchone()
                    if row:
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
                            created_at=row['created_at'].timestamp() if row['created_at'] else time.time()
                        )
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
        status: Optional[LeadStatus] = None
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
                    conn.commit()
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
    
    def get_all_leads(self) -> List[Lead]:
        if not DATABASE_URL:
            return []
        
        leads = []
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM leads ORDER BY created_at DESC")
                    for row in cur.fetchall():
                        leads.append(Lead(
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
                            created_at=row['created_at'].timestamp() if row['created_at'] else time.time()
                        ))
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


lead_manager = LeadManager()
