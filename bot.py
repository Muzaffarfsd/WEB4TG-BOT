#!/usr/bin/env python3
import asyncio
import logging
from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, InlineQueryHandler, ContextTypes, filters,
    PreCheckoutQueryHandler
)

from telegram.error import Forbidden
from src.config import config
from src.handlers import (
    start_handler, help_handler, clear_handler, menu_handler,
    price_handler, portfolio_handler, contact_handler, calc_handler,
    message_handler, callback_handler, voice_handler, video_handler, photo_handler, error_handler,
    leads_handler, stats_handler, export_handler, reviews_handler,
    history_handler, hot_handler, tag_handler, priority_handler,
    referral_handler, payment_handler, contract_handler, bonus_handler,
    followup_handler, broadcast_handler, privacy_handler, inline_query_handler,
    faq_handler, promo_handler, testimonials_handler,
    promo_create_handler, promo_list_handler, promo_off_handler,
    generate_daily_digest, handoff_handler, mystatus_handler, brief_handler, consult_handler, crm_handler,
    get_emoji_id_handler, sticker_emoji_handler,
    propensity_dashboard_handler, ab_results_handler,
    ab_detail_handler, feedback_insights_handler,
    health_handler, qa_handler, advanced_stats_handler,
    export_csv_handler, export_analytics_handler, webhook_handler,
    triggers_handler,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    """Set up bot commands menu after initialization."""
    from src.bot_api import get_api_version
    logger.info(f"Bot API target version: {get_api_version()}")

    commands = [
        BotCommand("start", "⚡ Начать"),
        BotCommand("menu", "✦ Все услуги и функции"),
        BotCommand("price", "✦ Цены и пакеты"),
        BotCommand("portfolio", "✦ Примеры работ"),
        BotCommand("mystatus", "✦ Мой кабинет"),
        BotCommand("consult", "✨ Бесплатная консультация"),
    ]
    await application.bot.set_my_commands(commands)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Bot commands menu configured")

    try:
        from src.broadcast import broadcast_manager
        resumed = await broadcast_manager.resume_broadcast(application.bot)
        if resumed:
            logger.info(f"Resumed {len(resumed)} interrupted broadcast(s) on startup")
    except Exception as e:
        logger.error(f"Failed to resume broadcasts on startup: {e}")

    if application.job_queue:
        application.job_queue.run_repeating(
            process_follow_ups,
            interval=300,
            first=60
        )
        logger.info("Follow-up background job scheduled")

        application.job_queue.run_repeating(
            process_payment_reminders,
            interval=3600,
            first=300
        )
        logger.info("Payment reminder job scheduled (every hour)")

        from datetime import time as dt_time
        import pytz
        try:
            tz = pytz.timezone("Asia/Bishkek")
            application.job_queue.run_daily(
                send_daily_digest,
                time=dt_time(hour=9, minute=0, tzinfo=tz),
            )
            logger.info("Daily digest scheduled at 09:00 Asia/Bishkek")
        except Exception as e:
            logger.warning(f"Failed to schedule daily digest: {e}")

        from src.monitoring import periodic_health_check, periodic_metrics_save
        application.job_queue.run_repeating(
            periodic_health_check,
            interval=600,
            first=120
        )
        logger.info("Health check job scheduled (every 10 min)")

        application.job_queue.run_repeating(
            periodic_metrics_save,
            interval=900,
            first=300
        )
        logger.info("Metrics save job scheduled (every 15 min)")

        application.job_queue.run_repeating(
            process_proactive_triggers,
            interval=180,
            first=90
        )
        logger.info("Proactive engagement job scheduled (every 3 min)")

        from src.rate_limiter import rate_limiter
        async def cleanup_rate_limiter(context):
            rate_limiter.cleanup()
        application.job_queue.run_repeating(
            cleanup_rate_limiter,
            interval=3600,
            first=1800
        )
    else:
        logger.warning("JobQueue not available, background jobs disabled")


async def send_daily_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    import os
    manager_id = os.environ.get("MANAGER_CHAT_ID")
    if not manager_id:
        return
    try:
        await generate_daily_digest(context.bot, int(manager_id))
    except Exception as e:
        logger.error(f"Daily digest error: {e}")


async def process_payment_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from src.payments import get_pending_payment_reminders, mark_payment_reminded
        pending = get_pending_payment_reminders(hours=24)
        for user_id in pending:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="💳 Напоминание: вы запросили реквизиты для оплаты.\n\n"
                         "Если вы уже оплатили — нажмите «Я оплатил» в меню оплаты (/payment).\n"
                         "Если есть вопросы — просто напишите, помогу!"
                )
                mark_payment_reminded(user_id)
                logger.info(f"Payment reminder sent to {user_id}")
            except Forbidden:
                mark_payment_reminded(user_id)
                from src.broadcast import broadcast_manager
                broadcast_manager.mark_blocked(user_id)
            except Exception as e:
                logger.error(f"Failed to send payment reminder to {user_id}: {e}")
    except Exception as e:
        logger.error(f"Payment reminder processing error: {e}")


