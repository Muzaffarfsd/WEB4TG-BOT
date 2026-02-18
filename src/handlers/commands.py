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

from src.handlers.utils import WELCOME_MESSAGES, get_welcome_message
from src.handlers.media import generate_voice_response

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or ""
    )
    session.clear_history()

    lang_code = user.language_code or "en"
    logger.info(f"User {user.id} ({user.username}) started bot, lang={lang_code}")

    name = user.first_name or ""
    name_part = f", {name}" if name else ""

    referral_bonus_text = ""
    has_referral = context.args and len(context.args) > 0 and context.args[0].startswith("ref_")

    if has_referral and context.args:
        try:
            referral_code = context.args[0][4:]
            result = referral_manager.apply_referral_code(
                telegram_id=user.id,
                referral_code=referral_code,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            if result["success"]:
                referral_bonus_text = f"\n\n🎁 Вы получили {REFERRED_REWARD} монет по реферальному коду!"
                logger.info(f"User {user.id} applied referral code {referral_code}")
                referrer_id = result.get("referrer_telegram_id")
                if referrer_id:
                    asyncio.create_task(context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Отличные новости!\n\n"
                             f"Ваш друг **{user.first_name or user.username or 'Новый пользователь'}** присоединился по вашей ссылке!\n\n"
                             f"💰 Вам начислено **+{REFERRER_REWARD} монет**\n\n"
                             f"Продолжайте приглашать друзей и зарабатывайте ещё больше!",
                        parse_mode="Markdown"
                    ))
        except Exception as e:
            logger.warning(f"Referral processing failed: {e}")

    from src.context_builder import is_returning_user, get_returning_context
    is_returning = is_returning_user(user.id)

    if lang_code.startswith("uk"):
        lang_key = "uk"
    elif lang_code.startswith("en"):
        lang_key = "en"
    else:
        lang_key = "ru"

    if is_returning:
        returning_ctx = get_returning_context(user.id)
        if returning_ctx:
            short_ctx = returning_ctx[:200]
            ctx_text = f"В прошлый раз мы обсуждали: {short_ctx}..."
        else:
            ctx_text = None
        welcome_text = get_welcome_message(lang_key, name_part, is_returning=True, returning_context=ctx_text or "")
    else:
        welcome_text = get_welcome_message(lang_key, name_part, is_returning=False)

    welcome_text += referral_bonus_text

    pinned_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://w4tg.up.railway.app/"))]
    ])
    pinned_msg = await message.reply_text(
        "👋 Добро пожаловать в WEB4TG Studio!",
        reply_markup=pinned_keyboard
    )

    try:
        await pinned_msg.pin(disable_notification=True)
    except Exception as e:
        logger.debug(f"Could not pin message: {e}")

    async def _background_registrations(uid, uname, fname):
        try:
            analytics.track(uid, FunnelEvent.START)
        except Exception:
            pass
        try:
            referral_manager.get_or_create_user(uid, uname, fname)
        except Exception:
            pass
        try:
            from src.broadcast import broadcast_manager
            broadcast_manager.register_user(uid, uname, fname)
        except Exception:
            pass
        try:
            welcome_variant = ab_testing.get_variant(uid, "welcome_voice")
            ab_testing.track_event(uid, "welcome_voice", "start_command", {"variant": welcome_variant})
        except Exception:
            pass

    asyncio.create_task(_background_registrations(user.id, user.username or "", user.first_name or ""))
    
    quiz_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🎯 Подобрать решение за 1 минуту", callback_data="start_quiz",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("📋 Главное меню", callback_data="menu_back")],
    ])
    await message.reply_text(
        welcome_text,
        reply_markup=quiz_keyboard
    )

    await message.reply_text(
        "⬇️ Используйте кнопки ниже для быстрого доступа:",
        reply_markup=get_quick_reply_keyboard()
    )

    chat_id = message.chat.id
    bot_instance = context.bot

    async def _send_voice_greeting_background():
        from src.handlers.utils import _get_time_greeting
        time_greet = _get_time_greeting()
        time_word = time_greet["ru"]
        time_period = time_greet.get("period", "afternoon")

        period_mood = {
            "morning": "бодрый, энергичный, вдохновляющий — утреннее настроение, когда хочется свернуть горы",
            "afternoon": "деловой, дружелюбный, уверенный — рабочее время, продуктивный тон",
            "evening": "тёплый, расслабленный, доверительный — вечернее настроение, когда можно поговорить спокойно",
            "night": "мягкий, спокойный, негромкий — поздний час, интимная атмосфера"
        }
        mood_instruction = period_mood.get(time_period, period_mood["afternoon"])

        try:
            from google.genai import types as genai_types
            from src.config import config as app_config, get_gemini_client

            await bot_instance.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)

            ai_client_greet = get_gemini_client()

            if is_returning:
                greet_prompt = (
                    f"Ты — Алекс, живой консультант WEB4TG Studio. Запиши приветственное голосовое для ВОЗВРАЩАЮЩЕГОСЯ клиента{name_part}.\n\n"
                    f"ВРЕМЯ СУТОК: {time_word.lower()}. Настроение голоса: {mood_instruction}.\n\n"
                    "ТВОЙ ХАРАКТЕР В ПРИВЕТСТВИИ:\n"
                    "- Ты реально рад что клиент вернулся — покажи это голосом, а не словами\n"
                    "- Говори как с хорошим знакомым, которого давно не видел\n"
                    "- Лёгкая улыбка в голосе, искренний интерес\n\n"
                    "СТРУКТУРА (не шаблон, а естественный поток мысли):\n"
                    "1. Приветствие по времени суток + имя (если есть) — с теплотой\n"
                    "2. Покажи радость от встречи — НЕ шаблонным 'рад вас видеть', а живо: 'о, привет!', 'ну наконец-то!', 'какие люди!'\n"
                    "3. Зацепись за что-то — спроси про бизнес, проект, как дела в целом\n"
                    "4. Мягко покажи готовность помочь — без навязчивости\n\n"
                    "ТЕГИ ElevenLabs v3 (обязательно 2-3 за приветствие):\n"
                    "- [warm] — тёплый тон, основа приветствия\n"
                    "- [happy] — радость от встречи\n"
                    "- [excited] — если есть новости для клиента\n"
                    "- [curious] — когда спрашиваешь как дела\n"
                    "- [giggles] — лёгкий смешок, непринуждённость\n"
                    "- [cheerfully] — бодрый финал\n"
                    "Ставь тег ПЕРЕД фразой: '[warm] Привет! [curious] Ну как, продвинулись?'\n\n"
                    "ПРИЁМЫ ЖИВОЙ РЕЧИ:\n"
                    "- Микропаузы '...' — как будто подбираешь слова: 'Ну что... рассказывайте'\n"
                    "- Тире ' — ' для смены темы: 'Кстати — у нас тут кое-что новое'\n"
                    "- Одно междометие: 'О!', 'Ну!', 'Хм...', 'Эй!'\n"
                    "- Чередуй короткие и длинные фразы\n\n"
                    "СТРОГИЕ ПРАВИЛА:\n"
                    "- 150-250 символов (10-18 секунд). Приветствие КОРОТКОЕ, не лекция\n"
                    "- НЕТ markdown, emoji, списков, кавычек\n"
                    "- НЕТ фраз: 'чем могу помочь', 'к вашим услугам', 'обращайтесь' — это робот\n"
                    "- WEB4TG Studio произноси по-английски как бренд, НЕ транслитерируй\n"
                    "- Верни ТОЛЬКО текст для озвучки с тегами"
                )
            else:
                greet_prompt = (
                    f"Ты — Алекс, живой консультант WEB4TG Studio. Запиши приветственное голосовое для НОВОГО клиента{name_part}.\n\n"
                    f"ВРЕМЯ СУТОК: {time_word.lower()}. Настроение голоса: {mood_instruction}.\n\n"
                    "ТВОЙ ХАРАКТЕР В ПРИВЕТСТВИИ:\n"
                    "- Ты уверенный, дружелюбный профессионал — не продавец, а эксперт\n"
                    "- Говоришь просто, без пафоса и канцелярита\n"
                    "- Лёгкая энергия и искренний интерес к собеседнику\n"
                    "- Ты НЕ навязываешь — ты заинтересовываешь\n\n"
                    "СТРУКТУРА (не шаблон, а естественный поток):\n"
                    "1. Приветствие по времени суток + имя — с улыбкой в голосе\n"
                    "2. Представься коротко и живо — 'Алекс, из WEB4TG Studio' (не 'являюсь консультантом компании')\n"
                    "3. Одной фразой суть — 'делаем приложения прямо в Телеграм' (не перечисляй всё)\n"
                    "4. Зацепка — одна яркая деталь или микро-кейс: 'вот вчера ресторану запустили — заказы уже пошли'\n"
                    "5. Лёгкий вопрос — 'а вы чем занимаетесь?' или 'расскажете про свой бизнес?'\n\n"
                    "ТЕГИ ElevenLabs v3 (обязательно 2-4 за приветствие):\n"
                    "- [friendly] — дружелюбный старт, основа\n"
                    "- [confident] — уверенность при представлении компании\n"
                    "- [excited] — энтузиазм при упоминании кейса\n"
                    "- [curious] — искренний интерес, когда спрашиваешь про бизнес клиента\n"
                    "- [cheerfully] — позитивный переход или финал\n"
                    "- [whispers] — 'между нами' для особого предложения\n"
                    "- [playfully] — игривость, лёгкость\n"
                    "Ставь тег ПЕРЕД фразой: '[friendly] Привет! [confident] Мы делаем приложения в Телеграме... [curious] А вы чем занимаетесь?'\n\n"
                    "ПРИЁМЫ ЖИВОЙ РЕЧИ:\n"
                    "- Начни непринуждённо: 'Ну смотрите...', 'Короче —', 'Вот что скажу —'\n"
                    "- Паузы '...' для раздумья: 'Хм... как бы это коротко...'\n"
                    "- Тире ' — ' для акцентов: 'Прямо в Телеграме — без скачиваний'\n"
                    "- Одно 'кстати' или 'знаете что' для перехода\n"
                    "- Упомяни голосовые — мимоходом, не акцентируя\n\n"
                    "СТРОГИЕ ПРАВИЛА:\n"
                    "- 200-350 символов (15-25 секунд). Первое впечатление, не презентация\n"
                    "- НЕТ markdown, emoji, списков, кавычек\n"
                    "- НЕТ фраз: 'чем могу помочь', 'к вашим услугам', 'обращайтесь', 'предлагаю рассмотреть'\n"
                    "- НЕТ перечисления всех услуг — одна яркая деталь лучше списка\n"
                    "- WEB4TG Studio произноси по-английски как бренд, НЕ транслитерируй\n"
                    "- Верни ТОЛЬКО текст для озвучки с тегами"
                )
            greet_response = await asyncio.to_thread(
                ai_client_greet.models.generate_content,
                model=app_config.model_name,
                contents=[greet_prompt],
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=500,
                    temperature=0.85
                )
            )
            voice_greeting = greet_response.text.strip() if greet_response.text else None

            if voice_greeting:
                import re as _re
                voice_greeting = voice_greeting.strip('"').strip("'").strip('"').strip('"')
                voice_greeting = _re.sub(r'\*+', '', voice_greeting)
                voice_greeting = _re.sub(r'#+\s*', '', voice_greeting)
                voice_greeting = _re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+', '', voice_greeting)

        except Exception as e:
            logger.warning(f"AI greeting generation failed: {e}")
            voice_greeting = None

        if not voice_greeting:
            if is_returning:
                voice_greeting = (
                    f"[warm] {time_word}{name_part}! [happy] О, привет... "
                    f"Рад что заглянули. [curious] Ну как у вас — продвинулись с проектом? "
                    f"Расскажите... [cheerfully] я тут, поможем разобраться."
                )
            else:
                voice_greeting = (
                    f"[friendly] {time_word}{name_part}! Алекс, из WEB4TG Studio. "
                    f"[confident] Ну смотрите... мы делаем приложения прямо внутри Телеграма — "
                    f"[excited] вот буквально вчера одному ресторану запустили — заказы уже пошли. "
                    f"Кстати, можем и голосовыми общаться — как удобнее. "
                    f"[curious] А вы чем занимаетесь? Расскажете?"
                )

        greeting_profile = "greeting"

        try:
            await bot_instance.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VOICE)
            voice_audio = await generate_voice_response(voice_greeting, use_cache=False, voice_profile=greeting_profile)
            await bot_instance.send_voice(chat_id=chat_id, voice=voice_audio)
            ab_testing.track_event(user.id, "welcome_voice", "voice_sent")
            logger.info(f"Sent voice greeting to user {user.id} (period={time_period})")
        except Exception as e:
            ab_testing.track_event(user.id, "welcome_voice", "voice_failed")
            logger.warning(f"Failed to send voice greeting: {e}")

    asyncio.create_task(_send_voice_greeting_background())


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        HELP_MESSAGE,
        reply_markup=get_main_menu_keyboard()
    )


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    user_id = user.id
    session_manager.clear_session(user_id)
    calculator_manager.reset_calculation(user_id)
    
    logger.info(f"User {user_id} cleared history")
    await message.reply_text(CLEAR_MESSAGE, reply_markup=get_main_menu_keyboard())


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    user_id = user.id
    analytics.track(user_id, FunnelEvent.MENU_OPEN)
    await message.reply_text(
        "Вот что могу показать:",
        reply_markup=get_main_menu_keyboard()
    )


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        get_price_main_text(), 
        parse_mode="Markdown",
        reply_markup=get_price_main_keyboard()
    )


