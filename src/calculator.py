from dataclasses import dataclass, field
from typing import Dict, Set


FEATURES = {
    "catalog": {"name": "Каталог", "price": 25000},
    "cart": {"name": "Корзина", "price": 20000},
    "auth": {"name": "Авторизация", "price": 15000},
    "search": {"name": "Поиск", "price": 20000},
    "favorites": {"name": "Избранное", "price": 12000},
    "reviews": {"name": "Отзывы", "price": 25000},
    "payments": {"name": "Приём платежей", "price": 45000},
    "subscriptions": {"name": "Подписки", "price": 55000},
    "installments": {"name": "Рассрочка", "price": 35000},
    "delivery": {"name": "Доставка", "price": 30000},
    "pickup": {"name": "Самовывоз", "price": 35000},
    "express": {"name": "Экспресс-доставка", "price": 25000},
    "push": {"name": "Push-уведомления", "price": 25000},
    "chat": {"name": "Чат поддержки", "price": 45000},
    "video": {"name": "Видеозвонки", "price": 60000},
    "loyalty": {"name": "Программа лояльности", "price": 65000},
    "promo": {"name": "Промокоды", "price": 30000},
    "referral": {"name": "Реферальная система", "price": 55000},
    "analytics": {"name": "Аналитика", "price": 45000},
    "admin": {"name": "Админ-панель", "price": 75000},
    "crm": {"name": "CRM-система", "price": 120000},
    "progress": {"name": "Трекинг прогресса", "price": 45000},
    "booking": {"name": "Система бронирования", "price": 55000},
    "queue": {"name": "Управление очередями", "price": 45000},
    "calendar": {"name": "Синхронизация календаря", "price": 30000},
    "ai": {"name": "AI чат-бот", "price": 49000},
    "ai_rec": {"name": "AI-рекомендации", "price": 55000},
    "auto_reply": {"name": "Автоответы", "price": 25000},
    "smart_search": {"name": "Умный поиск", "price": 35000},
    "voice": {"name": "Голосовой ассистент", "price": 75000},
    "tg_bot": {"name": "Telegram бот", "price": 35000},
    "whatsapp": {"name": "WhatsApp", "price": 45000},
    "maps": {"name": "Google Maps", "price": 20000},
    "sms": {"name": "SMS-уведомления", "price": 25000},
    "email": {"name": "Email-маркетинг", "price": 30000},
    "1c": {"name": "1С интеграция", "price": 85000},
    "api": {"name": "API доступ", "price": 55000},
}


@dataclass
class UserCalculation:
    selected_features: Set[str] = field(default_factory=set)
    
    def add_feature(self, feature_id: str) -> bool:
        if feature_id in FEATURES:
            if feature_id in self.selected_features:
                self.selected_features.remove(feature_id)
                return False
            else:
                self.selected_features.add(feature_id)
                return True
        return False
    
    def remove_feature(self, feature_id: str) -> None:
        self.selected_features.discard(feature_id)
    
    def reset(self) -> None:
        self.selected_features.clear()
    
    def get_total(self) -> int:
        return sum(FEATURES[f]["price"] for f in self.selected_features if f in FEATURES)
    
    def get_summary(self) -> str:
        if not self.selected_features:
            return "Пока ничего не выбрано. Нажмите на функции для добавления."
        
        lines = ["**Выбранные функции:**\n"]
        for feature_id in sorted(self.selected_features):
            if feature_id in FEATURES:
                f = FEATURES[feature_id]
                lines.append(f"✓ {f['name']} — {f['price']:,}₽".replace(",", " "))
        
        total = self.get_total()
        lines.append(f"\n**Итого: {total:,}₽**".replace(",", " "))
        
        prepay = int(total * 0.35)
        final = total - prepay
        lines.append(f"\nПредоплата 35%: {prepay:,}₽".replace(",", " "))
        lines.append(f"После сдачи 65%: {final:,}₽".replace(",", " "))
        
        return "\n".join(lines)


class CalculatorManager:
    def __init__(self):
        self._calculations: Dict[int, UserCalculation] = {}
    
    def get_calculation(self, user_id: int) -> UserCalculation:
        if user_id not in self._calculations:
            self._calculations[user_id] = UserCalculation()
        return self._calculations[user_id]
    
    def reset_calculation(self, user_id: int) -> None:
        if user_id in self._calculations:
            self._calculations[user_id].reset()


calculator_manager = CalculatorManager()