def _user_prefers_voice(user_id: int) -> bool:
    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile and profile.get("prefers_voice") == "true":
            return True
    except Exception:
        pass
    return False


async def _generate_voice_supplement(text_message: str, msg_type: str = "followup") -> str:
    """Generate a short emotional voice supplement — a hook to pull the person back into dialog about Telegram Mini App development."""
    import re as _re

    safe_text = (text_message or "").strip()
    if len(safe_text) < 10:
        safe_text = "общее сообщение о возможностях Telegram Mini App для бизнеса"
    elif len(safe_text) > 500:
        safe_text = safe_text[:500] + "..."

    try:
        from google.genai import types as genai_types
        from src.config import config as app_config, get_gemini_client

        client = get_gemini_client()

        prompt = (
            "Ты — Алекс, живой консультант WEB4TG Studio. Записываешь КОРОТКОЕ голосовое к текстовому сообщению.\n\n"
            f"ТЕКСТ (уже отправлен клиенту):\n{safe_text}\n\n"
            "ЦЕЛЬ: Вернуть человека в диалог и подвести к разработке Telegram Mini App. "
            "Голосовое — это крючок. Человек прочитал текст, слышит голос — и ОТВЕЧАЕТ.\n\n"
            "ОБЯЗАТЕЛЬНО используй МИНИМУМ ОДИН психологический триггер:\n"
            "1. CURIOSITY GAP — незавершённая мысль, 'у меня тут кое-что для тебя... напиши — расскажу'\n"
            "2. SOCIAL PROOF — 'тут один бизнес похожий на твой уже запустился и результат огонь'\n"
            "3. FOMO — 'это предложение скоро закроется', 'осталось пару мест на этот месяц'\n"
            "4. SCARCITY — 'берём только 3 проекта в месяц', 'пока есть окно'\n"
            "5. RECIPROCITY — 'я тут подготовил кое-что специально для тебя'\n\n"
            "СТРАТЕГИЧЕСКОЕ ИСПОЛЬЗОВАНИЕ ТЕГОВ (выбери ОДИН самый точный):\n"
            "- [whispers] — для эксклюзивности и секретов: 'между нами...', 'тебе первому говорю'\n"
            "- [excited] — для срочности и wow-момента: 'слушай, это реально крутая штука'\n"
            "- [curious] — для незавершённых мыслей: 'я тут подумал...', 'знаешь что...'\n"
            "- [warm] — для личного отношения: 'серьёзно, мне не всё равно'\n"
            "- [confident] — для экспертности: 'я точно знаю как это сработает'\n"
            "- [friendly] — для лёгкости: 'просто глянь, без обязательств'\n\n"
            "АНТИПАТТЕРНЫ (НИКОГДА так не делай):\n"
            "- НЕ повторяй текст сообщения\n"
            "- НЕ будь банальным: 'это интересно', 'стоит внимания' — ЗАПРЕЩЕНО\n"
            "- НЕ звучи как продажник или бот\n"
            "- НЕ используй больше одного тега\n\n"
            "ФОРМАТ: [тег] текст\n"
            "ДЛИНА: 40-80 символов чистого текста (без тега). Одна-две фразы.\n"
            "ОБЯЗАТЕЛЬНО заканчивай мини-CTA: 'напиши', 'глянь', 'ответь', 'давай обсудим'\n"
            "НЕТ markdown, emoji, кавычек. WEB4TG Studio — по-английски.\n"
            "Верни ТОЛЬКО текст для озвучки."
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=app_config.model_name,
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                max_output_tokens=120,
                temperature=0.7
            )
        )

        if response.text:
            result = _validate_voice_supplement(response.text, _re)
            if result:
                return result

    except Exception as e:
        logger.warning(f"Voice supplement generation failed: {e}")

    return ""


