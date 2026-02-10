import logging
import re
from datetime import datetime
from typing import Optional

from src.database import execute_query, execute_one

logger = logging.getLogger(__name__)


class PromoCodeManager:
    def __init__(self):
        self.init_tables()

    def init_tables(self):
        try:
            execute_query("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(30) UNIQUE NOT NULL,
                    discount_percent INTEGER NOT NULL,
                    max_uses INTEGER DEFAULT NULL,
                    current_uses INTEGER DEFAULT 0,
                    valid_from TIMESTAMP DEFAULT NOW(),
                    valid_until TIMESTAMP DEFAULT NULL,
                    created_by BIGINT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    description TEXT
                )
            """)
            execute_query("""
                CREATE TABLE IF NOT EXISTS promocode_uses (
                    id SERIAL PRIMARY KEY,
                    promocode_id INTEGER REFERENCES promocodes(id),
                    user_id BIGINT NOT NULL,
                    used_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(promocode_id, user_id)
                )
            """)
            logger.info("Promocode tables initialized")
        except Exception as e:
            logger.error(f"Failed to init promocode tables: {e}")

    def _validate_code(self, code: str) -> bool:
        return bool(re.match(r'^[A-Z0-9]{4,20}$', code))

    def create_promo(self, code: str, discount_percent: int, max_uses: Optional[int] = None,
                     valid_until: Optional[datetime] = None, created_by: Optional[int] = None,
                     description: Optional[str] = None) -> Optional[dict]:
        code = code.upper().strip()
        if not self._validate_code(code):
            logger.warning(f"Invalid promo code format: {code}")
            return None
        if not 1 <= discount_percent <= 50:
            logger.warning(f"Invalid discount percent: {discount_percent}")
            return None

        try:
            result = execute_one(
                """INSERT INTO promocodes (code, discount_percent, max_uses, valid_until, created_by, description)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, code, discount_percent, max_uses, created_at""",
                (code, discount_percent, max_uses, valid_until, created_by, description),
                dict_cursor=True
            )
            logger.info(f"Promo code created: {code} ({discount_percent}%)")
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to create promo code {code}: {e}")
            return None

    def activate_promo(self, user_id: int, code: str) -> dict:
        code = code.upper().strip()
        if not self._validate_code(code):
            return {"success": False, "message": "❌ Неверный формат промокода", "discount": None}

        try:
            promo = execute_one(
                "SELECT * FROM promocodes WHERE code = %s",
                (code,), dict_cursor=True
            )
            if not promo:
                return {"success": False, "message": "❌ Промокод не найден", "discount": None}

            if not promo['is_active']:
                return {"success": False, "message": "❌ Промокод деактивирован", "discount": None}

            if promo['valid_until'] and promo['valid_until'] < datetime.now():
                return {"success": False, "message": "❌ Срок действия промокода истёк", "discount": None}

            if promo['max_uses'] is not None and promo['current_uses'] >= promo['max_uses']:
                return {"success": False, "message": "❌ Промокод исчерпан", "discount": None}

            existing = execute_one(
                "SELECT id FROM promocode_uses WHERE promocode_id = %s AND user_id = %s",
                (promo['id'], user_id)
            )
            if existing:
                return {"success": False, "message": "❌ Вы уже использовали этот промокод", "discount": None}

            execute_query(
                "INSERT INTO promocode_uses (promocode_id, user_id) VALUES (%s, %s)",
                (promo['id'], user_id)
            )
            execute_query(
                "UPDATE promocodes SET current_uses = current_uses + 1 WHERE id = %s",
                (promo['id'],)
            )
            logger.info(f"User {user_id} activated promo {code} ({promo['discount_percent']}%)")
            return {
                "success": True,
                "message": f"✅ Промокод {code} активирован! Скидка: {promo['discount_percent']}%",
                "discount": promo['discount_percent']
            }
        except Exception as e:
            logger.error(f"Failed to activate promo {code} for user {user_id}: {e}")
            return {"success": False, "message": "❌ Ошибка при активации промокода", "discount": None}

    def get_user_active_promo(self, user_id: int) -> Optional[dict]:
        try:
            result = execute_one(
                """SELECT p.code, p.discount_percent, p.description, pu.used_at
                   FROM promocode_uses pu
                   JOIN promocodes p ON p.id = pu.promocode_id
                   WHERE pu.user_id = %s AND p.is_active = TRUE
                     AND (p.valid_until IS NULL OR p.valid_until > NOW())
                   ORDER BY p.discount_percent DESC
                   LIMIT 1""",
                (user_id,), dict_cursor=True
            )
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get active promo for user {user_id}: {e}")
            return None

    def get_all_promos(self, active_only: bool = True) -> list:
        try:
            if active_only:
                query = "SELECT * FROM promocodes WHERE is_active = TRUE ORDER BY created_at DESC"
            else:
                query = "SELECT * FROM promocodes ORDER BY created_at DESC"
            results = execute_query(query, fetch=True, dict_cursor=True)
            return [dict(r) for r in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get promos: {e}")
            return []

    def deactivate_promo(self, code: str) -> bool:
        code = code.upper().strip()
        try:
            result = execute_one(
                "UPDATE promocodes SET is_active = FALSE WHERE code = %s RETURNING id",
                (code,)
            )
            if result:
                logger.info(f"Promo code deactivated: {code}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to deactivate promo {code}: {e}")
            return False

    def format_promo_stats(self) -> str:
        promos = self.get_all_promos(active_only=False)
        if not promos:
            return "📊 Промокодов пока нет"

        lines = ["📊 <b>Промокоды:</b>\n"]
        for p in promos:
            status = "✅" if p['is_active'] else "❌"
            uses = f"{p['current_uses']}"
            if p['max_uses']:
                uses += f"/{p['max_uses']}"
            expiry = ""
            if p['valid_until']:
                expiry = f" | до {p['valid_until'].strftime('%d.%m.%Y')}"
            desc = f" — {p['description']}" if p.get('description') else ""
            lines.append(f"{status} <code>{p['code']}</code> — {p['discount_percent']}% | "
                         f"Использований: {uses}{expiry}{desc}")

        return "\n".join(lines)


try:
    promo_manager = PromoCodeManager()
except Exception as e:
    logger.error(f"Failed to initialize PromoCodeManager: {e}")
    promo_manager = None
