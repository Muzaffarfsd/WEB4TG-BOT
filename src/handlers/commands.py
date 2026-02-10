import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.config import config
from src.keyboards import (
    get_main_menu_keyboard, get_calculator_keyboard,
    get_lead_keyboard, get_quick_reply_keyboard,
    get_faq_keyboard
)
from src.calculator import calculator_manager
from src.knowledge_base import HELP_MESSAGE, PORTFOLIO_MESSAGE, CONTACT_MESSAGE, CLEAR_MESSAGE, PRIVACY_POLICY, FAQ_DATA
from src.tasks_tracker import tasks_tracker
from src.referrals import referral_manager, REFERRER_REWARD, REFERRED_REWARD
from src.pricing import get_price_main_text, get_price_main_keyboard
from src.ab_testing import ab_testing
from src.keyboards import get_portfolio_keyboard
from src.analytics import analytics, FunnelEvent
from src.bot_api import copy_text_button, styled_button_api_kwargs

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
    
    from src.broadcast import broadcast_manager
    broadcast_manager.register_user(user.id, user.username, user.first_name)
    
    name = user.first_name or ""
    name_part = f", {name}" if name else ""
    
    welcome_variant = ab_testing.get_variant(user.id, "welcome_voice")
    ab_testing.track_event(user.id, "welcome_voice", "start_command", {"variant": welcome_variant})
    
    if lang_code.startswith("ru"):
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
    
    voice_greeting = f"""Привет{name_part}! Меня зовут Алекс, я консультант в WEB4TG Studio.

Мы делаем Telegram Mini Apps для бизнеса — магазины, рестораны, салоны и много чего ещё.

Можем общаться как удобно — текстом или голосовыми, мне без разницы)

Расскажи, чем занимаешься? Посмотрим, чем можем помочь."""

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
        [InlineKeyboardButton(
            "📋 Скопировать код",
            callback_data="ref_copy_code_btn",
            **copy_text_button("copy", stats.referral_code)
        )],
        [InlineKeyboardButton("📤 Поделиться ссылкой", callback_data="ref_share")],
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="ref_list")],
        [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ **Частые вопросы**\n\nВыберите интересующий вопрос:",
        parse_mode="Markdown",
        reply_markup=get_faq_keyboard()
    )


async def privacy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        PRIVACY_POLICY,
        parse_mode="Markdown"
    )


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.payments import get_payment_main_text, get_payment_keyboard
    await update.message.reply_text(
        get_payment_main_text(),
        parse_mode="Markdown",
        reply_markup=get_payment_keyboard()
    )


async def promo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.promocodes import promo_manager
    user_id = update.effective_user.id

    if not promo_manager:
        await update.message.reply_text("⚠️ Система промокодов временно недоступна")
        return

    if context.args and len(context.args) > 0:
        code = context.args[0].upper().strip()
        result = promo_manager.activate_promo(user_id, code)
        await update.message.reply_text(result["message"])
        return

    active = promo_manager.get_user_active_promo(user_id)
    if active:
        text = (f"🎟 Ваш активный промокод: <code>{active['code']}</code>\n"
                f"💰 Скидка: {active['discount_percent']}%\n\n"
                f"Чтобы активировать другой промокод, отправьте:\n"
                f"/promo КОД")
    else:
        text = ("🎟 У вас нет активных промокодов\n\n"
                "Чтобы активировать промокод, отправьте:\n"
                "/promo КОД")

    await update.message.reply_text(text, parse_mode="HTML")


async def testimonials_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.handlers.utils import loyalty_system
    reviews = loyalty_system.get_approved_reviews(limit=5)
    
    if not reviews:
        text = "⭐ <b>Отзывы клиентов</b>\n\nПока нет опубликованных отзывов. Будьте первым!"
    else:
        text = "⭐ <b>Отзывы наших клиентов</b>\n\n"
        for review in reviews:
            stars = "⭐" * 5
            review_type_name = "🎬 Видео" if review.review_type == "video" else "📝 Текст"
            text += f"{stars}\n"
            if review.comment:
                text += f"<i>«{review.comment}»</i>\n"
            text += f"{review_type_name} • {review.created_at.strftime('%d.%m.%Y')}\n\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="loyalty_review")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


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


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_text = update.inline_query.query.lower()
    
    templates = [
        {
            "id": "shop",
            "title": "🛒 Интернет-магазин",
            "description": "от 150 000 ₽ • 7-10 дней",
            "text": "🛒 **Интернет-магазин в Telegram**\n\nГотовое решение от WEB4TG Studio за 7-10 дней.\n\n• Каталог, корзина, оплата\n• Дизайн уровня Apple\n• Без комиссий маркетплейсов\n\nОт 150 000 ₽\n\n👉 @w4tg_bot — рассчитать стоимость"
        },
        {
            "id": "restaurant",
            "title": "🍽 Ресторан и доставка",
            "description": "от 180 000 ₽ • 10-12 дней",
            "text": "🍽 **Ресторан в Telegram**\n\nПриложение для ресторана от WEB4TG Studio за 10-12 дней.\n\n• Меню, бронирование, доставка\n• Онлайн-оплата\n• Push-уведомления\n\nОт 180 000 ₽\n\n👉 @w4tg_bot — узнать подробнее"
        },
        {
            "id": "beauty",
            "title": "💅 Салон красоты",
            "description": "от 170 000 ₽ • 8-12 дней",
            "text": "💅 **Салон красоты в Telegram**\n\nОнлайн-запись от WEB4TG Studio за 8-12 дней.\n\n• Каталог услуг, выбор мастера\n• Онлайн-запись и напоминания\n• Программа лояльности\n\nОт 170 000 ₽\n\n👉 @w4tg_bot — обсудить проект"
        },
        {
            "id": "fitness",
            "title": "💪 Фитнес-клуб",
            "description": "от 200 000 ₽ • 12-15 дней",
            "text": "💪 **Фитнес-клуб в Telegram**\n\nПриложение для фитнеса от WEB4TG Studio за 12-15 дней.\n\n• Расписание, абонементы, тренеры\n• Трекер прогресса\n• Push-уведомления\n\nОт 200 000 ₽\n\n👉 @w4tg_bot — рассчитать стоимость"
        },
        {
            "id": "ai_agent",
            "title": "🤖 AI-агент для бизнеса",
            "description": "49 000 ₽ • 7 дней бесплатный тест",
            "text": "🤖 **AI-агент для бизнеса**\n\nУмный помощник от WEB4TG Studio.\n\n• Отвечает клиентам 24/7\n• Понимает контекст и историю\n• Обучается на ваших данных\n\n49 000 ₽ • 7 дней бесплатного теста\n\n👉 @w4tg_bot — попробовать"
        },
        {
            "id": "about",
            "title": "ℹ️ О WEB4TG Studio",
            "description": "Премиальная студия Telegram Mini Apps",
            "text": "🚀 **WEB4TG Studio**\n\nПремиальная студия разработки Telegram Mini Apps.\n\n• Приложения за 7-15 дней\n• Дизайн уровня Apple\n• 900+ млн аудитория Telegram\n• Без комиссий маркетплейсов\n\n👉 @w4tg_bot — бесплатная консультация"
        }
    ]
    
    results = []
    for t in templates:
        if not query_text or query_text in t["title"].lower() or query_text in t["description"].lower():
            results.append(
                InlineQueryResultArticle(
                    id=t["id"],
                    title=t["title"],
                    description=t["description"],
                    input_message_content=InputTextMessageContent(
                        message_text=t["text"],
                        parse_mode="Markdown"
                    )
                )
            )
    
    await update.inline_query.answer(results, cache_time=300)
