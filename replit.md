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
- **System Prompt v2**: Restructured from 25+ conflicting rules to 7 core flexible principles. #1 priority = tone mirroring. Removed conflicts (3-brain-every-msg vs word-limit). Techniques now contextual, not mandatory.
- **Hybrid Funnel Detection**: 3-signal system (keyword + semantic intent + lead score), picks highest stage, then applies backslide check. Semantic patterns detect implicit intent ("нужно автоматизировать заказы" → decision).
- **Funnel Backslide**: Detects doubt keywords ("подумаю", "дорого", "не уверен") and downgrades stage (decision→consideration, consideration→interest).
- **Client Style Detection**: `detect_client_style()` — 4 styles (laconic/detailed/formal/casual) with adaptive response instructions. Integrated into context builder.
- **Proactive Value Delivery**: Industry-specific ROI benchmarks (shop/restaurant/beauty/fitness/medical/AI/services/education/delivery) + stage-specific micro-assets (checklists, calculators, comparisons).
- **Industry-Matched Case Studies**: `get_relevant_case_study()` — Radiance for shops, DeluxeDine for restaurants, GlowSpa for beauty, FitPro for fitness, MedLine for medical, CleanPro for services, SkillUp for education. Auto-selected by client's industry tag.
- **Client Profiles (30+ days)**: New `client_profiles` table — stores industry, budget, timeline, needs, objections, style, timezone. Populated from AI insight extraction. Injected into context as [ДОЛГОСРОЧНЫЙ ПРОФИЛЬ].
- **Win-Back Follow-Up (4th touch)**: New follow-up #4 at 14-21 days with fresh value proposition (new case study, free audit offer). AI-generated with win-back prompt template.
- **Timezone-Aware Follow-Ups**: Uses `timezone_offset` from client profile to schedule follow-ups during business hours (9:00-20:00 client time).
- **Conversation History Extended**: TTL increased from 7 to 30 days for B2B sales cycle support.
- **Data Consistency Fixes**: compare_plans tool aligned with pricing.py (150k/170k/180k/200k templates, 9.9k/14.9k/24.9k subscriptions). Discount display corrected from max 15% to max 25% (5 tiers). Privacy policy TTL fixed from 24h to 30 days. Calculator.py synced with pricing.py (added progress feature). Industry mapping expanded (education, delivery, services). Semantic/backslide patterns expanded for better coverage.
- Previous: persistent memory, multimodal AI, 11 AI tools, agentic loop, auto lead scoring, insight extraction, dynamic buttons, smart callbacks

## Super Agent Architecture
- **Agentic Loop**: `src/ai_client.py` → `agentic_loop()` — multi-step tool calling (up to 4 steps), AI chains tools and synthesizes results
- **Session + Memory**: `src/session.py` — persistent memory (PostgreSQL, 30-day TTL), auto-summarization at 20+ messages, `client_profiles` table for long-term data (industry, budget, needs, timezone)
- **Context Builder (Hybrid Funnel)**: `src/context_builder.py` — 3-signal hybrid funnel (keywords + semantics + score), backslide detection, client style mirroring, proactive value delivery, industry case study matching, 8 objection types, emotional intelligence (5 tones), dynamic buttons
- **Knowledge Base (Optimized Prompt)**: `src/knowledge_base.py` — 7 core rules (mirror first), 3-brain model (pick 1-2), SPIN by stage, flexible question rule, value-first, grounded AI, ethical guardrails
- **Dynamic Button System**: `src/context_builder.py` → `get_dynamic_buttons()` → `src/handlers/messages.py` attaches stage-aware buttons to every AI response
- **AI Client**: `src/ai_client.py` — Gemini API with 11 function-calling tools, streaming, thinking modes, agentic loop
- **Auto Lead Scoring**: `src/handlers/messages.py` — 9 buying signal categories with weighted scoring, auto-priority escalation
- **Insight Extraction + Profile**: `src/handlers/messages.py` — AI extracts budget/timeline/needs every 5 messages, auto-saves to lead tags AND `client_profiles` table with industry mapping
- **Follow-Up System**: `src/followup.py` — 4 touches (including win-back), timezone-aware scheduling, AI-generated messages per stage
- **Guardrails**: System prompt rules preventing unauthorized promises (discounts, delivery dates, free features)
- **Tool Execution**: `src/handlers/messages.py` — handles all 11 AI tool calls with agentic loop and special actions

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, function calling, and vision (multimodal).
- **PostgreSQL**: As the primary database, hosted on Railway.
- **ElevenLabs**: (Optional) For voice greetings.