import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.keyboards import (
    get_main_menu_keyboard, get_services_keyboard, 
    get_portfolio_keyboard, get_calculator_keyboard,
    get_lead_keyboard, get_back_keyboard,
    get_loyalty_menu_keyboard, get_review_type_keyboard,
    get_package_deals_keyboard, get_faq_keyboard
)
from src.bot_api import copy_text_button, styled_button_api_kwargs
from src.calculator import calculator_manager
from src.leads import lead_manager
from src.knowledge_base import PORTFOLIO_MESSAGE, FAQ_DATA
from src.tasks_tracker import tasks_tracker, TASKS_CONFIG
from src.referrals import referral_manager, REFERRER_REWARD
from src.payments import handle_payment_callback
from src.pricing import handle_price_callback
from src.loyalty import (
    RETURNING_CUSTOMER_BONUS, PACKAGE_DEALS,
    format_package_deals, format_returning_customer_info, format_review_bonus_info
)
from src.analytics import analytics, FunnelEvent

from src.handlers.utils import loyalty_system, MANAGER_CHAT_ID

logger = logging.getLogger(__name__)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "open_app":
        await query.message.reply_text(
            "Вот что могу показать:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "request_manager":
        from src.leads import lead_manager as lm_handoff, LeadPriority
        user = query.from_user
        lm_handoff.create_lead(user_id=user.id, username=user.username, first_name=user.first_name)
        lm_handoff.update_lead(user.id, score=40, priority=LeadPriority.HOT)
        
        await query.message.edit_text(
            "👨‍💼 <b>Запрос отправлен!</b>\n\n"
            "Менеджер свяжется с вами в ближайшее время.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
            ])
        )
        
        import os
        manager_chat_id = os.environ.get("MANAGER_CHAT_ID")
        if manager_chat_id:
            try:
                await context.bot.send_message(
                    int(manager_chat_id),
                    f"🔔 <b>Запрос менеджера</b>\n"
                    f"👤 {user.first_name} (@{user.username or 'нет'})\n"
                    f"🆔 <code>{user.id}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    
    elif data == "menu_back":
        await query.edit_message_text(
            "Вот что могу показать:",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "menu_services":
        text = """Мы разрабатываем приложения для разных типов бизнеса:

Интернет-магазины — от 7 дней
Рестораны и доставка — от 7 дней
Салоны красоты, фитнес — от 10 дней
Медицинские центры — от 12 дней

Выберите направление, расскажу подробнее:"""
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
        analytics.track(user_id, FunnelEvent.CALCULATOR_OPEN)
        calc = calculator_manager.get_calculation(user_id)
        await query.edit_message_text(
            f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
            parse_mode="Markdown",
            reply_markup=get_calculator_keyboard()
        )
    
    elif data == "menu_ai_agent":
        text = """AI-агент — это умный помощник для вашего бизнеса.

Отвечает клиентам 24/7, понимает контекст, помнит историю общения. И главное — обучается на ваших данных.

Стоимость интеграции — 49 000 ₽. Окупается обычно за 6 месяцев.

Даём 7 дней бесплатного теста — можете попробовать на своём бизнесе.

Интересно?"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)
        text = """Отлично, давайте обсудим ваш проект!

Напишите мне:
— Какой у вас бизнес?
— Что хотите реализовать в приложении?
— Есть ли примерный бюджет?

Или нажмите кнопку — я свяжусь с вами и обсудим детали."""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "payment_stars":
        from src.keyboards import get_stars_payment_keyboard
        await query.message.edit_text(
            "⭐ <b>Оплата через Telegram Stars</b>\n\n"
            "Мгновенная оплата без банковских реквизитов.\n"
            "Выберите услугу:",
            parse_mode="HTML",
            reply_markup=get_stars_payment_keyboard()
        )
    
    elif data.startswith("stars_"):
        product_id = data.replace("stars_", "")
        from src.payments import create_stars_invoice
        success = await create_stars_invoice(context.bot, query.from_user.id, product_id)
        if success:
            await query.answer("Счёт отправлен!")
        else:
            await query.answer("Ошибка создания счёта", show_alert=True)
    
    elif data in ("payment", "pay_card", "pay_bank", "copy_card", "copy_bank",
                   "copy_card_fallback", "copy_bank_fallback", "pay_confirm", "pay_contract"):
        action = data.replace("_fallback", "")
        await handle_payment_callback(update, context, action)
    
    elif data == "menu_faq" or data == "faq_back":
        await query.edit_message_text(
            "❓ **Частые вопросы**\n\nВыберите интересующий вопрос:",
            parse_mode="Markdown",
            reply_markup=get_faq_keyboard()
        )
    
    elif data.startswith("faq_") and data in FAQ_DATA:
        faq = FAQ_DATA[data]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад к FAQ", callback_data="faq_back")],
            [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
        ])
        await query.edit_message_text(
            f"**{faq['question']}**\n\n{faq['answer']}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    elif data.startswith("price_"):
        await handle_price_callback(update, context, data)
    
    elif data == "menu_testimonials":
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
        
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    elif data == "loyalty_menu":
        text = """🎁 <b>Программа лояльности</b>

Получайте дополнительные скидки и бонусы:

⭐ <b>Отзывы</b> — до 500 монет за отзыв
🔄 <b>Постоянным клиентам</b> — +5% на следующий заказ
📦 <b>Пакеты</b> — до 15% при заказе с подпиской

Выберите раздел:"""
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_loyalty_menu_keyboard()
        )
    
    elif data == "loyalty_review":
        text = format_review_bonus_info()
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_review_type_keyboard()
        )
    
    elif data == "loyalty_packages":
        text = format_package_deals()
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_package_deals_keyboard()
        )
    
    elif data == "loyalty_returning":
        text = format_returning_customer_info()
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_loyalty_menu_keyboard()
        )
    
    elif data == "loyalty_my_discounts":
        user_progress = tasks_tracker.get_user_progress(user_id)
        base_discount = user_progress.get_discount_percent()
        
        discounts = loyalty_system.calculate_total_discount(user_id, base_discount)
        is_returning = loyalty_system.is_returning_customer(user_id)
        
        text = f"""📊 <b>Ваши скидки</b>

💰 <b>Монеты:</b> {user_progress.total_coins}
🎯 <b>Скидка от монет:</b> {base_discount}%
🏆 <b>Уровень:</b> {user_progress.get_tier_name()}

"""
        if is_returning:
            text += f"🔄 <b>Бонус постоянного клиента:</b> +{RETURNING_CUSTOMER_BONUS}%\n"
        else:
            text += "🔄 <i>Бонус постоянного клиента: станет доступен после первого заказа</i>\n"
        
        text += f"""
📦 <b>Пакетные скидки:</b> до 15% (при заказе с подпиской)

━━━━━━━━━━━━━━━
💎 <b>Максимальная скидка:</b> {discounts['total']}%

<i>Скидки суммируются (макс. 30%)</i>"""
        
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_loyalty_menu_keyboard()
        )
    
    elif data == "review_video":
        context.user_data["pending_review_type"] = "video"
        text = """🎬 <b>Видео-отзыв</b>

Запишите короткое видео (30 сек — 2 мин) с отзывом о работе с WEB4TG Studio.

📹 <b>Отправьте видео прямо в этот чат!</b>

Можно записать:
• Кружочек (видеосообщение)
• Обычное видео из галереи
• Записать новое видео

<i>Расскажите о вашем опыте работы с нами!</i>"""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="loyalty_review")]])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    elif data == "review_text":
        context.user_data["pending_review_type"] = "text_photo"
        text = """📝 <b>Текстовый отзыв</b>

Напишите отзыв и приложите скриншот вашего приложения.

Отправьте в этот чат:
1. Текст отзыва
2. Скриншот или фото приложения

<i>Можно отправить одним или несколькими сообщениями</i>"""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="loyalty_review")]])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    elif data.startswith("package_"):
        package_id = data.replace("package_", "")
        if package_id in PACKAGE_DEALS:
            deal = PACKAGE_DEALS[package_id]
            text = f"""📦 <b>{deal['name']}</b>

{deal['description']}

💰 <b>Скидка:</b> {deal['discount']}%

Чтобы воспользоваться предложением, напишите менеджеру или оставьте заявку.

<i>Скидка применяется к стоимости разработки</i>"""
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=get_lead_keyboard()
            )
    
    elif data.startswith("mod_approve_"):
        review_id = int(data.replace("mod_approve_", ""))
        manager_id = query.from_user.id
        
        if str(manager_id) != MANAGER_CHAT_ID:
            await query.answer("Только менеджер может модерировать отзывы", show_alert=True)
            return
        
        coins = loyalty_system.approve_review(review_id, manager_id)
        if coins:
            reviews = loyalty_system.get_pending_reviews()
            for r in reviews:
                if r.id == review_id:
                    tasks_tracker.add_coins(r.user_id, coins, f"review_{r.review_type}")
                    try:
                        await context.bot.send_message(
                            r.user_id,
                            f"✅ Ваш отзыв одобрен! Начислено <b>{coins} монет</b>.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user about review approval: {e}")
                    break
            
            await query.edit_message_text(
                query.message.text + f"\n\n✅ <b>Одобрено</b> — начислено {coins} монет",
                parse_mode="HTML"
            )
        else:
            await query.answer("Ошибка при одобрении отзыва", show_alert=True)
    
    elif data.startswith("mod_reject_"):
        review_id = int(data.replace("mod_reject_", ""))
        manager_id = query.from_user.id
        
        if str(manager_id) != MANAGER_CHAT_ID:
            await query.answer("Только менеджер может модерировать отзывы", show_alert=True)
            return
        
        if loyalty_system.reject_review(review_id, manager_id):
            await query.edit_message_text(
                query.message.text + "\n\n❌ <b>Отклонено</b>",
                parse_mode="HTML"
            )
        else:
            await query.answer("Ошибка при отклонении отзыва", show_alert=True)
    
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
                lead_manager.log_event("calculator_used", user_id, {
                    "features": list(calc.selected_features),
                    "total": calc.get_total()
                })
                lead_manager.update_activity(user_id)
                
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
            """Отлично, записал вашу заявку!

Свяжусь с вами в ближайшее время — обычно в течение пары часов в рабочее время.

А пока можете задавать любые вопросы, я на связи.""",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "Спрашивайте — отвечу на всё, что знаю)",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """Интернет-магазины — наша специализация.

Срок разработки: 7-10 дней. В базовый пакет входит каталог, корзина, оплата, профиль покупателя.

Дополнительно можно добавить поиск с фильтрами, избранное, push-уведомления, программу лояльности.

Примеры: Radiance (одежда), TechMart (электроника), SneakerVault (кроссовки).

Хотите посмотреть или сразу обсудим ваш проект?""",
            "service_restaurant": """Рестораны и доставку делаем часто.

Срок: 7-10 дней. Базово: меню, корзина, заказ, бронирование столов, доставка.

Можно добавить программу лояльности, push-уведомления о статусе заказа, онлайн-оплату.

Пример: DeluxeDine — красивый проект, могу показать.

Вам для какого формата — кафе, ресторан, доставка?""",
            "service_beauty": """Салоны красоты — одно из любимых направлений.

Срок: 10-12 дней. Каталог услуг, онлайн-запись, выбор мастера, профиль клиента.

Можно добавить напоминания о записи, программу лояльности, отзывы.

Пример: GlowSpa — очень красивый проект получился.

Расскажите про ваш салон, что хотите реализовать?""",
            "service_fitness": """Фитнес-клубы — интересные проекты.

Срок: 10-12 дней. Расписание занятий, абонементы, запись к тренеру, профиль с прогрессом.

Можно добавить push-уведомления, трекер тренировок, видео-тренировки.

У вас клуб или студия? Сколько направлений?""",
            "service_medical": """Медицинские проекты — сложнее, но делаем.

Срок: 12-15 дней. Список врачей, онлайн-запись, история приёмов, результаты анализов.

Можно добавить видеоконсультации, напоминания о приёме, чат с врачом.

Расскажите подробнее — клиника или частная практика?""",
            "service_services": """Сервисные бизнесы тоже разрабатываем.

Срок: 8-12 дней в зависимости от функционала. Каталог услуг, бронирование, оплата, история заказов.

Делали для автомоек, аренды авто, такси, курьерских служб.

Какой у вас сервис? Расскажите, подберём решение."""
        }
        
        text = services_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data.startswith("ref_"):
        user_id = query.from_user.id
        user = query.from_user
        stats = referral_manager.get_or_create_user(user_id, user.username, user.first_name)
        
        if data == "ref_copy_code":
            await query.answer(f"Код: {stats.referral_code}", show_alert=True)
        
        elif data == "ref_copy_code_btn":
            await query.answer("Код скопирован!")
        
        elif data == "ref_share":
            ref_link = referral_manager.get_bot_referral_link(stats.referral_code)
            share_text = f"Присоединяйся к WEB4TG Studio! Получи 50 монет по моей ссылке: {ref_link}"
            share_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "📋 Скопировать ссылку",
                    callback_data="ref_copy_link_btn",
                    **copy_text_button("copy", ref_link)
                )],
                [InlineKeyboardButton("◀️ Назад", callback_data="ref_back")]
            ])
            await query.answer()
            await query.message.reply_text(
                f"📤 **Поделитесь этой ссылкой:**\n\n{ref_link}\n\n"
                f"Или отправьте друзьям это сообщение:\n\n_{share_text}_",
                parse_mode="Markdown",
                reply_markup=share_keyboard
            )
        
        elif data == "ref_copy_link_btn":
            await query.answer("Ссылка скопирована!")
        
        elif data == "ref_list":
            referrals = referral_manager.get_referrals_list(user_id)
            
            if not referrals:
                text = "👥 **Мои рефералы**\n\nУ вас пока нет приглашённых друзей.\n\nПоделитесь своей ссылкой и получайте монеты!"
            else:
                text = f"👥 **Мои рефералы** ({len(referrals)})\n\n"
                for i, ref in enumerate(referrals[:10], 1):
                    name = ref.referred_first_name or ref.referred_username or f"User {ref.referred_telegram_id}"
                    status_icon = "✅" if ref.status == "active" else "⏳"
                    text += f"{i}. {status_icon} {name} — +{ref.bonus_amount} монет\n"
                
                if len(referrals) > 10:
                    text += f"\n...и ещё {len(referrals) - 10}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="ref_back")]
            ])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        
        elif data == "ref_back":
            tier_emoji = stats.get_tier_emoji()
            ref_link = referral_manager.get_bot_referral_link(stats.referral_code)
            
            text = f"""💰 **Реферальная программа**

📊 **Ваша статистика:**
{tier_emoji} Уровень: {stats.tier.value}
👥 Приглашено: {stats.total_referrals}
💵 Заработано: {stats.total_earnings} монет

🔗 **Ваш код:** `{stats.referral_code}`
📤 **Ссылка:** {ref_link}"""
            
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
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    
    elif data.startswith("tasks_"):
        user_id = query.from_user.id
        
        if data == "tasks_progress":
            progress = tasks_tracker.get_user_progress(user_id)
            available = tasks_tracker.get_available_tasks(user_id)
            
            completed_count = len(progress.completed_tasks)
            total_tasks = sum(len(tasks) for tasks in TASKS_CONFIG.values())
            
            tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
            current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
            
            text = f"""📊 **Твой прогресс**

{current_emoji} **Уровень:** {progress.get_tier_name()}
💰 **Монеты:** {progress.total_coins}
🔥 **Стрик:** {progress.current_streak} дней (макс: {progress.max_streak})
💵 **Скидка:** {progress.get_discount_percent()}%
✅ **Выполнено:** {completed_count} из {total_tasks} заданий

**До следующего уровня:**"""
            
            next_tiers = [(200, 5), (500, 10), (800, 15), (1200, 20), (1500, 25)]
            for coins_need, discount in next_tiers:
                if progress.total_coins < coins_need:
                    remaining = coins_need - progress.total_coins
                    text += f"\n🎯 Ещё {remaining} монет до {discount}% скидки"
                    break
            else:
                text += "\n👑 Максимальный уровень достигнут!"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Telegram", callback_data="tasks_telegram"),
                 InlineKeyboardButton("📺 YouTube", callback_data="tasks_youtube")],
                [InlineKeyboardButton("📸 Instagram", callback_data="tasks_instagram"),
                 InlineKeyboardButton("🎵 TikTok", callback_data="tasks_tiktok")],
                [InlineKeyboardButton("Назад", callback_data="tasks_back")]
            ])
            
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        
        elif data == "tasks_back" or data == "earn_coins" or data == "tasks_menu":
            progress = tasks_tracker.get_user_progress(user_id)
            tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇"}
            current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
            
            text = f"""🎁 <b>Получи скидку до 30%!</b>

{current_emoji} <b>Уровень:</b> {progress.get_tier_name()}
💰 <b>Монеты:</b> {progress.total_coins}
💵 <b>Скидка:</b> {progress.get_discount_percent()}%

<b>Как заработать скидку:</b>
📱 Выполняй задания — до 15%
👥 Приглашай друзей — 200 монет/друг
⭐ Оставь отзыв — до 500 монет

Выбери раздел:"""
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Telegram", callback_data="tasks_telegram"),
                 InlineKeyboardButton("📺 YouTube", callback_data="tasks_youtube")],
                [InlineKeyboardButton("📸 Instagram", callback_data="tasks_instagram"),
                 InlineKeyboardButton("🎵 TikTok", callback_data="tasks_tiktok")],
                [InlineKeyboardButton("👥 Пригласить друзей", callback_data="referral_menu")],
                [InlineKeyboardButton("⭐ Оставить отзыв", callback_data="loyalty_review")],
                [InlineKeyboardButton("📊 Мой прогресс", callback_data="tasks_progress")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
            ])
            
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        
        elif data in ["tasks_telegram", "tasks_youtube", "tasks_instagram", "tasks_tiktok"]:
            platform = data.replace("tasks_", "")
            platform_names = {
                "telegram": "📱 Telegram",
                "youtube": "📺 YouTube", 
                "instagram": "📸 Instagram",
                "tiktok": "🎵 TikTok"
            }
            
            tasks = tasks_tracker.get_available_tasks(user_id)["tasks"].get(platform, [])
            progress = tasks_tracker.get_user_progress(user_id)
            
            text = f"**{platform_names[platform]} задания**\n\n"
            
            buttons = []
            for task in tasks:
                status_icon = "✅" if task["status"] == "completed" else "⭐"
                tname = task.get("name", task["id"])
                text += f"{status_icon} {tname} — {task['coins']} монет\n"
                
                if task["status"] != "completed":
                    buttons.append([InlineKeyboardButton(
                        f"▶️ {tname} (+{task['coins']})",
                        callback_data=f"do_task_{task['id']}"
                    )])
            
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")])
            
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data.startswith("do_task_"):
        task_id = data.replace("do_task_", "")
        user_id = query.from_user.id
        
        task_config = None
        platform = None
        for plat, tasks in TASKS_CONFIG.items():
            if task_id in tasks:
                task_config = tasks[task_id]
                platform = plat
                break
        
        if not task_config:
            await query.answer("Задание не найдено", show_alert=True)
            return
        
        task_type = task_config.get("type", "view")
        task_name = task_config.get("name", task_id.replace(f"{platform}_", "").replace("_", " ").title())
        task_desc = task_config.get("desc", "")
        coins = task_config.get("coins", 0)
        task_url = task_config.get("url", "")
        
        platform_info = {
            "telegram": {"emoji": "📱", "name": "Telegram"},
            "youtube": {"emoji": "📺", "name": "YouTube"},
            "instagram": {"emoji": "📸", "name": "Instagram"},
            "tiktok": {"emoji": "🎵", "name": "TikTok"}
        }
        
        pinfo = platform_info.get(platform, {"emoji": "📱", "name": platform})
        
        task_type_names = {
            "subscribe": "Подписаться",
            "like": "Поставить лайк",
            "comment": "Написать комментарий",
            "share": "Поделиться",
            "view": "Посмотреть",
            "save": "Сохранить",
            "bell": "Включить уведомления"
        }
        
        action_text = task_type_names.get(task_type, "Выполнить")
        
        if platform == "telegram":
            if task_type == "subscribe":
                is_subscribed = await tasks_tracker.check_telegram_subscription(user_id, task_config.get("channel", "web4_tg"))
                
                if not is_subscribed:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"{pinfo['emoji']} Открыть канал @web4_tg", url=task_url or "https://t.me/web4_tg")],
                        [InlineKeyboardButton("✅ Я подписался", callback_data=f"verify_task_{task_id}")],
                        [InlineKeyboardButton("◀️ Назад", callback_data=f"tasks_{platform}")]
                    ])
                    
                    await query.edit_message_text(
                        f"{pinfo['emoji']} **{task_name}**\n\n"
                        f"📌 {task_desc}\n\n"
                        f"1️⃣ Нажми кнопку — откроется канал @web4_tg\n"
                        f"2️⃣ Подпишись на канал\n"
                        f"3️⃣ Вернись и нажми «Я подписался»\n\n"
                        f"🎁 Награда: **{coins} монет**",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                    return
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{pinfo['emoji']} Открыть канал @web4_tg", url=task_url or "https://t.me/web4_tg")],
                    [InlineKeyboardButton("✅ Готово", callback_data=f"confirm_task_{task_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data=f"tasks_{platform}")]
                ])
                
                await query.edit_message_text(
                    f"{pinfo['emoji']} **{task_name}**\n\n"
                    f"📌 {task_desc}\n\n"
                    f"1️⃣ Нажми кнопку — откроется канал @web4_tg\n"
                    f"2️⃣ {action_text}\n"
                    f"3️⃣ Вернись и нажми «Готово»\n\n"
                    f"🎁 Награда: **{coins} монет**",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                return
        
        if task_url:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{pinfo['emoji']} Открыть {pinfo['name']}", url=task_url)],
                [InlineKeyboardButton("✅ Готово", callback_data=f"confirm_task_{task_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data=f"tasks_{platform}")]
            ])
            
            await query.edit_message_text(
                f"{pinfo['emoji']} **{task_name}**\n\n"
                f"📌 {task_desc}\n\n"
                f"1️⃣ Нажми кнопку — откроется {pinfo['name']}\n"
                f"2️⃣ Выполни задание\n"
                f"3️⃣ Вернись и нажми «Готово»\n\n"
                f"🎁 Награда: **{coins} монет**",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
        
        result = await tasks_tracker.complete_task(user_id, task_id, platform)
        
        if result["success"]:
            await query.answer(f"🎉 +{result['coinsAwarded']} монет! Всего: {result['totalCoins']}", show_alert=True)
        else:
            await query.answer(result["message"], show_alert=True)
        
        tasks = tasks_tracker.get_available_tasks(user_id)["tasks"].get(platform, [])
        platform_names = {"telegram": "📱 Telegram", "youtube": "📺 YouTube", "instagram": "📸 Instagram", "tiktok": "🎵 TikTok"}
        
        text = f"**{platform_names[platform]} задания**\n\n"
        buttons = []
        for task in tasks:
            status_icon = "✅" if task["status"] == "completed" else "⭐"
            tname = task.get("name", task["id"])
            text += f"{status_icon} {tname} — {task['coins']} монет\n"
            
            if task["status"] != "completed":
                buttons.append([InlineKeyboardButton(f"▶️ {tname} (+{task['coins']})", callback_data=f"do_task_{task['id']}")])
        
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data.startswith("verify_task_"):
        task_id = data.replace("verify_task_", "")
        user_id = query.from_user.id
        
        platform = None
        for plat, tasks in TASKS_CONFIG.items():
            if task_id in tasks:
                platform = plat
                break
        
        result = await tasks_tracker.complete_task(user_id, task_id, platform or "telegram")
        
        if result["success"]:
            await query.answer(f"🎉 +{result['coinsAwarded']} монет! Всего: {result['totalCoins']}", show_alert=True)
            
            tasks = tasks_tracker.get_available_tasks(user_id)["tasks"].get(platform, [])
            platform_names = {"telegram": "📱 Telegram", "youtube": "📺 YouTube", "instagram": "📸 Instagram", "tiktok": "🎵 TikTok"}
            
            text = f"**{platform_names[platform]} задания**\n\n"
            buttons = []
            for task in tasks:
                status_icon = "✅" if task["status"] == "completed" else "⭐"
                tname = task.get("name", task["id"])
                text += f"{status_icon} {tname} — {task['coins']} монет\n"
                
                if task["status"] != "completed":
                    buttons.append([InlineKeyboardButton(f"▶️ {tname} (+{task['coins']})", callback_data=f"do_task_{task['id']}")])
            
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.answer(result["message"], show_alert=True)
    
    elif data.startswith("confirm_task_"):
        task_id = data.replace("confirm_task_", "")
        user_id = query.from_user.id
        
        platform = None
        for plat, tasks in TASKS_CONFIG.items():
            if task_id in tasks:
                platform = plat
                break
        
        result = await tasks_tracker.complete_task(user_id, task_id, platform or "youtube")
        
        if result["success"]:
            await query.answer(f"🎉 +{result['coinsAwarded']} монет! Всего: {result['totalCoins']}", show_alert=True)
            
            tasks = tasks_tracker.get_available_tasks(user_id)["tasks"].get(platform, [])
            platform_names = {"telegram": "📱 Telegram", "youtube": "📺 YouTube", "instagram": "📸 Instagram", "tiktok": "🎵 TikTok"}
            
            text = f"**{platform_names.get(platform, 'Задания')} задания**\n\n"
            buttons = []
            for task in tasks:
                status_icon = "✅" if task["status"] == "completed" else "⭐"
                tname = task.get("name", task["id"])
                text += f"{status_icon} {tname} — {task['coins']} монет\n"
                
                if task["status"] != "completed":
                    buttons.append([InlineKeyboardButton(f"▶️ {tname} (+{task['coins']})", callback_data=f"do_task_{task['id']}")])
            
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.answer(result["message"], show_alert=True)
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """🛒 <b>E-Commerce проекты</b>

<b>Radiance</b> — магазин одежды
• <i>Было:</i> Продажи только через Instagram DM, терялись заявки
• <i>Стало:</i> Telegram Mini App с каталогом 500+ товаров
• <i>Результат:</i> +40% к продажам за первый месяц

<b>TimeElite</b> — элитные часы
• <i>Было:</i> Сайт с низкой конверсией 0.8%
• <i>Стало:</i> Mini App с премиальным UX
• <i>Результат:</i> Конверсия выросла до 3.2%

Также: SneakerVault, FragranceRoyale, FloralArt

Хотите такой же результат для своего бизнеса?""",
            "portfolio_services": """💅 <b>Сервисные проекты</b>

<b>GlowSpa</b> — салон красоты
• <i>Было:</i> Запись по телефону, 30% no-show
• <i>Стало:</i> Онлайн-запись + автоматические напоминания
• <i>Результат:</i> No-show снизился до 5%

<b>DeluxeDine</b> — ресторан с доставкой
• <i>Было:</i> Заказы через WhatsApp, путаница с адресами
• <i>Стало:</i> Полная система заказов и доставки
• <i>Результат:</i> Обработка заказов ускорилась в 3 раза

Расскажите о вашем бизнесе — покажу подходящий кейс.""",
            "portfolio_fintech": """💰 <b>Финтех проекты</b>

<b>Banking App</b> — банковское приложение
• <i>Было:</i> Только веб-интерфейс, неудобно с телефона
• <i>Стало:</i> Mini App: счета, переводы, история
• <i>Результат:</i> 60% пользователей перешли на Mini App

<b>OXYZ NFT</b> — NFT маркетплейс
• <i>Было:</i> Сложная процедура покупки NFT
• <i>Стало:</i> Покупка в 2 клика через Telegram
• <i>Результат:</i> Средний чек вырос на 25%

Планируете финтех-проект?""",
            "portfolio_education": """📚 <b>Образовательные проекты</b>

<b>Courses</b> — онлайн-школа
• <i>Было:</i> Курсы на Getcourse, высокие комиссии
• <i>Стало:</i> Собственная платформа в Telegram
• <i>Результат:</i> Экономия 15% на комиссиях, рост завершаемости курсов на 20%

Каталог курсов, трекинг прогресса, сертификаты — всё внутри Telegram.

У вас образовательный проект?"""
        }
        
        text = portfolio_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "referral_menu":
        user = query.from_user
        stats = referral_manager.get_or_create_user(user.id, user.username, user.first_name)
        
        tier_emoji = stats.get_tier_emoji()
        ref_link = referral_manager.get_bot_referral_link(stats.referral_code)
        
        text = f"""💰 **Реферальная программа**

📊 **Ваша статистика:**
{tier_emoji} Уровень: {stats.tier.value}
👥 Приглашено: {stats.total_referrals}
💵 Заработано: {stats.total_earnings} монет

🔗 **Ваш код:** `{stats.referral_code}`
📤 **Ссылка:** {ref_link}

**Награды:**
• Вы получаете: {REFERRER_REWARD} монет за друга
• Друг получает: 50 монет

Приглашай друзей и зарабатывай!"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Скопировать код", callback_data="ref_copy_code")],
            [InlineKeyboardButton("📤 Поделиться ссылкой", callback_data="ref_share")],
            [InlineKeyboardButton("👥 Мои рефералы", callback_data="ref_list")],
            [InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")]
        ])
        
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif data and data.startswith("bc_"):
        from src.security import is_admin
        if not is_admin(user_id):
            await query.edit_message_text("⛔ Доступ запрещён")
            return

        if data == "bc_cancel":
            context.user_data.pop('broadcast_draft', None)
            context.user_data.pop('broadcast_compose', None)
            await query.edit_message_text("❌ Рассылка отменена")

        elif data.startswith("bc_audience_"):
            audience = data.replace("bc_audience_", "")
            draft = context.user_data.get('broadcast_draft')
            if not draft:
                await query.edit_message_text("❌ Черновик не найден. Начните заново: /broadcast")
                return

            from src.broadcast import broadcast_manager
            if audience == "all":
                count = len(broadcast_manager.get_user_ids('all'))
            else:
                count = len(broadcast_manager.get_user_ids('priority', priority=audience))

            context.user_data['broadcast_audience'] = audience

            audience_names = {'all': 'всем', 'hot': 'горячим', 'warm': 'тёплым', 'cold': 'холодным'}
            audience_name = audience_names.get(audience, audience)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Да, отправить {count} чел.", callback_data="bc_confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data="bc_cancel")]
            ])
            await query.edit_message_text(
                f"📤 <b>Подтверждение рассылки</b>\n\n"
                f"Аудитория: <b>{audience_name}</b>\n"
                f"Получателей: <b>{count}</b>\n\n"
                f"Отправить?",
                parse_mode="HTML",
                reply_markup=keyboard
            )

        elif data == "bc_confirm":
            draft = context.user_data.get('broadcast_draft')
            audience = context.user_data.get('broadcast_audience', 'all')
            if not draft:
                await query.edit_message_text("❌ Черновик не найден. Начните заново: /broadcast")
                return

            from src.broadcast import broadcast_manager

            bc_id = broadcast_manager.create_broadcast(
                admin_id=user_id,
                content_type=draft['type'],
                text_content=draft.get('text'),
                media_file_id=draft.get('file_id'),
                caption=draft.get('caption'),
                parse_mode='HTML' if draft['type'] == 'text' else None,
                target_audience=audience
            )

            context.user_data.pop('broadcast_draft', None)
            context.user_data.pop('broadcast_audience', None)

            await query.edit_message_text("📤 <b>Рассылка запущена...</b>\n\n⏳ Ожидайте отчёт.", parse_mode="HTML")

            admin_chat_id = query.message.chat_id

            async def progress_callback(sent, failed, blocked, total):
                try:
                    await context.bot.send_message(
                        chat_id=admin_chat_id,
                        text=f"📊 Прогресс: {sent + failed + blocked}/{total}\n✅ {sent} | ❌ {failed} | 🚫 {blocked}"
                    )
                except Exception:
                    pass

            result = await broadcast_manager.send_broadcast(
                bot=context.bot,
                broadcast_id=bc_id,
                progress_callback=progress_callback
            )

            bc = broadcast_manager.get_broadcast(bc_id)
            if bc:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"✅ <b>Рассылка завершена!</b>\n\n"
                         f"📊 <b>Результаты:</b>\n"
                         f"👥 Всего: {bc.get('total_users', 0)}\n"
                         f"✅ Доставлено: {bc.get('sent_count', 0)}\n"
                         f"❌ Ошибки: {bc.get('failed_count', 0)}\n"
                         f"🚫 Заблокировали: {bc.get('blocked_count', 0)}",
                    parse_mode="HTML"
                )

    elif data == "leave_request":
        analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)
        text = """Отлично, давайте обсудим ваш проект!

Напишите мне:
— Какой у вас бизнес?
— Что хотите реализовать?
— Какой бюджет рассматриваете?

Я подготовлю индивидуальное предложение."""
        await query.edit_message_text(
            text,
            reply_markup=get_lead_keyboard()
        )

    elif data.startswith("package_app_subscription_"):
        months = data.replace("package_app_subscription_", "")
        discount_map = {"3": 5, "6": 10, "12": 15}
        discount = discount_map.get(months, 0)
        text = (
            f"📦 <b>Пакет: Приложение + {months} мес подписки</b>\n\n"
            f"🎁 Скидка: <b>{discount}%</b> на всё\n\n"
            f"Для оформления этого пакета оставьте заявку, и менеджер рассчитает итоговую стоимость с учётом скидки."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Оставить заявку", callback_data="leave_request")],
            [InlineKeyboardButton("◀️ Назад", callback_data="loyalty_packages")]
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("sub_"):
        from src.pricing import SUBSCRIPTIONS, format_price
        sub_key = data.replace("sub_", "")
        sub = SUBSCRIPTIONS.get(sub_key)
        if sub:
            features_text = "\n".join([f"  • {f}" for f in sub["features"]])
            text = (
                f"📦 <b>{sub['name']}</b> — {format_price(sub['price'])}/мес\n\n"
                f"<b>Что входит:</b>\n{features_text}\n\n"
                f"Хотите подключить? Оставьте заявку!"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Оставить заявку", callback_data="leave_request")],
                [InlineKeyboardButton("◀️ Назад к ценам", callback_data="price_subs")]
            ])
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text("Информация не найдена", reply_markup=get_back_keyboard())

    else:
        logger.warning(f"Unknown callback_data: {data} from user {user_id}")
