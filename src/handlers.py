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
    
    welcome_text = f"""Привет, {user.first_name or 'друг'}! 

Я AI-ассистент **WEB4TG Studio** — премиальной студии разработки Telegram Mini Apps.

Чем могу помочь?"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


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
        "Главное меню:",
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
            "Главное меню:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "menu_services":
        text = """**Наши услуги:**

Мы создаём Telegram Mini Apps для любого бизнеса:

• **Интернет-магазины** — от 7 дней
• **Рестораны и доставка** — от 7 дней  
• **Салоны красоты** — от 10 дней
• **Фитнес-клубы** — от 10 дней
• **Медицинские центры** — от 12 дней
• **Сервисы услуг** — от 8 дней

Выберите тип для подробностей:"""
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
        text = """**AI-агент для вашего бизнеса**

Умный помощник, который работает 24/7:

✓ Ответ менее 2 секунд
✓ Понимает 150+ языков
✓ Самообучается на ваших данных
✓ Шифрование и GDPR

**Стоимость:** 49 000 ₽
**ROI:** 74% за первый год
**Окупаемость:** 6 месяцев

🎁 **Пробный период:** 7 дней бесплатно!"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        text = """**Оставить заявку**

Готовы начать свой проект?

Напишите мне:
1. Какой у вас бизнес?
2. Какие функции нужны?
3. Примерный бюджет?

Или нажмите кнопку ниже, и наш менеджер свяжется с вами!"""
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
            """✅ **Заявка отправлена!**

Наш менеджер свяжется с вами в ближайшее время.

Время ответа: до 2 часов в рабочее время.

А пока вы можете задать мне любые вопросы о наших услугах!""",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "Напишите ваш вопрос, и я отвечу!",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """**Интернет-магазин**

Срок разработки: 7-10 дней

Базовый функционал:
• Каталог товаров
• Корзина и оформление
• Приём платежей
• Профиль клиента

Дополнительно:
• Поиск и фильтры
• Избранное
• Push-уведомления
• Программа лояльности

Примеры: Radiance, TechMart, SneakerVault""",
            "service_restaurant": """**Ресторан / Доставка еды**

Срок разработки: 7-10 дней

Базовый функционал:
• Меню с категориями
• Корзина и заказ
• Бронирование столов
• Доставка

Дополнительно:
• Программа лояльности
• Push о статусе заказа
• Онлайн-оплата

Примеры: DeluxeDine""",
            "service_beauty": """**Салон красоты / SPA**

Срок разработки: 10-12 дней

Базовый функционал:
• Каталог услуг
• Онлайн-запись
• Выбор мастера
• Профиль клиента

Дополнительно:
• Напоминания о записи
• Программа лояльности
• Отзывы и рейтинги

Примеры: GlowSpa""",
            "service_fitness": """**Фитнес-клуб**

Срок разработки: 10-12 дней

Базовый функционал:
• Расписание занятий
• Абонементы
• Запись к тренеру
• Профиль с прогрессом

Дополнительно:
• Push-уведомления
• Трекер тренировок
• Видео-тренировки""",
            "service_medical": """**Медицинский центр**

Срок разработки: 12-15 дней

Базовый функционал:
• Список врачей
• Онлайн-запись
• История приёмов
• Результаты анализов

Дополнительно:
• Видеоконсультации
• Напоминания о приёме
• Чат с врачом""",
            "service_services": """**Сервис услуг**

Срок разработки: 8-12 дней

Базовый функционал:
• Каталог услуг
• Онлайн-бронирование
• Оплата
• История заказов

Примеры:
• Автомойка
• Аренда авто
• Такси
• Курьерская доставка"""
        }
        
        text = services_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """**E-Commerce проекты:**

• **Radiance** — премиум магазин одежды
  Digital Fashion, чёрный дизайн
  
• **TimeElite** — элитные часы
  Rolex, Omega, Cartier
  
• **SneakerVault** — кроссовки
  Jordan, Yeezy, лимитированные дропы
  
• **FragranceRoyale** — парфюмерия
  Премиальные ароматы
  
• **FloralArt** — цветы и букеты
  Романтичный розовый дизайн""",
            "portfolio_services": """**Сервисные проекты:**

• **GlowSpa** — салон красоты
  SPA, anti-age, косметология
  
• **DeluxeDine** — ресторан
  Меню, доставка, бронирование
  
• **Fitness Club** — фитнес
  Расписание, тренеры, абонементы
  
• **Medical Center** — медицина
  Врачи, запись, история""",
            "portfolio_fintech": """**Финтех проекты:**

• **Banking** — банковское приложение
  Счета, переводы, история
  
• **OXYZ NFT** — NFT маркетплейс
  Коллекции, покупка, продажа""",
            "portfolio_education": """**Образовательные проекты:**

• **Courses** — онлайн-школа
  Каталог курсов, прогресс, сертификаты"""
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
        "🎤 Голосовые сообщения пока в разработке. Напишите текстом, и я отвечу!"
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
