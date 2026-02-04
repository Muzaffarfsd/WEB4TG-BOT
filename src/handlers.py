import asyncio
import logging
import os
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.ai_client import ai_client
from src.config import config
from src.keyboards import (
    get_main_menu_keyboard, get_services_keyboard, 
    get_portfolio_keyboard, get_calculator_keyboard,
    get_lead_keyboard, get_back_keyboard, get_subscription_keyboard,
    get_quick_reply_keyboard
)
from src.calculator import calculator_manager, FEATURES
from src.leads import lead_manager
from src.knowledge_base import (
    WELCOME_MESSAGE, HELP_MESSAGE, PRICE_MESSAGE,
    PORTFOLIO_MESSAGE, CONTACT_MESSAGE, CLEAR_MESSAGE, ERROR_MESSAGE
)
from src.tasks_tracker import tasks_tracker, TASKS_CONFIG
from src.referrals import referral_manager, REFERRER_REWARD, REFERRED_REWARD
from src.payments import handle_payment_callback

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.environ.get("MANAGER_CHAT_ID")
if MANAGER_CHAT_ID:
    lead_manager.set_manager_chat_id(int(MANAGER_CHAT_ID))


async def send_typing_action(update: Update, duration: float = 4.0):
    try:
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(4.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.debug(f"Typing action error: {e}")


WELCOME_MESSAGES = {
    "ru": """Привет{name}! Меня зовут Алекс, работаю консультантом в WEB4TG Studio.

Мы делаем Telegram Mini Apps для бизнеса — интернет-магазины, рестораны, салоны красоты и многое другое.

Кстати, можем общаться как удобно — текстом или голосовыми, мне без разницы)

Расскажите, чем занимаетесь? Посмотрим, чем можем быть полезны.""",
    "en": """Hey{name}! I'm Alex, consultant at WEB4TG Studio.

We build Telegram Mini Apps for businesses — online stores, restaurants, beauty salons and more.

By the way, feel free to text or send voice messages — whatever works for you)

So what's your business about? Let's see how we can help.""",
    "uk": """Привіт{name}! Мене звати Алекс, працюю консультантом у WEB4TG Studio.

Ми робимо Telegram Mini Apps для бізнесу — інтернет-магазини, ресторани, салони краси та багато іншого.

До речі, можемо спілкуватися як зручно — текстом або голосовими, мені без різниці)

Розкажіть, чим займаєтесь? Подивимось, чим можемо бути корисні.""",
}


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    session = session_manager.get_session(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    session.clear_history()
    
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
    
    name = user.first_name or ""
    name_part = f", {name}" if name else ""
    
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
    await update.message.reply_text(
        "Вот что могу показать:",
        reply_markup=get_main_menu_keyboard()
    )


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        PRICE_MESSAGE, 
        parse_mode="Markdown",
        reply_markup=get_subscription_keyboard()
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
    calc = calculator_manager.get_calculation(user_id)
    
    await update.message.reply_text(
        f"**Калькулятор стоимости**\n\n{calc.get_summary()}",
        parse_mode="Markdown",
        reply_markup=get_calculator_keyboard()
    )


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
        [InlineKeyboardButton("📋 Скопировать код", callback_data="ref_copy_code")],
        [InlineKeyboardButton("📤 Поделиться ссылкой", callback_data="ref_share")],
        [InlineKeyboardButton("👥 Мои рефералы", callback_data="ref_list")],
        [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


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
    
    elif data in ("payment", "pay_card", "pay_bank", "copy_card", "copy_bank", "pay_confirm", "pay_contract"):
        await handle_payment_callback(update, context, data)
    
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
        
        elif data == "ref_share":
            ref_link = referral_manager.get_bot_referral_link(stats.referral_code)
            share_text = f"Присоединяйся к WEB4TG Studio! Получи 50 монет по моей ссылке: {ref_link}"
            await query.answer()
            await query.message.reply_text(
                f"📤 **Поделитесь этой ссылкой:**\n\n{ref_link}\n\n"
                f"Или отправьте друзьям это сообщение:\n\n_{share_text}_",
                parse_mode="Markdown"
            )
        
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
                [InlineKeyboardButton("📋 Скопировать код", callback_data="ref_copy_code")],
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
        
        elif data == "tasks_back":
            progress = tasks_tracker.get_user_progress(user_id)
            tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
            current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
            
            text = f"""🎁 **Получи скидку до 25%!**

{current_emoji} **Уровень:** {progress.get_tier_name()}
💰 **Монеты:** {progress.total_coins}
💵 **Скидка:** {progress.get_discount_percent()}%

Выбери задание:"""
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Telegram", callback_data="tasks_telegram")],
                [InlineKeyboardButton("📺 YouTube", callback_data="tasks_youtube")],
                [InlineKeyboardButton("📸 Instagram", callback_data="tasks_instagram")],
                [InlineKeyboardButton("🎵 TikTok", callback_data="tasks_tiktok")],
                [InlineKeyboardButton("📊 Мой прогресс", callback_data="tasks_progress")],
                [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
            ])
            
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        
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
                task_name = task["id"].replace(f"{platform}_", "").replace("_", " ").title()
                text += f"{status_icon} {task_name} — {task['coins']} монет\n"
                
                if task["status"] != "completed":
                    buttons.append([InlineKeyboardButton(
                        f"▶️ {task_name} (+{task['coins']})",
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
        
        if platform == "telegram" and task_config.get("type") == "subscribe":
            is_subscribed = await tasks_tracker.check_telegram_subscription(user_id, task_config.get("channel", "web4_tg"))
            
            if not is_subscribed:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Подписаться на канал", url=task_config.get("url", "https://t.me/web4_tg"))],
                    [InlineKeyboardButton("✅ Я подписался", callback_data=f"verify_task_{task_id}")],
                    [InlineKeyboardButton("◀️ Назад", callback_data=f"tasks_{platform}")]
                ])
                
                await query.edit_message_text(
                    "📱 **Подписка на Telegram канал**\n\nПодпишись на канал @web4_tg, затем нажми «Я подписался» для получения монет.",
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
            task_name = task["id"].replace(f"{platform}_", "").replace("_", " ").title()
            text += f"{status_icon} {task_name} — {task['coins']} монет\n"
            
            if task["status"] != "completed":
                buttons.append([InlineKeyboardButton(f"▶️ {task_name} (+{task['coins']})", callback_data=f"do_task_{task['id']}")])
        
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
                task_name = task["id"].replace(f"{platform}_", "").replace("_", " ").title()
                text += f"{status_icon} {task_name} — {task['coins']} монет\n"
                
                if task["status"] != "completed":
                    buttons.append([InlineKeyboardButton(f"▶️ {task_name} (+{task['coins']})", callback_data=f"do_task_{task['id']}")])
            
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="tasks_back")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.answer(result["message"], show_alert=True)
    
    elif data.startswith("portfolio_"):
        portfolio_info = {
            "portfolio_ecommerce": """E-Commerce проекты:

Radiance — премиум магазин одежды, стильный чёрный дизайн
TimeElite — элитные часы (Rolex, Omega, Cartier)
SneakerVault — лимитированные кроссовки (Jordan, Yeezy)
FragranceRoyale — парфюмерия
FloralArt — салон цветов

Что ближе к вашей тематике?""",
            "portfolio_services": """Проекты в сфере услуг:

GlowSpa — салон красоты, очень нежный дизайн
DeluxeDine — ресторан с доставкой
Также есть фитнес-клуб с расписанием, медцентр с записью.

Хотите посмотреть что-то конкретное?""",
            "portfolio_fintech": """Финтех проекты:

Banking — банковское приложение (счета, переводы, история операций)
OXYZ NFT — NFT маркетплейс

Вам для чего-то финансового нужно?""",
            "portfolio_education": """Образовательные проекты:

Courses — онлайн-школа с каталогом курсов, трекингом прогресса, сертификатами.

Планируете обучающий проект?"""
        }
        
        text = portfolio_info.get(data, "Информация не найдена")
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_lead_keyboard()
        )


STRESS_DICTIONARY = {
    "разработка": "разрабо́тка",
    "приложение": "приложе́ние",
    "приложения": "приложе́ния",
    "стоимость": "сто́имость",
    "договор": "догово́р",
    "звонит": "звони́т",
    "каталог": "катало́г",
    "маркетинг": "ма́ркетинг",
    "обеспечение": "обеспе́чение",
    "средства": "сре́дства",
    "процент": "проце́нт",
    "квартал": "кварта́л",
    "эксперт": "экспе́рт",
    "оптовый": "опто́вый",
    "украинский": "украи́нский",
    "красивее": "краси́вее",
    "мастерски": "мастерски́",
    "включит": "включи́т",
    "облегчить": "облегчи́ть",
    "углубить": "углуби́ть",
    "баловать": "балова́ть",
    "досуг": "досу́г",
    "жалюзи": "жалюзи́",
    "торты": "то́рты",
    "банты": "ба́нты",
    "шарфы": "ша́рфы",
    "порты": "по́рты",
    "склады": "скла́ды",
    "telegram": "телегра́м",
    "функционал": "функциона́л",
    "интерфейс": "интерфе́йс",
    "дизайн": "диза́йн",
    "контент": "конте́нт",
    "проект": "прое́кт",
    "клиент": "клие́нт",
    "сервис": "се́рвис",
    "бизнес": "би́знес",
    "менеджер": "ме́неджер",
    "маркетплейс": "маркетпле́йс",
}


async def analyze_emotions_and_prepare_text(text: str) -> str:
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=config.gemini_api_key)
    
    prompt = """Ты эксперт по подготовке текста для естественного озвучивания.

Твоя задача: добавить эмоциональные теги ElevenLabs v3 в текст для естественного звучания.

Доступные теги (вставляй в квадратных скобках перед фразой):
- [friendly] - дружелюбно
- [excited] - с энтузиазмом  
- [calm] - спокойно
- [professional] - деловой тон
- [warm] - тепло
- [curious] - с интересом
- [confident] - уверенно
- [helpful] - услужливо

Правила:
1. Добавляй теги перед предложениями/фразами где меняется эмоция
2. Не переусердствуй - 2-4 тега на абзац максимум
3. Приветствия: [friendly, warm]
4. Цены/факты: [confident, professional]  
5. Предложения помощи: [helpful, warm]
6. Интересные факты: [excited]
7. Вопросы: [curious]
8. Убери markdown разметку (**, *, #, •)
9. Замени переносы строк на точки или запятые для пауз
10. НЕ меняй смысл текста, только добавь теги

Верни ТОЛЬКО обработанный текст, без объяснений.

Текст для обработки:
"""
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[prompt + text],
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3
            )
        )
        
        if response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Emotion analysis error: {e}")
    
    return text


