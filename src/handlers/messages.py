import asyncio
import logging
import re
import time as _time_module
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.ai_client import ai_client, validate_response, check_response_quality
from src.config import config
from src.keyboards import get_main_menu_keyboard, get_lead_keyboard, get_loyalty_menu_keyboard
from src.leads import lead_manager, LeadPriority
from src.knowledge_base import ERROR_MESSAGE
from src.tasks_tracker import tasks_tracker
from src.pricing import get_price_main_text, get_price_main_keyboard
from src.loyalty import REVIEW_REWARDS, RETURNING_CUSTOMER_BONUS, format_review_notification
from src.tool_handlers import execute_tool_call
from src.prompt_composer import compose_system_prompt, build_context_signals_dict

from src.handlers.utils import send_typing_action, loyalty_system, MANAGER_CHAT_ID
from src.keyboards import get_review_moderation_keyboard

logger = logging.getLogger(__name__)


OBJECTION_KEYWORDS = [
    "дорого", "дороговато", "не потяну", "бюджет", "подумаю", "позже",
    "не сейчас", "потом", "сомневаюсь", "не уверен", "гарантии", "риск",
    "конкурент", "дешевле", "фрилансер", "сам сделаю", "бесплатно",
    "тильда", "wix", "не сезон", "кризис", "мошенник", "обман",
    "expensive", "cheaper", "not sure", "doubt", "later", "think about it"
]

CLOSING_KEYWORDS = [
    "хочу заказать", "готов начать", "давайте начнём", "оформляем", "оплат",
    "предоплат", "реквизит", "когда начнём", "договор", "подписываем",
    "go ahead", "let's start", "готов заплатить", "оплачу", "записаться",
    "созвон", "бриф", "ТЗ", "техническое задание"
]

FAQ_KEYWORDS = [
    "привет", "здравствуйте", "добрый", "hello", "hi", "что вы делаете",
    "чем занимаетесь", "расскажите о себе", "кто вы", "как дела",
    "что такое mini app", "что умеет бот"
]

CREATIVE_KEYWORDS = [
    "опиши", "представь", "покажи", "расскажи подробно", "нарисуй",
    "визуализируй", "imagine", "describe", "show me", "придумай",
    "предложи варианты", "как бы выглядел"
]


def _build_returning_client_context(user_id, profile, session):
    try:
        if not (session._loaded_from_db and session.message_count <= 1):
            return None
        industry = profile.get('industry', 'не указана')
        budget = profile.get('budget_range', profile.get('budget', 'не обсуждался'))
        needs = profile.get('needs', 'не выявлены')
        business_name = profile.get('business_name', '')
        ctx = (
            "[ВОЗВРАЩЕНИЕ КЛИЕНТА — персонализируй приветствие!]\n"
            "Клиент уже обращался ранее.\n"
            f"Ниша: {industry}\n"
            f"Бюджет: {budget}\n"
            f"Потребности: {needs}\n"
            f"Имя: {business_name}\n"
            "► Стратегия: \"Рад снова вас видеть! Мы обсуждали [тема] — готовы продолжить?\"\n"
            "► НЕ начинай сначала — продолжай с того места, где остановились"
        )
        return ctx
    except Exception:
        return None


def detect_query_context(message_text: str) -> str:
    text_lower = message_text.lower()

    for kw in OBJECTION_KEYWORDS:
        if kw in text_lower:
            return "objection"

    for kw in CLOSING_KEYWORDS:
        if kw in text_lower:
            return "closing"

    for kw in FAQ_KEYWORDS:
        if kw in text_lower:
            return "faq"

    for kw in CREATIVE_KEYWORDS:
        if kw in text_lower:
            return "creative"

    question_marks = text_lower.count("?")
    commas = text_lower.count(",")
    words = len(text_lower.split())
    if (question_marks >= 2 or commas >= 3) and words > 30:
        return "complex"

    return ""


