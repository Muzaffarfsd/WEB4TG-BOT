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
    welcome_text = f"""Привет{', ' + name if name else ''}! Рад что написал)

Меня зовут Алекс, я консультант WEB4TG Studio — мы делаем приложения для Telegram.

Расскажи, какой у тебя бизнес? Хочу понять, чем могу помочь"""
    
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
        text = """Так, по услугам расскажу)

Мы делаем приложения для разных бизнесов:

Магазины — обычно за 7-10 дней готово
Рестораны, доставка — тоже около недели
Салоны красоты, фитнес — чуть дольше, 10-12 дней
Медицина — там посложнее, 12-15 дней

Выбери что ближе, расскажу подробнее:"""
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
        text = """О, AI-агент — это вообще крутая штука)

Представь: бот который отвечает клиентам 24/7, понимает контекст, помнит историю общения. И главное — обучается на твоих данных.

По цене — 49к за интеграцию. Окупается обычно за полгода, у клиентов ROI около 74% за год.

Кстати, даём 7 дней бесплатного теста — можешь попробовать на своём бизнесе)

Интересно?"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        text = """Супер, давай обсудим твой проект!

Напиши мне:
— Чем занимаешься, какой бизнес?
— Что хочешь реализовать в приложении?
— Есть ли примерный бюджет?

Или просто нажми кнопку — я сам напишу, обсудим детали)"""
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
            """Отлично, записал!

Скоро напишу тебе — обычно в течение пары часов в рабочее время.

А пока можешь задавать любые вопросы, я на связи)""",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "Давай, спрашивай — отвечу на всё что знаю)",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """Интернет-магазин — это наш конёк)

Делаем за 7-10 дней. В базе идёт каталог, корзина, оплата, профиль покупателя.

Можно добавить поиск с фильтрами, избранное, пуши, программу лояльности — это уже доп.

Из похожих проектов — Radiance (одежда премиум), TechMart (электроника), SneakerVault (кроссы).

Хочешь посмотреть или сразу обсудим твой проект?""",
            "service_restaurant": """Рестораны и доставку делаем часто)

Срок примерно 7-10 дней. Базово: меню, корзина, заказ, бронь столов, доставка.

Можно добавить лояльность, пуши со статусом заказа, онлайн-оплату.

У нас есть DeluxeDine — красивый проект, могу показать.

Тебе для какого формата — кафе, ресторан, доставка?""",
            "service_beauty": """Салоны красоты — одно из любимых направлений)

Делается за 10-12 дней. Каталог услуг, онлайн-запись, выбор мастера, профиль клиента.

Можно добавить напоминалки о записи, программу лояльности, отзывы.

Смотрел наш проект GlowSpa? Очень красивый получился.

Расскажи про свой салон, что хочешь реализовать?""",
            "service_fitness": """Фитнес-клубы — интересные проекты)

Срок 10-12 дней. Расписание, абонементы, запись к тренеру, профиль с прогрессом.

Можно добавить пуши, трекер тренировок, даже видео-тренировки.

У тебя клуб или студия? Сколько направлений?""",
            "service_medical": """Медицина — посложнее, но делаем)

Срок 12-15 дней. Список врачей, запись, история приёмов, результаты анализов.

Можно добавить видеоконсультации, напоминания, чат с врачом.

Расскажи подробнее — клиника или частная практика?""",
            "service_services": """Сервисные бизнесы — тоже работаем)

Срок 8-12 дней в зависимости от функций. Каталог, бронирование, оплата, история.

Делали для автомоек, аренды авто, такси, курьеров.

Какой у тебя сервис? Расскажи, подберём решение"""
        }
        
        text = services_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """Из e-commerce покажу несколько)

Radiance — это премиум одежда, очень стильный чёрный дизайн. Digital Fashion концепция.

TimeElite — элитные часы. Rolex, Omega, Cartier. Дорого-богато)

SneakerVault — кроссовки. Jordan, Yeezy, лимитированные дропы. Для хайпбистов.

FragranceRoyale — парфюмерия. FloralArt — цветы, романтичный дизайн.

Что ближе к твоей тематике?""",
            "portfolio_services": """По услугам есть несколько крутых)

GlowSpa — салон красоты. SPA, anti-age, косметология. Очень нежный дизайн.

DeluxeDine — ресторан с доставкой. Меню, бронирование, всё как надо.

Ещё фитнес-клуб с расписанием и тренерами, медцентр с записью.

Хочешь покажу что-то конкретное?""",
            "portfolio_fintech": """В финтехе есть парочка проектов)

Banking — полноценное банковское приложение. Счета, переводы, история операций.

OXYZ NFT — NFT маркетплейс. Коллекции, покупка, продажа.

Тебе для чего-то финансового нужно?""",
            "portfolio_education": """В образовании пока один, но хороший)

Courses — онлайн-школа с каталогом курсов, трекингом прогресса, сертификатами.

Планируешь обучающий проект?"""
        }
        
        text = portfolio_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    await update.message.reply_text(
        "Ой, голосовые пока не могу слушать — связь плохая) Напиши текстом, пожалуйста!"
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
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await update.message.reply_text(chunk, reply_markup=get_back_keyboard())
                else:
                    await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response, reply_markup=get_back_keyboard())
        
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
