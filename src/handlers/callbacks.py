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

    _followup_cta_callbacks = {"menu_portfolio", "menu_calculator", "book_consultation", "menu_ai_agent", "menu_services"}
    if data in _followup_cta_callbacks:
        try:
            from src.followup import follow_up_manager
            follow_up_manager.track_cta_click(user_id)
            follow_up_manager.handle_silent_activity(user_id, activity_type="cta_click")
        except Exception:
            pass

    if data == "open_app":
        await query.message.reply_text(
            "Выбирайте — я на связи 👇",
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
                try:
                    from src.manager_coaching import generate_coaching_briefing
                    briefing = generate_coaching_briefing(
                        user_id=user.id,
                        trigger_type="explicit_request",
                    )
                    if briefing:
                        await context.bot.send_message(int(manager_chat_id), briefing, parse_mode="HTML")
                except Exception:
                    pass
            except Exception:
                pass
    
    elif data == "menu_back":
        await query.edit_message_text(
            "Выбирайте — я на связи 👇",
            reply_markup=get_main_menu_keyboard()
        )
    
    elif data == "menu_services":
        text = """🚀 200+ проектов запущено — и каждый приносит результат.

Наши клиенты получают первые заказы уже через неделю после запуска. Мини-апп внутри Telegram — это x3 к конверсии по сравнению с обычным сайтом.

Выберите свою нишу — покажу, что мы можем для вас 👇"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_services_keyboard()
        )
    
    elif data == "menu_portfolio":
        from src.portfolio_showcase import get_portfolio_menu
        text, keyboard = get_portfolio_menu()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    elif data == "menu_compare":
        from src.package_comparison import get_comparison_view
        text, keyboard = get_comparison_view()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "menu_calculator":
        analytics.track(user_id, FunnelEvent.CALCULATOR_OPEN)
        calc = calculator_manager.get_calculation(user_id)
        await query.edit_message_text(
            f"**🧮 Калькулятор стоимости**\nСоберите свой проект за 30 секунд\n\n{calc.get_summary()}",
            parse_mode="Markdown",
            reply_markup=get_calculator_keyboard()
        )
    
    elif data == "menu_ai_agent":
        text = """Ваши менеджеры тратят 4 часа в день на одни и те же вопросы?

AI-агент берёт это на себя — отвечает клиентам 24/7, помнит каждый разговор и не уходит в отпуск. Наши клиенты экономят до 120 000 ₽/мес на поддержке.

Стоимость — 49 000 ₽. Окупается за 2-3 месяца.

🎁 Первые 7 дней — бесплатный тест на вашем бизнесе. Без обязательств.

Хотите попробовать?"""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "menu_lead":
        analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)
        text = """Рад, что заинтересовались! 🙌

Давайте так: просто расскажите в двух словах, чем занимаетесь и что хотите получить от приложения. Без формальностей — как другу.

Или нажмите кнопку ниже, и я сам свяжусь с вами в течение часа."""
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )
    
    elif data == "payment_stars":
        from src.keyboards import get_stars_payment_keyboard
        await query.message.edit_text(
            "⭐ <b>Оплата через Telegram Stars</b>\n\n"
            "Мгновенно, без карт и реквизитов — всё прямо в Telegram.\n"
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
        try:
            from src.feedback_loop import feedback_loop
            feedback_loop.record_outcome(user_id, 'callback_payment')
        except Exception:
            pass
        await handle_payment_callback(update, context, action)
    
    elif data == "menu_faq" or data == "faq_back":
        await query.edit_message_text(
            "❓ **Частые вопросы**\n\nВыберите тему — а если не найдёте ответ, просто напишите мне. Я рядом 😉",
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
        text = """🎁 <b>Ваши привилегии</b>

Здесь вы получаете реальные деньги обратно — скидки до 25% на любой проект:

💎 <b>Оставьте отзыв</b> — до 500 монет (= живая скидка)
🔄 <b>Закажите повторно</b> — автоматически +5% сверху
📦 <b>Возьмите пакет</b> — экономия до 15% на подписке

Чем активнее вы с нами — тем выгоднее каждый следующий проект 👇"""
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

<i>Скидки суммируются (макс. 25%)</i>"""
        
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=get_loyalty_menu_keyboard()
        )
    
    elif data == "review_video":
        context.user_data["pending_review_type"] = "video"
        text = """🎬 <b>Видео-отзыв</b>

Будем рады увидеть вас! Запишите короткое видео (30 сек — 2 мин) — расскажите, как прошла работа с WEB4TG Studio.

📹 <b>Просто отправьте видео в этот чат:</b>
• Кружочек (видеосообщение)
• Видео из галереи
• Свежую запись

<i>Ваш отзыв вдохновляет нас и помогает другим сделать правильный выбор 🙏</i>"""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="loyalty_review")]])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    elif data == "review_text":
        context.user_data["pending_review_type"] = "text_photo"
        text = """📝 <b>Текстовый отзыв</b>

Расскажите, как всё прошло — нам важно каждое мнение!

Просто отправьте в этот чат:
1. Пару слов о вашем опыте
2. Скриншот или фото приложения

<i>Можно одним сообщением или несколькими — как удобнее 😊</i>"""
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
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Оставить заявку", callback_data="leave_request")],
                [InlineKeyboardButton("◀️ Назад", callback_data="loyalty_packages")]
            ])
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text("Информация не найдена", reply_markup=get_back_keyboard())
    
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

