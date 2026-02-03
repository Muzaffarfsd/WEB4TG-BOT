import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

conversation_history = {}

SYSTEM_PROMPT = """You are a helpful AI assistant in a Telegram bot. 
You provide clear, concise, and helpful responses.
Be friendly and conversational while remaining informative."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text(
        "Hello! I'm an AI assistant. Send me any message and I'll respond. "
        "Use /clear to reset our conversation history."
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text("Conversation history cleared!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_message = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(conversation_history[user_id])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )

        assistant_message = response.choices[0].message.content

        conversation_history[user_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        await update.message.reply_text(assistant_message)

    except Exception as e:
        logger.error(f"Error getting AI response: {e}")
        await update.message.reply_text(
            "Sorry, I encountered an error. Please try again."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_error_handler(error_handler)

    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
