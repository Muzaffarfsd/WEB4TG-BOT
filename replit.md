# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot is designed to act as an AI-powered support agent for WEB4TG Studio, a premium Telegram Mini Apps development studio. Its primary purpose is to consult clients on services, pricing, assist in selecting appropriate solutions, and calculate application costs. This project aims to streamline client interaction, enhance lead generation, and provide an efficient, automated support system for potential clients, ultimately contributing to business growth and market expansion in the Telegram Mini Apps ecosystem.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is built on Python and utilizes Telegram Bot API 9.4 for advanced features like message streaming, custom button styles, and private chat topics. It employs a modular handler architecture (commands, callbacks, messages, media, admin) for maintainability. Core architectural decisions include a unified PostgreSQL database connection pool, TTL caching for frequently accessed data, and robust analytics for funnel tracking and A/B testing.

Key features include:
- **AI Integration**: Powered by Gemini 3 Pro Preview for intelligent responses, real-time streaming, and function calling (calculator, portfolio, payment).
- **Interactive Tools**: An interactive cost calculator, portfolio examples, and a comprehensive FAQ system.
- **Lead Management**: Automatic lead capture, manager notifications, lead auto-tagging based on keywords, and priority setting.
- **Gamification & Loyalty**: A system for earning coins through tasks, a referral program with tiered commissions, and a loyalty program offering discounts for reviews and repeat purchases.
- **Payment System**: Manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: A smart follow-up system with AI-generated personalized messages, a broadcast system for mass messaging with audience targeting, and multi-language support.
- **Security & Administration**: Admin access control, audit logging, and environment variable management for sensitive data.
- **Deployment**: Exclusively deployed on Railway with a PostgreSQL database, explicitly designed *not* to run on Replit to avoid conflicts.

## Custom Emoji Configuration
Custom emoji IDs on buttons are loaded from environment variables (set on Railway):
- `EMOJI_LEAD` — кнопка "Оставить заявку"
- `EMOJI_PAYMENT` — кнопка "Оплата"
- `EMOJI_CALCULATOR` — кнопка "Калькулятор"
- `EMOJI_PORTFOLIO` — кнопка "Портфолио"
- `EMOJI_SERVICES` — кнопка "Услуги и цены"
- `EMOJI_MANAGER` — кнопка "Связаться с менеджером"
- `EMOJI_FAQ` — кнопка "FAQ"
- `EMOJI_BONUS` — кнопка "Бонусы"
- `EMOJI_STARS` — кнопки Stars-оплаты

To get custom emoji IDs: send a custom emoji from a sticker pack to the bot, use `getCustomEmojiStickers` API, or find them in Telegram sticker sets. If env vars are not set, buttons work normally without custom icons.

Button styles (Bot API 9.4): `constructive` (green), `destructive` (red) applied via `styled_button_api_kwargs()`.

## Recent Changes (Feb 11, 2026)
- Fixed callback routing bug: `callback_data="menu"` in payments.py changed to `"menu_back"` (button "Назад" was not working)
- Added handlers for subscription buttons (`sub_min`, `sub_std`, `sub_premium`) — now show detailed plan info with CTA
- Updated `price_subs` callback to show subscription selection buttons instead of just back button
- Removed dead code: duplicate `package_app_subscription_` handler (was unreachable because general `package_` handler catches it first via `startswith`)
- Improved `package_` handler: added proper "Назад → loyalty_packages" navigation and fallback for unknown package IDs
- Full callback_data audit: all 81 callback_data values handled, 31 commands registered, 0 syntax errors, 0 dead routes
- Prefix conflict `bc_` → `bc_audience_` verified as correct nested elif (not a routing bug)
- **Critical fix**: Added missing `add_coins` method to `TasksTracker` class — was causing `AttributeError` when manager approves a review (callback `mod_approve_*`)

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, and function calling.
- **PostgreSQL**: As the primary database, hosted on Railway.
- **ElevenLabs**: (Optional) For voice greetings.