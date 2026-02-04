import os
import logging
import secrets
import string
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")

REFERRER_REWARD = 200
REFERRED_REWARD = 50


class ReferralTier(Enum):
    BRONZE = "Bronze"
    SILVER = "Silver"
    GOLD = "Gold"
    PLATINUM = "Platinum"


TIER_THRESHOLDS = {
    ReferralTier.BRONZE: (0, 10),
    ReferralTier.SILVER: (10, 15),
    ReferralTier.GOLD: (30, 20),
    ReferralTier.PLATINUM: (100, 30),
}


def calculate_tier(total_referrals: int) -> ReferralTier:
    if total_referrals >= 100:
        return ReferralTier.PLATINUM
    elif total_referrals >= 30:
        return ReferralTier.GOLD
    elif total_referrals >= 10:
        return ReferralTier.SILVER
    return ReferralTier.BRONZE


def get_tier_commission(tier: ReferralTier) -> int:
    commissions = {
        ReferralTier.BRONZE: 10,
        ReferralTier.SILVER: 15,
        ReferralTier.GOLD: 20,
        ReferralTier.PLATINUM: 30,
    }
    return commissions.get(tier, 10)


def generate_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(6))
    return f"WEB4TG{random_part}"


@dataclass
class ReferralStats:
    telegram_id: int
    referral_code: str
    referred_by_code: Optional[str] = None
    total_referrals: int = 0
    active_referrals: int = 0
    tier: ReferralTier = ReferralTier.BRONZE
    total_earnings: int = 0
    
    def get_tier_emoji(self) -> str:
        emojis = {
            ReferralTier.BRONZE: "🥉",
            ReferralTier.SILVER: "🥈",
            ReferralTier.GOLD: "🥇",
            ReferralTier.PLATINUM: "💎",
        }
        return emojis.get(self.tier, "🥉")
    
    def get_next_tier_info(self) -> Optional[tuple]:
        if self.tier == ReferralTier.PLATINUM:
            return None
        
        next_tiers = {
            ReferralTier.BRONZE: (10, ReferralTier.SILVER),
            ReferralTier.SILVER: (30, ReferralTier.GOLD),
            ReferralTier.GOLD: (100, ReferralTier.PLATINUM),
        }
        
        if self.tier in next_tiers:
            needed, next_tier = next_tiers[self.tier]
            remaining = needed - self.total_referrals
            return (remaining, next_tier)
        return None


@dataclass
class Referral:
    id: int
    referrer_telegram_id: int
    referred_telegram_id: int
    referred_username: Optional[str]
    referred_first_name: Optional[str]
    bonus_amount: int
    status: str
    created_at: datetime