_VALID_TAGS = {"warm", "excited", "curious", "confident", "whispers", "friendly"}
_CTA_WORDS = {"напиши", "глянь", "ответь", "обсудим", "покажу", "расскажу", "скину", "давай"}


def _validate_voice_supplement(raw_text: str, _re=None) -> str:
    """Hard validation: single tag, CTA present, 35-90 chars clean text."""
    if _re is None:
        import re as _re

    result = raw_text.strip().strip('"').strip("'").strip('\u201c').strip('\u201d')
    result = _re.sub(r'\*+', '', result)
    result = _re.sub(r'#+\s*', '', result)
    result = _re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]+', '', result)
    result = result.strip()

    tags_found = _re.findall(r'\[(\w+)\]', result)
    if len(tags_found) > 1:
        first_tag = tags_found[0]
        result = _re.sub(r'\[\w+\]\s*', '', result)
        if first_tag in _VALID_TAGS:
            result = f"[{first_tag}] {result.strip()}"
        tags_found = [first_tag] if first_tag in _VALID_TAGS else []

    if tags_found and tags_found[0] not in _VALID_TAGS:
        result = _re.sub(r'\[\w+\]\s*', '', result).strip()

    clean = _re.sub(r'\[\w[\w\s]*?\]\s*', '', result).strip()
    if not (35 <= len(clean) <= 90):
        return ""

    clean_lower = clean.lower()
    has_cta = any(w in clean_lower for w in _CTA_WORDS)
    if not has_cta:
        return ""

    return result


VOICE_SUPPLEMENT_FALLBACKS_CURIOSITY = [
    "[curious] Слушай, я тут нашёл кое-что для твоего бизнеса... напиши — расскажу",
    "[curious] Знаешь что... у меня появилась идея, но лучше голосом — ответь мне",
    "[curious] Тут одна штука которая может изменить подход к клиентам — давай покажу",
]
VOICE_SUPPLEMENT_FALLBACKS_SOCIAL_PROOF = [
    "[warm] Один бизнес как твой запустил мини-апп и за месяц окупил вложения — покажу",
    "[confident] Три проекта похожих на твой уже работают и приносят заказы — давай обсудим",
    "[excited] Клиент запустился две недели назад — конверсия выросла на 40 процентов, глянь",
]
VOICE_SUPPLEMENT_FALLBACKS_FOMO = [
    "[excited] В этом месяце ещё есть окно — потом очередь на два месяца, напиши",
    "[whispers] Между нами — текущие условия действуют до конца недели, напиши пока есть",
    "[excited] Сейчас акция на запуск — через неделю цены вырастут, давай обсудим",
]
VOICE_SUPPLEMENT_FALLBACKS_SCARCITY = [
    "[whispers] Мы берём только три проекта в месяц... одно место осталось, напиши",
    "[confident] Сейчас свободный слот на разработку — такое бывает раз в два месяца, давай обсудим",
]
VOICE_SUPPLEMENT_FALLBACKS_RECIPROCITY = [
    "[warm] Я тут подготовил расчёт специально под твой бизнес — напиши, скину",
    "[friendly] Сделал подборку идей с ценами под твою нишу — глянь, это бесплатно, ответь мне",
    "[warm] Подобрал три кейса из твоей сферы с результатами — давай покажу",
]

