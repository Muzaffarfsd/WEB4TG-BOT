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
├── bot.py                     # Entry point
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── database.py            # Shared DB connection pool (1-15 connections)
│   ├── cache.py               # TTL cache for frequent queries
│   ├── analytics.py           # Funnel tracking and events
│   ├── security.py            # Admin access control
│   ├── knowledge_base.py      # System prompts & messages
│   ├── session.py             # User session management with TTL
│   ├── ai_client.py           # Gemini AI client
│   ├── keyboards.py           # Inline keyboard layouts
│   ├── calculator.py          # Interactive cost calculator
│   ├── leads.py               # Lead collection & manager notifications
│   ├── tasks_tracker.py       # Task gamification system
│   ├── referrals.py           # Referral program
│   ├── loyalty.py             # Loyalty system (reviews, packages)
│   ├── payments.py            # Manual payment integration
│   ├── pricing.py             # Pricing information and menus
│   ├── ab_testing.py          # A/B testing for welcome messages
│   ├── followup.py            # Smart follow-up system
│   ├── broadcast.py           # Broadcast/mailing system
│   └── handlers/              # Modular handlers (refactored)
│       ├── __init__.py        # Exports all handlers
│       ├── utils.py           # Shared utilities
│       ├── commands.py        # Command handlers (/start, /menu, etc)
│       ├── callbacks.py       # Callback query handler
│       ├── messages.py        # Message handler + AI responses
│       ├── media.py           # Voice, video, photo handlers
│       └── admin.py           # Admin commands with @admin_required
└── attached_assets/           # Knowledge base source
```

## Architecture Features (2026)
- **Modular handlers** - Split into domain-specific modules (commands, callbacks, media, admin)
- **Unified DB pool** - Shared ThreadedConnectionPool (1-15 connections) across all modules
- **TTL caching** - Cache module for frequently accessed data (src/cache.py)
- **Funnel analytics** - Event tracking for conversion optimization (src/analytics.py)
- **Admin security** - @admin_required decorator, ADMIN_IDS env var, audit logging
- **A/B testing** - Welcome message variants with tracking (variant A/B)
- **Photo reviews** - Direct video/photo upload in chat for reviews
- **Inline keyboards** - Interactive navigation with callback queries
- **Thinking mode** - Gemini 3 Pro thinking for complex queries (4096 tokens)
- **Cost calculator** - Interactive feature selection & price calculation
- **Lead management** - Automatic lead capture with manager notifications
- **Session management** - Per-user conversation history with TTL (24h)
- **Memory limits** - Max 30 messages per conversation, 10k sessions
- **Rate limiting** - Tenacity retry with exponential backoff
- **Gamification system** - Tasks, coins, streaks, discount tiers
- **Loyalty program** - Reviews, packages, returning customer bonuses
- **Smart follow-ups** - AI-generated personalized follow-up messages based on conversation context
- **Broadcast system** - Mass messaging with audience targeting, rate limiting, progress tracking

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

## Loyalty Program
Additional ways to earn discounts:
- **Review bonus**: Video review = 500 coins, Text+photo = 200 coins
- **Returning customer**: +5% discount on repeat orders
- **Package deals**: App + subscription bundles (3mo=-5%, 6mo=-10%, 12mo=-15%)
- **Maximum total discount**: 30% (all bonuses combined)
- **Tables**: `customer_reviews`, `customer_orders`

## Payment System
Manual payment integration with downloadable contract:
- **Visa card**: From env PAYMENT_CARD_NUMBER
- **Bank transfer**: From env PAYMENT_* variables
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
- `/leads` - Просмотр лидов (только админ)
- `/stats` - Статистика бота (только админ)
- `/export` - Экспорт лидов в CSV (только админ)
- `/reviews` - Отзывы на модерацию (только админ)
- `/history <user_id>` - История взаимодействий (только админ)
- `/hot` - Горячие лиды (только админ)
- `/tag <user_id> <тег>` - Добавить тег лиду (только админ)
- `/priority <user_id> <cold|warm|hot>` - Установить приоритет (только админ)
- `/followup` - Статистика follow-up системы (только админ)
- `/followup pause <user_id>` - Приостановить follow-up (только админ)
- `/followup resume <user_id>` - Возобновить follow-up (только админ)
- `/broadcast` - Запуск рассылки (только админ)
- `/broadcast cancel` - Отмена рассылки (только админ)

## Environment Variables
### Required
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `GEMINI_API_KEY` - Google AI API key for Gemini 3 Pro
- `RAILWAY_DATABASE_URL` - PostgreSQL database URL

### Optional
- `ELEVENLABS_API_KEY` - ElevenLabs for voice greeting
- `MANAGER_CHAT_ID` - Chat ID for lead notifications
- `ADMIN_IDS` - Comma-separated admin user IDs (additional to MANAGER_CHAT_ID)

### Payment (moved from code for security)
- `PAYMENT_CARD_NUMBER` - Visa card number
- `PAYMENT_RECIPIENT` - Recipient name
- `PAYMENT_INN` - Recipient INN
- `PAYMENT_ACCOUNT` - Bank account number
- `PAYMENT_BANK_NAME` - Bank name
- `PAYMENT_BANK_ADDRESS` - Bank address
- `PAYMENT_BIK` - Bank BIK
- `PAYMENT_BANK_INN` - Bank INN

## AI Models
- **Primary**: Gemini 3 Pro Preview (thinking mode, 4096 budget)

## A/B Testing
- **welcome_voice** test: variant A (short informal) vs B (detailed professional)
- Random 50/50 assignment on first visit
- Event tracking: start_command, voice_sent, voice_failed
- Stats available via ab_testing.format_stats_message()

## Analytics & Funnel
- Funnel events tracked: start → menu → calculator → lead → payment
- Conversion rate calculation between any two events
- Daily stats with user/event counts
- Admin command `/stats` shows funnel analytics

## Follow-up System (Smart Reminders)
Automatic AI-generated follow-up messages for inactive users:
- **Schedule by lead priority**:
  - Hot (score >= 50): 4h → 24h → 3 days
  - Warm (score >= 25): 24h → 3 days → 7 days
  - Cold (score < 25): 3 days → 7 days (no 3rd)
- **Rules**: Max 3 follow-ups, min 2 messages before enabling, cancel on new message
- **AI messages**: Personalized based on conversation context, sounds like Alex (human)
- **Background job**: Runs every 5 minutes, checks for due follow-ups
- **Admin controls**: `/followup`, pause/resume per user
- **Statuses**: scheduled, sent, responded, cancelled, paused
- **Table**: `follow_ups`

## Broadcast System (Mass Messaging)
Admin-only mass messaging with audience targeting:
- **Content types**: Text, Photo with caption, Video with caption
- **Audience targeting**: All users, Hot leads, Warm leads, Cold leads
- **Rate limiting**: 25 messages/second to avoid Telegram API limits
- **Progress tracking**: Real-time updates every 50 users sent
- **Blocked user handling**: Gracefully skips blocked/deactivated users
- **User registration**: Auto-registers users on /start, backfills from leads/referrals
- **Compose mode**: Admin sends content via chat, then selects audience via inline keyboard
- **Confirmation**: Shows recipient count before sending
- **Stats**: `/broadcast` shows history of all broadcasts with results
- **Tables**: `bot_users`, `broadcasts`
- **Commands**: `/broadcast` (start/stats), `/broadcast cancel` (abort compose)

## Security
- @admin_required decorator for all admin commands
- ADMIN_IDS env var for additional admins
- Audit logging for admin actions
- Payment details moved to environment variables

## Running (Railway only)
```bash
python bot.py
```
**Do NOT run on Replit** - will cause "Conflict: terminated by other getUpdates request"
