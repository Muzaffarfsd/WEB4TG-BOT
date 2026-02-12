# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot serves as an AI-powered support agent for WEB4TG Studio, a development studio specializing in Telegram Mini Apps. Its core function is to guide clients through services, provide pricing information, help select optimal solutions, and calculate application costs. The project aims to improve client engagement, boost lead generation, and offer an automated, efficient support system for potential clients, thereby fostering business expansion within the Telegram Mini Apps market.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## Recent Changes (February 2026)
- **Copywriting & Anthropomorphism Upgrade (Feb 12)**:
  - ENHANCED: `knowledge_base.py` — Expanded anthropomorphism section (25+ speech patterns, human imperfections, 8 situational reactions, messenger style rules, anti-patterns)
  - ENHANCED: `knowledge_base.py` — Upsell with ROI by 6 industries, benefit formulas (5 templates), pain points by 7 niches, urgency/scarcity triggers (5 types)
  - ENHANCED: `context_builder.py` — SOCIAL_PROOF_TRIGGERS expanded with concrete metrics, added "timing" category
  - ENHANCED: `context_builder.py` — INDUSTRY_CASE_STUDIES: 8 cases with investment/payback/ROI metrics, prices aligned with price list
  - ENHANCED: `context_builder.py` — All 8 OBJECTION_STRATEGIES rewritten with numbered steps, formulas, case references
  - ENHANCED: Static messages (welcome, help, price, portfolio, contact, clear, error) rewritten for natural human tone
  - FIX: Voice transcription and emotion analysis switched from gemini-2.0-flash to gemini-3-pro-preview (config.model_name)
  - FIX: Price consistency audit — all case study numbers aligned with price list
- **Enterprise Features (Feb 11, session 3)**:
  - NEW: `src/monitoring.py` — Performance monitoring, health checks, metrics DB, manager alerts (30-min cooldown)
  - NEW: `src/rate_limiter.py` — Token bucket rate limiting (12/min), circuit breaker (5 failures → 60s open), exponential backoff
  - NEW: `src/multilang.py` — Auto-detect language (RU/EN/UZ/KZ), localized UI strings, AI prompt suffixes
  - NEW: `src/conversation_qa.py` — Dialog quality scoring 0-1, handoff triggers (frustration/explicit/complex/high-value/low-quality)
  - NEW: `src/advanced_analytics.py` — Cohort retention, conversion attribution, revenue tracking, daily funnel, LTV/ARPU
  - NEW: `src/crm_export.py` — CSV/JSON lead export, analytics export, webhooks (new_lead/payment events)
  - INTEGRATION: Rate limiter + monitoring in message_handler, QA scoring after each AI response
  - INTEGRATION: Multilang auto-detect + prompt suffix injection in context builder
  - ADMIN: 6 new commands: /health, /qa, /analytics, /export_csv, /export_analytics, /webhook
  - BACKGROUND: Health check (10 min), metrics save (15 min), rate limiter cleanup (1 hr)
  - DB: `language` column added to `client_profiles`, new tables: bot_metrics, bot_alerts, conversation_quality, handoff_requests, revenue_events, attribution_events, crm_webhooks, crm_export_log
- **Deep Security & Performance Audit (Feb 11, session 2)**:
  - CRITICAL: `media.py` — fixed wrong import of `execute_tool_call` (was from messages.py, now tool_handlers.py)
  - SECURITY: `broadcast.py` — added `ALLOWED_BROADCAST_COLUMNS` whitelist for SQL injection protection
  - SECURITY: `payments.py` — added `_validate_payment_amount()` with payload-to-product price verification
  - BUG: `followup.py` — added `sent_today` field to `get_stats()` (was using nonexistent key in admin digest)
  - PERFORMANCE: `leads.py` — `update_activity()` consolidated to single DB connection with RETURNING
  - PERFORMANCE: `followup.py` — `generate_follow_up_message()` now uses shared `ai_client` instead of creating new Gemini instances
  - ERROR HANDLING: `session.py` — `_save_message_to_db()` truncates content at 10,000 chars
