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
        app_cost = args.get("app_cost", 150000)
        if app_cost < 100000 or app_cost > 500000:
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
                "📦 Сравнение шаблонов:\n\n"
                "Интернет-магазин (от 150 000₽, 7-10 дней):\n"
                "• Каталог + корзина + авторизация + оплата\n"
                "• Идеально для онлайн-продаж\n\n"
                "Услуги/Сервис (от 170 000₽, 8-12 дней):\n"
                "• Каталог услуг + запись + оплата + управление\n"
                "• Для сферы услуг и сервисов\n\n"
                "Ресторан/Доставка (от 180 000₽, 10-12 дней):\n"
                "• Меню + корзина + бронирование + доставка\n"
                "• Для общепита и доставки\n\n"
                "Фитнес-клуб (от 200 000₽, 12-15 дней):\n"
                "• Расписание + абонементы + прогресс\n"
                "• Для спорта и фитнеса\n\n"
                "Всё кастомизируется + доп. функции от 12 000₽"
            )
        elif plan_type == "subscriptions":
            return (
                "🔄 Подписки на поддержку:\n\n"
                "Минимальный (9 900₽/мес):\n"
                "• Хостинг (99% uptime) + мелкие правки + email поддержка\n\n"
                "Стандартный (14 900₽/мес) ⭐:\n"
                "• + приоритетная поддержка + обновления + ответ за 2 часа\n\n"
                "Премиум (24 900₽/мес):\n"
                "• + персональный менеджер + бизнес-консультации + приоритетные доработки"
            )
        else:
            return (
                "⚖️ Шаблон vs Кастомная сборка:\n\n"
                "Шаблон (от 150 000₽):\n"
                "✅ Быстро (7-15 дней)\n"
                "✅ Проверенные решения\n"
                "✅ Полный функционал для ниши\n\n"
                "Кастомная сборка (от 100 000₽):\n"
                "✅ Только нужные функции\n"
                "✅ Уникальный набор модулей\n"
                "✅ Гибкость в бюджете\n\n"
                "Оплата: 35% предоплата + 65% после сдачи"
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
            return "Пока нет скидок, но вы можете заработать монеты через задания (/bonus) и получить скидку до 25%!"

    return "Инструмент не найден"


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
    
    from src.context_builder import build_full_context, get_dynamic_buttons
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
            async def _tool_executor(tool_name, tool_args):
                return await execute_tool_call(
                    tool_name, tool_args,
                    user.id, user.username, user.first_name
                )
            
            agentic_result = await ai_client.agentic_loop(
                messages=messages_for_ai,
                tool_executor=_tool_executor,
                thinking_level=thinking_level,
                max_steps=4
            )
            
            if agentic_result["special_actions"]:
                for action_type, action_data in agentic_result["special_actions"]:
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

        dynamic_btns = get_dynamic_buttons(user.id, user_message, session.message_count)
        reply_markup = None
        if dynamic_btns:
            keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in dynamic_btns[:3]]
            reply_markup = InlineKeyboardMarkup(keyboard_rows)

        if len(response) > 4096:
            chunks = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await update.message.reply_text(chunk, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response, reply_markup=reply_markup)

        logger.info(f"User {user.id}: processed message #{session.message_count} (stage buttons attached)")

        auto_tag_lead(user.id, user_message)
        auto_score_lead(user.id, user_message)
        
        asyncio.create_task(
            extract_insights_if_needed(user.id, session)
        )
        asyncio.create_task(
            summarize_if_needed(user.id, session)
        )

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
