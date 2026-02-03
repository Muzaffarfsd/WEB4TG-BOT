#!/usr/bin/env python3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.config import config
from src.handlers import (
    start_handler, help_handler, clear_handler,
    price_handler, portfolio_handler, contact_handler,
    message_handler, error_handler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    application = Application.builder().token(config.telegram_token).build()
    
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("clear", clear_handler))
    application.add_handler(CommandHandler("price", price_handler))
    application.add_handler(CommandHandler("portfolio", portfolio_handler))
    application.add_handler(CommandHandler("contact", contact_handler))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    application.add_error_handler(error_handler)
    
    logger.info("WEB4TG Studio AI Agent (Gemini 3 Pro) starting...")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Max history: {config.max_history_length} messages")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