- **Code Audit & Bug Fixes (Feb 11)**:
  - FIXED: `context_builder.py` — `fetch_one` replaced with `execute_one` (undefined import bug)
  - FIXED: `tool_handlers.py` — `compare_plans` now tracks propensity scoring
  - SECURITY: `session.py` — added `ALLOWED_PROFILE_COLUMNS` whitelist for SQL safety
  - PERFORMANCE: `propensity.py` — added `score is not None` check before extra DB write
- **Admin Analytics Commands (Feb 11)**: Added `/propensity`, `/ab_results`, `/ab_detail`, `/feedback`
- **Refactoring (Feb 11)**: Extracted `src/tool_handlers.py` from messages.py (918→550 lines)
- **RAG Enhancement**: Weighted relevance scoring with multi-tag bonuses, 16 intent categories
- **A/B Testing**: Chi-square statistical significance, auto-winner detection, min 30 users/variant
- **Propensity Scoring**: All 14 tools tracked, smart social context injection

## System Architecture
The bot is developed in Python (~15,500 lines, 46 files), leveraging Telegram Bot API 9.4 for advanced features. It employs a modular handler architecture for maintainability. Key architectural decisions include a unified PostgreSQL database connection pool (1-15 connections), TTL caching for frequently accessed data, and robust analytics for funnel tracking and A/B testing.

### Project Structure
```
bot.py                          # Entry point, handler registration, background jobs
main.py                         # Simple launcher
status.py                       # Health check script
src/
├── config.py                   # Configuration from env vars
├── database.py                 # Shared PostgreSQL connection pool
├── ai_client.py                # Gemini API client (streaming, tools, agentic loop)
├── tool_handlers.py            # Centralized tool execution (14 tools)
├── context_builder.py          # Hybrid funnel, SPIN, neuro-selling context
├── knowledge_base.py           # System prompt and knowledge
├── rag.py                      # RAG knowledge base (PostgreSQL-backed)
├── session.py                  # Session management, client profiles
├── propensity.py               # Propensity scoring 0-100
├── ab_testing.py               # A/B testing with chi-square significance
├── feedback_loop.py            # Self-learning feedback loop
├── leads.py                    # Lead management and scoring
├── calculator.py               # Cost calculator (37 features)
├── pricing.py                  # Pricing display
├── keyboards.py                # Inline keyboards
├── payments.py                 # Payment system
├── loyalty.py                  # Loyalty program
├── referrals.py                # Referral system
├── tasks_tracker.py            # Gamification tasks
├── calendar_booking.py         # Calendar and consultation booking
├── social_links.py             # Social media links
├── broadcast.py                # Broadcast messaging
├── followup.py                 # Smart follow-up system
├── promocodes.py               # Promo code system
├── analytics.py                # Analytics
├── bot_api.py                  # Telegram Bot API helpers
├── cache.py                    # TTL caching
├── security.py                 # Admin access control
├── monitoring.py               # Health checks, metrics, alerts
├── rate_limiter.py             # Token bucket, circuit breaker
├── multilang.py                # Auto-detect language (RU/EN/UZ/KZ)
├── conversation_qa.py          # Dialog quality scoring, handoff
├── advanced_analytics.py       # Cohorts, attribution, LTV
├── crm_export.py               # CSV/JSON export, webhooks
├── utils.py                    # Utilities
├── handlers/
│   ├── __init__.py             # Handler exports
│   ├── messages.py             # Main message handler, agentic loop
│   ├── commands.py             # Command handlers
│   ├── callbacks.py            # Callback query handlers
│   ├── admin.py                # Admin commands (leads, stats, analytics)
│   ├── media.py                # Voice, video, photo handlers
│   └── utils.py                # Handler utilities
```

