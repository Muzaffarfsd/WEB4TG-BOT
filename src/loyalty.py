import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")

REVIEW_REWARDS = {
    "video": 500,
    "text_photo": 200,
}

RETURNING_CUSTOMER_BONUS = 5

PACKAGE_DEALS = {
    "app_subscription_3": {
        "name": "Приложение + Подписка 3 мес",
        "discount": 5,
        "description": "Скидка 5% при заказе приложения с подпиской на 3 месяца",
    },
    "app_subscription_6": {
        "name": "Приложение + Подписка 6 мес",
        "discount": 10,
        "description": "Скидка 10% при заказе приложения с подпиской на 6 месяцев",
    },
    "app_subscription_12": {
        "name": "Приложение + Подписка 12 мес",
        "discount": 15,
        "description": "Скидка 15% при заказе приложения с подпиской на год",
    },
}


class ReviewType(Enum):
    VIDEO = "video"
    TEXT_PHOTO = "text_photo"


class ReviewStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Review:
    id: int
    user_id: int
    review_type: str
    status: str
    content_url: Optional[str]
    comment: Optional[str]
    coins_awarded: int
    created_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[int]


@dataclass 
class CustomerOrder:
    id: int
    user_id: int
    order_type: str
    amount: int
    package_deal: Optional[str]
    discount_applied: int
    created_at: datetime
    completed_at: Optional[datetime]
    status: str


class LoyaltySystem:
    def __init__(self):
        self._init_db()
    
    def _get_connection(self):
        if not DATABASE_URL:
            raise Exception("DATABASE_URL not configured")
        return psycopg2.connect(DATABASE_URL)
    
    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, loyalty system disabled")
            return
        
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customer_reviews (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    review_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    content_url TEXT,
                    comment TEXT,
                    coins_awarded INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by BIGINT
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customer_orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    order_type VARCHAR(50) NOT NULL,
                    amount INTEGER NOT NULL,
                    package_deal VARCHAR(50),
                    discount_applied INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'pending'
                )
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_user_id 
                ON customer_reviews(user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_status 
                ON customer_reviews(status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_user_id 
                ON customer_orders(user_id)
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Loyalty system tables initialized")
        except Exception as e:
            logger.error(f"Failed to init loyalty tables: {e}")
    
    def submit_review(self, user_id: int, review_type: str, 
                      content_url: str = None, comment: str = None) -> Optional[int]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id FROM customer_reviews 
                WHERE user_id = %s AND review_type = %s AND status != 'rejected'
            """, (user_id, review_type))
            
            if cur.fetchone():
                cur.close()
                conn.close()
                return None
            
            cur.execute("""
                INSERT INTO customer_reviews (user_id, review_type, content_url, comment)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (user_id, review_type, content_url, comment))
            
            review_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            return review_id
        except Exception as e:
            logger.error(f"Failed to submit review: {e}")
            return None
    
    def approve_review(self, review_id: int, manager_id: int) -> Optional[int]:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT user_id, review_type, status FROM customer_reviews 
                WHERE id = %s
            """, (review_id,))
            
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return None
            
            user_id, review_type, status = row
            
            if status != 'pending':
                cur.close()
                conn.close()
                return None
            
            coins = REVIEW_REWARDS.get(review_type, 0)
            
            cur.execute("""
                UPDATE customer_reviews 
                SET status = 'approved', 
                    coins_awarded = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by = %s
                WHERE id = %s
            """, (coins, manager_id, review_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return coins
        except Exception as e:
            logger.error(f"Failed to approve review: {e}")
            return None
    
    def reject_review(self, review_id: int, manager_id: int) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE customer_reviews 
                SET status = 'rejected',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by = %s
                WHERE id = %s AND status = 'pending'
            """, (manager_id, review_id))
            
            affected = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return affected > 0
        except Exception as e:
            logger.error(f"Failed to reject review: {e}")
            return False
    
    def get_pending_reviews(self) -> List[Review]:
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM customer_reviews 
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            return [Review(**row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get pending reviews: {e}")
            return []
    
    def get_user_reviews(self, user_id: int) -> List[Review]:
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM customer_reviews 
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            return [Review(**row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get user reviews: {e}")
            return []
    
    def create_order(self, user_id: int, order_type: str, amount: int,
                     package_deal: str = None) -> Optional[int]:
        try:
            discount = 0
            if package_deal and package_deal in PACKAGE_DEALS:
                discount = PACKAGE_DEALS[package_deal]["discount"]
            
            if self.is_returning_customer(user_id):
                discount += RETURNING_CUSTOMER_BONUS
            
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO customer_orders 
                (user_id, order_type, amount, package_deal, discount_applied)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, order_type, amount, package_deal, discount))
            
            order_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            return order_id
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return None
    
    def complete_order(self, order_id: int) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE customer_orders 
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (order_id,))
            
            affected = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            return affected > 0
        except Exception as e:
            logger.error(f"Failed to complete order: {e}")
            return False
    
    def is_returning_customer(self, user_id: int) -> bool:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) FROM customer_orders 
                WHERE user_id = %s AND status = 'completed'
            """, (user_id,))
            
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check returning customer: {e}")
            return False
    
    def get_customer_orders(self, user_id: int) -> List[CustomerOrder]:
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM customer_orders 
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            return [CustomerOrder(**row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get customer orders: {e}")
            return []
    
    def calculate_total_discount(self, user_id: int, base_discount: int = 0,
                                  package_deal: str = None) -> dict:
        discounts = {
            "base_discount": base_discount,
            "returning_bonus": 0,
            "package_discount": 0,
            "total": base_discount,
        }
        
        if self.is_returning_customer(user_id):
            discounts["returning_bonus"] = RETURNING_CUSTOMER_BONUS
        
        if package_deal and package_deal in PACKAGE_DEALS:
            discounts["package_discount"] = PACKAGE_DEALS[package_deal]["discount"]
        
        discounts["total"] = min(
            discounts["base_discount"] + 
            discounts["returning_bonus"] + 
            discounts["package_discount"],
            30
        )
        
        return discounts
    
    def get_loyalty_stats(self) -> dict:
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM customer_reviews WHERE status = 'approved'")
            approved_reviews = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM customer_reviews WHERE status = 'pending'")
            pending_reviews = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM customer_orders WHERE status = 'completed'")
            completed_orders = cur.fetchone()[0]
            
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) FROM customer_orders 
                WHERE status = 'completed'
                GROUP BY user_id HAVING COUNT(*) > 1
            """)
            returning_customers = len(cur.fetchall())
            
            cur.close()
            conn.close()
            
            return {
                "approved_reviews": approved_reviews,
                "pending_reviews": pending_reviews,
                "completed_orders": completed_orders,
                "returning_customers": returning_customers,
            }
        except Exception as e:
            logger.error(f"Failed to get loyalty stats: {e}")
            return {}