def get_adaptive_length_hint(session) -> str:
    user_messages = []
    for msg in reversed(session.messages):
        if msg.get("role") == "user" and msg.get("parts"):
            for part in msg["parts"]:
                if isinstance(part, dict) and part.get("text"):
                    text = part["text"]
                    if not text.startswith("["):
                        user_messages.append(text)
                        if len(user_messages) >= 3:
                            break
        if len(user_messages) >= 3:
            break

    if len(user_messages) < 3:
        return ""

    if all(len(m) < 20 for m in user_messages):
        return "[АДАПТАЦИЯ ДЛИНЫ] Клиент пишет коротко — отвечай max 2-3 предложения"

    if all(len(m) > 100 for m in user_messages):
        return "[АДАПТАЦИЯ ДЛИНЫ] Клиент пишет подробно — можешь дать развёрнутый ответ до 150 слов"

    return ""


def track_conversation_velocity(user_id: int, user_data: dict) -> dict:
    now = _time_module.time()
    last_ts = user_data.get("_last_message_ts")
    velocity_info = {"timestamp": now, "delta": None}

    if last_ts:
        delta = now - last_ts
        velocity_info["delta"] = round(delta, 2)

    user_data["_last_message_ts"] = now

    msg_timestamps = user_data.get("_msg_timestamps", [])
    msg_timestamps.append(now)
    if len(msg_timestamps) > 20:
        msg_timestamps = msg_timestamps[-20:]
    user_data["_msg_timestamps"] = msg_timestamps

    return velocity_info


INTEREST_TAGS = {
    "shop": ["магазин", "товар", "продаж"],
    "restaurant": ["ресторан", "доставк", "еда", "кафе"],
    "beauty": ["салон", "красот", "маникюр"],
    "fitness": ["фитнес", "спорт", "тренировк"],
    "medical": ["врач", "клиник", "медиц"],
    "ai": ["бот", "ai", "автоматиз"],
}


BUYING_SIGNALS = {
    "budget": (["бюджет", "готов заплатить", "сколько стоит", "какая цена", "прайс", "budget", "price", "cost"], 5),
    "payment": (["оплат", "предоплат", "реквизит", "карт", "перевод", "pay", "invoice"], 15),
    "deadline": (["когда начнём", "сроки", "как быстро", "дедлайн", "к какому числу", "deadline", "asap"], 10),
    "commitment": (["хочу заказать", "готов начать", "давайте начнём", "оформляем", "подписываем", "go ahead", "let's start"], 20),
    "details": (["техзадание", "ТЗ", "бриф", "функционал", "фичи", "requirements", "features"], 8),
    "contact": (["позвоните", "созвонимся", "мой номер", "мой телефон", "call me", "напишите мне"], 12),
    "comparison": (["а если сравнить", "что лучше", "разница между", "compare", "vs"], 3),
    "positive": (["отлично", "круто", "интересно", "нравится", "вау", "wow", "great", "cool", "amazing"], 2),
    "photo": (["вот скриншот", "вот макет", "вот дизайн", "смотрите фото"], 5),
}


def auto_score_lead(user_id: int, message_text: str) -> None:
    try:
        text_lower = message_text.lower()
        score_delta = 0
        
        for signal_type, (keywords, points) in BUYING_SIGNALS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    score_delta += points
                    break
        
        if score_delta > 0:
            lead = lead_manager.get_lead(user_id)
            if lead:
                new_score = min(100, (lead.score or 0) + score_delta)
                new_priority = lead.priority
                if new_score >= 60:
                    new_priority = LeadPriority.HOT
                elif new_score >= 30:
                    new_priority = LeadPriority.WARM
                lead_manager.update_lead(user_id, score=new_score, priority=new_priority)
                logger.debug(f"Auto-scored lead {user_id}: +{score_delta} → {new_score}")
    except Exception as e:
        logger.debug(f"Auto-scoring failed for user {user_id}: {e}")


