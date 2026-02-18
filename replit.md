# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot is an AI-powered sales agent for WEB4TG Studio, specializing in Telegram Mini Apps. Its core purpose is to guide clients through services, provide pricing, assist in solution selection, and calculate application costs. This project aims to maximize client engagement, boost lead generation and conversion rates, and provide automated, enterprise-grade support to expand WEB4TG Studio's presence in the Telegram Mini Apps market.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is developed in Python, leveraging Telegram Bot API 9.4. It features a modular handler architecture, a unified PostgreSQL database connection pool, and TTL caching. The system incorporates robust analytics for funnel tracking and A/B testing.

**UI/UX Decisions:**
- Custom emoji IDs are dynamically loaded from environment variables for buttons, with fallback to text-only buttons.
- Button styles are applied through `styled_button_api_kwargs()`.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 3 Pro Preview with smart multi-model routing, real-time streaming with retry, 17 function calling tools (RAG search, client memory, competitor comparison, request_screenshot for proactive visual analysis), response validation/hallucination guard, and graceful degradation.
- **Multimodal Vision Sales Analysis**: `src/vision_sales.py` — 10 image type classifications (app_screenshot, website_screenshot, competitor_app, design_mockup, business_photo, product_photo, menu_catalog, analytics_screenshot, document_tz, general), sales-oriented prompts per type, smart buttons per image type, lead score boosts (up to +30 for ТЗ/documents), manager notifications for hot/warm leads, integration with context_builder and propensity scoring.
- **Advanced Sales Intelligence**: Incorporates BANT qualification, decision-maker detection, negotiation stance analysis, 6 advanced closing techniques, competitor handling for 6 types, and dynamic pricing presentation.
- **Conversation Intelligence**: Features adaptive response length, smart thinking level routing, response diversity tracking, multi-intent handling, dialog repair, decision fatigue prevention, conversation velocity tracking, sentiment trajectory analysis, and question density as an interest signal.
- **Interactive Tools**: Includes a cost calculator, portfolio with before/after metrics, competitor comparison, FAQ, interactive onboarding quiz, brief generator wizard, package comparison visual, payment calculator with discount, timeline visualization, and savings calculator.
- **Client Experience**: Provides a personal dashboard (/mystatus), consultation booking with calendar UI, countdown limited offers, trial/demo access, a gift catalog with coin redemption, and a success story rotator.
- **Lead Management**: Automates lead capture, manager notifications, AI-based auto-tagging, and priority setting with propensity scoring.
- **Gamification & Loyalty**: Implements a system for earning coins, a tiered referral program, and a loyalty program with discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a 7-step adaptive follow-up system with AI-generated personalized messages, CTA buttons, voice follow-ups, adaptive scheduling, timezone-aware delivery, a broadcast system with audience targeting, and multi-language support (RU/EN/UZ/KZ auto-detection with cultural adaptation).
- **Proactive Engagement Engine**: Utilizes trigger-based dialog initiation with 8 trigger types, predictive engagement scoring, behavioral signal tracking, AI-generated contextual messages per trigger, and anti-spam measures.
- **Security & Administration**: Provides admin access control, audit logging, column whitelist for SQL safety, and environment variable management.
- **Voice System**: Integrates Gemini Flash transcription and ElevenLabs v3 TTS for voice interactions, including emotion detection.
- **Enterprise Features**: Includes performance monitoring, health checks, token bucket rate limiting, dialog quality scoring, and advanced analytics (cohorts, attribution, LTV prediction, churn prediction, ARPU, drop-off analysis, conversion attribution).
- **CRM Integration**: Supports CSV/JSON lead export, webhooks, and an admin CRM dashboard (/crm) with lead pipeline, revenue forecasting, and client health scoring.
- **Gamification Extended**: Includes an achievements system, VIP program (5 tiers), a referral leaderboard, seasonal promos, and an AI Sales Coach.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Multi-step tool calling with smart query context routing for chaining tools.
- **Session & Memory**: Persistent memory (PostgreSQL with 30-day TTL) and auto-summarization using `client_profiles` table for long-term client data.
- **Context Builder (Hybrid Funnel)**: Uses a 3-signal hybrid funnel (keywords, semantics, score) with backslide detection and 29 context signals (includes JOLT indecision, risk aversion, micro-commitments, trust velocity).
- **Knowledge Base**: Optimized prompt (36,876 chars, 5,434 words) with 20 methodologies (BANT, MEDDIC, N.E.A.T., JOLT, SPIN, Challenger, Sandler, Cialdini, Kahneman, Voss, Klaff, Gap Selling, Pink ABCs, NEPQ, Sales EQ, Tracy, Blount, Stanley, AI Persuasion Science 2025, Heath SUCCESS), 13 closing techniques, 7 core rules, 3-brain model, competitor handling, dynamic pricing, negotiation stance handling, win-back strategy, decision fatigue prevention, response diversity, multi-intent handling, dialog repair, confidence scoring, communication preferences, cultural adaptation, and ethical guardrails.
- **RAG Knowledge Base**: PostgreSQL-backed searchable knowledge base with weighted relevance scoring.
- **Smart Button System**: Context-aware buttons after every AI response based on funnel stage, detected intents, and propensity score.
- **Response Validation**: Hallucination guard validates prices, timelines, guarantees, and discounts against known data.
- **Self-Learning Feedback Loop v2.1**: Active learning with session attribution + outcome weighting. Auto-tags AI responses with closing technique (13 patterns), business niche (10 patterns), communication style (5 patterns). Session attribution credits ALL responses in 1-hour window (not just last). 16 weighted outcome types (consultation=1.0, lead=0.9, calculator=0.5, portfolio=0.3). Wilson score confidence ranking. Niche persistence to client profile. Auto-refresh every 6h. Callback button tracking (booking, payment, brief).
- **Manager Coaching**: Real-time briefing for managers on handoff — client profile, BANT qualification, funnel stage, pain points, negotiation style, red flags, recommended closing strategy (self-learning powered), conversation summary, next actions. Integrated into 5 notification touchpoints.
- **Propensity Scoring**: Composite score (0-100) based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **Proactive Engagement**: ProactiveEngagementEngine with behavioral signals + trigger history DB tables, 8 deterministic trigger rules, predictive scoring model, AI message generation, and anti-spam controls.
- **A/B Dialog Testing**: Chi-square test with auto-winner detection and significance monitoring.
- **Calendar Booking**: AI-enabled availability slots and booking management.
- **Guardrails**: System prompt rules to prevent unauthorized promises, response validation, and confidence scoring.

