# WEB4TG Studio AI Agent Bot

## Overview
AI-агент поддержки для WEB4TG Studio — премиальной студии разработки Telegram Mini Apps. Бот консультирует клиентов по услугам, ценам, помогает подобрать решение и рассчитать стоимость приложения.

## Deployment
- **Development**: Replit (code only, NO RUNNING - bot uses long polling)
- **Production**: Railway (deployment only)
- Database: Railway PostgreSQL
- **IMPORTANT**: Do NOT run bot on Replit - will conflict with Railway production bot

## Project Structure (2026 Best Practices)
```
├── bot.py                 # Entry point
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management (URLs, API keys)
│   ├── database.py        # Shared database connection pool (1-15 connections)
│   ├── knowledge_base.py  # System prompts & messages
│   ├── session.py         # User session management with TTL
│   ├── ai_client.py       # Gemini AI client with OpenAI fallback
│   ├── handlers.py        # Telegram command, message & callback handlers
│   ├── keyboards.py       # Inline keyboard layouts
│   ├── calculator.py      # Interactive cost calculator
│   ├── leads.py           # Lead collection & manager notifications
│   ├── tasks_tracker.py   # Task gamification system (coins, discounts)
│   ├── referrals.py       # Referral program (invite friends, earn coins)
│   ├── loyalty.py         # Loyalty system (reviews, packages, returning customers)
│   ├── payments.py        # Manual payment integration
│   ├── pricing.py         # Pricing information and menus
│   └── ab_testing.py      # A/B testing for welcome messages
└── attached_assets/       # Knowledge base source
```

## Architecture Features (2026)
- **Modular structure** - Separate modules for config, AI, sessions, handlers
- **Unified DB pool** - Shared ThreadedConnectionPool (1-15 connections) across all modules
- **A/B testing** - Welcome message variants with tracking (variant A/B)
- **Photo reviews** - Direct video/photo upload in chat for reviews
- **Inline keyboards** - Interactive navigation with callback queries
- **Thinking mode** - Gemini 3 Pro thinking for complex queries (4096 tokens)
- **Cost calculator** - Interactive feature selection & price calculation
- **Lead management** - Automatic lead capture with manager notifications
- **Session management** - Per-user conversation history with TTL (24h)
- **Memory limits** - Max 30 messages per conversation, 10k sessions
- **Rate limiting** - Tenacity retry with exponential backoff
- **Typing indicators** - Shows "typing..." while generating response
- **Long message handling** - Splits messages >4096 chars
- **Async processing** - Non-blocking AI calls
- **Gamification system** - Tasks, coins, streaks, discount tiers
- **Loyalty program** - Reviews, packages, returning customer bonuses

## Gamification System (Business Optimized)
Users earn coins by completing tasks, which convert to discounts:
- **Discount tiers**: 500→5%, 1000→10%, 1500→15% (max)
- **Coin expiry**: 90 days from earning
- **Platforms**: Telegram, YouTube, Instagram, TikTok
- **Task types**: Subscribe, Like, Comment, Share, View
- **Task rewards**: Halved to encourage referrals
- **Telegram verification**: Auto-checks channel subscription via Bot API
- **Streaks**: Daily activity tracking for bonus engagement
- **Tables**: `tasks_progress`, `user_coins`

## Referral Program
Users can invite friends and earn coins:
- **Referrer reward**: 200 coins per invited friend
- **Referred reward**: 50 coins welcome bonus
- **Tiers**: Bronze (0-9), Silver (10-29), Gold (30-99), Platinum (100+)
- **Commission**: 10% → 15% → 20% → 30% based on tier
- **Code format**: WEB4TG + 6 random chars (e.g., WEB4TG7X9K2M)
- **Link format**: `https://t.me/w4tg_bot?start=ref_{CODE}`
- **Tables**: `referral_users`, `referrals`

## Loyalty Program (NEW)
Additional ways to earn discounts:
- **Review bonus**: Video review = 500 coins, Text+photo = 200 coins
- **Returning customer**: +5% discount on repeat orders
- **Package deals**: App + subscription bundles (3mo=-5%, 6mo=-10%, 12mo=-15%)
- **Maximum total discount**: 30% (all bonuses combined)
- **Tables**: `customer_reviews`, `customer_orders`

## Payment System
Manual payment integration with downloadable contract:
- **Visa card**: 4177 4901 1819 6304 (Muzaparov M.Sh.)
- **Bank transfer**: Mbank Bishkek
- **Contract PDF**: Downloadable from bot
- **Commands**: `/payment`, `/contract`

## Bot Capabilities
- Ответы на вопросы об услугах и ценах WEB4TG Studio
- Консультации по выбору шаблона и функций
- Интерактивный расчёт стоимости приложения
- Примеры из портфолио по категориям
- Автоматический сбор лидов
- Уведомления менеджеру о заявках
- Программа лояльности с бонусами за отзывы
- **Мультиязычность** — автоопределение языка клиента и ответ на его языке

## Commands
- `/start` - Начать диалог
- `/help` - Список команд
- `/clear` - Очистить историю
- `/menu` - Главное меню
- `/price` - Цены на услуги
- `/payment` - Оплата услуг
- `/contract` - Скачать договор
- `/portfolio` - Примеры работ
- `/contact` - Контакты
- `/calc` - Калькулятор стоимости
- `/referral` - Реферальная программа
- `/leads` - Просмотр лидов (только менеджер)
- `/stats` - Статистика бота (только менеджер)
- `/export` - Экспорт лидов в CSV (только менеджер)
- `/reviews` - Отзывы на модерацию (только менеджер)
- `/history <user_id>` - История взаимодействий с лидом (только менеджер)
- `/hot` - Горячие лиды (только менеджер)
- `/tag <user_id> <тег>` - Добавить тег лиду (только менеджер)
- `/priority <user_id> <cold|warm|hot>` - Установить приоритет (только менеджер)

## Environment Variables
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `GEMINI_API_KEY` - Google AI API key for Gemini 3 Pro
- `ELEVENLABS_API_KEY` - (Optional) ElevenLabs for voice greeting
- `MANAGER_CHAT_ID` - (Optional) Chat ID for lead notifications
- `RAILWAY_DATABASE_URL` - PostgreSQL database URL

## AI Models
- **Primary**: Gemini 3 Pro Preview (thinking mode, 4096 budget)

## A/B Testing
- **welcome_voice** test: variant A (short informal) vs B (detailed professional)
- Random 50/50 assignment on first visit
- Event tracking: start_command, voice_sent, voice_failed
- Stats available via ab_testing.format_stats_message()

## Running (Railway only)
```bash
python bot.py
```
**Do NOT run on Replit** - will cause "Conflict: terminated by other getUpdates request"
