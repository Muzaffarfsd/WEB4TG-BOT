# WEB4TG Studio AI Agent Bot

## Overview
AI-агент поддержки для WEB4TG Studio — премиальной студии разработки Telegram Mini Apps. Бот консультирует клиентов по услугам, ценам, помогает подобрать решение и рассчитать стоимость приложения.

## Project Structure (2026 Best Practices)
```
├── bot.py                 # Entry point
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── knowledge_base.py  # System prompts & messages
│   ├── session.py         # User session management with TTL
│   ├── ai_client.py       # Gemini AI client with retries
│   └── handlers.py        # Telegram command & message handlers
└── attached_assets/       # Knowledge base source
```

## Architecture Features
- **Modular structure** - Separate modules for config, AI, sessions, handlers
- **Session management** - Per-user conversation history with TTL (24h)
- **Memory limits** - Max 30 messages per conversation, 10k sessions
- **Retry logic** - Auto-retry on AI failures with exponential backoff
- **Typing indicators** - Shows "typing..." while generating response
- **Long message handling** - Splits messages >4096 chars
- **Async processing** - Non-blocking AI calls

## Bot Capabilities
- Ответы на вопросы об услугах и ценах WEB4TG Studio
- Консультации по выбору шаблона и функций
- Расчёт примерной стоимости приложения
- Примеры из портфолио
- Подведение к заказу

## Commands
- `/start` - Начать диалог
- `/help` - Список команд
- `/clear` - Очистить историю
- `/price` - Цены на услуги
- `/portfolio` - Примеры работ
- `/contact` - Контакты

## Environment Variables
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `AI_INTEGRATIONS_GEMINI_API_KEY` - Auto-configured
- `AI_INTEGRATIONS_GEMINI_BASE_URL` - Auto-configured

## AI Model
Gemini 3 Pro Preview (via Replit AI Integrations)

## Running
```bash
python bot.py
```