## Recent Changes
- **2026-02-18**: Phase 6 — Daily Digest v2 (12 секций)
  - NEW: `src/daily_digest.py` — полная переработка ежедневной сводки для админа
  - 12 секций: обзор, propensity pipeline, воронка с конверсиями, drop-off анализ, горячие лиды (топ-5), AI самообучение (техники+конверсия), revenue/LTV/ARPU, proactive engagement, follow-up, vision sales, A/B тесты, тренд vs вчера
  - Авто-сплит: при >4000 символов разбивает на 2 сообщения (Telegram лимит)
  - Graceful degradation: каждая секция независима, пропускается при отсутствии данных
  - Тренд-анализ: дельты vs вчера с процентами и стрелками (📈/📉)
  - Горячие лиды: топ-5 клиентов с propensity+lead score для немедленного контакта
  - REPLACED: старый generate_daily_digest в admin.py (6 метрик → 12 секций)
- **2026-02-18**: Phase 5 — Real-time Manager Coaching
  - NEW: `src/manager_coaching.py` — generates comprehensive coaching briefings for managers
  - 9 sections: profile, BANT, funnel/propensity, objections, negotiation style, red flags, strategy, conversation, next actions
  - INTEGRATED into 5 notification touchpoints: handoff (conversation_qa), request_manager, brief_send, consultation booking, hot lead photos
  - Strategy section uses self-learning feedback loop data (best techniques per niche, avoid list)
  - Red flags: frustration, JOLT indecision, risk aversion detection
  - Next actions: personalized based on trigger type and missing lead data
  - Graceful degradation: all sections handle missing data