def _get_random_voice_fallback() -> str:
    import random
    all_fallbacks = (
        VOICE_SUPPLEMENT_FALLBACKS_CURIOSITY +
        VOICE_SUPPLEMENT_FALLBACKS_SOCIAL_PROOF +
        VOICE_SUPPLEMENT_FALLBACKS_FOMO +
        VOICE_SUPPLEMENT_FALLBACKS_SCARCITY +
        VOICE_SUPPLEMENT_FALLBACKS_RECIPROCITY
    )
    return random.choice(all_fallbacks)


async def _send_voice_supplement(bot, user_id: int, text_message: str) -> bool:
    """Send a short voice supplement AFTER the text message."""
    try:
        from src.config import config
        if not config.elevenlabs_api_key:
            return False
        from src.handlers.media import generate_voice_response
        from telegram.constants import ChatAction

        voice_text = await _generate_voice_supplement(text_message)
        if not voice_text:
            voice_text = _get_random_voice_fallback()

        await bot.send_chat_action(chat_id=user_id, action=ChatAction.RECORD_VOICE)
        voice_audio = await generate_voice_response(voice_text, voice_profile="greeting")
        await bot.send_voice(chat_id=user_id, voice=voice_audio)
        return True
    except Exception as e:
        logger.warning(f"Voice supplement failed for {user_id}: {e}")
        return False


def _get_followup_cta_keyboard(follow_up_number: int):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if follow_up_number <= 2:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✦ Посмотреть портфолио", callback_data="menu_portfolio")],
            [InlineKeyboardButton("⚡ Рассчитать стоимость", callback_data="menu_calculator")],
        ])
    elif follow_up_number <= 4:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Бесплатная консультация", callback_data="book_consultation")],
            [InlineKeyboardButton("✦ Посмотреть кейсы", callback_data="menu_portfolio")],
        ])
    elif follow_up_number <= 6:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Написать Алексу", callback_data="menu_ai_agent")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Узнать подробнее", callback_data="menu_services")],
            [InlineKeyboardButton("✨ Бесплатный аудит", callback_data="book_consultation")],
        ])


