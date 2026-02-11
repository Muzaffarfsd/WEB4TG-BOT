import asyncio
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.session import session_manager
from src.ai_client import ai_client
from src.config import config
from src.keyboards import get_main_menu_keyboard, get_lead_keyboard, get_loyalty_menu_keyboard
from src.leads import lead_manager, LeadPriority
from src.knowledge_base import ERROR_MESSAGE
from src.tasks_tracker import tasks_tracker
from src.pricing import get_price_main_text, get_price_main_keyboard
from src.loyalty import REVIEW_REWARDS, RETURNING_CUSTOMER_BONUS, format_review_notification

from src.handlers.utils import send_typing_action, loyalty_system, MANAGER_CHAT_ID
from src.keyboards import get_review_moderation_keyboard

logger = logging.getLogger(__name__)


async def execute_tool_call(tool_name: str, args: dict, user_id: int, username: str, first_name: str) -> str:
    from src.calculator import FEATURES

    if tool_name == "calculate_price":
        features = args.get("features", [])
        valid = [f for f in features if f in FEATURES]
        if not valid:
            return "Не удалось распознать функции. Доступные: " + ", ".join(sorted(FEATURES.keys()))
        total = sum(FEATURES[f]["price"] for f in valid)
        lines = [f"✓ {FEATURES[f]['name']} — {FEATURES[f]['price']:,}₽".replace(",", " ") for f in valid]
        prepay = int(total * 0.35)
        return (
            "Расчёт стоимости:\n" +
            "\n".join(lines) +
            f"\n\nИтого: {total:,}₽".replace(",", " ") +
            f"\nПредоплата 35%: {prepay:,}₽".replace(",", " ") +
            f"\nПосле сдачи: {total - prepay:,}₽".replace(",", " ")
        )

    elif tool_name == "show_portfolio":
        category = args.get("category", "all")
        return f"[PORTFOLIO:{category}]"

    elif tool_name == "show_pricing":
        return "[PRICING]"

    elif tool_name == "create_lead":
        lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
        interest = args.get("interest", "")
        if interest:
            lead_manager.add_tag(user_id, interest[:50])
        lead_manager.update_lead(user_id, score=30, priority=LeadPriority.HOT)
        lead_manager.log_event("ai_lead", user_id, {"interest": interest})
        return f"Заявка создана. Интерес клиента: {interest}"

    elif tool_name == "show_payment_info":
        return "[PAYMENT]"

    elif tool_name == "calculate_roi":
        business_type = args.get("business_type", "other")
        monthly_clients = args.get("monthly_clients", 200)
        avg_check = args.get("avg_check", 3000)
        
        roi_data = {
            "restaurant": {"conversion_boost": 0.25, "retention_boost": 0.30, "name": "Ресторан/Кафе"},
            "shop": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Магазин"},
            "beauty": {"conversion_boost": 0.30, "retention_boost": 0.35, "name": "Салон красоты"},
            "education": {"conversion_boost": 0.15, "retention_boost": 0.20, "name": "Образование"},
            "services": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Услуги"},
            "fitness": {"conversion_boost": 0.25, "retention_boost": 0.30, "name": "Фитнес"},
            "delivery": {"conversion_boost": 0.30, "retention_boost": 0.20, "name": "Доставка"},
            "other": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Бизнес"},
        }
        
        data = roi_data.get(business_type, roi_data["other"])
        extra_clients = int(monthly_clients * data["conversion_boost"])
        extra_revenue = extra_clients * avg_check
        yearly_extra = extra_revenue * 12
        app_cost = 150000
        roi_percent = int((yearly_extra - app_cost) / app_cost * 100)
        payback_months = max(1, int(app_cost / extra_revenue)) if extra_revenue > 0 else 12
        
        return (
            f"📊 Расчёт ROI для: {data['name']}\n\n"
            f"Текущие клиенты/мес: {monthly_clients}\n"
            f"Средний чек: {avg_check:,}₽\n\n".replace(",", " ") +
            f"С Mini App (+{int(data['conversion_boost']*100)}% конверсия):\n"
            f"• Доп. клиенты: +{extra_clients}/мес\n"
            f"• Доп. выручка: +{extra_revenue:,}₽/мес\n".replace(",", " ") +
            f"• За год: +{yearly_extra:,}₽\n\n".replace(",", " ") +
            f"ROI: {roi_percent}%\n"
            f"Окупаемость: ~{payback_months} мес."
        )

    elif tool_name == "compare_plans":
        plan_type = args.get("plan_type", "packages")
        
        if plan_type == "packages":
            return (
                "📦 Сравнение пакетов:\n\n"
                "MVP (от 80 000₽, 7-10 дней):\n"
                "• Каталог + корзина + оплата\n"
                "• Идеально для запуска и проверки идеи\n\n"
                "Standard (от 180 000₽, 10-15 дней):\n"
                "• MVP + личный кабинет + push + аналитика\n"
                "• Для растущего бизнеса\n\n"
                "Premium (от 350 000₽, 15-25 дней):\n"
                "• Полный функционал + AI + CRM + интеграции\n"
                "• Для масштабирования"
            )
        elif plan_type == "subscriptions":
            return (
                "🔄 Подписки на поддержку:\n\n"
                "Минимум (15 000₽/мес):\n"
                "• Техподдержка + мониторинг + мелкие правки\n\n"
                "Стандарт (35 000₽/мес):\n"
                "• + новые фичи + A/B тесты + аналитика\n\n"
                "Премиум (70 000₽/мес):\n"
                "• + выделенный разработчик + приоритет + стратегия"
            )
        else:
            return (
                "⚖️ Заказная разработка vs Шаблон:\n\n"
                "Шаблон (от 30 000₽):\n"
                "✅ Быстро (3-5 дней)\n"
                "❌ Ограничен по функционалу\n\n"
                "Заказная (от 80 000₽):\n"
                "✅ Уникальный дизайн и функционал\n"
                "✅ Масштабируется под бизнес\n"
                "✅ Premium Apple-стиль дизайн"
            )

    elif tool_name == "schedule_consultation":
        topic = args.get("topic", "обсуждение проекта")
        preferred_time = args.get("preferred_time", "")
        
        lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
        lead_manager.update_lead(user_id, score=40, priority=LeadPriority.HOT)
        lead_manager.add_tag(user_id, "consultation")
        lead_manager.log_event("schedule_consultation", user_id, {"topic": topic, "time": preferred_time})
        
        time_str = f" на {preferred_time}" if preferred_time else ""
        return (
            f"📅 Заявка на консультацию создана!\n\n"
            f"Тема: {topic}\n"
            f"{f'Время: {preferred_time}' if preferred_time else ''}\n\n"
            f"Менеджер свяжется в ближайшее время{time_str}. "
            f"Консультация бесплатная и ни к чему не обязывает."
        )

    elif tool_name == "generate_brief":
        desc = args.get("project_description", "")
        features = args.get("features", [])
        deadline = args.get("deadline", "")
        
        brief_lines = ["📋 Бриф проекта:\n"]
        brief_lines.append(f"Описание: {desc}")
        if features:
            brief_lines.append(f"Функции: {', '.join(features)}")
        if deadline:
            brief_lines.append(f"Сроки: {deadline}")
        
        from src.calculator import FEATURES as CALC_FEATURES
        if features:
            valid_features = [f for f in features if f in CALC_FEATURES]
            if valid_features:
                total = sum(CALC_FEATURES[f]["price"] for f in valid_features)
                brief_lines.append(f"\nОриентировочная стоимость: {total:,}₽".replace(",", " "))
        
        brief_lines.append("\nСледующий шаг: отправить бриф менеджеру для точной оценки")
        
        lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
        lead_manager.add_tag(user_id, "brief")
        lead_manager.log_event("generate_brief", user_id, {"description": desc[:200]})
        
        return "\n".join(brief_lines)

    elif tool_name == "check_discount":
        discounts = []
        try:
            from src.tasks_tracker import tasks_tracker
            progress = tasks_tracker.get_user_progress(user_id)
            if progress and progress.total_coins > 0:
                discount = progress.get_discount_percent()
                discounts.append(f"🪙 Накоплено {progress.total_coins} монет → скидка {discount}%")
        except Exception:
            pass
        try:
            from src.loyalty import loyalty_system as ls
            if ls.is_returning_customer(user_id):
                discounts.append("🔄 Постоянный клиент → +5% скидка")
            reviews = ls.get_user_reviews(user_id)
            if reviews:
                discounts.append(f"⭐ Оставлено {len(reviews)} отзывов → бонусы начислены")
        except Exception:
            pass
        try:
            from src.referrals import referral_system
            referrals = referral_system.get_referrals_list(user_id)
            if referrals:
                discounts.append(f"👥 {len(referrals)} рефералов → реферальные бонусы")
        except Exception:
            pass
        
        if discounts:
            return "🎁 Ваши доступные скидки:\n\n" + "\n".join(discounts)
        else:
            return "Пока нет скидок, но вы можете заработать монеты через задания (/bonus) и получить скидку до 10%!"

    return "Инструмент не найден"


