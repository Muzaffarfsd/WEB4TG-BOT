"""Security module for admin access control."""

import os
import logging
from typing import Set, Optional
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")

def get_admin_ids() -> Set[int]:
    """Get set of admin user IDs from environment."""
    admin_ids = set()
    
    if MANAGER_CHAT_ID:
        try:
            admin_ids.add(int(MANAGER_CHAT_ID))
        except ValueError:
            pass
    
    if ADMIN_IDS_STR:
        for id_str in ADMIN_IDS_STR.split(","):
            try:
                admin_ids.add(int(id_str.strip()))
            except ValueError:
                pass
    
    return admin_ids


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in get_admin_ids()


def admin_required(func):
    """Decorator to restrict handler to admins only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            logger.warning(f"Unauthorized admin access attempt by user {user_id}")
            await update.message.reply_text(
                "⛔ Эта команда доступна только администраторам."
            )
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def log_admin_action(user_id: int, action: str, details: Optional[str] = None) -> None:
    """Log admin actions for audit trail."""
    log_msg = f"ADMIN ACTION: user_id={user_id}, action={action}"
    if details:
        log_msg += f", details={details}"
    logger.info(log_msg)
