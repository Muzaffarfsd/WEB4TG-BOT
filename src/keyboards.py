import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from src.bot_api import styled_button_api_kwargs, copy_text_button

BUTTON_EMOJI_IDS = {
    "lead": os.environ.get("EMOJI_LEAD"),
    "payment": os.environ.get("EMOJI_PAYMENT"),
    "calculator": os.environ.get("EMOJI_CALCULATOR"),
    "portfolio": os.environ.get("EMOJI_PORTFOLIO"),
    "services": os.environ.get("EMOJI_SERVICES"),
    "manager": os.environ.get("EMOJI_MANAGER"),
    "faq": os.environ.get("EMOJI_FAQ"),
    "bonus": os.environ.get("EMOJI_BONUS"),
    "stars": os.environ.get("EMOJI_STARS"),
}


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "💡 Что мы делаем", callback_data="menu_services",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("services"))
            ),
            InlineKeyboardButton(
                "📊 Кейсы с результатами", callback_data="menu_portfolio",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("portfolio"))
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Рассчитать стоимость", callback_data="menu_calculator",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("calculator"))
            ),
            InlineKeyboardButton("🤖 Спросить AI", callback_data="menu_ai_agent")
        ],
        [
            InlineKeyboardButton(
                "💳 Оплата", callback_data="payment",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("payment"))
            ),
            InlineKeyboardButton(
                "🎁 Мои привилегии", callback_data="loyalty_menu",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("bonus"))
            )
        ],
        [
            InlineKeyboardButton(
                "🏆 Что говорят клиенты", callback_data="menu_testimonials",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("stars"))
            ),
        ],
        [
            InlineKeyboardButton(
                "💬 Написать менеджеру", callback_data="request_manager",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("manager"))
            ),
        ],
        [
            InlineKeyboardButton(
                "📖 Частые вопросы", callback_data="menu_faq",
                **styled_button_api_kwargs(icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("faq"))
            ),
            InlineKeyboardButton(
                "🚀 Начать проект", callback_data="menu_lead",
                **styled_button_api_kwargs(
                    style="constructive",
                    icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("lead")
                )
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_services_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🛒 Магазин в Telegram", callback_data="service_shop"),
            InlineKeyboardButton("🍽 Ресторан и доставка", callback_data="service_restaurant")
        ],
        [
            InlineKeyboardButton("💇‍♀️ Бьюти и запись", callback_data="service_beauty"),
            InlineKeyboardButton("🏋️ Фитнес и абонементы", callback_data="service_fitness")
        ],
        [
            InlineKeyboardButton("🏥 Медицина и клиники", callback_data="service_medical"),
            InlineKeyboardButton("🔧 Сфера услуг", callback_data="service_services")
        ],
        [
            InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_portfolio_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🛍 E-Commerce кейсы", callback_data="portfolio_ecommerce"),
            InlineKeyboardButton("🔧 Кейсы в услугах", callback_data="portfolio_services")
        ],
        [
            InlineKeyboardButton("💰 Финтех-проекты", callback_data="portfolio_fintech"),
            InlineKeyboardButton("📚 EdTech-решения", callback_data="portfolio_education")
        ],
        [
            InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_calculator_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📋 Каталог товаров +25к", callback_data="calc_catalog"),
            InlineKeyboardButton("🛒 Корзина и заказы +20к", callback_data="calc_cart")
        ],
        [
            InlineKeyboardButton("💳 Приём оплаты +45к", callback_data="calc_payments"),
            InlineKeyboardButton("🤖 AI-ассистент +49к", callback_data="calc_ai")
        ],
        [
            InlineKeyboardButton("🚚 Логистика +30к", callback_data="calc_delivery"),
            InlineKeyboardButton("📊 Дашборд и метрики +45к", callback_data="calc_analytics")
        ],
        [
            InlineKeyboardButton(
                "✅ Узнать итоговую цену", callback_data="calc_total",
                **styled_button_api_kwargs(style="constructive")
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 Сбросить", callback_data="calc_reset",
                **styled_button_api_kwargs(style="destructive")
            ),
            InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_lead_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Запустить проект", callback_data="lead_submit",
                **styled_button_api_kwargs(style="constructive")
            )
        ],
        [
            InlineKeyboardButton("💬 Уточнить детали", callback_data="lead_question"),
            InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📦 Минимальный 9 900₽", callback_data="sub_min"),
        ],
        [
            InlineKeyboardButton("⭐ Стандартный 14 900₽", callback_data="sub_std"),
        ],
        [
            InlineKeyboardButton("👑 Премиум 24 900₽", callback_data="sub_premium"),
        ],
        [
            InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_quick_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton("⚡ Открыть приложение", web_app=WebAppInfo(url="https://w4tg.up.railway.app/"))
        ],
        [
            KeyboardButton("✦ Сколько стоит?"),
            KeyboardButton("✨ Получить скидку −20%")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True
    )


def get_loyalty_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✍️ Написать отзыв и получить бонус", callback_data="loyalty_review"),
        ],
        [
            InlineKeyboardButton("📦 Выгодные пакеты", callback_data="loyalty_packages"),
        ],
        [
            InlineKeyboardButton("🔄 Бонус за лояльность", callback_data="loyalty_returning"),
        ],
        [
            InlineKeyboardButton("📊 Мои скидки и баланс", callback_data="loyalty_my_discounts"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="menu_back"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_review_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎬 Видео-отзыв → +500 монет", callback_data="review_video"),
        ],
        [
            InlineKeyboardButton("📝 Текст + фото → +200 монет", callback_data="review_text"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="loyalty_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_package_deals_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📱 + 3 мес подписки (−5%)", callback_data="package_app_subscription_3"),
        ],
        [
            InlineKeyboardButton("📱 + 6 мес подписки (−10%)", callback_data="package_app_subscription_6"),
        ],
        [
            InlineKeyboardButton("📱 + 12 мес подписки (−15%)", callback_data="package_app_subscription_12"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="loyalty_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_faq_keyboard() -> InlineKeyboardMarkup:
    from src.knowledge_base import FAQ_DATA
    keyboard = []
    for key, faq in FAQ_DATA.items():
        keyboard.append([InlineKeyboardButton(f"❔ {faq['question']}", callback_data=key)])
    keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)


def get_stars_payment_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(
            "💬 Личная консультация — 500 ⭐", callback_data="stars_consultation",
            **styled_button_api_kwargs(style="constructive", icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("stars"))
        )],
        [InlineKeyboardButton(
            "🎨 Дизайн за 24 часа — 2000 ⭐", callback_data="stars_express_design",
            **styled_button_api_kwargs(style="constructive", icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("stars"))
        )],
        [InlineKeyboardButton(
            "🔍 Аудит и рекомендации — 1000 ⭐", callback_data="stars_audit",
            **styled_button_api_kwargs(style="constructive", icon_custom_emoji_id=BUTTON_EMOJI_IDS.get("stars"))
        )],
        [InlineKeyboardButton("◀️ Назад", callback_data="payment")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_review_moderation_keyboard(review_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{review_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{review_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