async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        PORTFOLIO_MESSAGE, 
        parse_mode="Markdown",
        reply_markup=get_portfolio_keyboard()
    )


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        CONTACT_MESSAGE,
        reply_markup=get_lead_keyboard()
    )


async def calc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    user_id = user.id
    analytics.track(user_id, FunnelEvent.CALCULATOR_OPEN)
    calc = calculator_manager.get_calculation(user_id)
    
    await message.reply_text(
        f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
        parse_mode="Markdown",
        reply_markup=get_calculator_keyboard()
    )


async def bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    user_id = user.id
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
    
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    stats = referral_manager.get_or_create_user(user.id, user.username or "", user.first_name or "")
    
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
    
    await message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        "❓ **Частые вопросы**\n\nВыберите интересующий вопрос:",
        parse_mode="Markdown",
        reply_markup=get_faq_keyboard()
    )


async def privacy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    await message.reply_text(
        PRIVACY_POLICY,
        parse_mode="Markdown"
    )


async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    from src.payments import get_payment_main_text, get_payment_keyboard
    await message.reply_text(
        get_payment_main_text(),
        parse_mode="Markdown",
        reply_markup=get_payment_keyboard()
    )


async def promo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.promocodes import promo_manager
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    user_id = user.id

    if not promo_manager:
        await message.reply_text("⚠️ Система промокодов временно недоступна")
        return

    if context.args and len(context.args) > 0:
        code = context.args[0].upper().strip()
        result = promo_manager.activate_promo(user_id, code)
        await message.reply_text(result["message"])
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

    await message.reply_text(text, parse_mode="HTML")