**UI/UX Decisions:**
- Custom emoji IDs are loaded from environment variables for buttons (e.g., `EMOJI_LEAD`, `EMOJI_PAYMENT`). If not set, buttons function without custom icons.
- Button styles (`constructive` (green), `destructive` (red)) are applied via `styled_button_api_kwargs()`.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 3 Pro Preview, supporting intelligent responses, real-time streaming, and function calling (14 tools).
- **Interactive Tools**: Features an interactive cost calculator, portfolio examples, and an extensive FAQ system.
- **Lead Management**: Includes automatic lead capture, manager notifications, AI-based lead auto-tagging, and priority setting.
- **Gamification & Loyalty**: Implements a system for earning coins through tasks, a tiered referral program, and a loyalty program offering discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a smart follow-up system with AI-generated personalized messages, a broadcast system with audience targeting, and multi-language support.
- **Security & Administration**: Provides admin access control, audit logging, column whitelist for SQL safety, and environment variable management for sensitive data.
- **Deployment**: Exclusively deployed on Railway using a PostgreSQL database.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Multi-step tool calling (max 4 steps) where AI chains tools and synthesizes results.
- **Session & Memory**: Persistent memory (PostgreSQL with 30-day TTL) and auto-summarization at 20+ messages. `client_profiles` table for long-term client data with `ALLOWED_PROFILE_COLUMNS` whitelist.
- **Context Builder (Hybrid Funnel)**: 3-signal hybrid funnel (keywords, semantics, score) with backslide detection, client style mirroring, proactive value delivery, industry case study matching, objection handling, and dynamic buttons.
- **Knowledge Base**: Optimized prompt with 7 core rules, 3-brain model, and ethical guardrails.
- **RAG Knowledge Base**: PostgreSQL-backed searchable knowledge base (`knowledge_chunks` table) with weighted relevance scoring (priority + tag_overlap×5 + word_hits×2 + title_bonus).
- **Dynamic Button System**: Stage-aware buttons attached to every AI response.
- **AI Client**: Gemini API with 14 function-calling tools, streaming, thinking modes (high/medium).
- **Self-Learning Feedback Loop**: Tracks AI response outcomes, conversion rates by stage/variant, learning insights.
- **Propensity Scoring**: Composite score 0-100 based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **A/B Dialog Testing**: Chi-square test with p-value (0.05/0.01/0.001), auto-winner detection, min 30 users per variant. Tests: response_style, cta_style, objection_handling, pricing_reveal, followup_tone.
- **Calendar Booking**: Availability slots and bookings with AI tools for showing/booking.
- **Social Links**: Conditional context injection (keywords or awareness/interest stage only).
- **Voice System**: Full agentic pipeline with Gemini Flash transcription, ElevenLabs v3 TTS, emotion preprocessing, abbreviation expansion, stress dictionary.
- **Guardrails**: System prompt rules prevent unauthorized promises.

**Admin Commands:**
- `/leads`, `/stats`, `/export`, `/reviews`, `/history`, `/hot`, `/tag`, `/priority` — Lead management
- `/followup`, `/broadcast` — Communication
- `/promo_create`, `/promo_list`, `/promo_off` — Promo codes
- `/propensity` — Propensity scoring dashboard (distribution + top prospects)
- `/ab_results` — A/B testing summary with significance
- `/ab_detail <test>` — Detailed A/B test stats
- `/feedback` — Learning insights and conversion analytics
- `/health` — System health: uptime, service status, error rate, AI latency, rate limiter, circuit breakers
- `/qa` — Dialog quality scores, pending handoff requests
- `/analytics [days]` — Advanced analytics: revenue, cohorts, attribution, daily funnel
- `/export_csv [days]` — Export leads to CSV file
- `/export_analytics [days]` — Export full analytics to JSON
- `/webhook add|remove` — Manage CRM webhooks for events

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, function calling, and multimodal capabilities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: (Optional) Used for voice greetings and voice responses (v3 model).
