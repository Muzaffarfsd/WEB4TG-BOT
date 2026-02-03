import asyncio
import logging
import os
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.ai_client import ai_client
from src.config import config
from src.keyboards import (
    get_main_menu_keyboard, get_services_keyboard, 
    get_portfolio_keyboard, get_calculator_keyboard,
    get_lead_keyboard, get_back_keyboard, get_subscription_keyboard
)
from src.calculator import calculator_manager, FEATURES
from src.leads import lead_manager
from src.knowledge_base import (
    WELCOME_MESSAGE, HELP_MESSAGE, PRICE_MESSAGE,
    PORTFOLIO_MESSAGE, CONTACT_MESSAGE, CLEAR_MESSAGE, ERROR_MESSAGE
)

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")
if MANAGER_CHAT_ID:
    lead_manager.set_manager_chat_id(int(MANAGER_CHAT_ID))


async def send_typing_action(update: Update, duration: float = 4.0):
    try:
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Typing action error: {e}")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    session.clear_history()
    
    logger.info(f"User {user.id} ({user.username}) started bot")
    
    name = user.first_name or ""
    if name:
        welcome_text = f"""Добрый день, {name}! Меня зовут Алекс, я консультант WEB4TG Studio.

Мы разрабатываем приложения для Telegram под ключ.

Расскажите, какой у вас бизнес? Хочу понять, как лучше помочь."""
    else:
        welcome_text = """Добрый день! Меня зовут Алекс, я консультант WEB4TG Studio.

Мы разрабатываем приложения для Telegram под ключ.

Расскажите, какой у вас бизнес? Хочу понять, как лучше помочь."""
    
    await update.message.reply_text(welcome_text)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session_manager.clear_session(user_id)
    calculator_manager.reset_calculation(user_id)
    
    logger.info(f"User {user_id} cleared history")
    await update.message.reply_text(CLEAR_MESSAGE, reply_markup=get_main_menu_keyboard())


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Вот что могу показать:",
        reply_markup=get_main_menu_keyboard()
    )


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        PRICE_MESSAGE, 
        parse_mode="Markdown",
        reply_markup=get_subscription_keyboard()
    )


async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        PORTFOLIO_MESSAGE, 
        parse_mode="Markdown",
        reply_markup=get_portfolio_keyboard()
    )


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        CONTACT_MESSAGE,
        reply_markup=get_lead_keyboard()
    )


