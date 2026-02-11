# WEB4TG Studio AI Agent Bot

## Overview
The WEB4TG Studio AI Agent Bot serves as an AI-powered support agent for WEB4TG Studio, a development studio specializing in Telegram Mini Apps. Its core function is to guide clients through services, provide pricing information, help select optimal solutions, and calculate application costs. The project aims to improve client engagement, boost lead generation, and offer an automated, efficient support system for potential clients, thereby fostering business expansion within the Telegram Mini Apps market.

## User Preferences
- **Язык общения**: Всегда писать на русском языке
- **Развёртывание**: Бот работает ТОЛЬКО на Railway, НЕ запускать на Replit

## System Architecture
The bot is developed in Python, leveraging Telegram Bot API 9.4 for advanced features. It employs a modular handler architecture for maintainability. Key architectural decisions include a unified PostgreSQL database connection pool, TTL caching for frequently accessed data, and robust analytics for funnel tracking and A/B testing.

**UI/UX Decisions:**
- Custom emoji IDs are loaded from environment variables for buttons (e.g., `EMOJI_LEAD`, `EMOJI_PAYMENT`). If not set, buttons function without custom icons.
- Button styles (`constructive` (green), `destructive` (red)) are applied via `styled_button_api_kwargs()`.

**Technical Implementations & Feature Specifications:**
- **AI Integration**: Powered by Gemini 3 Pro Preview, supporting intelligent responses, real-time streaming, and function calling (calculator, portfolio, payment).
- **Interactive Tools**: Features an interactive cost calculator, portfolio examples, and an extensive FAQ system.
- **Lead Management**: Includes automatic lead capture, manager notifications, AI-based lead auto-tagging, and priority setting.
- **Gamification & Loyalty**: Implements a system for earning coins through tasks, a tiered referral program, and a loyalty program offering discounts.
- **Payment System**: Supports manual payment integration, downloadable contracts, and automated payment reminders.
- **Communication & Marketing**: Features a smart follow-up system with AI-generated personalized messages, a broadcast system with audience targeting, and multi-language support.
- **Security & Administration**: Provides admin access control, audit logging, and environment variable management for sensitive data.
- **Deployment**: Exclusively deployed on Railway using a PostgreSQL database.

**System Design Choices (Super Agent Architecture):**
- **Agentic Loop**: Utilizes a multi-step tool calling mechanism where the AI can chain tools and synthesize results.
- **Session & Memory**: Implements persistent memory (PostgreSQL with 30-day TTL) and auto-summarization. It also includes a `client_profiles` table for long-term client data.
- **Context Builder (Hybrid Funnel)**: Integrates a 3-signal hybrid funnel (keywords, semantics, score) with backslide detection, client style mirroring, proactive value delivery, industry case study matching, objection handling, and dynamic buttons.
- **Knowledge Base**: Employs an optimized prompt with 7 core rules, a 3-brain model, and ethical guardrails.
- **RAG Knowledge Base**: A PostgreSQL-backed searchable knowledge base (`knowledge_chunks` table) for intent-based tag matching and RAG knowledge injection.
- **Dynamic Button System**: Attaches stage-aware buttons to every AI response.
- **AI Client**: Interfaces with the Gemini API, offering 14 function-calling tools, streaming, and different thinking modes.
- **Self-Learning Feedback Loop**: Tracks AI response outcomes against conversion events to provide learning insights.
- **Propensity Scoring**: Calculates a real-time composite score based on user interaction metrics, influencing AI context.
- **A/B Dialog Testing**: Supports A/B testing for various dialog elements like welcome messages, CTA styles, and objection handling.
- **Calendar Booking**: Manages availability slots and bookings, including AI tools for showing slots and booking consultations.
- **Social Links**: Provides context for AI regarding social media links and loyalty tasks.
- **Voice System Architecture**: Features a full agentic pipeline for voice messages, including Gemini Flash for transcription, ElevenLabs v3 TTS with native audio tags, emotion preprocessing, and voice-aware prompts with abbreviation expansion and a stress dictionary. It also includes number-to-words conversion and speech naturalization.
- **Guardrails**: System prompt rules prevent AI from making unauthorized promises.

## External Dependencies
- **Telegram Bot API**: Version 9.4 (via `python-telegram-bot` 22.6) for core bot functionalities.
- **Google AI (Gemini 3 Pro Preview)**: For natural language processing, AI responses, function calling, and multimodal capabilities.
- **PostgreSQL**: The primary database, hosted on Railway.
- **ElevenLabs**: (Optional) Used for voice greetings and voice responses (v3 model).