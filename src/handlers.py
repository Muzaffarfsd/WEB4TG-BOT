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
    welcome_text = f"""о привет{', ' + name if name else ''}!
рад что написал)

я Алекс, работаю в WEB4TG
мы делаем приложения для телеграма

расскажи какой у тебя бизнес?
хочу понять чем могу помочь"""
    
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
        "вот что могу показать:",
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
            "вот что могу показать:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "menu_services":
        text = """так, по услугам...

делаем приложения для разных бизнесов:

магазины — обычно за 7-10 дней готово
рестораны, доставка — тоже около недели
салоны, фитнес — чуть дольше, 10-12 дней
медицина — посложнее, 12-15

выбери что ближе, расскажу подробнее"""
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
        text = """о, ai-агент это вообще крутая штука)

представь: бот который отвечает клиентам 24/7
понимает контекст, помнит историю общения
и главное — обучается на твоих данных

по цене — 49к за интеграцию
окупается обычно за полгода

кстати даём 7 дней бесплатного теста
можешь попробовать на своём бизнесе

интересно?"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        text = """супер, давай обсудим)

напиши мне:
— чем занимаешься, какой бизнес?
— что хочешь реализовать?
— есть примерный бюджет?

или просто нажми кнопку — сам напишу, обсудим"""
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
            """отлично, записал!

скоро напишу тебе
обычно за пару часов в рабочее время

а пока можешь спрашивать что угодно, я тут)""",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "давай, спрашивай)\nотвечу на всё что знаю",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """магазины это наш конёк)

делаем за 7-10 дней
в базе идёт каталог, корзина, оплата, профиль

можно добавить поиск, избранное, пуши, лояльность — это уже доп

из похожих — Radiance (одежда), TechMart (электроника), SneakerVault (кроссы)

хочешь посмотреть или сразу обсудим твой?""",
            "service_restaurant": """рестораны делаем часто)

срок 7-10 дней
базово: меню, корзина, заказ, бронь, доставка

можно добавить лояльность, пуши статуса, онлайн-оплату

есть DeluxeDine — красивый проект

тебе для какого формата? кафе, ресторан, доставка?""",
            "service_beauty": """салоны — одно из любимых направлений)

10-12 дней делается
каталог услуг, онлайн-запись, выбор мастера, профиль

можно добавить напоминалки, лояльность, отзывы

смотрел GlowSpa? оч красивый получился

расскажи про свой салон, что хочешь?""",
            "service_fitness": """фитнес — интересные проекты)

срок 10-12 дней
расписание, абонементы, запись к тренеру, профиль с прогрессом

можно добавить пуши, трекер, даже видео-тренировки

у тебя клуб или студия?""",
            "service_medical": """медицина — посложнее, но делаем)

12-15 дней срок
список врачей, запись, история, результаты анализов

можно видеоконсультации, напоминания, чат с врачом

расскажи подробнее — клиника или частная практика?""",
            "service_services": """сервисные бизнесы тоже работаем)

8-12 дней в зависимости от функций
каталог, бронирование, оплата, история

делали для автомоек, аренды авто, такси, курьеров

какой у тебя сервис?"""
        }
        
        text = services_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """из e-commerce покажу)

Radiance — премиум одежда, стильный чёрный дизайн
TimeElite — элитные часы, Rolex, Omega
SneakerVault — кроссы, Jordan, Yeezy
FragranceRoyale — парфюм
FloralArt — цветы

что ближе к твоей тематике?""",
            "portfolio_services": """по услугам есть несколько крутых)

GlowSpa — салон красоты, оч нежный дизайн
DeluxeDine — ресторан с доставкой
ещё фитнес с расписанием, медцентр с записью

хочешь покажу что-то конкретное?""",
            "portfolio_fintech": """в финтехе есть парочка)

Banking — банковское приложение
счета, переводы, история

OXYZ NFT — nft маркетплейс

тебе для чего-то финансового нужно?""",
            "portfolio_education": """в образовании пока один но хороший)

Courses — онлайн-школа
каталог курсов, прогресс, сертификаты

планируешь обучающий проект?"""
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
        "ой голосовые пока не могу слушать\nсвязь плохая) напиши текстом плз"
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