Отличный выбор! Готовы обсудить детали? Жмите кнопку — ответим быстро 👇"""
                await query.edit_message_text(
                    text,
                    parse_mode="Markdown",
                    reply_markup=get_lead_keyboard()
                )
                return
        elif data in feature_map:
            calc.add_feature(feature_map[data])
        
        await query.edit_message_text(
            f"**🧮 Калькулятор стоимости**\nСоберите свой проект за 30 секунд\n\n{calc.get_summary()}",
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
            """✅ Заявка принята, спасибо!

Наш менеджер свяжется с вами в течение 30 минут в рабочее время (10:00–19:00 МСК).

А пока я здесь — задавайте любые вопросы, помогу разобраться 😊""",
            reply_markup=get_back_keyboard()
        )
    
    elif data == "lead_question":
        await query.edit_message_text(
            "Спрашивайте что угодно — я AI-консультант WEB4TG и знаю всё о наших проектах, ценах и сроках 💬",
            reply_markup=get_back_keyboard()
        )
    
    elif data.startswith("service_"):
        services_info = {
            "service_shop": """Ваши клиенты уходят с сайта, не завершив покупку? У 70% интернет-магазинов та же проблема.

Мини-апп в Telegram решает это: каталог, корзина, оплата — всё в 2 клика, без загрузки сайта. Наш клиент Radiance получил +40% к продажам за первый месяц.

Запуск — от 7 дней. Каталог, корзина, оплата, профиль — всё в базе. Можно добавить фильтры, избранное, push, лояльность.

А что продаёте вы? Покажу похожий кейс 👇""",
            "service_restaurant": """Сколько заказов вы теряете, пока клиент ждёт ответа в WhatsApp?

Мини-апп автоматизирует всё: меню, заказ, оплата, бронь стола — без звонков и переписки. DeluxeDine ускорил обработку заказов в 3 раза.

Запуск — от 7 дней. Можно добавить лояльность, push о статусе заказа, онлайн-оплату.

У вас кафе, ресторан или доставка? Подберу решение под формат 👇""",
            "service_beauty": """30% записей не приходят? Знакомая боль для салонов.

Онлайн-запись с автоматическими напоминаниями решает это. GlowSpa снизил no-show с 30% до 5% за первый месяц.

Запуск — от 10 дней. Каталог услуг, выбор мастера, профиль клиента — в базе. Плюс лояльность, отзывы, напоминания.

Сколько мастеров у вас работает? Покажу, как это будет выглядеть 👇""",
            "service_fitness": """Клиенты покупают абонемент и забывают о нём? Push-уведомления и трекер прогресса возвращают до 35% «спящих» клиентов.

Мини-апп: расписание, абонементы, запись к тренеру, прогресс — всё в одном месте. Можно добавить видео-тренировки и программы.

Запуск — от 10 дней.

У вас клуб или студия? Сколько направлений — подберу оптимальную структуру 👇""",
            "service_medical": """Пациенты не могут дозвониться в регистратуру? 40% звонков в клиники остаются без ответа.

Мини-апп решает это: онлайн-запись, выбор врача, история приёмов, результаты анализов — без очередей и ожидания. Можно добавить видеоконсультации и чат с врачом.