- **2026-02-18**: Phase 4 — Self-Learning Loop v2.1 (session attribution + outcome weighting)
  - UPGRADED: `src/feedback_loop.py` — v2.1 with session attribution, outcome weights, niche persistence
  - NEW: Session attribution — credits ALL responses in 1-hour window, not just last one
  - NEW: 16 outcome weights (consultation=1.0 → discount_checked=0.2) for weighted conversion ranking
  - NEW: `outcome_weight` column in response_outcomes for weighted analysis
  - NEW: Callback outcome tracking in `src/handlers/callbacks.py` (payment, booking, brief_send)
  - NEW: All 17 AI tools now record outcomes (was only 3)
  - NEW: Niche persistence — saves detected niche to client_profiles via session module
  - NEW: Auto-refresh niche memory every 6 hours (triggered lazily from get_adaptive_instructions)
  - UPGRADED: `_get_user_niche` checks client_profiles first, then response_tags history
  - UPGRADED: `get_best_techniques` returns weighted_rate alongside raw_rate
  - INTEGRATED: `context_builder.py` calls `get_adaptive_instructions()` as 30th context signal
  - 13 closing technique patterns, 10 niche patterns, 5 style patterns, 16 outcome weights
  - All tests pass: 8/8 techniques, 8/8 niches, 16/16 weights, Wilson score verified
- **2026-02-18**: Phase 3 — Multimodal Vision Sales Analysis
  - NEW: `src/vision_sales.py` — 10 image types with tailored sales prompts, smart buttons, lead scoring, manager notifications
  - UPGRADED: `src/handlers/media.py` — photo_handler rewritten with 2-step flow: AI classification → sales-oriented analysis
  - NEW tool: `request_screenshot` in ai_client.py (17th tool) — AI proactively asks clients for photos for visual analysis
  - NEW: `PropensityScorer.boost_score()` for image-driven lead scoring boosts
  - Hot leads (design_mockup, document_tz) trigger instant manager notifications
  - REMOVED: `src/demo_preview.py` and `generate_demo_preview` tool — Pillow mock-ups not production quality
  - All modified files compile with 0 errors
- **2026-02-18**: World-class sales AI upgrade (Round 2 — final)
  - SYSTEM_PROMPT expanded to 36,876 chars (5,434 words) with 20 total methodologies
  - Round 1: Cialdini, Kahneman, Voss, SPIN, Challenger, Sandler, Klaff, Heath, Tracy, Blount, Stanley, Gap Selling, Sales EQ
  - Round 2: +JOLT Effect, +MEDDIC, +N.E.A.T. Selling, +Daniel Pink ABCs, +NEPQ, +AI Persuasion Science 2025
  - 13 closing techniques (added JOLT close, Negative reverse close, NEPQ commitment close)
  - 9 new psychological detectors total in context_builder.py (1,719 lines):
    - Round 1: buying signals (3 levels), Cialdini triggers (5 principles), communication preference, multi-intent, confidence scoring
    - Round 2: JOLT indecision detection, risk aversion (2 levels), micro-commitment tracking (Persuasive Cascading), trust velocity scoring
  - 29 total context signals in build_full_context()
  - Data integrity enforced: removed unverified statistics, all claims from verified sources only
  - All 8 core modules compile with 0 errors, 11 unit tests pass
- **2026-02-16**: Full LSP refactoring — fixed 765 type diagnostics across 10 files
  - Added null guards for `update.effective_user`, `update.message`, `update.callback_query` in all handlers
  - Fixed `is_rate_limit_error` function (was missing, now defined in `ai_client.py`)
  - Corrected import paths: `loyalty_system` from `handlers/utils`, `referral_manager` from `referrals`
  - Fixed Gemini API type annotations with proper `type: ignore` comments
  - Fixed `database.py` connection null safety and Optional parameter types
  - Fixed `context_builder.py`: Optional function params, `max()` key argument, `get_events` hasattr guard
  - All 10 files pass Python compilation and 0 LSP diagnostics

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6).
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing and AI functionalities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: For voice synthesis (v3 model).