async def calc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    calc = calculator_manager.get_calculation(user_id)
    
    await update.message.reply_text(
        f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
        parse_mode="Markdown",
        reply_markup=get_calculator_keyboard()
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "menu_back":
        await query.edit_message_text(
            "Вот что могу показать:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "menu_services":
        text = """Мы разрабатываем приложения для разных типов бизнеса:

Интернет-магазины — от 7 дней
Рестораны и доставка — от 7 дней
Салоны красоты, фитнес — от 10 дней
Медицинские центры — от 12 дней

Выберите направление, расскажу подробнее:"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_services_keyboard()
        )
    
    elif data == "menu_portfolio":
        await query.edit_message_text(
            PORTFOLIO_MESSAGE,
            parse_mode="Markdown",
            reply_markup=get_portfolio_keyboard()
        )
    
    elif data == "menu_calculator":
        calc = calculator_manager.get_calculation(user_id)
        await query.edit_message_text(
            f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
            parse_mode="Markdown",
            reply_markup=get_calculator_keyboard()
        )
    
    elif data == "menu_ai_agent":
        text = """AI-агент — это умный помощник для вашего бизнеса.

Отвечает клиентам 24/7, понимает контекст, помнит историю общения. И главное — обучается на ваших данных.

Стоимость интеграции — 49 000 ₽. Окупается обычно за 6 месяцев.

Даём 7 дней бесплатного теста — можете попробовать на своём бизнесе.

Интересно?"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        text = """Отлично, давайте обсудим ваш проект!

Напишите мне:
— Какой у вас бизнес?
— Что хотите реализовать в приложении?
— Есть ли примерный бюджет?

Или нажмите кнопку — я свяжусь с вами и обсудим детали."""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("calc_"):
        calc = calculator_manager.get_calculation(user_id)
        feature_map = {
            "calc_catalog": "catalog",
            "calc_cart": "cart",
            "calc_payments": "payments",
            "calc_ai": "ai",
            "calc_delivery": "delivery",
            "calc_analytics": "analytics",
        }
        
        if data == "calc_reset":
            calc.reset()
        elif data == "calc_total":
            if calc.selected_features:
                lead = lead_manager.create_lead(
                    user_id=user_id,
                    username=query.from_user.username,
                    first_name=query.from_user.first_name
                )
                lead_manager.update_lead(
                    user_id=user_id,
                    selected_features=list(calc.selected_features),
                    estimated_cost=calc.get_total()
                )
                
                text = f"""{calc.get_summary()}

Хотите оформить заказ? Нажмите кнопку ниже!"""
                await query.edit_message_text(
                    text,
                    parse_mode="Markdown",
                    reply_markup=get_lead_keyboard()
                )
                return
        elif data in feature_map:
            calc.add_feature(feature_map[data])
        
        await query.edit_message_text(
            f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
            parse_mode="Markdown",
            reply_markup=get_calculator_keyboard()
        )
    
    elif data == "lead_submit":
        user = query.from_user
        lead = lead_manager.get_lead(user_id)
        if not lead:
            lead = lead_manager.create_lead(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name
            )
        
        notification = lead_manager.format_lead_notification(lead)
        
        manager_id = lead_manager.get_manager_chat_id()
        if manager_id:
            try:
                await context.bot.send_message(
                    chat_id=manager_id,
                    text=notification,
                    parse_mode="Markdown"
                )
                logger.info(f"Lead notification sent for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send lead notification: {e}")
        
        await query.edit_message_text(
            """Отлично, записал вашу заявку!

Свяжусь с вами в ближайшее время — обычно в течение пары часов в рабочее время.

А пока можете задавать любые вопросы, я на связи.""",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "Спрашивайте — отвечу на всё, что знаю)",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """Интернет-магазины — наша специализация.

Срок разработки: 7-10 дней. В базовый пакет входит каталог, корзина, оплата, профиль покупателя.

Дополнительно можно добавить поиск с фильтрами, избранное, push-уведомления, программу лояльности.

Примеры: Radiance (одежда), TechMart (электроника), SneakerVault (кроссовки).

Хотите посмотреть или сразу обсудим ваш проект?""",
            "service_restaurant": """Рестораны и доставку делаем часто.

Срок: 7-10 дней. Базово: меню, корзина, заказ, бронирование столов, доставка.

Можно добавить программу лояльности, push-уведомления о статусе заказа, онлайн-оплату.

Пример: DeluxeDine — красивый проект, могу показать.

Вам для какого формата — кафе, ресторан, доставка?""",
            "service_beauty": """Салоны красоты — одно из любимых направлений.

Срок: 10-12 дней. Каталог услуг, онлайн-запись, выбор мастера, профиль клиента.

Можно добавить напоминания о записи, программу лояльности, отзывы.

Пример: GlowSpa — очень красивый проект получился.

Расскажите про ваш салон, что хотите реализовать?""",
            "service_fitness": """Фитнес-клубы — интересные проекты.

Срок: 10-12 дней. Расписание занятий, абонементы, запись к тренеру, профиль с прогрессом.

Можно добавить push-уведомления, трекер тренировок, видео-тренировки.

У вас клуб или студия? Сколько направлений?""",
            "service_medical": """Медицинские проекты — сложнее, но делаем.

Срок: 12-15 дней. Список врачей, онлайн-запись, история приёмов, результаты анализов.

Можно добавить видеоконсультации, напоминания о приёме, чат с врачом.

Расскажите подробнее — клиника или частная практика?""",
            "service_services": """Сервисные бизнесы тоже разрабатываем.

Срок: 8-12 дней в зависимости от функционала. Каталог услуг, бронирование, оплата, история заказов.

Делали для автомоек, аренды авто, такси, курьерских служб.

Какой у вас сервис? Расскажите, подберём решение."""
        }
        
        text = services_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """E-Commerce проекты:

Radiance — премиум магазин одежды, стильный чёрный дизайн
TimeElite — элитные часы (Rolex, Omega, Cartier)
SneakerVault — лимитированные кроссовки (Jordan, Yeezy)
FragranceRoyale — парфюмерия
FloralArt — салон цветов

Что ближе к вашей тематике?""",
            "portfolio_services": """Проекты в сфере услуг:

GlowSpa — салон красоты, очень нежный дизайн
DeluxeDine — ресторан с доставкой
Также есть фитнес-клуб с расписанием, медцентр с записью.

Хотите посмотреть что-то конкретное?""",
            "portfolio_fintech": """Финтех проекты:

Banking — банковское приложение (счета, переводы, история операций)
OXYZ NFT — NFT маркетплейс

Вам для чего-то финансового нужно?""",
            "portfolio_education": """Образовательные проекты:

Courses — онлайн-школа с каталогом курсов, трекингом прогресса, сертификатами.

Планируете обучающий проект?"""
        }
        
        text = portfolio_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=30.0)
    )
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        voice_bytes = await file.download_as_bytearray()
        
        session = session_manager.get_session(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        from google import genai
        from google.genai import types
        from src.config import config
        from src.knowledge_base import SYSTEM_PROMPT
        
        client = genai.Client(api_key=config.gemini_api_key)
        
        audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
        text_part = types.Part(text="Это голосовое сообщение от клиента. Пойми что он сказал и сразу ответь на его вопрос как консультант Алекс из WEB4TG Studio. НЕ пиши расшифровку, НЕ пиши 'вы сказали', просто отвечай на вопрос.")
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.model_name,
            contents=[audio_part, text_part],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        
        typing_task.cancel()
        
        if response.text:
            session.add_message("user", "[Голосовое сообщение]", config.max_history_length)
            session.add_message("assistant", response.text, config.max_history_length)
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("Не удалось распознать сообщение. Попробуйте ещё раз или напишите текстом.")
            
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Voice processing error: {e}")
        await update.message.reply_text(
            "Не удалось обработать голосовое сообщение. Напишите текстом, пожалуйста."
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_message = update.message.text
    
    if not user_message or not user_message.strip():
        return
    
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    session.add_message("user", user_message, config.max_history_length)
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        thinking_level = "high" if len(user_message) > 200 else "medium"
        
        response = await ai_client.generate_response(
            messages=session.get_history(),
            thinking_level=thinking_level,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay
        )
        
        session.add_message("assistant", response, config.max_history_length)
        
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
        
        if len(response) > 4096:
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)
        
        logger.info(f"User {user.id}: processed message #{session.message_count}")
        
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Error handling message from user {user.id}: {e}")
        await update.message.reply_text(
            ERROR_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
