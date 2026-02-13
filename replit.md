# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot is a world-class AI-powered sales agent for WEB4TG Studio, specializing in Telegram Mini Apps. Its primary goal is to guide clients through services, provide pricing, assist in solution selection, and calculate application costs using advanced neuro-selling techniques. This project aims to maximize client engagement, boost lead generation and conversion rates, and provide an automated, enterprise-grade support system for potential clients, thereby expanding WEB4TG Studio's reach in the Telegram Mini Apps market.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is developed in Python, utilizing Telegram Bot API 9.4. It features a modular handler architecture, a unified PostgreSQL database connection pool, and TTL caching. The system incorporates robust analytics for funnel tracking, A/B testing, and 40 world-class AI sales improvements.

**UI/UX Decisions:**
- Custom emoji IDs are dynamically loaded from environment variables for buttons (e.g., `EMOJI_LEAD`, `EMOJI_PAYMENT`), with fallback to text-only buttons if not configured.
- Button styles (constructive/green, destructive/red) are applied through `styled_button_api_kwargs()`.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 3 Pro Preview with smart multi-model routing (fast model for FAQ, thinking model for objections/closing), real-time streaming with retry, function calling (17 tools including RAG search, client memory, and competitor comparison), response validation/hallucination guard, and graceful degradation with contextual fallbacks.
- **Advanced Sales Intelligence**: BANT qualification framework (Budget/Authority/Need/Timeline), decision-maker (LPR) detection, negotiation stance analysis (hard/soft/analytical/emotional), 6 advanced closing techniques (trial, assumptive, alternative, Ben Franklin, puppy dog, summary), competitor handling for 6 types (freelancer, agency, constructor, nocode, inhouse, general), dynamic pricing presentation with anchoring.
- **Conversation Intelligence**: Adaptive response length based on user message patterns, smart thinking level routing, response diversity tracking (anti-repetition), multi-intent handling, dialog repair, decision fatigue prevention, conversation velocity tracking, sentiment trajectory analysis, question density as interest signal.
- **Interactive Tools**: Cost calculator, portfolio with before/after metrics and ROI, competitor comparison, FAQ, interactive onboarding quiz (4 steps), brief generator wizard (6 steps), package comparison visual, payment calculator with discount, timeline visualization, savings calculator.
- **Client Experience**: Personal dashboard (/mystatus with coins/tier/discount/referrals), consultation booking with calendar UI, countdown limited offers with urgency mechanics, trial/demo access, gift catalog with coin redemption, success story rotator, share/referral with preview.
- **Lead Management**: Automates lead capture, manager notifications, AI-based auto-tagging, and priority setting with propensity scoring and buying signal decay.
- **Gamification & Loyalty**: Implements a system for earning coins through tasks, a tiered referral program with quality scoring, and a loyalty program with discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a smart follow-up system with AI-generated personalized messages, win-back strategy for cold clients, a broadcast system with audience targeting, and multi-language support (RU/EN/UZ/KZ auto-detection with cultural adaptation).
- **Security & Administration**: Provides admin access control, audit logging, column whitelist for SQL safety, and environment variable management.
- **Deployment**: Exclusively deployed on Railway using a PostgreSQL database.
- **Voice System**: Integrates Gemini Flash transcription and ElevenLabs v3 TTS for voice interactions, including emotion detection and proactive voice responses during key sales moments.
- **Enterprise Features**: Includes performance monitoring, health checks, token bucket rate limiting, dialog quality scoring, and advanced analytics (cohorts, attribution, LTV prediction, churn prediction, ARPU, drop-off analysis, conversion attribution).
- **CRM Integration**: Supports CSV/JSON lead export, webhooks, admin CRM dashboard (/crm) with lead pipeline, revenue forecasting, and client health scoring.
- **Gamification Extended**: Achievements system (10 achievements), VIP program (5 tiers: Bronze→Diamond), referral leaderboard, seasonal promos (New Year/Spring/Summer/Black Friday), AI Sales Coach.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Multi-step tool calling (max 4 steps) with smart query context routing for chaining tools and synthesizing results.
- **Session & Memory**: Persistent memory (PostgreSQL with 30-day TTL) and auto-summarization. `client_profiles` table for long-term client data with whitelisted columns.
- **Context Builder (Hybrid Funnel)**: Uses a 3-signal hybrid funnel (keywords, semantics, score) with backslide detection, client style mirroring, proactive value delivery, industry case study matching, objection handling, dynamic buttons, BANT signals, decision-maker detection, negotiation stance, competitor context, budget signals, question density, decision fatigue detection, smart upsell, response diversity tracking, conversation velocity, sentiment trajectory, and win-back context. Total: 25 context signals.
- **Knowledge Base**: Optimized prompt with 7 core rules, a 3-brain model, BANT qualification, advanced closing techniques, competitor handling, dynamic pricing, negotiation stance handling, win-back strategy, decision fatigue prevention, response diversity, multi-intent handling, dialog repair, confidence scoring, communication preferences, cultural adaptation, and ethical guardrails.
- **RAG Knowledge Base**: PostgreSQL-backed searchable knowledge base with weighted relevance scoring.
- **Smart Button System**: Context-aware buttons after every AI response based on funnel stage, detected intents (price/portfolio/buy/objection/booking/competitor), and propensity score. Stage-aware fallback buttons.
- **AI Client**: Gemini API with 17 function-calling tools (including competitor comparison), streaming, smart multi-model routing, response validation/hallucination guard, quality checks, and graceful degradation with contextual fallbacks.
- **Response Validation**: Hallucination guard validates prices (templates 150-200k, subscriptions 9.9-24.9k/mo), timelines (7-30 days), guarantees, and discounts against known data. Auto-corrects invalid claims.
- **Self-Learning Feedback Loop**: Tracks AI response outcomes, conversion rates, conversion attribution, and learning insights.
- **Propensity Scoring**: Composite score (0-100) based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **A/B Dialog Testing**: Chi-square test with auto-winner detection, significance monitoring (p<0.05), and comprehensive test results summary.
- **Calendar Booking**: AI-enabled availability slots and booking management.
- **Guardrails**: System prompt rules to prevent unauthorized promises, response validation, and confidence scoring.