async def summarize_if_needed(user_id: int, session) -> None:
    try:
        if not session._needs_summarization:
            return
        if session.message_count < 20:
            return
        
        old_messages = session.messages[:len(session.messages) - 10]
        texts = []
        for msg in old_messages:
            if msg.get("parts"):
                for part in msg["parts"]:
                    if isinstance(part, dict) and part.get("text"):
                        text = part["text"][:150]
                        texts.append(f"{msg['role']}: {text}")
        
        if not texts:
            return
        
        conversation_text = "\n".join(texts)
        existing_summary = session._summary or ""
        
        prompt = f"""Сожми этот диалог в компактное резюме (максимум 200 слов). Сохрани ключевую информацию: тип бизнеса, потребности, бюджет, решения, договорённости. 

{f'Предыдущее резюме: {existing_summary}' if existing_summary else ''}

Диалог для сжатия:
{conversation_text}

Верни ТОЛЬКО резюме, без пояснений."""
        
        from src.ai_client import ai_client
        summary = await ai_client.quick_response(prompt)
        
        if summary and len(summary) > 20:
            session.set_summary(summary)
            session.messages = session.messages[-10:]
            logger.info(f"Summarized conversation for user {user_id}: {len(summary)} chars")
    except Exception as e:
        logger.debug(f"Summarization failed for user {user_id}: {e}")


async def extract_insights_if_needed(user_id: int, session) -> None:
    try:
        if session.message_count < 6 or session.message_count % 5 != 0:
            return
        
        history = session.get_history()
        if len(history) < 6:
            return
        
        recent_texts = []
        for msg in history[-10:]:
            if msg.get("parts"):
                for part in msg["parts"]:
                    if isinstance(part, dict) and part.get("text"):
                        recent_texts.append(f"{msg['role']}: {part['text'][:200]}")
        
        if not recent_texts:
            return
        
        conversation_text = "\n".join(recent_texts)
        
        prompt = f"""Проанализируй диалог и извлеки ключевые данные о клиенте. Верни ТОЛЬКО JSON (без markdown):
{{"business_type": "тип бизнеса или null", "budget": "бюджет или null", "timeline": "желаемые сроки или null", "needs": ["список потребностей"], "ready_to_buy": true/false}}

Диалог:
{conversation_text}"""
        
        from src.ai_client import ai_client
        result = await ai_client.quick_response(prompt)
        
        import json
        import re
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1] if "\n" in result else result
            result = result.rsplit("```", 1)[0] if "```" in result else result
            result = result.strip()
        
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result)
        if json_match:
            result = json_match.group(0)
        
        try:
            insights = json.loads(result)
        except json.JSONDecodeError:
            result = result.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
            try:
                insights = json.loads(result)
            except json.JSONDecodeError:
                logger.debug(f"Could not parse insights JSON for user {user_id}")
                return
        
        if insights.get("business_type"):
            lead_manager.add_tag(user_id, insights["business_type"])
        if insights.get("budget"):
            lead_manager.add_tag(user_id, f"budget:{insights['budget']}")
        if insights.get("needs"):
            for need in insights["needs"][:3]:
                lead_manager.add_tag(user_id, need[:30])
        if insights.get("ready_to_buy"):
            lead_manager.update_lead(user_id, priority=LeadPriority.HOT)
            lead_manager.add_tag(user_id, "ready_to_buy")

        try:
            from src.session import save_client_profile
            profile_data = {}
            if insights.get("business_type"):
                industry_map = {
                    "магазин": "shop", "shop": "shop", "интернет-магазин": "shop", "ecommerce": "shop",
                    "ресторан": "restaurant", "restaurant": "restaurant", "кафе": "restaurant", "общепит": "restaurant",
                    "салон": "beauty", "beauty": "beauty", "красота": "beauty", "косметология": "beauty",
                    "фитнес": "fitness", "fitness": "fitness", "спорт": "fitness", "gym": "fitness",
                    "клиника": "medical", "medical": "medical", "медицина": "medical",
                    "образование": "education", "education": "education", "школа": "education", "курсы": "education", "обучение": "education",
                    "доставка еды": "delivery", "delivery": "delivery", "курьер": "delivery",
                    "услуги": "services", "services": "services", "сервис": "services", "клининг": "services", "ремонт": "services",
                }
                btype = insights["business_type"].lower()
                for key, val in industry_map.items():
                    if key in btype:
                        profile_data["industry"] = val
                        break
                if "industry" not in profile_data:
                    profile_data["industry"] = insights["business_type"][:50]
            if insights.get("budget"):
                profile_data["budget_range"] = str(insights["budget"])[:50]
            if insights.get("timeline"):
                profile_data["timeline"] = str(insights["timeline"])[:50]
            if insights.get("needs"):
                profile_data["needs"] = ", ".join(insights["needs"][:5])[:200]
            if profile_data:
                save_client_profile(user_id, **profile_data)
        except Exception as e:
            logger.debug(f"Failed to save client profile: {e}")

        logger.info(f"Extracted insights for user {user_id}: {insights}")
    except Exception as e:
        logger.debug(f"Insight extraction failed for user {user_id}: {e}")