def format_review_notification(review: Review, username: str = None) -> str:
    type_names = {
        "video": "Видео-отзыв",
        "text_photo": "Текст + фото",
    }
    coins = REVIEW_REWARDS.get(review.review_type, 0)
    
    text = f"""🎬 <b>Новый отзыв на модерацию</b>

👤 Пользователь: {username or f'ID {review.user_id}'}
📝 Тип: {type_names.get(review.review_type, review.review_type)}
💰 Награда: {coins} монет

"""
    if review.content_url:
        text += f"🔗 Ссылка: {review.content_url}\n"
    if review.comment:
        text += f"💬 Комментарий: {review.comment}\n"
    
    text += f"\n📅 Отправлен: {review.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    return text


def format_package_deals() -> str:
    text = "📦 <b>Пакетные предложения</b>\n\n"
    text += "Закажите приложение вместе с подпиской и получите дополнительную скидку:\n\n"
    
    for deal_id, deal in PACKAGE_DEALS.items():
        text += f"🎁 <b>{deal['name']}</b>\n"
        text += f"   Скидка: <b>{deal['discount']}%</b>\n"
        text += f"   {deal['description']}\n\n"
    
    text += "💡 <i>Скидки суммируются с бонусом постоянного клиента (+5%)</i>"
    
    return text


def format_returning_customer_info() -> str:
    return f"""🔄 <b>Бонус постоянного клиента</b>

Уже заказывали у нас? Получите дополнительную скидку <b>+{RETURNING_CUSTOMER_BONUS}%</b> на следующий заказ!

✅ Автоматически применяется к каждому новому заказу
✅ Суммируется с другими скидками
✅ Действует бессрочно

💡 <i>Максимальная суммарная скидка — 30%</i>"""


def format_review_bonus_info() -> str:
    return f"""⭐ <b>Бонус за отзыв</b>

Поделитесь впечатлениями о работе с WEB4TG Studio и получите монеты:

🎬 <b>Видео-отзыв</b> — <b>{REVIEW_REWARDS['video']} монет</b>
   Запишите короткое видео (30 сек - 2 мин)
   
📝 <b>Текст + скриншот</b> — <b>{REVIEW_REWARDS['text_photo']} монет</b>
   Напишите отзыв и приложите скрин приложения

💡 <i>Отзывы проверяются менеджером перед начислением</i>

Готовы оставить отзыв? Выберите тип:"""
