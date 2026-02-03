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
│   ├── ai_client.py       # Gemini AI client with retries & thinking mode
│   ├── handlers.py        # Telegram command, message & callback handlers
│   ├── keyboards.py       # Inline keyboard layouts
│   ├── calculator.py      # Interactive cost calculator
│   └── leads.py           # Lead collection & manager notifications
└── attached_assets/       # Knowledge base source
```

## Architecture Features (2026)
- **Modular structure** - Separate modules for config, AI, sessions, handlers
- **Inline keyboards** - Interactive navigation with callback queries
- **Thinking mode** - Gemini 3 Pro thinking for complex queries (8192 tokens)
- **Cost calculator** - Interactive feature selection & price calculation
- **Lead management** - Automatic lead capture with manager notifications
- **Session management** - Per-user conversation history with TTL (24h)
- **Memory limits** - Max 30 messages per conversation, 10k sessions
- **Rate limiting** - Tenacity retry with exponential backoff
- **Typing indicators** - Shows "typing..." while generating response
- **Long message handling** - Splits messages >4096 chars
- **Async processing** - Non-blocking AI calls

## Bot Capabilities
- Ответы на вопросы об услугах и ценах WEB4TG Studio
- Консультации по выбору шаблона и функций
- Интерактивный расчёт стоимости приложения
- Примеры из портфолио по категориям
- Автоматический сбор лидов
- Уведомления менеджеру о заявках
- **Мультиязычность** — автоопределение языка клиента и ответ на его языке

## Commands
- `/start` - Начать диалог
- `/help` - Список команд
- `/clear` - Очистить историю
- `/menu` - Главное меню
- `/price` - Цены на услуги
- `/portfolio` - Примеры работ
- `/contact` - Контакты
- `/calc` - Калькулятор стоимости
- `/leads` - Просмотр лидов (только менеджер)
- `/stats` - Статистика бота (только менеджер)
- `/export` - Экспорт лидов в CSV (только менеджер)
- `/history <user_id>` - История взаимодействий с лидом (только менеджер)
- `/hot` - Горячие лиды (только менеджер)
- `/tag <user_id> <тег>` - Добавить тег лиду (только менеджер)
- `/priority <user_id> <cold|warm|hot>` - Установить приоритет (только менеджер)

## Environment Variables
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `GEMINI_API_KEY` - Google AI API key for Gemini 3 Pro
- `MANAGER_CHAT_ID` - (Optional) Chat ID for lead notifications

## AI Models
- **Fast responses**: Gemini 2.0 Flash (instant replies)
- **Complex queries**: Gemini 2.5 Pro Preview (thinking mode, 4096 budget)

## Running
```bash
python bot.py
```
