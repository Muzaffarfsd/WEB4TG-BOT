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
- **Self-Learning Feedback Loop**: Tracks AI response outcomes, conversion rates, and learning insights.
- **Propensity Scoring**: Composite score (0-100) based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **Proactive Engagement**: ProactiveEngagementEngine with behavioral signals + trigger history DB tables, 8 deterministic trigger rules, predictive scoring model, AI message generation, and anti-spam controls.
- **A/B Dialog Testing**: Chi-square test with auto-winner detection and significance monitoring.
- **Calendar Booking**: AI-enabled availability slots and booking management.
- **Guardrails**: System prompt rules to prevent unauthorized promises, response validation, and confidence scoring.

## Recent Changes
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