async def process_follow_ups(context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.followup import follow_up_manager

    try:
        due = follow_up_manager.get_due_follow_ups()
        for fu in due:
            try:
                result = await follow_up_manager.generate_follow_up_message(
                    fu['user_id'], fu['follow_up_number']
                )
                if isinstance(result, tuple):
                    message, ab_variant = result
                else:
                    message, ab_variant = result, ""

                cta_keyboard = _get_followup_cta_keyboard(fu['follow_up_number'])

                await context.bot.send_message(
                    chat_id=fu['user_id'],
                    text=message,
                    reply_markup=cta_keyboard
                )

                voice_sent = False
                try:
                    voice_sent = await _send_voice_supplement(
                        context.bot, fu['user_id'], message
                    )
                except Exception as ve:
                    logger.debug(f"Voice supplement skipped for {fu['user_id']}: {ve}")

                follow_up_manager.mark_sent(fu['id'], message, ab_variant=ab_variant)

                from src.leads import lead_manager
                lead_manager.save_message(fu['user_id'], "assistant", message)
                lead_manager.log_event("followup_sent", fu['user_id'], {
                    "followup_number": fu['follow_up_number'],
                    "voice": voice_sent,
                    "ab_variant": ab_variant
                })

                follow_up_manager.schedule_follow_up(fu['user_id'])

                logger.info(f"Sent follow-up #{fu['follow_up_number']} to user {fu['user_id']} (voice={voice_sent}, variant={ab_variant})")

                await asyncio.sleep(2)
            except Forbidden:
                follow_up_manager.cancel_for_blocked_user(fu['user_id'])
                from src.broadcast import broadcast_manager
                broadcast_manager.mark_blocked(fu['user_id'])
                logger.info(f"User {fu['user_id']} blocked bot, cancelled follow-ups")
            except Exception as e:
                if "Forbidden" in str(type(e).__name__) or "blocked" in str(e).lower():
                    follow_up_manager.cancel_for_blocked_user(fu['user_id'])
                    from src.broadcast import broadcast_manager
                    broadcast_manager.mark_blocked(fu['user_id'])
                    logger.info(f"User {fu['user_id']} blocked bot, cancelled follow-ups")
                else:
                    logger.error(f"Failed to send follow-up to {fu['user_id']}: {e}")
    except Exception as e:
        logger.error(f"Follow-up processing error: {e}")


def _get_trigger_cta_keyboard(trigger_type: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if trigger_type in ("cart_abandonment", "high_intent_no_action"):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Бесплатная консультация", callback_data="book_consultation")],
            [InlineKeyboardButton("⚡ Рассчитать стоимость", callback_data="menu_calculator")],
        ])
    elif trigger_type in ("competitor_research",):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✦ Сравнить решения", callback_data="menu_compare")],
            [InlineKeyboardButton("✦ Наши преимущества", callback_data="menu_portfolio")],
        ])
    elif trigger_type in ("funnel_stall", "engagement_drop"):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✦ Посмотреть портфолио", callback_data="menu_portfolio")],
            [InlineKeyboardButton("⚡ Задать вопрос", callback_data="menu_ai_agent")],
        ])
    elif trigger_type in ("comeback_window", "warm_reactivation"):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Что нового?", callback_data="menu_services")],
            [InlineKeyboardButton("✨ Бесплатный аудит", callback_data="book_consultation")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✦ Узнать подробнее", callback_data="menu_services")],
        ])


async def process_proactive_triggers(context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.proactive_engagement import proactive_engine

    try:
        triggered = proactive_engine.evaluate_triggers()
        if not triggered:
            return

        for trigger in triggered[:5]:
            try:
                message = await proactive_engine.generate_trigger_message(trigger)
                user_id = trigger["user_id"]

                cta_keyboard = _get_trigger_cta_keyboard(trigger["trigger_type"])

                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=cta_keyboard
                )

                voice_sent = False
                try:
                    voice_sent = await _send_voice_supplement(
                        context.bot, user_id, message
                    )
                except Exception as ve:
                    logger.debug(f"Voice supplement skipped for proactive {user_id}: {ve}")

                proactive_engine.record_trigger_sent(
                    user_id, trigger["trigger_type"],
                    trigger["score"], message
                )

                from src.leads import lead_manager
                lead_manager.save_message(user_id, "assistant", message)
                lead_manager.log_event("proactive_trigger", user_id, {
                    "trigger_type": trigger["trigger_type"],
                    "score": trigger["score"],
                    "voice": voice_sent
                })

                logger.info(
                    f"Proactive trigger '{trigger['trigger_type']}' sent to {user_id} "
                    f"(score={trigger['score']:.0f}, voice={voice_sent})"
                )

                await asyncio.sleep(2)
            except Forbidden:
                from src.broadcast import broadcast_manager
                broadcast_manager.mark_blocked(trigger["user_id"])
                logger.info(f"User {trigger['user_id']} blocked bot, skipping proactive trigger")
            except Exception as e:
                if "Forbidden" in str(type(e).__name__) or "blocked" in str(e).lower():
                    from src.broadcast import broadcast_manager
                    broadcast_manager.mark_blocked(trigger["user_id"])
                else:
                    logger.error(f"Failed to send proactive trigger to {trigger['user_id']}: {e}")
    except Exception as e:
        logger.error(f"Proactive trigger processing error: {e}")


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment
    from src.payments import handle_successful_payment
    
    result_text = await handle_successful_payment(
        user_id=update.effective_user.id,
        payload=payment.invoice_payload,
        total_amount=payment.total_amount
    )
    await update.message.reply_text(result_text)
    
    import os
    manager_id = os.environ.get("MANAGER_CHAT_ID")
    if manager_id:
        try:
            user = update.effective_user
            await context.bot.send_message(
                int(manager_id),
                f"💫 <b>Оплата Stars!</b>\n\n"
                f"👤 {user.first_name} (@{user.username or 'нет'})\n"
                f"💰 {payment.total_amount} ⭐\n"
                f"📦 {payment.invoice_payload}",
                parse_mode="HTML"
            )
        except Exception:
            pass