class ReferralManager:
    def __init__(self):
        self._init_db()
    
    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)
    
    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, referral program will not work")
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS referral_users (
                            telegram_id BIGINT PRIMARY KEY,
                            username VARCHAR(255),
                            first_name VARCHAR(255),
                            referral_code VARCHAR(50) UNIQUE NOT NULL,
                            referred_by_code VARCHAR(50),
                            total_referrals INTEGER DEFAULT 0,
                            active_referrals INTEGER DEFAULT 0,
                            tier VARCHAR(50) DEFAULT 'Bronze',
                            total_earnings INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS referrals (
                            id SERIAL PRIMARY KEY,
                            referrer_telegram_id BIGINT NOT NULL,
                            referred_telegram_id BIGINT NOT NULL,
                            bonus_amount INTEGER DEFAULT 100,
                            status VARCHAR(50) DEFAULT 'active',
                            created_at TIMESTAMP DEFAULT NOW(),
                            UNIQUE(referrer_telegram_id, referred_telegram_id)
                        )
                    """)
                    
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_referral_users_code ON referral_users(referral_code)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_telegram_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_telegram_id)")
                    
                    conn.commit()
                    logger.info("Referral tables initialized")
        except Exception as e:
            logger.error(f"Failed to init referral tables: {e}")
    
    def get_or_create_user(self, telegram_id: int, username: Optional[str] = None, 
                           first_name: Optional[str] = None) -> ReferralStats:
        if not DATABASE_URL:
            return ReferralStats(telegram_id=telegram_id, referral_code=generate_referral_code())
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM referral_users WHERE telegram_id = %s", (telegram_id,))
                    row = cur.fetchone()
                    
                    if row:
                        return ReferralStats(
                            telegram_id=row["telegram_id"],
                            referral_code=row["referral_code"],
                            referred_by_code=row["referred_by_code"],
                            total_referrals=row["total_referrals"],
                            active_referrals=row["active_referrals"],
                            tier=ReferralTier(row["tier"]),
                            total_earnings=row["total_earnings"]
                        )
                    
                    referral_code = generate_referral_code()
                    while True:
                        cur.execute("SELECT 1 FROM referral_users WHERE referral_code = %s", (referral_code,))
                        if not cur.fetchone():
                            break
                        referral_code = generate_referral_code()
                    
                    cur.execute("""
                        INSERT INTO referral_users (telegram_id, username, first_name, referral_code)
                        VALUES (%s, %s, %s, %s)
                        RETURNING *
                    """, (telegram_id, username, first_name, referral_code))
                    row = cur.fetchone()
                    conn.commit()
                    
                    logger.info(f"Created referral user {telegram_id} with code {referral_code}")
                    
                    return ReferralStats(
                        telegram_id=row["telegram_id"],
                        referral_code=row["referral_code"],
                        total_referrals=0,
                        active_referrals=0,
                        tier=ReferralTier.BRONZE,
                        total_earnings=0
                    )
        except Exception as e:
            logger.error(f"Error getting/creating referral user: {e}")
            return ReferralStats(telegram_id=telegram_id, referral_code=generate_referral_code())
    
    def apply_referral_code(self, telegram_id: int, referral_code: str, 
                            username: Optional[str] = None, 
                            first_name: Optional[str] = None) -> dict:
        if not DATABASE_URL:
            return {"success": False, "error": "Database not available"}
        
        referral_code = referral_code.upper().strip()
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM referral_users WHERE telegram_id = %s", (telegram_id,))
                    existing_user = cur.fetchone()
                    
                    if existing_user and existing_user.get("referred_by_code"):
                        return {
                            "success": False,
                            "error": "already_used",
                            "message": "Вы уже использовали реферальный код"
                        }
                    
                    cur.execute("SELECT * FROM referral_users WHERE referral_code = %s", (referral_code,))
                    referrer = cur.fetchone()
                    
                    if not referrer:
                        return {
                            "success": False,
                            "error": "invalid_code",
                            "message": "Реферальный код не найден"
                        }
                    
                    if referrer["telegram_id"] == telegram_id:
                        return {
                            "success": False,
                            "error": "self_referral",
                            "message": "Нельзя использовать свой собственный код"
                        }
                    
                    if existing_user:
                        cur.execute("""
                            UPDATE referral_users 
                            SET referred_by_code = %s, updated_at = NOW()
                            WHERE telegram_id = %s
                        """, (referral_code, telegram_id))
                    else:
                        new_code = generate_referral_code()
                        while True:
                            cur.execute("SELECT 1 FROM referral_users WHERE referral_code = %s", (new_code,))
                            if not cur.fetchone():
                                break
                            new_code = generate_referral_code()
                        
                        cur.execute("""
                            INSERT INTO referral_users (telegram_id, username, first_name, referral_code, referred_by_code)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (telegram_id, username, first_name, new_code, referral_code))
                    
                    cur.execute("""
                        INSERT INTO referrals (referrer_telegram_id, referred_telegram_id, bonus_amount, status)
                        VALUES (%s, %s, %s, 'active')
                        ON CONFLICT (referrer_telegram_id, referred_telegram_id) DO NOTHING
                    """, (referrer["telegram_id"], telegram_id, REFERRER_REWARD))
                    
                    new_total = referrer["total_referrals"] + 1
                    new_active = referrer["active_referrals"] + 1
                    new_tier = calculate_tier(new_total)
                    new_earnings = referrer["total_earnings"] + REFERRER_REWARD
                    
                    cur.execute("""
                        UPDATE referral_users 
                        SET total_referrals = %s, active_referrals = %s, 
                            tier = %s, total_earnings = %s, updated_at = NOW()
                        WHERE telegram_id = %s
                    """, (new_total, new_active, new_tier.value, new_earnings, referrer["telegram_id"]))
                    
                    conn.commit()
                    
                    logger.info(f"User {telegram_id} applied referral code {referral_code} from {referrer['telegram_id']}")
                    
                    return {
                        "success": True,
                        "message": f"Код применён! Вы получили {REFERRED_REWARD} монет!",
                        "referrer_reward": REFERRER_REWARD,
                        "referred_reward": REFERRED_REWARD,
                        "referrer_telegram_id": referrer["telegram_id"]
                    }
        except Exception as e:
            logger.error(f"Error applying referral code: {e}")
            return {"success": False, "error": str(e), "message": "Ошибка при применении кода"}
    
    def get_referrals_list(self, telegram_id: int) -> List[Referral]:
        if not DATABASE_URL:
            return []
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT r.*, u.username, u.first_name
                        FROM referrals r
                        LEFT JOIN referral_users u ON r.referred_telegram_id = u.telegram_id
                        WHERE r.referrer_telegram_id = %s
                        ORDER BY r.created_at DESC
                        LIMIT 50
                    """, (telegram_id,))
                    
                    return [
                        Referral(
                            id=row["id"],
                            referrer_telegram_id=row["referrer_telegram_id"],
                            referred_telegram_id=row["referred_telegram_id"],
                            referred_username=row.get("username"),
                            referred_first_name=row.get("first_name"),
                            bonus_amount=row["bonus_amount"],
                            status=row["status"],
                            created_at=row["created_at"]
                        )
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            logger.error(f"Error getting referrals list: {e}")
            return []
    
    def get_referral_link(self, referral_code: str) -> str:
        return f"https://t.me/w4tg_bot/w4tg?startapp={referral_code}"
    
    def get_bot_referral_link(self, referral_code: str) -> str:
        return f"https://t.me/w4tg_bot?start=ref_{referral_code}"


referral_manager = ReferralManager()