Запуск — от 12 дней.

У вас клиника или частная практика? Покажу готовое решение 👇""",
            "service_services": """Ваши клиенты хотят заказать услугу в один клик — но приходится звонить, ждать, переписываться?

Мини-апп: каталог услуг, бронирование, оплата, статус заказа — всё автоматизировано. Делали для автомоек, аренды, такси, курьерских служб.

Запуск — от 8 дней.

Какой у вас сервис? Подберу лучшее решение под вашу нишу 👇"""
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
            share_text = f"🎁 Зацени WEB4TG Studio — делают крутые мини-аппы для Telegram. Переходи по моей ссылке и получи 50 монет на старт: {ref_link}"
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
                f"📤 **Ваша персональная ссылка:**\n\n{ref_link}\n\n"
                f"Перешлите друзьям — за каждого вы получите 200 монет:\n\n_{share_text}_",
                parse_mode="Markdown",
                reply_markup=share_keyboard
            )
        
        elif data == "ref_copy_link_btn":
            await query.answer("Ссылка скопирована!")
        
        elif data == "ref_list":
            referrals = referral_manager.get_referrals_list(user_id)
            
            if not referrals:
                text = "👥 **Мои рефералы**\n\nПока пусто — но это легко исправить!\n\nОтправьте ссылку другу и получите 200 монет, когда он присоединится 🎁"
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
            
            text = f"""🎁 **Приглашай друзей — зарабатывай вместе!**

{tier_emoji} Уровень: {stats.tier.value}
👥 Приглашено: {stats.total_referrals}
💵 Заработано: {stats.total_earnings} монет