INTEREST_TAGS = {
    "shop": ["магазин", "товар", "продаж"],
    "restaurant": ["ресторан", "доставк", "еда", "кафе"],
    "beauty": ["салон", "красот", "маникюр"],
    "fitness": ["фитнес", "спорт", "тренировк"],
    "medical": ["врач", "клиник", "медиц"],
    "ai": ["бот", "ai", "автоматиз"],
}


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
    user_message = update.message.text
    
    if user_message and len(user_message) > 4000:
        await update.message.reply_text(
            "Сообщение слишком длинное. Пожалуйста, сократите до 4000 символов."
        )
        return
    
    if context.user_data.get('broadcast_compose'):
        from src.security import is_admin
        if is_admin(user.id):
            context.user_data.pop('broadcast_compose', None)
            context.user_data['broadcast_draft'] = {
                'type': 'text',
                'text': user_message,
            }
            from src.broadcast import broadcast_manager
            counts = broadcast_manager.get_audience_counts()
            from src.handlers.utils import get_broadcast_audience_keyboard
            keyboard = get_broadcast_audience_keyboard(counts)
            await update.message.reply_text(
                f"📋 <b>Предпросмотр рассылки:</b>\n\n{user_message}\n\n<b>Выберите аудиторию:</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return
    
    pending_review_type = context.user_data.get("pending_review_type")
    if pending_review_type and user_message:
        review_id = loyalty_system.submit_review(
            user_id=user.id,
            review_type=pending_review_type,
            content_url=user_message if user_message.startswith("http") else None,
            comment=user_message if not user_message.startswith("http") else None
        )
        
        if review_id:
            context.user_data.pop("pending_review_type", None)
            
            coins = REVIEW_REWARDS.get(pending_review_type, 0)
            await update.message.reply_text(
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
                            format_review_notification(review, user.username or user.first_name),
                            parse_mode="HTML",
                            reply_markup=get_review_moderation_keyboard(review_id)
                        )
                except Exception as e:
                    logger.error(f"Failed to notify manager about review: {e}")
            
            return
        else:
            await update.message.reply_text(
                "❌ Вы уже отправляли отзыв этого типа.",
                reply_markup=get_loyalty_menu_keyboard()
            )
            context.user_data.pop("pending_review_type", None)
            return
    
    if not user_message or not user_message.strip():
        return
    
    if user_message == "💰 Цены":
        await update.message.reply_text(
            get_price_main_text(), 
            parse_mode="Markdown",
            reply_markup=get_price_main_keyboard()
        )
        return
    
    if user_message == "🎁 Получить скидку":
        progress = tasks_tracker.get_user_progress(user.id)
        
        tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇"}
        current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
        
        is_returning = loyalty_system.is_returning_customer(user.id)
        returning_bonus = f"\n🔄 **Бонус постоянного клиента:** +{RETURNING_CUSTOMER_BONUS}%" if is_returning else ""
        
        discount_text = f"""🎁 **Получи скидку до 15% на разработку!**

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
🥇 1500+ монет → 15% (максимум)

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
        
        await update.message.reply_text(
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
                username=user.username,
                first_name=user.first_name
            )
            lead_manager.update_lead(user.id, score=30, priority=LeadPriority.HOT)
            lead_manager.log_event("hot_button", user.id)
            
            text = """🔥 Отлично! Вы готовы к запуску своего приложения!

Напишите мне:
— Какой у вас бизнес?
— Что хотите реализовать?
— Примерный бюджет?

Или нажмите «Да, хочу заказать!» — и я свяжусь с вами для обсуждения деталей."""
            await update.message.reply_text(
                text,
                reply_markup=get_lead_keyboard()
            )
            return
        else:
            user_message = quick_buttons[user_message]
    
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    session.add_message("user", user_message, config.max_history_length)
    
    lead_manager.save_message(user.id, "user", user_message)
    lead_manager.log_event("message", user.id, {"length": len(user_message)})
    lead_manager.update_activity(user.id)
    
    from src.followup import follow_up_manager
    follow_up_manager.cancel_follow_ups(user.id)
    follow_up_manager.schedule_follow_up(user.id)
    
    from src.context_builder import build_full_context
    client_context = build_full_context(user.id, user_message, user.username, user.first_name)
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        thinking_level = "high" if len(user_message) > 200 else "medium"

        response = None

        messages_for_ai = session.get_history()
        if client_context:
            context_msg = {"role": "user", "parts": [{"text": f"[СИСТЕМНЫЙ КОНТЕКСТ — не показывай клиенту, используй для персонализации]\n{client_context}"}]}
            response_ack = {"role": "model", "parts": [{"text": "Понял контекст, учту в ответе."}]}
            messages_for_ai = [context_msg, response_ack] + messages_for_ai

        try:
            result = await ai_client.generate_response_with_tools(
                messages=messages_for_ai,
                thinking_level=thinking_level
            )

            if result["tool_calls"]:
                tool_results = []
                special_actions = []
                for tc in result["tool_calls"]:
                    tool_result = await execute_tool_call(
                        tc["name"], tc["args"],
                        user.id, user.username, user.first_name
                    )
                    if tool_result.startswith("[PORTFOLIO:"):
                        special_actions.append(("portfolio", tool_result))
                    elif tool_result == "[PRICING]":
                        special_actions.append(("pricing", None))
                    elif tool_result == "[PAYMENT]":
                        special_actions.append(("payment", None))
                    else:
                        tool_results.append(tool_result)

                if special_actions:
                    for action_type, action_data in special_actions:
                        if action_type == "portfolio":
                            from src.keyboards import get_portfolio_keyboard
                            from src.knowledge_base import PORTFOLIO_MESSAGE
                            await update.message.reply_text(
                                PORTFOLIO_MESSAGE, parse_mode="Markdown",
                                reply_markup=get_portfolio_keyboard()
                            )
                        elif action_type == "pricing":
                            await update.message.reply_text(
                                get_price_main_text(), parse_mode="Markdown",
                                reply_markup=get_price_main_keyboard()
                            )
                        elif action_type == "payment":
                            from src.payments import get_payment_keyboard
                            await update.message.reply_text(
                                "💳 Выберите способ оплаты:",
                                reply_markup=get_payment_keyboard()
                            )

                if tool_results:
                    tool_context = "\n".join(tool_results)
                    session.add_message("assistant", f"[Результат инструмента: {tool_context}]", config.max_history_length)

                    narration = await ai_client.generate_response(
                        messages=session.get_history(),
                        thinking_level="medium"
                    )
                    response = narration
                elif not special_actions:
                    response = "Готово!"
                else:
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass
                    session.add_message("assistant", "Показал запрошенную информацию", config.max_history_length)
                    lead_manager.save_message(user.id, "assistant", "Показал запрошенную информацию")
                    logger.info(f"User {user.id}: processed message #{session.message_count} (tool action)")
                    auto_tag_lead(user.id, user_message)
                    return
            else:
                response = result["text"]
        except Exception as e:
            logger.warning(f"Tool calling failed, falling back to streaming: {e}")

            from src.bot_api import send_message_draft
            last_draft_len = 0
            draft_count = 0

            async def on_stream_chunk(partial_text: str):
                nonlocal last_draft_len, draft_count
                if len(partial_text) - last_draft_len >= 40:
                    try:
                        await send_message_draft(
                            context.bot,
                            update.effective_chat.id,
                            partial_text + " ▌"
                        )
                        last_draft_len = len(partial_text)
                        draft_count += 1
                    except Exception:
                        pass

            response = await ai_client.generate_response_stream(
                messages=messages_for_ai,
                thinking_level=thinking_level,
                on_chunk=on_stream_chunk
            )

            if draft_count > 0:
                try:
                    await send_message_draft(context.bot, update.effective_chat.id, "")
                except Exception:
                    pass

        if not response:
            response = "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."

        session.add_message("assistant", response, config.max_history_length)

        lead_manager.save_message(user.id, "assistant", response)

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

        auto_tag_lead(user.id, user_message)

    except Exception as e:
        typing_task.cancel()
        error_type = type(e).__name__
        logger.error(f"Error handling message from user {user.id}: {error_type}: {e}")
        await update.message.reply_text(
            ERROR_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
