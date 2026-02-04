import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.config import config
from src.keyboards import (
    get_main_menu_keyboard, get_calculator_keyboard,
    get_lead_keyboard, get_quick_reply_keyboard
)
from src.calculator import calculator_manager
from src.knowledge_base import HELP_MESSAGE, PORTFOLIO_MESSAGE, CONTACT_MESSAGE, CLEAR_MESSAGE
from src.tasks_tracker import tasks_tracker
from src.referrals import referral_manager, REFERRER_REWARD, REFERRED_REWARD
from src.pricing import get_price_main_text, get_price_main_keyboard
from src.ab_testing import ab_testing
from src.keyboards import get_portfolio_keyboard
from src.analytics import analytics, FunnelEvent

from src.handlers.utils import WELCOME_MESSAGES
from src.handlers.media import generate_voice_response

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    session.clear_history()
    
    analytics.track(user.id, FunnelEvent.START)
    
    lang_code = user.language_code or "en"
    logger.info(f"User {user.id} ({user.username}) started bot, lang={lang_code}")
    
    referral_bonus_text = ""
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            referral_code = arg[4:]
            result = referral_manager.apply_referral_code(
                telegram_id=user.id,
                referral_code=referral_code,
                username=user.username,
                first_name=user.first_name
            )
            if result["success"]:
                referral_bonus_text = f"\n\n🎁 Вы получили {REFERRED_REWARD} монет по реферальному коду!"
                logger.info(f"User {user.id} applied referral code {referral_code}")
                
                referrer_id = result.get("referrer_telegram_id")
                if referrer_id:
                    try:
                        new_user_name = user.first_name or user.username or "Новый пользователь"
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 Отличные новости!\n\n"
                                 f"Ваш друг **{new_user_name}** присоединился по вашей ссылке!\n\n"
                                 f"💰 Вам начислено **+{REFERRER_REWARD} монет**\n\n"
                                 f"Продолжайте приглашать друзей и зарабатывайте ещё больше!",
                            parse_mode="Markdown"
                        )
                        logger.info(f"Sent referral notification to {referrer_id}")
                    except Exception as e:
                        logger.warning(f"Failed to notify referrer {referrer_id}: {e}")
    
    referral_manager.get_or_create_user(user.id, user.username, user.first_name)
    
    name = user.first_name or ""
    name_part = f", {name}" if name else ""
    
    welcome_variant = ab_testing.get_variant(user.id, "welcome_voice")
    ab_testing.track_event(user.id, "welcome_voice", "start_command", {"variant": welcome_variant})
    
    if lang_code.startswith("ru"):
        if welcome_variant == "b":
            welcome_text = f"""Привет{name_part}! Я AI-консультант WEB4TG Studio — премиальной студии разработки Telegram Mini Apps.

Я помогу вам:
• Подобрать готовое решение или создать уникальное приложение
• Рассчитать стоимость разработки
• Узнать о бонусах и скидках
• Посмотреть примеры наших работ

Задавайте любые вопросы!"""
        else:
            welcome_text = WELCOME_MESSAGES["ru"].format(name=name_part)
    elif lang_code.startswith("uk"):
        welcome_text = WELCOME_MESSAGES["uk"].format(name=name_part)
    else:
        welcome_text = WELCOME_MESSAGES["en"].format(name=name_part)
    
    welcome_text += referral_bonus_text
    
    pinned_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://w4tg.up.railway.app/"))]
    ])
    pinned_msg = await update.message.reply_text(
        "👋 Добро пожаловать в WEB4TG Studio!",
        reply_markup=pinned_keyboard
    )
    
    try:
        await pinned_msg.pin(disable_notification=True)
    except Exception as e:
        logger.debug(f"Could not pin message: {e}")
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_quick_reply_keyboard()
    )
    
    if welcome_variant == "b":
        voice_greeting = f"""Привет{name_part}! Рад познакомиться!
        
Я твой персональный AI-консультант. Знаешь, что самое крутое? То, что ты сейчас слушаешь — это живое доказательство того, как работает моя система!

Telegram Mini App привлёк внимание, а AI-агент удержал. Связка визуала и интеллекта — это мощно!

Я помогу выбрать решение под твой бизнес, рассчитаю стоимость и отвечу на все вопросы. Пиши или жми кнопки!"""
    else:
        voice_greeting = f"""Оо, привет{name_part}! Слушай, знаешь что самое крутое? То, что ты сейчас слушаешь это сообщение — это и есть лучшее доказательство, что моя система работает!

Подумай: тебя зацепило моё приложение, а удержал — вот этот ИИ-агент. Визуал плюс интеллект — бомбическая связка!

Я себе это внедрил и просто кайфую — забыл что такое рутина. Хочешь так же? Жми кнопку — сделаем такую же систему для твоего бизнеса!"""

    try:
        await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
        voice_audio = await generate_voice_response(voice_greeting)
        await update.message.reply_voice(voice=voice_audio)
        ab_testing.track_event(user.id, "welcome_voice", "voice_sent")
        logger.info(f"Sent voice greeting to user {user.id}")
    except Exception as e:
        ab_testing.track_event(user.id, "welcome_voice", "voice_failed")
        logger.warning(f"Failed to send voice greeting: {e}")


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
    user_id = update.effective_user.id
    analytics.track(user_id, FunnelEvent.MENU_OPEN)
    await update.message.reply_text(
        "Вот что могу показать:",
        reply_markup=get_main_menu_keyboard()
    )


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        get_price_main_text(), 
        parse_mode="Markdown",
        reply_markup=get_price_main_keyboard()
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
    analytics.track(user_id, FunnelEvent.CALCULATOR_OPEN)
    calc = calculator_manager.get_calculation(user_id)
    
    await update.message.reply_text(
        f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
        parse_mode="Markdown",
        reply_markup=get_calculator_keyboard()
    )


