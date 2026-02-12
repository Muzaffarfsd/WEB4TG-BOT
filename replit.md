# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot is an AI-powered support agent for WEB4TG Studio, specializing in Telegram Mini Apps. Its primary goal is to guide clients through services, provide pricing, assist in solution selection, and calculate application costs. This project aims to enhance client engagement, boost lead generation, and provide an automated, efficient support system for potential clients, thereby expanding WEB4TG Studio's reach in the Telegram Mini Apps market.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is developed in Python, utilizing Telegram Bot API 9.4. It features a modular handler architecture, a unified PostgreSQL database connection pool, and TTL caching. The system incorporates robust analytics for funnel tracking and A/B testing.

**UI/UX Decisions:**
- Custom emoji IDs are dynamically loaded from environment variables for buttons (e.g., `EMOJI_LEAD`, `EMOJI_PAYMENT`), with fallback to text-only buttons if not configured.
- Button styles (constructive/green, destructive/red) are applied through `styled_button_api_kwargs()`.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 3 Pro Preview for intelligent responses, real-time streaming, and function calling (14 tools).
- **Interactive Tools**: Includes a cost calculator, portfolio examples, and an extensive FAQ system.
- **Lead Management**: Automates lead capture, manager notifications, AI-based auto-tagging, and priority setting.
- **Gamification & Loyalty**: Implements a system for earning coins through tasks, a tiered referral program, and a loyalty program with discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a smart follow-up system with AI-generated personalized messages, a broadcast system with audience targeting, and multi-language support (RU/EN/UZ/KZ auto-detection).
- **Security & Administration**: Provides admin access control, audit logging, column whitelist for SQL safety, and environment variable management.
- **Deployment**: Exclusively deployed on Railway using a PostgreSQL database.
- **Voice System**: Integrates Gemini Flash transcription and ElevenLabs v3 TTS for voice interactions, including emotion detection and proactive voice responses during key sales moments.
- **Enterprise Features**: Includes performance monitoring, health checks, token bucket rate limiting, dialog quality scoring, and advanced analytics (cohorts, attribution, LTV, ARPU).
- **CRM Integration**: Supports CSV/JSON lead export and webhooks for new lead/payment events.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Multi-step tool calling (max 4 steps) for chaining tools and synthesizing results.
- **Session & Memory**: Persistent memory (PostgreSQL with 30-day TTL) and auto-summarization. `client_profiles` table for long-term client data with whitelisted columns.
- **Context Builder (Hybrid Funnel)**: Uses a 3-signal hybrid funnel (keywords, semantics, score) with backslide detection, client style mirroring, proactive value delivery, industry case study matching, objection handling, and dynamic buttons.
- **Knowledge Base**: Optimized prompt with 7 core rules, a 3-brain model, and ethical guardrails.
- **RAG Knowledge Base**: PostgreSQL-backed searchable knowledge base with weighted relevance scoring.
- **Dynamic Button System**: Stage-aware buttons attached to every AI response.
- **AI Client**: Gemini API with 14 function-calling tools, streaming, and different thinking modes.
- **Self-Learning Feedback Loop**: Tracks AI response outcomes, conversion rates, and learning insights.
- **Propensity Scoring**: Composite score (0-100) based on engagement velocity, session depth, tool usage, buying signals, and time decay.
- **A/B Dialog Testing**: Chi-square test with auto-winner detection for various response elements.
- **Calendar Booking**: AI-enabled availability slots and booking management.
- **Guardrails**: System prompt rules to prevent unauthorized promises.

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, function calling, and multimodal capabilities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: For voice synthesis (v3 model).