def apply_stress_marks(text: str) -> str:
    result = text
    for word, stressed in STRESS_DICTIONARY.items():
        import re
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub(stressed, result)
    return result


async def generate_voice_response(text: str) -> bytes:
    from elevenlabs import ElevenLabs
    
    client = ElevenLabs(api_key=config.elevenlabs_api_key)
    
    clean_text = text.replace("**", "").replace("*", "").replace("#", "").replace("•", ",")
    clean_text = clean_text.replace("\n\n", ". ").replace("\n", ", ")
    
    voice_text = await analyze_emotions_and_prepare_text(clean_text)
    
    voice_text = apply_stress_marks(voice_text)
    
    audio_generator = await asyncio.to_thread(
        client.text_to_speech.convert,
        voice_id=config.elevenlabs_voice_id,
        text=voice_text,
        model_id="eleven_v3",
        output_format="mp3_44100_192"
    )
    
    audio_bytes = b"".join(audio_generator)
    return audio_bytes


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=30.0)
    )
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        voice_bytes = await file.download_as_bytearray()
        
        session = session_manager.get_session(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        from google import genai
        from google.genai import types
        from src.knowledge_base import SYSTEM_PROMPT
        
        client = genai.Client(api_key=config.gemini_api_key)
        
        audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
        text_part = types.Part(text="Это голосовое сообщение от клиента. Пойми что он сказал и сразу ответь на его вопрос как консультант Алекс из WEB4TG Studio. НЕ пиши расшифровку, НЕ пиши 'вы сказали', просто отвечай на вопрос.")
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.model_name,
            contents=[audio_part, text_part],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        
        typing_task.cancel()
        
        if response.text:
            session.add_message("user", "[Голосовое сообщение]", config.max_history_length)
            session.add_message("assistant", response.text, config.max_history_length)
            
            lead_manager.save_message(user.id, "user", "[Голосовое сообщение]")
            lead_manager.save_message(user.id, "assistant", response.text)
            lead_manager.log_event("voice_message", user.id)
            lead_manager.update_activity(user.id)
            
            if config.elevenlabs_api_key:
                try:
                    await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
                    voice_response = await generate_voice_response(response.text)
                    await update.message.reply_voice(voice=voice_response)
                except Exception as e:
                    logger.error(f"ElevenLabs TTS error: {e}")
                    await update.message.reply_text(response.text)
            else:
                await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("Не удалось распознать сообщение. Попробуйте ещё раз или напишите текстом.")
            
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Voice processing error: {e}")
        await update.message.reply_text(
            "Не удалось обработать голосовое сообщение. Напишите текстом, пожалуйста."
        )


async def leads_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    leads = lead_manager.get_all_leads(limit=20)
    
    if not leads:
        await update.message.reply_text("Лидов пока нет.")
        return
    
    text_parts = ["📋 **Последние лиды:**\n"]
    for lead in leads[:10]:
        status_emoji = {"new": "🆕", "contacted": "📞", "qualified": "✅", "converted": "💰"}.get(lead.status.value, "❓")
        name = lead.first_name or "Без имени"
        username = f"@{lead.username}" if lead.username else "—"
        cost = f"{lead.estimated_cost:,}₽".replace(",", " ") if lead.estimated_cost else "—"
        text_parts.append(f"{status_emoji} {name} ({username}) — {cost}")
    
    await update.message.reply_text("\n".join(text_parts), parse_mode="Markdown")


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    stats = lead_manager.get_stats()
    analytics = lead_manager.get_analytics_stats()
    
    text = f"""📊 **Статистика бота**

**Лиды:**
🆕 Новые: {stats.get('new', 0)}
📞 В работе: {stats.get('contacted', 0)}
✅ Квалифицированы: {stats.get('qualified', 0)}
💰 Конвертированы: {stats.get('converted', 0)}
📈 Всего: {stats.get('total', 0)}

**Активность:**
💬 Сообщений: {analytics.get('total_messages', 0)}
🎙 Голосовых: {analytics.get('voice_messages', 0)}
🧮 Калькулятор: {analytics.get('calculator_uses', 0)}
👥 Всего юзеров: {analytics.get('unique_users', 0)}
📅 Сегодня: {analytics.get('today_users', 0)}
📆 За неделю: {analytics.get('week_users', 0)}"""

    await update.message.reply_text(text, parse_mode="Markdown")


async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    csv_data = lead_manager.export_leads_csv()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_data)
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="leads_export.csv",
                caption="📥 Экспорт лидов"
            )
    finally:
        import os
        os.unlink(temp_path)


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /history <user_id>")
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    lead = lead_manager.get_lead(target_user_id)
    if not lead:
        await update.message.reply_text("Лид не найден")
        return
    
    history = lead_manager.get_lead_history(target_user_id, limit=30)
    
    priority_emoji = {"cold": "❄️", "warm": "🌡", "hot": "🔥"}.get(lead.priority.value, "❓")
    
    def escape_md(text: str) -> str:
        for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(char, f'\\{char}')
        return text
    
    name = escape_md(lead.first_name or 'Без имени')
    username = escape_md(lead.username or '—')
    tags_str = escape_md(', '.join(lead.tags)) if lead.tags else '—'
    
    text_parts = [
        f"📋 История лида #{lead.id}\n",
        f"👤 {name} (@{username})",
        f"📊 Скоринг: {lead.score}/100 {priority_emoji}",
        f"🏷 Теги: {tags_str}",
        f"💬 Сообщений: {lead.message_count}",
        "\nПоследние события:\n"
    ]
    
    for item in history[-15:]:
        dt = item['created_at'].strftime("%d.%m %H:%M") if item['created_at'] else ""
        if item['type'] == 'message':
            role_icon = "👤" if item['role'] == 'user' else "🤖"
            content = escape_md(item['content'][:80]) + "..." if len(item['content']) > 80 else escape_md(item['content'])
            text_parts.append(f"{dt} {role_icon} {content}")
        else:
            text_parts.append(f"{dt} 📌 {item['role']}")
    
    await update.message.reply_text("\n".join(text_parts))


