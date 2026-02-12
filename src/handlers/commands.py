import os
import logging
import asyncio
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
from src.knowledge_base import HELP_MESSAGE, PORTFOLIO_MESSAGE, CONTACT_MESSAGE, CLEAR_MESSAGE, PRIVACY_POLICY, FAQ_DATA, WELCOME_MESSAGE_RETURNING
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
    
    from src.context_builder import is_returning_user, get_returning_context
    is_returning = is_returning_user(user.id)
    
    if is_returning and lang_code.startswith("ru"):
        returning_ctx = get_returning_context(user.id)
        if returning_ctx:
            short_ctx = returning_ctx[:200]
            welcome_text = WELCOME_MESSAGE_RETURNING.format(
                context=f"В прошлый раз мы обсуждали: {short_ctx}..."
            )
        else:
            welcome_text = WELCOME_MESSAGE_RETURNING.format(
                context="Помню вас) Как продвигаются дела с проектом?"
            )
    elif lang_code.startswith("ru"):
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
    
    quiz_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🎯 Подобрать решение за 1 минуту", callback_data="start_quiz",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("📋 Главное меню", callback_data="menu_back")],
    ])
    await update.message.reply_text(
        welcome_text,
        reply_markup=quiz_keyboard
    )
    
    try:
        from google import genai
        from google.genai import types as genai_types
        from src.config import config as app_config

        ai_client_greet = genai.Client(api_key=app_config.gemini_api_key)
        greet_prompt = (
            f"Ты — Алекс, живой консультант WEB4TG Studio. Запиши приветственное голосовое для нового клиента{name_part}.\n\n"
            "ЗАДАЧА: поздороваться, коротко представиться, сказать что делаете (мини-аппс для Телеграм — магазины, рестораны, салоны), "
            "упомянуть что можно общаться текстом или голосовыми, и спросить чем занимается клиент.\n\n"
            "ПРАВИЛА:\n"
            "- 200-350 символов максимум (15-25 секунд речи)\n"
            "- Говори КАК ЖИВОЙ ЧЕЛОВЕК — с паузами (...), переходами ( — ), речевыми маркерами\n"
            "- Никакого markdown, emoji, списков\n"
            "- Каждый раз говори немного по-разному, не шаблонно\n"
            "- Аббревиатуры раскрывай: WEB4TG = вэб-фор-тэ-гэ\n"
            "- Верни ТОЛЬКО текст для озвучки, без комментариев"
        )
        greet_response = await asyncio.to_thread(
            ai_client_greet.models.generate_content,
            model=app_config.model_name,
            contents=[greet_prompt],
            config=genai_types.GenerateContentConfig(
                max_output_tokens=400,
                temperature=0.9
            )
        )
        voice_greeting = greet_response.text.strip() if greet_response.text else None
    except Exception as e:
        logger.warning(f"AI greeting generation failed: {e}")
        voice_greeting = None

    if not voice_greeting:
        voice_greeting = (
            f"Привет{name_part}! Меня зовут Алекс, я консультант в вэб-фор-тэ-гэ Студио. "
            f"Ну смотрите... мы делаем мини-аппс для Телеграм — магазины, рестораны, салоны и много чего ещё. "
            f"Кстати, можем общаться как удобно — текстом, голосовыми — мне без разницы. "
            f"Расскажите, чем занимаетесь? Посмотрим, чем можем быть полезны."
        )

    try:
        await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
        voice_audio = await generate_voice_response(voice_greeting, use_cache=False)
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
    tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
    current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
    
    text = f"""🎁 <b>Получи скидку до 25%!</b>

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


async def consult_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    from src.consultation import consultation_manager
    text, keyboard = consultation_manager.start_booking(user.id)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def crm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    import os
    admin_ids = [os.environ.get("MANAGER_CHAT_ID", "")]
    if str(user.id) not in admin_ids:
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return
    from src.crm_dashboard import get_crm_dashboard
    text, keyboard = get_crm_dashboard()
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def mystatus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    from src.client_dashboard import build_dashboard
    text, keyboard = build_dashboard(
        user.id,
        username=user.username or "",
        first_name=user.first_name or ""
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def brief_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    from src.brief_generator import brief_generator
    brief_generator.start_brief(user.id)
    result = brief_generator.get_current_step(user.id)
    if result:
        text, keyboard = result
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handoff_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Request manager contact - available to all users."""
    user = update.effective_user
    
    from src.leads import lead_manager, LeadPriority
    lead_manager.create_lead(user_id=user.id, username=user.username, first_name=user.first_name)
    lead_manager.update_lead(user.id, score=40, priority=LeadPriority.HOT)
    lead_manager.log_event("handoff_request", user.id)
    
    await update.message.reply_text(
        "👨‍💼 <b>Передаю вас менеджеру</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n"
        "А пока — можете написать, что именно вас интересует, и я передам ему контекст.",
        parse_mode="HTML"
    )
    
    manager_chat_id = os.environ.get("MANAGER_CHAT_ID")
    if manager_chat_id:
        try:
            from src.session import session_manager
            session = session_manager.get_session(user.id, user.username, user.first_name)
            history = session.get_history()
            
            context_lines = []
            for msg in history[-6:]:
                role = "👤" if msg.get("role") == "user" else "🤖"
                text = ""
                if isinstance(msg.get("parts"), list):
                    for part in msg["parts"]:
                        if isinstance(part, dict) and "text" in part:
                            text = part["text"][:200]
                            break
                        elif isinstance(part, str):
                            text = part[:200]
                            break
                if text:
                    context_lines.append(f"{role} {text}")
            
            lead = lead_manager.get_lead(user.id)
            tags = ""
            if lead and lead.tags:
                tags = f"\n🏷 Теги: {lead.tags}"
            
            context_text = "\n".join(context_lines) if context_lines else "Нет истории"
            
            await context.bot.send_message(
                int(manager_chat_id),
                f"🔔 <b>Запрос на менеджера!</b>\n\n"
                f"👤 {user.first_name} (@{user.username or 'нет'})\n"
                f"🆔 <code>{user.id}</code>{tags}\n\n"
                f"<b>Контекст разговора:</b>\n{context_text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Handoff notification failed: {e}")
