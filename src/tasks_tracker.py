import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import dataclass
from typing import List, Optional, Set
from datetime import datetime, date
from enum import Enum

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("RAILWAY_DATABASE_URL") or os.environ.get("DATABASE_URL")

TASKS_CONFIG = {
    "daily": {
        "daily_visit": {"coins": 10, "type": "visit", "daily": True},
        "daily_view_demos": {"coins": 25, "type": "view", "daily": True},
        "daily_share": {"coins": 30, "type": "share", "daily": True},
    },
    "telegram": {
        "telegram_subscribe": {"coins": 100, "type": "subscribe", "url": "https://t.me/web4_tg", "channel": "web4_tg"},
        "telegram_read_1": {"coins": 20, "type": "view", "url": "https://t.me/web4_tg"},
        "telegram_read_2": {"coins": 20, "type": "view", "url": "https://t.me/web4_tg"},
        "telegram_read_3": {"coins": 20, "type": "view", "url": "https://t.me/web4_tg"},
        "telegram_reaction_1": {"coins": 30, "type": "like", "url": "https://t.me/web4_tg"},
        "telegram_reaction_2": {"coins": 30, "type": "like", "url": "https://t.me/web4_tg"},
        "telegram_share": {"coins": 50, "type": "share", "url": "https://t.me/web4_tg"},
        "telegram_comment": {"coins": 40, "type": "comment", "url": "https://t.me/web4_tg"},
    },
    "youtube": {
        "youtube_subscribe": {"coins": 100, "type": "subscribe", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_bell": {"coins": 50, "type": "bell", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_like_1": {"coins": 30, "type": "like", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_like_2": {"coins": 30, "type": "like", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_like_3": {"coins": 30, "type": "like", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_comment_1": {"coins": 50, "type": "comment", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_comment_2": {"coins": 50, "type": "comment", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_view_1": {"coins": 40, "type": "view", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_view_2": {"coins": 40, "type": "view", "url": "https://www.youtube.com/@WEB4TG"},
        "youtube_share": {"coins": 60, "type": "share", "url": "https://www.youtube.com/@WEB4TG"},
    },
    "instagram": {
        "instagram_subscribe": {"coins": 100, "type": "subscribe", "url": "https://www.instagram.com/web4tg/"},
        "instagram_like_1": {"coins": 25, "type": "like", "url": "https://www.instagram.com/web4tg/"},
        "instagram_like_2": {"coins": 25, "type": "like", "url": "https://www.instagram.com/web4tg/"},
        "instagram_like_3": {"coins": 25, "type": "like", "url": "https://www.instagram.com/web4tg/"},
        "instagram_like_reels": {"coins": 30, "type": "like", "url": "https://www.instagram.com/web4tg/"},
        "instagram_comment_1": {"coins": 50, "type": "comment", "url": "https://www.instagram.com/web4tg/"},
        "instagram_comment_2": {"coins": 50, "type": "comment", "url": "https://www.instagram.com/web4tg/"},
        "instagram_save": {"coins": 35, "type": "save", "url": "https://www.instagram.com/web4tg/"},
        "instagram_story": {"coins": 70, "type": "share", "url": "https://www.instagram.com/web4tg/"},
        "instagram_share": {"coins": 40, "type": "share", "url": "https://www.instagram.com/web4tg/"},
    },
    "tiktok": {
        "tiktok_subscribe": {"coins": 100, "type": "subscribe", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_like_1": {"coins": 25, "type": "like", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_like_2": {"coins": 25, "type": "like", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_like_3": {"coins": 25, "type": "like", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_like_4": {"coins": 25, "type": "like", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_comment_1": {"coins": 50, "type": "comment", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_comment_2": {"coins": 50, "type": "comment", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_view_1": {"coins": 20, "type": "view", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_view_2": {"coins": 20, "type": "view", "url": "https://www.tiktok.com/@web4tg"},
        "tiktok_share": {"coins": 60, "type": "share", "url": "https://www.tiktok.com/@web4tg"},
    },
}

DISCOUNT_TIERS = [
    (0, 0),
    (200, 5),
    (500, 10),
    (800, 15),
    (1200, 20),
    (1500, 25),
]


class VerificationStatus(Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class UserProgress:
    telegram_id: int
    total_coins: int = 0
    completed_tasks: Set[str] = None
    current_streak: int = 0
    max_streak: int = 0
    last_activity_date: Optional[date] = None
    
    def __post_init__(self):
        if self.completed_tasks is None:
            self.completed_tasks = set()
    
    def get_discount_percent(self) -> int:
        for coins_threshold, discount in reversed(DISCOUNT_TIERS):
            if self.total_coins >= coins_threshold:
                return discount
        return 0
    
    def get_tier_name(self) -> str:
        tier_names = {
            0: "Начальный уровень",
            5: "Активный пользователь",
            10: "Продвинутый уровень",
            15: "Эксперт соцсетей",
            20: "Мастер активности",
            25: "Легенда WEB4TG",
        }
        return tier_names.get(self.get_discount_percent(), "Начальный уровень")


class TasksTracker:
    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self._init_db()
    
    def _get_connection(self):
        return psycopg2.connect(DATABASE_URL)
    
    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, tasks tracking will not work")
            return
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS tasks_progress (
                            id SERIAL PRIMARY KEY,
                            telegram_id BIGINT NOT NULL,
                            task_id VARCHAR(100) NOT NULL,
                            platform VARCHAR(50) NOT NULL,
                            task_type VARCHAR(50) NOT NULL,
                            coins_reward INTEGER NOT NULL,
                            completed BOOLEAN DEFAULT FALSE NOT NULL,
                            verification_status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                            attempts INTEGER DEFAULT 0 NOT NULL,
                            last_attempt_at TIMESTAMP,
                            completed_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT NOW(),
                            UNIQUE(telegram_id, task_id)
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_coins (
                            telegram_id BIGINT PRIMARY KEY,
                            total_coins INTEGER DEFAULT 0,
                            current_streak INTEGER DEFAULT 0,
                            max_streak INTEGER DEFAULT 0,
                            last_activity_date DATE,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_progress_telegram_id ON tasks_progress(telegram_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_progress_task_id ON tasks_progress(task_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_progress_completed ON tasks_progress(completed)")
                    
                    conn.commit()
                    logger.info("Tasks tracking tables initialized")
        except Exception as e:
            logger.error(f"Failed to init tasks tracking tables: {e}")
    
    async def check_telegram_subscription(self, telegram_id: int, channel_username: str) -> bool:
        import httpx
        
        if not self.bot_token:
            logger.error("Bot token not set for subscription check")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getChatMember"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "chat_id": f"@{channel_username}",
                    "user_id": telegram_id
                })
                data = response.json()
                
                if data.get("ok"):
                    status = data.get("result", {}).get("status", "")
                    is_member = status in ["member", "administrator", "creator"]
                    logger.info(f"User {telegram_id} subscription status to @{channel_username}: {status} (member={is_member})")
                    return is_member
                else:
                    logger.warning(f"Failed to check subscription: {data}")
                    return False
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    def get_user_progress(self, telegram_id: int) -> UserProgress:
        if not DATABASE_URL:
            return UserProgress(telegram_id=telegram_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT total_coins, current_streak, max_streak, last_activity_date
                        FROM user_coins WHERE telegram_id = %s
                    """, (telegram_id,))
                    coins_row = cur.fetchone()
                    
                    cur.execute("""
                        SELECT task_id FROM tasks_progress
                        WHERE telegram_id = %s AND completed = TRUE
                    """, (telegram_id,))
                    completed = {row["task_id"] for row in cur.fetchall()}
                    
                    if coins_row:
                        return UserProgress(
                            telegram_id=telegram_id,
                            total_coins=coins_row["total_coins"],
                            completed_tasks=completed,
                            current_streak=coins_row["current_streak"],
                            max_streak=coins_row["max_streak"],
                            last_activity_date=coins_row["last_activity_date"]
                        )
                    else:
                        return UserProgress(telegram_id=telegram_id, completed_tasks=completed)
        except Exception as e:
            logger.error(f"Error getting user progress: {e}")
            return UserProgress(telegram_id=telegram_id)
    
    def _get_daily_tasks_completed_today(self, telegram_id: int) -> set:
        """Get all daily tasks completed today in one query."""
        if not DATABASE_URL:
            return set()
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT DISTINCT task_id FROM tasks_progress
                        WHERE telegram_id = %s 
                        AND completed = TRUE 
                        AND DATE(completed_at) = CURRENT_DATE
                    """, (telegram_id,))
                    return {row["task_id"] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"Error checking daily tasks: {e}")
            return set()
    
    def _update_streak(self, telegram_id: int):
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT current_streak, max_streak, last_activity_date
                        FROM user_coins WHERE telegram_id = %s
                    """, (telegram_id,))
                    row = cur.fetchone()
                    
                    today = date.today()
                    
                    if row:
                        last_date = row["last_activity_date"]
                        current_streak = row["current_streak"]
                        max_streak = row["max_streak"]
                        
                        if last_date == today:
                            return current_streak
                        elif last_date and (today - last_date).days == 1:
                            current_streak += 1
                        else:
                            current_streak = 1
                        
                        max_streak = max(max_streak, current_streak)
                        
                        cur.execute("""
                            UPDATE user_coins 
                            SET current_streak = %s, max_streak = %s, 
                                last_activity_date = %s, updated_at = NOW()
                            WHERE telegram_id = %s
                        """, (current_streak, max_streak, today, telegram_id))
                    else:
                        cur.execute("""
                            INSERT INTO user_coins (telegram_id, current_streak, max_streak, last_activity_date)
                            VALUES (%s, 1, 1, %s)
                        """, (telegram_id, today))
                        current_streak = 1
                    
                    conn.commit()
                    return current_streak
        except Exception as e:
            logger.error(f"Error updating streak: {e}")
            return 0
    
    async def complete_task(self, telegram_id: int, task_id: str, platform: str) -> dict:
        task_config = None
        for plat, tasks in TASKS_CONFIG.items():
            if task_id in tasks:
                task_config = tasks[task_id]
                platform = plat
                break
        
        if not task_config:
            return {"success": False, "error": "Task not found", "message": "Задание не найдено"}
        
        is_daily = task_config.get("daily", False)
        
        if is_daily:
            if self._is_daily_task_completed_today(telegram_id, task_id):
                return {
                    "success": False,
                    "error": "Daily task already completed today",
                    "message": "Это ежедневное задание уже выполнено сегодня. Попробуйте завтра!"
                }
        else:
            progress = self.get_user_progress(telegram_id)
            if task_id in progress.completed_tasks:
                return {
                    "success": False,
                    "error": "Task already completed",
                    "message": "Это задание уже выполнено"
                }
        
        if platform == "telegram" and task_config.get("type") == "subscribe":
            channel = task_config.get("channel", "web4_tg")
            is_subscribed = await self.check_telegram_subscription(telegram_id, channel)
            if not is_subscribed:
                return {
                    "success": False,
                    "error": "Not subscribed to channel",
                    "message": f"Сначала подпишитесь на канал @{channel}"
                }
        
        coins = task_config["coins"]
        task_type = task_config["type"]
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if is_daily:
                        cur.execute("""
                            INSERT INTO tasks_progress 
                            (telegram_id, task_id, platform, task_type, coins_reward, completed, verification_status, completed_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, 'verified', NOW())
                        """, (telegram_id, task_id, platform, task_type, coins))
                    else:
                        cur.execute("""
                            INSERT INTO tasks_progress 
                            (telegram_id, task_id, platform, task_type, coins_reward, completed, verification_status, completed_at)
                            VALUES (%s, %s, %s, %s, %s, TRUE, 'verified', NOW())
                            ON CONFLICT (telegram_id, task_id) 
                            DO UPDATE SET completed = TRUE, verification_status = 'verified', completed_at = NOW()
                        """, (telegram_id, task_id, platform, task_type, coins))
                    
                    cur.execute("""
                        INSERT INTO user_coins (telegram_id, total_coins, last_activity_date)
                        VALUES (%s, %s, CURRENT_DATE)
                        ON CONFLICT (telegram_id) 
                        DO UPDATE SET total_coins = user_coins.total_coins + %s, 
                                      last_activity_date = CURRENT_DATE,
                                      updated_at = NOW()
                    """, (telegram_id, coins, coins))
                    
                    conn.commit()
            
            streak = self._update_streak(telegram_id)
            progress = self.get_user_progress(telegram_id)
            
            logger.info(f"User {telegram_id} completed task {task_id}, earned {coins} coins, total: {progress.total_coins}")
            
            return {
                "success": True,
                "message": "Задание выполнено!",
                "coinsAwarded": coins,
                "totalCoins": progress.total_coins,
                "streak": streak,
                "discount": progress.get_discount_percent()
            }
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return {"success": False, "error": str(e), "message": "Ошибка при выполнении задания"}
    
    def get_available_tasks(self, telegram_id: int) -> dict:
        progress = self.get_user_progress(telegram_id)
        daily_completed_today = self._get_daily_tasks_completed_today(telegram_id)
        
        available = {}
        for platform, tasks in TASKS_CONFIG.items():
            platform_tasks = []
            for task_id, config in tasks.items():
                is_daily = config.get("daily", False)
                
                if is_daily:
                    status = "completed" if task_id in daily_completed_today else "available"
                else:
                    status = "completed" if task_id in progress.completed_tasks else "available"
                
                platform_tasks.append({
                    "id": task_id,
                    "coins": config["coins"],
                    "type": config["type"],
                    "url": config.get("url"),
                    "status": status,
                    "daily": is_daily
                })
            available[platform] = platform_tasks
        
        return {
            "tasks": available,
            "progress": {
                "totalCoins": progress.total_coins,
                "completedCount": len(progress.completed_tasks),
                "streak": progress.current_streak,
                "discount": progress.get_discount_percent(),
                "tierName": progress.get_tier_name()
            }
        }


tasks_tracker = TasksTracker()