async def hot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    from src.leads import LeadPriority
    leads = lead_manager.get_leads_by_priority(LeadPriority.HOT, limit=15)
    
    if not leads:
        await update.message.reply_text("🔥 Горячих лидов пока нет")
        return
    
    text_parts = ["🔥 **Горячие лиды:**\n"]
    for lead in leads:
        name = lead.first_name or "Без имени"
        username = f"@{lead.username}" if lead.username else "—"
        tags = f"[{', '.join(lead.tags)}]" if lead.tags else ""
        text_parts.append(f"• {name} ({username}) — {lead.score}pts {tags}")
    
    await update.message.reply_text("\n".join(text_parts), parse_mode="Markdown")


async def tag_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /tag <user_id> <тег>\nПример: /tag 123456 vip")
        return
    
    try:
        target_user_id = int(args[0])
        tag = args[1].lower()
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    lead = lead_manager.add_tag(target_user_id, tag)
    if lead:
        await update.message.reply_text(f"✅ Тег '{tag}' добавлен\nВсе теги: {', '.join(lead.tags)}")
    else:
        await update.message.reply_text("Лид не найден")


async def priority_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    manager_id = lead_manager.get_manager_chat_id()
    
    if manager_id and user_id != manager_id:
        await update.message.reply_text("Эта команда только для менеджера.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /priority <user_id> <cold|warm|hot>")
        return
    
    try:
        target_user_id = int(args[0])
        priority_str = args[1].lower()
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    from src.leads import LeadPriority
    priority_map = {"cold": LeadPriority.COLD, "warm": LeadPriority.WARM, "hot": LeadPriority.HOT}
    
    if priority_str not in priority_map:
        await update.message.reply_text("Приоритет: cold, warm или hot")
        return
    
    lead = lead_manager.update_lead(target_user_id, priority=priority_map[priority_str])
    if lead:
        emoji = {"cold": "❄️", "warm": "🌡", "hot": "🔥"}[priority_str]
        await update.message.reply_text(f"✅ Приоритет изменён на {emoji} {priority_str}")
    else:
        await update.message.reply_text("Лид не найден")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_message = update.message.text
    
    if not user_message or not user_message.strip():
        return
    
    if user_message == "💰 Цены":
        await update.message.reply_text(
            PRICE_MESSAGE, 
            parse_mode="Markdown",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    if user_message == "🎁 Получить скидку":
        progress = tasks_tracker.get_user_progress(user.id)
        
        tier_emoji = {0: "🔰", 5: "🥉", 10: "🥈", 15: "🥇", 20: "💎", 25: "👑"}
        current_emoji = tier_emoji.get(progress.get_discount_percent(), "🔰")
        
        discount_text = f"""🎁 **Получи скидку до 25% на разработку!**

{current_emoji} **Твой уровень:** {progress.get_tier_name()}
💰 **Монеты:** {progress.total_coins}
🔥 **Стрик:** {progress.current_streak} дней
💵 **Текущая скидка:** {progress.get_discount_percent()}%

**Как это работает:**
1. Подписывайся на наши соцсети
2. Лайкай, комментируй, делись постами
3. За каждое действие получаешь монеты
4. Монеты = скидка на разработку

**Уровни скидок:**
🥉 200+ монет → 5%
🥈 500+ монет → 10%
🥇 800+ монет → 15%
💎 1200+ монет → 20%
👑 1500+ монет → 25%

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
            lead_manager.update_score(user.id, 30)
            lead_manager.set_priority(user.id, "hot")
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
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        thinking_level = "high" if len(user_message) > 200 else "medium"
        
        response = await ai_client.generate_response(
            messages=session.get_history(),
            thinking_level=thinking_level,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay
        )
        
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
        logger.error(f"Error handling message from user {user.id}: {e}")
        await update.message.reply_text(
            ERROR_MESSAGE,
            reply_markup=get_main_menu_keyboard()
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
