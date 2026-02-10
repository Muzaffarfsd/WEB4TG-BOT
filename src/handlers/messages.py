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
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        thinking_level = "high" if len(user_message) > 200 else "medium"

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
            messages=session.get_history(),
            thinking_level=thinking_level,
            on_chunk=on_stream_chunk
        )

        if draft_count > 0:
            try:
                await send_message_draft(context.bot, update.effective_chat.id, "")
            except Exception:
                pass
        
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
