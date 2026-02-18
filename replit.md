# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot is an AI-powered sales agent specializing in Telegram Mini Apps. Its primary goal is to enhance client engagement, boost lead generation and conversion rates, and provide automated, enterprise-grade support for WEB4TG Studio's services. The project aims to expand WEB4TG Studio's presence in the Telegram Mini Apps market by guiding clients through services, providing pricing, assisting in solution selection, and calculating application costs.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is developed in Python, utilizing Telegram Bot API 9.4. It features a modular handler architecture, a unified PostgreSQL database connection pool, and TTL caching. The system includes robust analytics for funnel tracking and A/B testing.

**UI/UX Decisions:**
- Custom emoji IDs are dynamically loaded for buttons with text-only fallbacks.
- Button styles are applied programmatically.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 2.5 Flash and Gemini 2.5 Pro with smart multi-model routing, dynamic system prompt composition, 3 temperature tiers, real-time streaming, 17 function calling tools (RAG search, client memory, competitor comparison, `request_screenshot`), response validation, active response quality control, and graceful degradation.
- **Multimodal Vision Sales Analysis**: Classifies 10 image types, applies sales-oriented prompts, generates smart buttons, and boosts lead scores based on image content, triggering manager notifications for hot leads.
- **Advanced Sales Intelligence**: Incorporates BANT qualification, decision-maker detection, negotiation stance analysis, 6 advanced closing techniques, competitor handling, and dynamic pricing.
- **Conversation Intelligence**: Features adaptive response length, smart thinking level routing, response diversity, multi-intent handling, dialog repair, decision fatigue prevention, conversation velocity tracking, and sentiment analysis.
- **Interactive Tools**: Includes a cost calculator, portfolio, competitor comparison, FAQ, onboarding quiz, brief generator, package comparison, payment calculator, timeline visualization, and savings calculator.
- **Client Experience**: Provides a personal dashboard, consultation booking with calendar UI, limited offers, trial/demo access, a gift catalog, and success stories.
- **Lead Management**: Automates lead capture, manager notifications, AI-based auto-tagging, and priority setting with propensity scoring.
- **Gamification & Loyalty**: Implements a system for earning coins, a tiered referral program, and a loyalty program with discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a 7-step adaptive follow-up system with AI-generated personalized messages, CTA buttons, voice follow-ups, adaptive scheduling, timezone-aware delivery, a broadcast system, and multi-language support (RU/EN/UZ/KZ auto-detection).
- **Proactive Engagement Engine**: Utilizes trigger-based dialog initiation with 8 trigger types, predictive engagement scoring, behavioral signal tracking, AI-generated contextual messages, and anti-spam measures.
- **Security & Administration**: Provides admin access control, audit logging, column whitelist for SQL safety, and environment variable management.
- **Voice System**: Integrates Gemini Flash transcription and ElevenLabs v3 TTS for voice interactions, including emotion detection.
- **Enterprise Features**: Includes performance monitoring, health checks, token bucket rate limiting, dialog quality scoring, and advanced analytics (cohorts, attribution, LTV prediction, churn prediction, ARPU, drop-off analysis, conversion attribution).
- **CRM Integration**: Supports CSV/JSON lead export, webhooks, and an admin CRM dashboard with lead pipeline, revenue forecasting, and client health scoring.
- **Gamification Extended**: Includes an achievements system, VIP program (5 tiers), a referral leaderboard, seasonal promos, and an AI Sales Coach.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Multi-step tool calling with smart query context routing for chaining tools.
- **Session & Memory**: Persistent memory (PostgreSQL with 30-day TTL) and auto-summarization for long-term client data.
- **Context Builder (Hybrid Funnel)**: Uses a 3-signal hybrid funnel (keywords, semantics, score) with backslide detection and 29 context signals.
- **Knowledge Base**: Optimized prompt (36,876 chars) with 20 methodologies, 13 closing techniques, 7 core rules, 3-brain model, competitor handling, dynamic pricing, negotiation stance handling, win-back strategy, decision fatigue prevention, response diversity, multi-intent handling, dialog repair, confidence scoring, communication preferences, cultural adaptation, and ethical guardrails.
- **RAG Knowledge Base**: PostgreSQL-backed searchable knowledge base with weighted relevance scoring.
- **Smart Button System**: Context-aware buttons after every AI response based on funnel stage, detected intents, and propensity score.
- **Response Validation**: Hallucination guard validates prices, timelines, guarantees, and discounts.
- **Self-Learning Feedback Loop v2.1**: Active learning with session attribution and outcome weighting. Auto-tags AI responses with closing technique, business niche, and communication style.
- **Manager Coaching**: Real-time briefing for managers on handoff, including client profile, BANT qualification, funnel stage, pain points, negotiation style, red flags, recommended closing strategy, conversation summary, and next actions.
- **Propensity Scoring**: Composite score (0-100) based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **Proactive Engagement**: Utilizes behavioral signals and trigger history, 8 deterministic trigger rules, predictive scoring, AI message generation, and anti-spam controls.
- **A/B Dialog Testing**: Chi-square test with auto-winner detection and significance monitoring.
- **Calendar Booking**: AI-enabled availability slots and booking management.
- **Guardrails**: System prompt rules to prevent unauthorized promises, response validation, and confidence scoring.

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6).
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing and AI functionalities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: For voice synthesis (v3 model).