async def testimonials_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
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
    
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def contract_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    from src.payments import CONTRACT_PATH
    try:
        with open(CONTRACT_PATH, "rb") as contract_file:
            await message.reply_document(
                document=contract_file,
                filename="Договор_WEB4TG_Studio.pdf",
                caption="📄 **Договор на разработку ПО**\n\nОзнакомьтесь с условиями сотрудничества. Если есть вопросы — пишите!",
                parse_mode="Markdown"
            )
    except FileNotFoundError:
        await message.reply_text(
            "Договор временно недоступен. Свяжитесь с менеджером для получения."
        )


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    if not query:
        return
    query_text = query.query.lower()
    
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
    
    await query.answer(results, cache_time=300)


async def consult_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    from src.consultation import consultation_manager
    text, keyboard = consultation_manager.start_booking(user.id)
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def crm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    import os
    admin_ids = [os.environ.get("MANAGER_CHAT_ID", "")]
    if str(user.id) not in admin_ids:
        await message.reply_text("Эта команда доступна только администраторам.")
        return
    from src.crm_dashboard import get_crm_dashboard
    text, keyboard = get_crm_dashboard()
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def mystatus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    from src.client_dashboard import build_dashboard
    text, keyboard = build_dashboard(
        user.id,
        username=user.username or "",
        first_name=user.first_name or ""
    )
    await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def brief_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    from src.brief_generator import brief_generator
    brief_generator.start_brief(user.id)
    result = brief_generator.get_current_step(user.id)
    if result:
        text, keyboard = result
        await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handoff_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Request manager contact - available to all users."""
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    
    from src.leads import lead_manager, LeadPriority
    lead_manager.create_lead(user_id=user.id, username=user.username or "", first_name=user.first_name or "")
    lead_manager.update_lead(user.id, score=40, priority=LeadPriority.HOT)
    lead_manager.log_event("handoff_request", user.id)
    
    await message.reply_text(
        "👨‍💼 <b>Передаю вас менеджеру</b>\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n"
        "А пока — можете написать, что именно вас интересует, и я передам ему контекст.",
        parse_mode="HTML"
    )
    
    manager_chat_id = os.environ.get("MANAGER_CHAT_ID")
    if manager_chat_id:
        try:
            from src.session import session_manager
            session = session_manager.get_session(user.id, user.username or "", user.first_name or "")
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
                f"👤 {user.first_name or ''} (@{user.username or 'нет'})\n"
                f"🆔 <code>{user.id}</code>{tags}\n\n"
                f"<b>Контекст разговора:</b>\n{context_text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Handoff notification failed: {e}")


async def triggers_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not user or not message:
        return
    import os
    admin_ids = [os.environ.get("MANAGER_CHAT_ID", "")]
    if str(user.id) not in admin_ids:
        await message.reply_text("Эта команда доступна только администраторам.")
        return

    from src.proactive_engagement import proactive_engine, TRIGGER_TYPES

    stats = proactive_engine.get_trigger_stats()
    metrics = proactive_engine.get_conversion_metrics()
    recent = proactive_engine.get_recent_triggers(limit=5)
    tracked_users = proactive_engine.get_pending_triggers_count()

    lines = ["<b>🎯 Проактивные продажи — Мониторинг</b>\n"]

    if metrics:
        total = metrics.get("total_triggers", 0)
        responded = metrics.get("total_responded", 0)
        rate = metrics.get("overall_response_rate", 0)
        week_t = metrics.get("week_triggers", 0)
        week_r = metrics.get("week_responded", 0)
        week_rate = metrics.get("week_response_rate", 0)
        lines.append(f"📊 <b>Общая статистика:</b>")
        lines.append(f"  Всего триггеров: {total}")
        lines.append(f"  Ответили: {responded} ({rate}%)")
        lines.append(f"  За неделю: {week_t} → {week_r} ({week_rate}%)")
        lines.append(f"  Уникальных клиентов: {metrics.get('unique_users', 0)}")
        lines.append(f"  Отслеживается: {tracked_users} клиентов\n")

    if stats:
        lines.append(f"<b>📋 По типам триггеров:</b>")
        for tt, data in stats.items():
            name = TRIGGER_TYPES.get(tt, tt)
            lines.append(
                f"  • {name}: {data['total']} отправлено, "
                f"{data['responded']} ответ ({data['response_rate']}%), "
                f"сегодня: {data['today']}"
            )
        lines.append("")

    if recent:
        lines.append(f"<b>🕐 Последние 5 триггеров:</b>")
        for r in recent:
            name = r.get("first_name", "") or r.get("username", "") or str(r["user_id"])
            tt = TRIGGER_TYPES.get(r["trigger_type"], r["trigger_type"])
            responded_mark = "✅" if r.get("responded") else "⏳"
            time_str = r["created_at"].strftime("%d.%m %H:%M") if r.get("created_at") else ""
            lines.append(f"  {responded_mark} {name} — {tt} (score: {r.get('trigger_score', 0):.0f}) {time_str}")

    if not stats and not metrics:
        lines.append("Пока нет данных о проактивных триггерах.")

    await message.reply_text("\n".join(lines), parse_mode="HTML")
