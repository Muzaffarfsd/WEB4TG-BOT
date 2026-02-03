import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


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


class LeadManager:
    def __init__(self):
        self._leads: Dict[int, Lead] = {}
        self._manager_chat_id: Optional[int] = None
    
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
        self._leads[user_id] = lead
        return lead
    
    def get_lead(self, user_id: int) -> Optional[Lead]:
        return self._leads.get(user_id)
    
    def update_lead(
        self,
        user_id: int,
        phone: Optional[str] = None,
        business_type: Optional[str] = None,
        budget: Optional[str] = None,
        message: Optional[str] = None,
        selected_features: Optional[List[str]] = None,
        estimated_cost: Optional[int] = None
    ) -> Optional[Lead]:
        lead = self._leads.get(user_id)
        if lead:
            if phone:
                lead.phone = phone
            if business_type:
                lead.business_type = business_type
            if budget:
                lead.budget = budget
            if message:
                lead.message = message
            if selected_features:
                lead.selected_features = selected_features
            if estimated_cost:
                lead.estimated_cost = estimated_cost
        return lead
    
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
        return list(self._leads.values())
    
    def get_stats(self) -> Dict:
        leads = self.get_all_leads()
        return {
            "total": len(leads),
            "new": len([l for l in leads if l.status == LeadStatus.NEW]),
            "contacted": len([l for l in leads if l.status == LeadStatus.CONTACTED]),
            "qualified": len([l for l in leads if l.status == LeadStatus.QUALIFIED]),
            "converted": len([l for l in leads if l.status == LeadStatus.CONVERTED]),
        }


lead_manager = LeadManager()