## File Structure (~20,000+ lines total)
- `bot.py` — Main entry point, application setup, command registration
- `src/knowledge_base.py` — SYSTEM_PROMPT with 14 advanced sales sections, WELCOME_MESSAGE
- `src/context_builder.py` — 25 context signals including 12 new detectors
- `src/ai_client.py` — AIClient with multi-model routing, agentic loop, response validation
- `src/handlers/messages.py` — Message handler with smart buttons integration
- `src/handlers/callbacks.py` — Callback query handlers (all interactive flows)
- `src/handlers/commands.py` — Command handlers (/start, /mystatus, /brief, /consult, /crm, etc.)
- `src/handlers/media.py` — Media/voice handlers
- `src/handlers/admin.py` — Admin panel
- `src/tool_handlers.py` — Tool execution including competitor comparison
- `src/onboarding.py` — Interactive onboarding quiz (4 steps with ROI recommendation)
- `src/client_dashboard.py` — Client dashboard /mystatus (coins, tier, activity, propensity)
- `src/brief_generator.py` — Interactive brief wizard (6 steps with lead creation)
- `src/smart_buttons.py` — Context-aware smart buttons after AI responses
- `src/portfolio_showcase.py` — Portfolio with before/after metrics and ROI data
- `src/package_comparison.py` — Visual package comparison, payment calc, timeline viz
- `src/consultation.py` — Consultation booking with calendar UI
- `src/countdown_offers.py` — Countdown limited-time offers with urgency mechanics
- `src/trial_demo.py` — Trial/demo access + savings calculator
- `src/crm_dashboard.py` — Admin CRM dashboard with revenue forecasting + health score
- `src/achievements.py` — Achievements, VIP program, leaderboard, seasonal promos
- `src/kp_generator.py` — PDF commercial proposal generator (Gemini AI text + fpdf2 PDF rendering)
- `src/ai_tools_extended.py` — AI case study generator, KP text prompts, AI coach
- `src/social_features.py` — Story rotator, share, gift catalog
- `src/advanced_analytics.py` — Analytics with drop-off, LTV/churn prediction
- `src/ab_testing.py` — A/B testing with significance monitoring
- `src/referrals.py` — Referral system with quality scoring
- `src/propensity.py` — Propensity scoring
- `src/feedback_loop.py` — Self-learning feedback loop
- `src/followup.py` — Smart follow-up with win-back
- `src/session.py` — Session management
- `src/rag.py` — RAG knowledge base
- `src/tasks_tracker.py` — Gamification tasks
- `src/database.py` — Database connection pool
- `src/config.py` — Configuration from environment variables
- `src/pricing.py` — Pricing calculator
- `src/payments.py` — Payment system
- `src/calculator.py` — Feature-based cost calculator

## Recent Changes (February 2026)
- **40 World-Class AI Improvements** implemented across all modules (BANT, LPR, negotiation, velocity, sentiment, etc.)
- **34 Functional Improvements** (Batch 2 of project):
  - Interactive onboarding quiz with personalized ROI recommendations
  - Client dashboard /mystatus with gamification progress
  - Brief generator wizard (6-step interactive project brief)
  - Context-aware smart buttons after every AI response
  - Portfolio showcase with before/after metrics and ROI data
  - Visual package comparison (Starter/Business/Premium)
  - Payment calculator with loyalty discount application
  - Timeline visualization for each package
  - Consultation booking with calendar UI and manager notifications
  - Countdown limited-time offers with urgency mechanics
  - Trial/Demo access with demo bot links
  - Savings calculator (time, revenue, errors)
  - CRM dashboard for admins with lead pipeline and revenue forecasting
  - Client health scoring (healthy/at-risk/churning)
  - Achievement system (10 achievements with coin rewards)
  - VIP program (5 tiers: Bronze→Diamond with progressive discounts)
  - Referral leaderboard
  - Seasonal promotions (New Year/Spring/Summer/Black Friday)
  - AI Case Study Generator prompts
  - AI Sales Coach prompts
  - AI KP (Commercial Proposal) Generator — text prompts
  - PDF Commercial Proposal auto-generation (Gemini AI text + fpdf2 PDF with DejaVu Cyrillic fonts, VIP discount, timeline, payment schedule)
  - Success story rotator (non-repeating)
  - Share/invite system with referral preview
  - Gift catalog with coin redemption (4 gifts)
  - Modified /start to offer quiz as primary CTA
- **Performance Optimizations** (February 2026):
  - Singleton Gemini client (`get_gemini_client()`) — eliminated 5 redundant `genai.Client()` creations across files
  - /start voice greeting moved to background `asyncio.create_task` — instant welcome text, voice arrives async
  - Non-critical DB operations (analytics, broadcast, AB testing) moved to background tasks in /start
  - Post-response analytics (auto-tag, feedback loop, QA scoring) moved to background in message handler
  - TTL cache (30s) for heavy context queries: RAG knowledge, client profiles, propensity scores
  - Voice emotion analysis skipped for short texts (<200 chars), uses fast model for longer texts
  - Session data snapshots for background tasks to prevent race conditions

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, function calling, and multimodal capabilities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: For voice synthesis (v3 model).