def main() -> None:
    application = Application.builder().token(config.telegram_token).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("clear", clear_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("price", price_handler))
    application.add_handler(CommandHandler("portfolio", portfolio_handler))
    application.add_handler(CommandHandler("contact", contact_handler))
    application.add_handler(CommandHandler("calc", calc_handler))
    application.add_handler(CommandHandler("leads", leads_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("export", export_handler))
    application.add_handler(CommandHandler("reviews", reviews_handler))
    application.add_handler(CommandHandler("history", history_handler))
    application.add_handler(CommandHandler("hot", hot_handler))
    application.add_handler(CommandHandler("tag", tag_handler))
    application.add_handler(CommandHandler("priority", priority_handler))
    application.add_handler(CommandHandler("referral", referral_handler))
    application.add_handler(CommandHandler("bonus", bonus_handler))
    application.add_handler(CommandHandler("payment", payment_handler))
    application.add_handler(CommandHandler("contract", contract_handler))
    application.add_handler(CommandHandler("faq", faq_handler))
    application.add_handler(CommandHandler("promo", promo_handler))
    application.add_handler(CommandHandler("testimonials", testimonials_handler))
    application.add_handler(CommandHandler("promo_create", promo_create_handler))
    application.add_handler(CommandHandler("promo_list", promo_list_handler))
    application.add_handler(CommandHandler("promo_off", promo_off_handler))
    application.add_handler(CommandHandler("followup", followup_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_handler))
    application.add_handler(CommandHandler("privacy", privacy_handler))
    application.add_handler(CommandHandler("manager", handoff_handler))
    application.add_handler(CommandHandler("mystatus", mystatus_handler))
    application.add_handler(CommandHandler("brief", brief_handler))
    application.add_handler(CommandHandler("consult", consult_handler))
    application.add_handler(CommandHandler("crm", crm_handler))
    application.add_handler(CommandHandler("get_emoji_id", get_emoji_id_handler))
    application.add_handler(CommandHandler("propensity", propensity_dashboard_handler))
    application.add_handler(CommandHandler("ab_results", ab_results_handler))
    application.add_handler(CommandHandler("ab_detail", ab_detail_handler))
    application.add_handler(CommandHandler("feedback", feedback_insights_handler))
    application.add_handler(CommandHandler("health", health_handler))
    application.add_handler(CommandHandler("qa", qa_handler))
    application.add_handler(CommandHandler("analytics", advanced_stats_handler))
    application.add_handler(CommandHandler("export_csv", export_csv_handler))
    application.add_handler(CommandHandler("export_analytics", export_analytics_handler))
    application.add_handler(CommandHandler("webhook", webhook_handler))
    application.add_handler(CommandHandler("triggers", triggers_handler))
    
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(InlineQueryHandler(inline_query_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_emoji_handler), group=1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sticker_emoji_handler), group=2)
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, video_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler
    ))
    
    application.add_error_handler(error_handler)
    
    from src.bot_api import get_api_version
    logger.info("WEB4TG Studio AI Agent starting...")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"Bot API: {get_api_version()}")
    logger.info(f"Features: Inline, Calculator, Leads, Streaming, FAQ, Promo, Testimonials, DailyDigest, PaymentReminders, Monitoring, RateLimiter, MultiLang, QA, AdvancedAnalytics, CRM, ProactiveEngagement")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
