#!/usr/bin/env python3
import logging
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters
)

from src.config import config
from src.handlers import (
    start_handler, help_handler, clear_handler, menu_handler,
    price_handler, portfolio_handler, contact_handler, calc_handler,
    message_handler, callback_handler, voice_handler, error_handler,
    leads_handler, stats_handler, export_handler,
    history_handler, hot_handler, tag_handler, priority_handler,
    referral_handler
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    """Set up bot commands menu after initialization."""
    commands = [
        BotCommand("start", "🚀 Открыть приложение"),
        BotCommand("menu", "📋 Главное меню"),
        BotCommand("price", "💰 Цены на услуги"),
        BotCommand("referral", "👥 Реферальная программа"),
        BotCommand("portfolio", "🎨 Примеры работ"),
        BotCommand("calc", "📱 Калькулятор стоимости"),
        BotCommand("contact", "📞 Связаться с нами"),
        BotCommand("help", "❓ Помощь"),
    ]
    await application.bot.set_my_commands(commands)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Bot commands menu configured")


def main() -> None:
    application = Application.builder().token(config.telegram_token).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("clear", clear_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("price", price_handler))
    application.add_handler(CommandHandler("portfolio", portfolio_handler))
    application.add_handler(CommandHandler("contact", contact_handler))
    application.add_handler(CommandHandler("calc", calc_handler))
    application.add_handler(CommandHandler("leads", leads_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("export", export_handler))
    application.add_handler(CommandHandler("history", history_handler))
    application.add_handler(CommandHandler("hot", hot_handler))
    application.add_handler(CommandHandler("tag", tag_handler))
    application.add_handler(CommandHandler("priority", priority_handler))
    application.add_handler(CommandHandler("referral", referral_handler))
    
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    application.add_error_handler(error_handler)
    
    logger.info("WEB4TG Studio AI Agent starting...")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Features: Inline keyboards, Calculator, Leads, Thinking mode")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