def auto_tag_lead(user_id: int, message_text: str) -> None:
    try:
        lead = lead_manager.get_lead(user_id)
        if not lead:
            return
        
        text_lower = message_text.lower()
        for tag, keywords in INTEREST_TAGS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    lead_manager.add_tag(user_id, tag)
                    break
    except Exception as e:
        logger.debug(f"Auto-tagging failed for user {user_id}: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    chat = update.effective_chat
    if not user or not message or not chat:
        return
    user_data = context.user_data or {}
    user_message = message.text or ""

    from src.rate_limiter import rate_limiter
    allowed, rate_msg = rate_limiter.check_rate_limit(user.id)
    if not allowed:
        await message.reply_text(rate_msg)
        return

    from src.monitoring import monitor
    import time as _time
    _msg_start = _time.time()
    monitor.track_message()
    
    if user_message and len(user_message) > 4000:
        await message.reply_text(
            "Сообщение слишком длинное. Пожалуйста, сократите до 4000 символов."
        )
        return
    
    if user_data.get('broadcast_compose'):
        from src.security import is_admin
        if is_admin(user.id):
            user_data.pop('broadcast_compose', None)
            user_data['broadcast_draft'] = {
                'type': 'text',
                'text': user_message,
            }
            from src.broadcast import broadcast_manager
            counts = broadcast_manager.get_audience_counts()
            from src.handlers.utils import get_broadcast_audience_keyboard
            keyboard = get_broadcast_audience_keyboard(counts)
            await message.reply_text(
                f"📋 <b>Предпросмотр рассылки:</b>\n\n{user_message}\n\n<b>Выберите аудиторию:</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
    
    pending_review_type = user_data.get("pending_review_type")
    if pending_review_type and user_message:
        review_id = loyalty_system.submit_review(
            user_id=user.id,
            review_type=pending_review_type,
            content_url=user_message if user_message.startswith("http") else None,
            comment=user_message if not user_message.startswith("http") else None
        )
        
        if review_id:
            user_data.pop("pending_review_type", None)
            
            coins = REVIEW_REWARDS.get(pending_review_type, 0)
            await message.reply_text(
                f"✅ <b>Отзыв отправлен на модерацию!</b>\n\n"
                f"После проверки вам будет начислено <b>{coins} монет</b>.\n"
                f"Обычно это занимает до 24 часов.",
                parse_mode="HTML",
                reply_markup=get_loyalty_menu_keyboard()
            )
            
            if MANAGER_CHAT_ID:
                try:
                    review = None
                    reviews = loyalty_system.get_pending_reviews()
                    for r in reviews:
                        if r.id == review_id:
                            review = r
                            break
                    
                    if review:
                        await context.bot.send_message(
                            int(MANAGER_CHAT_ID),
                            format_review_notification(review, (user.username or user.first_name or "")),
                            parse_mode="HTML",
                            reply_markup=get_review_moderation_keyboard(review_id)
                        )
                except Exception as e:
                    logger.error(f"Failed to notify manager about review: {e}")
            
            return
        else:
            await message.reply_text(
                "❌ Вы уже отправляли отзыв этого типа.",
                reply_markup=get_loyalty_menu_keyboard()
            )
            user_data.pop("pending_review_type", None)
            return
    
    if not user_message or not user_message.strip():
        return
    
    if user_message == "💰 Цены":
        await message.reply_text(
            get_price_main_text(), 
            parse_mode="Markdown",
            reply_markup=get_price_main_keyboard()
        )
        return
    
    if user_message == "🎁 Получить скидку":
        progress = tasks_tracker.get_user_progress(user.id)
        
        tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
        current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
        
        is_returning = loyalty_system.is_returning_customer(user.id)
        returning_bonus = f"\n🔄 **Бонус постоянного клиента:** +{RETURNING_CUSTOMER_BONUS}%" if is_returning else ""
        
        discount_text = f"""🎁 **Получи скидку до 25% на разработку!**

{current_emoji} **Твой уровень:** {progress.get_tier_name()}
💰 **Монеты:** {progress.total_coins}
🔥 **Стрик:** {progress.current_streak} дней
💵 **Текущая скидка:** {progress.get_discount_percent()}%{returning_bonus}

**Как это работает:**
1. Подписывайся на наши соцсети
2. Лайкай, комментируй, делись постами
3. Приглашай друзей (+200 монет за друга)
4. Монеты = скидка на разработку

**Уровни скидок:**
🥉 500+ монет → 5%
🥈 1000+ монет → 10%
🥇 1500+ монет → 15%
💎 2000+ монет → 20%
👑 2500+ монет → 25%

⏰ **Монеты действуют 90 дней**

Выбери задание:"""
        
        earn_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Telegram задания", callback_data="tasks_telegram")],
            [InlineKeyboardButton("📺 YouTube задания", callback_data="tasks_youtube")],
            [InlineKeyboardButton("📸 Instagram задания", callback_data="tasks_instagram")],
            [InlineKeyboardButton("🎵 TikTok задания", callback_data="tasks_tiktok")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="tasks_progress")],
            [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
        ])
        
        await message.reply_text(
            discount_text,
            parse_mode="Markdown",
            reply_markup=earn_keyboard
        )
        return
    
    quick_buttons = {
        "💰 Узнать цену": "Сколько стоит разработка Telegram Mini App? Расскажи про цены и тарифы",
        "🎯 Подобрать решение": "Помоги подобрать подходящее решение для моего бизнеса",
        "🚀 Хочу приложение!": "lead"
    }
    
    if user_message in quick_buttons:
        if user_message == "🚀 Хочу приложение!":
            lead = lead_manager.create_lead(
                user_id=user.id,
                username=(user.username or ""),
                first_name=(user.first_name or "")
            )
            lead_manager.update_lead(user.id, score=30, priority=LeadPriority.HOT)
            lead_manager.log_event("hot_button", user.id)
            
            text = """🔥 Отлично! Вы готовы к запуску своего приложения!

Напишите мне:
— Какой у вас бизнес?
— Что хотите реализовать?
— Примерный бюджет?

Или нажмите «Да, хочу заказать!» — и я свяжусь с вами для обсуждения деталей."""
            await message.reply_text(
                text,
                reply_markup=get_lead_keyboard()
            )
            return
        else:
            user_message = quick_buttons[user_message]
    
    session = session_manager.get_session(
        user_id=user.id,
        username=(user.username or ""),
        first_name=(user.first_name or "")
    )
    
    session.add_message("user", user_message, config.max_history_length)
    
    lead_manager.save_message(user.id, "user", user_message)
    lead_manager.log_event("message", user.id, {"length": len(user_message)})
    lead_manager.update_activity(user.id)

    try:
        from src.propensity import propensity_scorer
        propensity_scorer.record_interaction(user.id, 'message')
    except Exception as e:
        logger.debug(f"Propensity tracking skipped: {e}")

    try:
        from src.proactive_engagement import proactive_engine
        proactive_engine.update_behavioral_signals(user.id, "message")
        proactive_engine.mark_trigger_responded(user.id)

        from src.context_builder import detect_competitor_mention
        competitor = detect_competitor_mention(user_message)
        if competitor:
            proactive_engine.update_behavioral_signals(
                user.id, "competitor_mention",
                competitor_context=user_message[:300]
            )
    except Exception as e:
        logger.debug(f"Proactive engagement tracking skipped: {e}")

    if 'prefers_voice' not in user_data:
        try:
            from src.session import get_client_profile
            profile = get_client_profile(user.id)
            if profile and profile.get("prefers_voice") == "true":
                user_data['prefers_voice'] = True
                user_data['voice_message_count'] = 1
        except Exception as e:
            logger.debug(f"Voice preference check skipped: {e}")

    from src.followup import follow_up_manager
    follow_up_manager.cancel_follow_ups(user.id)
    follow_up_manager.schedule_follow_up(user.id)
    
    from src.multilang import detect_and_remember_language, get_prompt_suffix, get_user_language
    user_lang = detect_and_remember_language(user.id, user_message)

    from src.conversation_qa import qa_manager
    handoff_trigger = qa_manager.check_handoff_triggers(user.id, user_message)
    if handoff_trigger:
        trigger_type, trigger_reason = handoff_trigger
        qa_manager.create_handoff_request(
            user_id=user.id,
            reason=trigger_reason,
            trigger_type=trigger_type,
            context_summary=user_message[:500]
        )
        await qa_manager.notify_manager_handoff(
            context.bot, user.id, trigger_reason, trigger_type,
            user_name=f"{user.first_name or ''} (@{user.username or 'нет'})"
        )
        if trigger_type == "explicit_request":
            from src.multilang import get_string
            await message.reply_text(get_string("handoff_request", user_lang))
    
    from src.context_builder import parse_ai_buttons

    context_signals = build_context_signals_dict(
        user_id=user.id,
        user_message=user_message,
        username=user.username or "",
        first_name=user.first_name or "",
        message_count=session.message_count
    )

    try:
        from src.session import get_client_profile
        profile = get_client_profile(user.id)
        if profile:
            returning_ctx = _build_returning_client_context(user.id, profile, session)
            if returning_ctx:
                context_signals["returning_context"] = returning_ctx
    except Exception:
        pass

    try:
        from src.session import get_vision_history
        vision_hist = get_vision_history(user.id)
        if vision_hist:
            context_signals["vision_history"] = vision_hist
    except Exception:
        pass

    lang_suffix = get_prompt_suffix(user_lang)

    adaptive_hint = get_adaptive_length_hint(session)
    
    velocity_info = track_conversation_velocity(user.id, user_data)
    if velocity_info.get("delta") is not None:
        logger.debug(f"User {user.id} response delta: {velocity_info['delta']}s")

    query_context = detect_query_context(user_message)
    if query_context:
        logger.debug(f"User {user.id} query_context: {query_context}")

    dynamic_prompt = compose_system_prompt(
        context_signals=context_signals,
        query_context=query_context or None,
        adaptive_hint=adaptive_hint or None,
        lang_suffix=lang_suffix or None,
        user_id=user.id,
    )

    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        thinking_level = "medium"
        if len(user_message) > 200:
            thinking_level = "high"

        propensity_val = context_signals.get("propensity", "")
        funnel_val = context_signals.get("funnel_stage", "")
        has_objection = "objection" in context_signals
        has_buying = "buying_signal" in context_signals

        if has_objection or has_buying:
            thinking_level = "high"
            if not query_context:
                query_context = "objection" if has_objection else "sales"
        elif "ГОРЯЧИЙ" in propensity_val or funnel_val in ("decision", "negotiation"):
            thinking_level = "high"
            if not query_context or query_context in ("faq", "simple"):
                query_context = "sales"
        elif funnel_val in ("consideration",) and "ТЁПЛЫЙ" in propensity_val:
            thinking_level = "high"

        response = None

        messages_for_ai = session.get_history()

        try:
            async def _tool_executor(tool_name, tool_args):
                return await execute_tool_call(
                    tool_name, tool_args,
                    user.id, user.username or "", user.first_name or ""
                )
            
            agentic_result = await ai_client.agentic_loop(
                messages=messages_for_ai,
                tool_executor=_tool_executor,
                thinking_level=thinking_level,
                max_steps=3,
                query_context=query_context or None,
                dynamic_system_prompt=dynamic_prompt
            )
            
            if agentic_result["special_actions"]:
                for action_type, action_data in agentic_result["special_actions"]:
                    if action_type == "portfolio":
                        from src.keyboards import get_portfolio_keyboard
                        from src.knowledge_base import PORTFOLIO_MESSAGE
                        await message.reply_text(
                            PORTFOLIO_MESSAGE, parse_mode="Markdown",
                            reply_markup=get_portfolio_keyboard()
                        )
                    elif action_type == "pricing":
                        await message.reply_text(
                            get_price_main_text(), parse_mode="Markdown",
                            reply_markup=get_price_main_keyboard()
                        )
                    elif action_type == "payment":
                        from src.payments import get_payment_keyboard
                        await message.reply_text(
                            "💳 Выберите способ оплаты:",
                            reply_markup=get_payment_keyboard()
                        )
                    elif action_type == "ai_brief":
                        from src.brief_generator import brief_generator
                        brief_text, brief_keyboard = brief_generator.format_brief(user.id)
                        if "не завершён" not in brief_text:
                            try:
                                await message.reply_text(
                                    brief_text, parse_mode="HTML",
                                    reply_markup=brief_keyboard
                                )
                            except Exception:
                                await message.reply_text(
                                    brief_text.replace("<b>", "").replace("</b>", ""),
                                    reply_markup=brief_keyboard
                                )
            
            if agentic_result["text"]:
                response = agentic_result["text"]
            elif agentic_result["special_actions"]:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
                session.add_message("assistant", "Показал запрошенную информацию", config.max_history_length)
                lead_manager.save_message(user.id, "assistant", "Показал запрошенную информацию")
                logger.info(f"User {user.id}: processed message #{session.message_count} (agentic, {len(agentic_result['all_tool_results'])} tools)")
                auto_tag_lead(user.id, user_message)
                auto_score_lead(user.id, user_message)
                return
            else:
                response = None
                
        except Exception as e:
            logger.warning(f"Agentic loop failed, falling back to streaming: {e}")

            from src.bot_api import send_message_draft
            last_draft_len = 0
            draft_count = 0

            async def on_stream_chunk(partial_text: str):
                nonlocal last_draft_len, draft_count
                import re as _re
                display_text = _re.sub(r'\[BUTTONS:.*$', '', partial_text, flags=_re.DOTALL).rstrip()
                if len(display_text) - last_draft_len >= 40:
                    try:
                        await send_message_draft(
                            context.bot,
                            chat.id,
                            display_text + " ▌"
                        )
                        last_draft_len = len(partial_text)
                        draft_count += 1
                    except Exception as e:
                        logger.debug(f"Stream chunk callback error: {e}")

            response = await ai_client.generate_response_stream(
                messages=messages_for_ai,
                thinking_level=thinking_level,
                on_chunk=on_stream_chunk,
                query_context=query_context or None,
                dynamic_system_prompt=dynamic_prompt
            )

            if draft_count > 0:
                try:
                    await send_message_draft(context.bot, chat.id, "")
                except Exception as e:
                    logger.debug(f"Draft clear error: {e}")

        if not response:
            response = "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."

        is_valid, cleaned = validate_response(response)
        if not is_valid:
            logger.info(f"Response validation corrected issues for user {user.id}")
            response = cleaned

        response = check_response_quality(response, user_message, query_context=query_context or "")

        response, ai_buttons = parse_ai_buttons(response)

        session.add_message("assistant", response, config.max_history_length)

        lead_manager.save_message(user.id, "assistant", response)

        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

        reply_markup = None
        if ai_buttons:
            keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in ai_buttons]
            reply_markup = InlineKeyboardMarkup(keyboard_rows)

        smart_voice_sent = False
        try:
            from src.handlers.media import (
                should_send_smart_voice,
                generate_voice_bridge
            )
            voice_decision = should_send_smart_voice(
                user.id, user_message, user_data, response_text=response
            )
            if voice_decision.get("send"):
                voice_mode = voice_decision.get("mode", "full")
                voice_profile = voice_decision.get("profile", "default")
                voice_trigger = voice_decision.get("trigger", "unknown")

                for _sv_attempt in range(2):
                    try:
                        await chat.send_action(ChatAction.RECORD_VOICE)

                        voice_audio = await generate_voice_bridge(
                            response, user_message, voice_profile=voice_profile
                        )

                        if not voice_audio or len(voice_audio) < 100:
                            raise RuntimeError(f"Voice audio too small: {len(voice_audio) if voice_audio else 0} bytes")

                        await message.reply_voice(voice=voice_audio)

                        if len(response) > 4096:
                            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
                            for i, chunk in enumerate(chunks):
                                if i == len(chunks) - 1:
                                    await message.reply_text(chunk, reply_markup=reply_markup)
                                else:
                                    await message.reply_text(chunk)
                        else:
                            await message.reply_text(response, reply_markup=reply_markup)

                        smart_voice_sent = True
                        lead_manager.log_event("smart_voice_sent", user.id, {
                            "trigger": voice_trigger,
                            "mode": voice_mode,
                            "profile": voice_profile,
                            "priority": voice_decision.get("priority", 0),
                            "audio_size": len(voice_audio),
                            "attempt": _sv_attempt + 1,
                            "message_preview": user_message[:100]
                        })
                        logger.info(f"Smart voice SENT to user {user.id} (trigger={voice_trigger}, mode={voice_mode}, profile={voice_profile}, attempt={_sv_attempt+1}, size={len(voice_audio)})")
                        break
                    except Exception as voice_err:
                        logger.warning(f"Smart voice attempt {_sv_attempt+1} failed for user {user.id}: {type(voice_err).__name__}: {voice_err}")
                        if _sv_attempt == 0:
                            await asyncio.sleep(1)

                if not smart_voice_sent:
                    logger.error(f"Smart voice FAILED for user {user.id} after 2 attempts (trigger={voice_trigger}), falling back to text")
                    user_data['smart_voice_count'] = max(0, user_data.get('smart_voice_count', 1) - 1)
        except ImportError:
            pass

        if not smart_voice_sent:
            if len(response) > 4096:
                chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        await message.reply_text(chunk, reply_markup=reply_markup)
                    else:
                        await message.reply_text(chunk)
            else:
                await message.reply_text(response, reply_markup=reply_markup)

        logger.info(f"User {user.id}: processed message #{session.message_count} (voice={'smart' if smart_voice_sent else 'text'})")

        monitor.track_request("message_handler", _time.time() - _msg_start, success=True)

        _msg_count_snap = session.message_count
        _sess_msgs_snap = len(session.messages)

        _query_ctx_snap = query_context or ""

        async def _post_response_analytics(uid, u_msg, resp, msg_count, sess_msgs_len):
            try:
                auto_tag_lead(uid, u_msg)
                auto_score_lead(uid, u_msg)
            except Exception as e:
                logger.debug(f"Auto-tagging skipped: {e}")

            try:
                from src.feedback_loop import feedback_loop
                from src.context_builder import detect_funnel_stage
                stage = detect_funnel_stage(uid, u_msg, msg_count)
                p_score = None
                try:
                    from src.propensity import propensity_scorer
                    p_score = propensity_scorer.get_score(uid)
                except Exception:
                    pass
                from src.ab_testing import ab_testing
                variant = None
                try:
                    variant = ab_testing.get_variant(uid, "response_style")
                except Exception:
                    pass
                feedback_loop.log_response(
                    user_id=uid,
                    message_text=u_msg[:500],
                    response_text=resp[:1000] if resp else "",
                    variant=variant,
                    funnel_stage=stage,
                    propensity_score=p_score
                )
            except Exception as e:
                logger.debug(f"Feedback loop logging skipped: {e}")

            try:
                qa_manager.score_conversation(
                    user_id=uid,
                    user_message=u_msg,
                    ai_response=resp,
                    message_count=msg_count,
                    session_messages=sess_msgs_len
                )
            except Exception as e:
                logger.debug(f"QA scoring skipped: {e}")

            try:
                await qa_manager.ai_evaluate_response(
                    user_id=uid,
                    user_message=u_msg,
                    ai_response=resp,
                    context_scenario=_query_ctx_snap,
                    methodology_used=""
                )
            except Exception as e:
                logger.debug(f"AI evaluation skipped: {e}")

        asyncio.create_task(_post_response_analytics(
            user.id, user_message, response, _msg_count_snap, _sess_msgs_snap
        ))
        asyncio.create_task(extract_insights_if_needed(user.id, session))
        asyncio.create_task(summarize_if_needed(user.id, session))

    except Exception as e:
        typing_task.cancel()
        error_type = type(e).__name__
        logger.error(f"Error handling message from user {user.id}: {error_type}: {e}")
        monitor.track_request("message_handler", _time.time() - _msg_start, success=False, error=str(e))
        await message.reply_text(
            ERROR_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