async def bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    progress = tasks_tracker.get_user_progress(user_id)
    tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇"}
    current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
    
    text = f"""🎁 <b>Получи скидку до 30%!</b>

{current_emoji} Твоя скидка: <b>{progress.get_discount_percent()}%</b>
💰 Монеты: <b>{progress.total_coins}</b>

<b>Как получить скидку:</b>

📱 <b>Задания</b> — подписки, лайки, комментарии
👥 <b>Рефералы</b> — приглашай друзей  
⭐ <b>Отзывы</b> — до 500 монет за видео-отзыв
🔄 <b>Постоянный клиент</b> — +5% на повторный заказ
📦 <b>Пакеты</b> — приложение + подписка = до -15%

Выбери раздел:"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Задания", callback_data="tasks_menu"),
         InlineKeyboardButton("👥 Рефералы", callback_data="referral_menu")],
        [InlineKeyboardButton("⭐ Отзывы и бонусы", callback_data="loyalty_menu")],
        [InlineKeyboardButton("📊 Мои скидки", callback_data="loyalty_my_discounts")]
    ])
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = referral_manager.get_or_create_user(user.id, user.username, user.first_name)
    
    tier_emoji = stats.get_tier_emoji()
    ref_link = referral_manager.get_bot_referral_link(stats.referral_code)
    
    text = f"""💰 **Реферальная программа**

📊 **Ваша статистика:**
{tier_emoji} Уровень: {stats.tier.value}
👥 Приглашено: {stats.total_referrals}
✅ Активных: {stats.active_referrals}
💵 Заработано: {stats.total_earnings} монет

🔗 **Ваш реферальный код:**
`{stats.referral_code}`

📤 **Ссылка для приглашения:**
{ref_link}

**Награды:**
• Вы получаете: {REFERRER_REWARD} монет за каждого друга
• Друг получает: {REFERRED_REWARD} монет при регистрации

**Уровни партнёра:**
🥉 Bronze (0-9) — 10% комиссия
🥈 Silver (10-29) — 15% комиссия  
🥇 Gold (30-99) — 20% комиссия
💎 Platinum (100+) — 30% комиссия"""

    next_tier = stats.get_next_tier_info()
    if next_tier:
        remaining, next_level = next_tier
        text += f"\n\n🎯 До уровня {next_level.value}: ещё {remaining} рефералов"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Скопировать код", callback_data="ref_copy_code")],
        [InlineKeyboardButton("📤 Поделиться ссылкой", callback_data="ref_share")],
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="ref_list")],
        [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.payments import get_payment_main_text, get_payment_keyboard
    await update.message.reply_text(
        get_payment_main_text(),
        parse_mode="Markdown",
        reply_markup=get_payment_keyboard()
    )


async def contract_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.payments import CONTRACT_PATH
    try:
        with open(CONTRACT_PATH, "rb") as contract_file:
            await update.message.reply_document(
                document=contract_file,
                filename="Договор_WEB4TG_Studio.pdf",
                caption="📄 **Договор на разработку ПО**\n\nОзнакомьтесь с условиями сотрудничества. Если есть вопросы — пишите!",
                parse_mode="Markdown"
            )
    except FileNotFoundError:
        await update.message.reply_text(
            "Договор временно недоступен. Свяжитесь с менеджером для получения."
        )
