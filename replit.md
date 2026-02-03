# WEB4TG-BOT

## Overview
A Telegram bot with AI capabilities powered by OpenAI's GPT model. The bot maintains conversation history per user and can engage in helpful dialogues.

## Project Structure
- `bot.py` - Main bot application with Telegram handlers and OpenAI integration

## Commands
- `/start` - Start the bot and reset conversation
- `/clear` - Clear conversation history

## Environment Variables Required
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather on Telegram
- `OPENAI_API_KEY` - OpenAI API key

## Running
The bot runs as a console application using polling mode.
