# WEB4TG Studio AI Agent Bot

## Overview
AI-агент поддержки для WEB4TG Studio — премиальной студии разработки Telegram Mini Apps. Бот консультирует клиентов по услугам, ценам, помогает подобрать решение и рассчитать стоимость приложения.

## Project Structure
- `bot.py` - Main bot application with Telegram handlers and OpenAI integration
- `attached_assets/ai-agent-knowledge-base_1770135411189.md` - Full knowledge base

## Bot Capabilities
- Ответы на вопросы об услугах и ценах WEB4TG Studio
- Консультации по выбору шаблона и функций
- Расчёт примерной стоимости приложения
- Примеры из портфолио
- Подведение к заказу

## Commands
- `/start` - Start the bot and reset conversation
- `/clear` - Clear conversation history

## Environment Variables Required
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather on Telegram
- `OPENAI_API_KEY` - OpenAI API key

## Running
The bot runs as a console application using polling mode.