🔗 **Твой код:** `{stats.referral_code}`
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
            
            tier_emoji_map = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
            current_emoji = tier_emoji_map.get(progress.get_discount_percent(), "🔰")
            
            text = f"""🏆 **Твой прогресс — так держать!**

{current_emoji} **Уровень:** {progress.get_tier_name()}
💰 **Монеты:** {progress.total_coins}
🔥 **Стрик:** {progress.current_streak} дней (макс: {progress.max_streak})
💵 **Твоя скидка:** {progress.get_discount_percent()}%
✅ **Выполнено:** {completed_count} из {total_tasks} заданий

**🎯 До следующей награды:**"""
            
            next_tiers = [(500, 5), (1000, 10), (1500, 15), (2000, 20), (2500, 25)]
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
            tier_emoji_map = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
            current_emoji = tier_emoji_map.get(progress.get_discount_percent(), "🔰")
            
            text = f"""🎮 <b>Зарабатывай скидку до 25% — это реально просто!</b>

{current_emoji} <b>Твой уровень:</b> {progress.get_tier_name()}
💰 <b>На счету:</b> {progress.total_coins} монет
💵 <b>Текущая скидка:</b> {progress.get_discount_percent()}%

🔥 <b>Быстрые способы заработать:</b>
📱 Простые задания = до 25% скидки
👥 Пригласи друга = 200 монет сразу
⭐ Оставь отзыв = до 500 монет

Жми и зарабатывай 👇"""
            
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
            "portfolio_ecommerce": """🛒 <b>E-Commerce — как наши клиенты растут на 40%+</b>

<b>Radiance</b> — магазин одежды
😩 <i>Было:</i> Продажи только через Instagram DM — заявки терялись, менеджеры не справлялись
🚀 <i>Стало:</i> Telegram Mini App с каталогом 500+ товаров, корзиной и онлайн-оплатой
💰 <i>Результат:</i> <b>+40% к продажам за первый месяц</b>

<b>TimeElite</b> — элитные часы
😩 <i>Было:</i> Сайт с конверсией 0.8% — трафик есть, продаж нет
🚀 <i>Стало:</i> Mini App с премиальным UX и персонализацией
💰 <i>Результат:</i> <b>Конверсия выросла до 3.2% (x4!)</b>

Также: SneakerVault, FragranceRoyale, FloralArt

Хотите такие же цифры для вашего магазина? 👇""",
            "portfolio_services": """💅 <b>Сервисы — автоматизация, которая экономит часы каждый день</b>

<b>GlowSpa</b> — салон красоты
😩 <i>Было:</i> Запись по телефону, 30% клиентов просто не приходили
🚀 <i>Стало:</i> Онлайн-запись + автоматические напоминания за 2 часа до визита
💰 <i>Результат:</i> <b>No-show снизился с 30% до 5%</b> — это десятки тысяч рублей в месяц

<b>DeluxeDine</b> — ресторан с доставкой
😩 <i>Было:</i> Заказы через WhatsApp — путаница с адресами, потерянные заказы
🚀 <i>Стало:</i> Полная система заказов и доставки в Mini App
💰 <i>Результат:</i> <b>Обработка заказов ускорилась в 3 раза</b>

Узнали свою ситуацию? Давайте обсудим ваш проект 👇""",
            "portfolio_fintech": """💰 <b>Финтех — когда удобство = деньги</b>

<b>Banking App</b> — банковское приложение
😩 <i>Было:</i> Только веб-интерфейс — с телефона пользоваться невозможно
🚀 <i>Стало:</i> Mini App: счета, переводы, история — всё в Telegram
💰 <i>Результат:</i> <b>60% пользователей перешли на Mini App</b>

<b>OXYZ NFT</b> — NFT маркетплейс
😩 <i>Было:</i> Сложная процедура покупки — клиенты уходили на полпути
🚀 <i>Стало:</i> Покупка в 2 клика через Telegram
💰 <i>Результат:</i> <b>Средний чек вырос на 25%</b>

У вас финтех-идея? Давайте обсудим реализацию 👇""",
            "portfolio_education": """📚 <b>Образование — учиться прямо в Telegram</b>

<b>Courses</b> — онлайн-школа
😩 <i>Было:</i> Getcourse — высокие комиссии и низкая завершаемость курсов
🚀 <i>Стало:</i> Собственная платформа в Telegram: каталог, прогресс, сертификаты
💰 <i>Результат:</i> <b>Экономия 15% на комиссиях + рост завершаемости на 20%</b>

Ученики не уходят на другие платформы — всё внутри мессенджера, который они и так открывают 50 раз в день.

Запускаете образовательный проект? Давайте обсудим 👇"""
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
        
        text = f"""🎁 **Приглашай друзей — зарабатывай вместе!**

{tier_emoji} Уровень: {stats.tier.value}
👥 Приглашено: {stats.total_referrals}
💵 Заработано: {stats.total_earnings} монет

🔗 **Твой код:** `{stats.referral_code}`
📤 **Ссылка:** {ref_link}

💰 **За каждого друга:**
• Тебе — **{REFERRER_REWARD} монет** на счёт
• Другу — **50 монет** в подарок

Чем больше друзей — тем больше скидка 🚀"""
        
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
        text = """Отлично, давайте знакомиться! 🤝

Расскажите в свободной форме: чем занимаетесь и какое приложение хотите получить. Можно коротко — я задам уточняющие вопросы сам.

Или нажмите кнопку, и менеджер свяжется с вами в течение часа."""
        await query.edit_message_text(
            text,
            reply_markup=get_lead_keyboard()
        )

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

    elif data.startswith("smart_"):
        try:
            await _handle_smart_button(query, context, data, user_id)
        except Exception as e:
            logger.error(f"Smart button '{data}' error for user {user_id}: {e}")
            await query.message.reply_text("Произошла ошибка, попробуйте ещё раз.")

    elif data == "start_quiz":
        from src.onboarding import onboarding_manager
        onboarding_manager.start_quiz(user_id)
        text, keyboard = onboarding_manager.get_step_keyboard(0)
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("quiz_biz_"):
        from src.onboarding import onboarding_manager
        answer = data.replace("quiz_biz_", "")
        state = onboarding_manager.process_answer(user_id, answer)
        if state:
            text, keyboard = onboarding_manager.get_step_keyboard(state.step)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("quiz_prob_"):
        from src.onboarding import onboarding_manager
        answer = data.replace("quiz_prob_", "")
        state = onboarding_manager.process_answer(user_id, answer)
        if state:
            text, keyboard = onboarding_manager.get_step_keyboard(state.step)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("quiz_bud_"):
        from src.onboarding import onboarding_manager
        answer = data.replace("quiz_bud_", "")
        state = onboarding_manager.process_answer(user_id, answer)
        if state:
            text, keyboard = onboarding_manager.get_step_keyboard(state.step)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("quiz_time_"):
        from src.onboarding import onboarding_manager
        answer = data.replace("quiz_time_", "")
        state = onboarding_manager.process_answer(user_id, answer)
        if state and state.completed:
            onboarding_manager.save_to_lead(user_id)
            analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)
            text, keyboard = onboarding_manager.generate_recommendation(user_id)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "quiz_skip":
        from src.onboarding import onboarding_manager
        onboarding_manager.clear_state(user_id)
        await query.edit_message_text(
            "Без проблем! Вот всё, что я умею — выбирайте 👇",
            reply_markup=get_main_menu_keyboard()
        )

    elif data == "quiz_to_ai":
        from src.onboarding import onboarding_manager
        state = onboarding_manager.get_state(user_id)
        hint = ""
        if state and state.business_type:
            from src.onboarding import BUSINESS_TYPES
            biz = BUSINESS_TYPES.get(state.business_type, {})
            hint = f" для направления «{biz.get('name', '')}»"
        await query.message.reply_text(
            f"💬 Супер! Задавайте любой вопрос{hint} — "
            "я AI-консультант WEB4TG и помогу подобрать идеальное решение для вашего бизнеса 🚀"
        )

    elif data == "start_brief":
        from src.brief_generator import brief_generator
        brief_generator.start_brief(user_id)
        result = brief_generator.get_current_step(user_id)
        if result:
            text, keyboard = result
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("brief_") and not data.startswith("brief_send"):
        from src.brief_generator import brief_generator
        if data == "brief_cancel":
            brief_generator.clear_state(user_id)
            await query.edit_message_text(
                "❌ Бриф отменён.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
                ])
            )
        else:
            parts = data.split("_", 2)
            if len(parts) >= 3:
                step_id = parts[1]
                answer = parts[2]
                state = brief_generator.process_answer(user_id, step_id, answer)
                if state and state.completed:
                    brief_generator.save_to_lead(
                        user_id,
                        username=query.from_user.username,
                        first_name=query.from_user.first_name
                    )
                    analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)
                    text, keyboard = brief_generator.format_brief(user_id)
                    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
                elif state:
                    result = brief_generator.get_current_step(user_id)
                    if result:
                        text, keyboard = result
                        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "brief_send_manager":
        try:
            from src.feedback_loop import feedback_loop
            feedback_loop.record_outcome(user_id, 'brief_sent_manager')
        except Exception:
            pass
        from src.brief_generator import brief_generator
        import os
        manager_chat_id = os.environ.get("MANAGER_CHAT_ID")
        brief_text = brief_generator.get_brief_summary_for_manager(user_id)
        await query.edit_message_text(
            "✅ <b>Бриф отправлен менеджеру!</b>\n\n"
            "Он подготовит коммерческое предложение и свяжется с вами.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
            ])
        )
        if manager_chat_id:
            try:
                await context.bot.send_message(
                    int(manager_chat_id),
                    f"📋 <b>Новый бриф от клиента!</b>\n\n"
                    f"👤 {query.from_user.first_name} (@{query.from_user.username or 'нет'})\n"
                    f"🆔 <code>{user_id}</code>\n\n"
                    f"{brief_text}",
                    parse_mode="HTML"
                )
                try:
                    from src.manager_coaching import generate_coaching_briefing
                    briefing = generate_coaching_briefing(user_id=user_id)
                    if briefing:
                        await context.bot.send_message(int(manager_chat_id), briefing, parse_mode="HTML")
                except Exception:
                    pass
            except Exception:
                pass

    elif data == "generate_kp":
        from src.brief_generator import brief_generator
        from src.kp_generator import generate_and_send_kp, get_kp_prompt_for_brief
        state = brief_generator.get_state(user_id)
        if not state or not state.completed:
            await query.answer("Сначала пройдите бриф!", show_alert=True)
        else:
            await query.answer()
            await query.edit_message_text(
                "⏳ <b>Генерирую персональное предложение...</b>\n\n"
                "AI анализирует ваш бриф и формирует PDF-документ.",
                parse_mode="HTML"
            )
            client_name = query.from_user.first_name or ""
            ai_text = ""
            try:
                from src.ai_client import ai_client
                prompt = get_kp_prompt_for_brief(state.answers, client_name)
                messages = [{"role": "user", "parts": [{"text": prompt}]}]
                ai_text = await ai_client.generate_response(
                    messages, thinking_level="medium"
                )
            except Exception as e:
                logger.warning(f"AI KP text generation failed: {e}")

            discount_pct = 0
            try:
                from src.achievements import vip_program
                tier = vip_program.get_user_tier(user_id)
                tier_discounts = {"bronze": 0, "silver": 5, "gold": 10, "platinum": 15, "diamond": 20}
                discount_pct = tier_discounts.get(tier, 0)
            except Exception:
                pass

            success = await generate_and_send_kp(
                update=update,
                context=context,
                brief_answers=state.answers,
                client_name=client_name,
                ai_text=ai_text,
                discount_pct=discount_pct,
            )

            if success:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "✅ <b>PDF отправлен!</b>\n\n"
                        "Вы можете переслать документ коллегам для согласования."
                    ),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👨‍💼 Отправить менеджеру", callback_data="brief_send_manager")],
                        [InlineKeyboardButton("📄 Скачать ещё раз", callback_data="generate_kp")],
                        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu_back")],
                    ])
                )
                analytics.track(user_id, FunnelEvent.LEAD_FORM_OPEN)

    elif data == "my_dashboard":
        from src.client_dashboard import build_dashboard
        text, keyboard = build_dashboard(
            user_id,
            username=query.from_user.username or "",
            first_name=query.from_user.first_name or ""
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "referral_info":
        from src.referrals import referral_manager, REFERRER_REWARD
        ref_code = referral_manager.get_referral_code(user_id)
        ref_stats = referral_manager.get_user_stats(user_id)
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        text = (
            f"👥 <b>Ваша реферальная программа</b>\n\n"
            f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
            f"👥 Приглашено: {ref_stats.get('referral_count', 0)}\n"
            f"💰 Заработано: {ref_stats.get('total_earned', 0)} монет\n\n"
            f"За каждого друга: <b>+{REFERRER_REWARD} монет</b>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="my_dashboard")]
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "compare_packages":
        from src.package_comparison import get_comparison_view
        text, keyboard = get_comparison_view()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("pkg_"):
        from src.package_comparison import get_package_detail
        pkg_id = data.replace("pkg_", "")
        text, keyboard = get_package_detail(pkg_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("pkg_calc_"):
        from src.package_comparison import calculate_with_discount
        pkg_id = data.replace("pkg_calc_", "")
        discount = 0
        try:
            from src.tasks_tracker import tasks_tracker
            progress = tasks_tracker.get_user_progress(user_id)
            discount = progress.get_discount_percent()
        except Exception:
            pass
        text, keyboard = calculate_with_discount(pkg_id, discount)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("timeline_"):
        from src.package_comparison import get_timeline_view
        pkg_id = data.replace("timeline_", "")
        text, keyboard = get_timeline_view(pkg_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "portfolio_cases":
        from src.portfolio_showcase import get_portfolio_menu
        text, keyboard = get_portfolio_menu()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("pcase_"):
        from src.portfolio_showcase import get_case_detail
        case_id = data.replace("pcase_", "")
        text, keyboard = get_case_detail(case_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data in ("book_consult", "book_consultation"):
        try:
            from src.feedback_loop import feedback_loop
            feedback_loop.record_outcome(user_id, 'callback_booking')
        except Exception:
            pass
        from src.consultation import consultation_manager
        text, keyboard = consultation_manager.start_booking(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("consult_date_"):
        from src.consultation import consultation_manager
        date = data.replace("consult_date_", "")
        text, keyboard = consultation_manager.set_date(user_id, date)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("consult_time_"):
        from src.consultation import consultation_manager
        time_slot = data.replace("consult_time_", "")
        text, keyboard = consultation_manager.set_time(user_id, time_slot)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("consult_topic_"):
        from src.consultation import consultation_manager
        import os
        topic = data.replace("consult_topic_", "")
        text, keyboard = consultation_manager.set_topic(user_id, topic)
        consultation_manager.save_to_lead(user_id)
        try:
            from src.feedback_loop import feedback_loop
            feedback_loop.record_outcome(user_id, 'consultation_booked')
        except Exception:
            pass
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        manager_chat_id = os.environ.get("MANAGER_CHAT_ID")
        if manager_chat_id:
            try:
                notif = consultation_manager.get_manager_notification(
                    user_id, query.from_user.username or "", query.from_user.first_name or ""
                )
                await context.bot.send_message(int(manager_chat_id), notif, parse_mode="HTML")
                try:
                    from src.manager_coaching import generate_coaching_briefing
                    briefing = generate_coaching_briefing(user_id=user_id)
                    if briefing:
                        await context.bot.send_message(int(manager_chat_id), briefing, parse_mode="HTML")
                except Exception:
                    pass
            except Exception:
                pass

    elif data == "consult_cancel":
        await query.edit_message_text(
            "❌ Запись отменена.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Меню", callback_data="menu_back")]
            ])
        )

    elif data == "offers_menu":
        from src.countdown_offers import countdown_manager
        text, keyboard = countdown_manager.get_offers_menu()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("claim_offer_"):
        from src.countdown_offers import countdown_manager
        offer_id = data.replace("claim_offer_", "")
        text, keyboard = countdown_manager.claim_offer(user_id, offer_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "demo_menu":
        from src.trial_demo import get_demo_menu
        text, keyboard = get_demo_menu()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "savings_calc":
        from src.trial_demo import calculate_savings
        text, keyboard = calculate_savings()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "crm_dashboard":
        from src.crm_dashboard import get_crm_dashboard
        text, keyboard = get_crm_dashboard()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "crm_hot":
        from src.crm_dashboard import get_hot_leads_view
        text, keyboard = get_hot_leads_view()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "crm_health":
        from src.crm_dashboard import get_client_health_view
        text, keyboard = get_client_health_view()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "crm_analytics":
        from src.advanced_analytics import advanced_analytics as adv_analytics
        try:
            dropoff = adv_analytics.get_dropoff_analysis(days=30)
            stages = dropoff.get("stages", {})
            text = "📊 <b>Аналитика воронки (30 дней)</b>\n\n"
            if stages:
                for stage_name, stage_data in stages.items():
                    count = stage_data.get("count", 0)
                    text += f"• {stage_name}: {count}\n"
            else:
                text += "Данных пока недостаточно для анализа.\n"
            text += "\n<i>Подробная аналитика доступна через /crm</i>"
        except Exception as e:
            logger.warning(f"CRM analytics error: {e}")
            text = "📊 <b>Аналитика</b>\n\nДанных пока недостаточно для анализа."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад к CRM", callback_data="crm_dashboard")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "promo_enter":
        text = ("🎟 <b>Введите промокод</b>\n\n"
                "Отправьте команду с кодом:\n"
                "<code>/promo ВАШКОД</code>")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "achievements_view":
        from src.achievements import achievement_manager
        text, keyboard = achievement_manager.get_achievements_view(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "vip_program":
        from src.achievements import get_vip_view
        text, keyboard = get_vip_view(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "leaderboard":
        from src.achievements import get_leaderboard
        text, keyboard = get_leaderboard()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "seasonal_promo":
        from src.achievements import get_seasonal_promo_view
        text, keyboard = get_seasonal_promo_view()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "next_story":
        from src.social_features import story_rotator
        text, keyboard = story_rotator.get_story_view(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "share_story":
        from src.social_features import get_share_text
        ref_code = ""
        try:
            from src.referrals import referral_manager
            ref_code = referral_manager.get_referral_code(user_id)
        except Exception:
            pass
        text, keyboard = get_share_text(user_id, ref_code)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "gift_catalog":
        from src.social_features import get_gift_catalog
        text, keyboard = get_gift_catalog(user_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data.startswith("buy_gift_"):
        from src.social_features import buy_gift
        gift_id = data.replace("buy_gift_", "")
        text, keyboard = buy_gift(user_id, gift_id)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "ai_coach_analyze":
        await query.edit_message_text(
            "📊 <b>AI-коуч анализирует ваши диалоги...</b>\n\n"
            "Для полного анализа обратитесь к менеджеру — он подготовит "
            "персональные рекомендации по улучшению конверсии.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💼 Связаться с менеджером", callback_data="request_manager")],
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
            ])
        )

    else:
        logger.warning(f"Unknown callback_data: {data} from user {user_id}")


async def _handle_smart_button(query, context, data: str, user_id: int) -> None:
    import os

    async def _safe_reply(text, parse_mode=None, reply_markup=None):
        try:
            await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text, reply_markup=reply_markup)

    if data == "smart_prices":
        from src.pricing import get_price_main_text, get_price_main_keyboard
        await _safe_reply(get_price_main_text(), parse_mode="Markdown", reply_markup=get_price_main_keyboard())

    elif data == "smart_portfolio":
        await _safe_reply(PORTFOLIO_MESSAGE, parse_mode="Markdown", reply_markup=get_portfolio_keyboard())

    elif data == "smart_faq":
        await query.message.reply_text("❓ Выберите вопрос:", reply_markup=get_faq_keyboard())

    elif data == "smart_calc":
        await query.message.reply_text("🧮 Выберите функции для расчёта:", reply_markup=get_calculator_keyboard())

    elif data == "smart_compare":
        from src.pricing import get_price_main_text, get_price_main_keyboard
        await _safe_reply(get_price_main_text(), parse_mode="Markdown", reply_markup=get_price_main_keyboard())

    elif data == "smart_roi":
        await query.message.reply_text(
            "Давайте прикинем, как быстро окупится ваш проект. "
            "Расскажите — какая у вас сфера, примерный средний чек и сколько клиентов в месяц? "
            "Я посчитаю всё конкретно под вас."
        )

    elif data == "smart_discount":
        from src.tasks_tracker import tasks_tracker as tt_smart
        progress = tt_smart.get_user_progress(user_id)
        discount = progress.get_discount_percent()
        coins = progress.total_coins
        if discount > 0:
            text = (
                f"У вас уже есть скидка {discount}% и {coins} монет на счету. "
                f"Можно ещё увеличить — до 25%. Попробуйте /bonus, там несложные задания."
            )
        else:
            text = (
                "Сейчас у вас скидок пока нет, но это легко исправить. "
                "Напишите /bonus — там задания, за которые начисляются монеты. "
                "Скидка растёт до 25%."
            )
        await query.message.reply_text(text)

    elif data == "smart_consult":
        await query.message.reply_text(
            "📞 Отлично! Напишите удобное время для созвона — "
            "менеджер свяжется с вами. Или просто расскажите о проекте здесь, "
            "и я помогу подготовить всю информацию."
        )
        lead_manager.create_lead(user_id=user_id, username=query.from_user.username, first_name=query.from_user.first_name)
        lead_manager.add_tag(user_id, "consult_request")

    elif data == "smart_brief":
        await query.message.reply_text(
            "Отлично, давайте соберём ТЗ. Расскажите своими словами — "
            "что за бизнес, что хотите от приложения, есть ли макеты или референсы? "
            "Я помогу всё структурировать."
        )

    elif data == "smart_lead":
        lead_manager.create_lead(user_id=user_id, username=query.from_user.username, first_name=query.from_user.first_name)
        from src.leads import LeadPriority
        lead_manager.update_lead(user_id, score=40, priority=LeadPriority.HOT)
        await query.message.reply_text(
            "Записал! Менеджер свяжется с вами в ближайшее время. "
            "А пока можем продолжить — расскажите, что хотите реализовать, и я помогу подготовить детали."
        )

    elif data == "smart_payment":
        from src.payments import get_payment_keyboard
        await query.message.reply_text("💳 Выберите способ оплаты:", reply_markup=get_payment_keyboard())

    elif data == "smart_contract":
        await query.message.reply_text(
            "Договор подготовим после того, как согласуем ТЗ и стоимость. "
            "Если ещё не обсудили детали — давайте начнём с описания проекта, а дальше я всё оформлю.",
            reply_markup=get_lead_keyboard()
        )

    elif data == "smart_manager":
        lead_manager.create_lead(user_id=user_id, username=query.from_user.username, first_name=query.from_user.first_name)
        lead_manager.add_tag(user_id, "manager_request")
        await query.message.reply_text("📞 Запрос передан менеджеру. Он свяжется с вами в ближайшее время!")
        manager_id = os.environ.get("MANAGER_CHAT_ID")
        if manager_id:
            try:
                await context.bot.send_message(
                    int(manager_id),
                    f"🔔 Запрос от клиента\n"
                    f"👤 {query.from_user.first_name} (@{query.from_user.username or 'нет'})\n"
                    f"🆔 {user_id}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    else:
        logger.warning(f"Unknown smart button: {data}")
