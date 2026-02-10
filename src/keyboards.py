from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from src.bot_api import styled_button_api_kwargs, copy_text_button


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Услуги и цены", callback_data="menu_services"),
            InlineKeyboardButton("Портфолио", callback_data="menu_portfolio")
        ],
        [
            InlineKeyboardButton("Калькулятор", callback_data="menu_calculator"),
            InlineKeyboardButton("AI-агент", callback_data="menu_ai_agent")
        ],
        [
            InlineKeyboardButton("💳 Оплата", callback_data="payment"),
            InlineKeyboardButton("🎁 Бонусы", callback_data="loyalty_menu")
        ],
        [
            InlineKeyboardButton("⭐ Отзывы клиентов", callback_data="menu_testimonials"),
        ],
        [
            InlineKeyboardButton("❓ FAQ", callback_data="menu_faq"),
            InlineKeyboardButton(
                "📝 Оставить заявку", callback_data="menu_lead",
                **styled_button_api_kwargs(style="constructive")
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_services_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Интернет-магазин", callback_data="service_shop"),
            InlineKeyboardButton("Ресторан", callback_data="service_restaurant")
        ],
        [
            InlineKeyboardButton("Салон красоты", callback_data="service_beauty"),
            InlineKeyboardButton("Фитнес-клуб", callback_data="service_fitness")
        ],
        [
            InlineKeyboardButton("Медицина", callback_data="service_medical"),
            InlineKeyboardButton("Услуги", callback_data="service_services")
        ],
        [
            InlineKeyboardButton("Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_portfolio_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("E-Commerce", callback_data="portfolio_ecommerce"),
            InlineKeyboardButton("Услуги", callback_data="portfolio_services")
        ],
        [
            InlineKeyboardButton("Финтех", callback_data="portfolio_fintech"),
            InlineKeyboardButton("Образование", callback_data="portfolio_education")
        ],
        [
            InlineKeyboardButton("Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_calculator_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Каталог +25к", callback_data="calc_catalog"),
            InlineKeyboardButton("Корзина +20к", callback_data="calc_cart")
        ],
        [
            InlineKeyboardButton("Платежи +45к", callback_data="calc_payments"),
            InlineKeyboardButton("AI-бот +49к", callback_data="calc_ai")
        ],
        [
            InlineKeyboardButton("Доставка +30к", callback_data="calc_delivery"),
            InlineKeyboardButton("Аналитика +45к", callback_data="calc_analytics")
        ],
        [
            InlineKeyboardButton(
                "Рассчитать стоимость", callback_data="calc_total",
                **styled_button_api_kwargs(style="constructive")
            )
        ],
        [
            InlineKeyboardButton(
                "Сбросить", callback_data="calc_reset",
                **styled_button_api_kwargs(style="destructive")
            ),
            InlineKeyboardButton("Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_lead_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Да, хочу заказать!", callback_data="lead_submit",
                **styled_button_api_kwargs(style="constructive")
            )
        ],
        [
            InlineKeyboardButton("Задать вопрос", callback_data="lead_question"),
            InlineKeyboardButton("Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Назад в меню", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Минимальный 9 900₽", callback_data="sub_min"),
        ],
        [
            InlineKeyboardButton("Стандартный 14 900₽", callback_data="sub_std"),
        ],
        [
            InlineKeyboardButton("Премиум 24 900₽", callback_data="sub_premium"),
        ],
        [
            InlineKeyboardButton("Назад в меню", callback_data="menu_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_quick_reply_keyboard() -> ReplyKeyboardMarkup:
    """Quick action buttons at the bottom of chat."""
    keyboard = [
        [
            KeyboardButton("🚀 Открыть приложение", web_app=WebAppInfo(url="https://w4tg.up.railway.app/"))
        ],
        [
            KeyboardButton("💰 Цены"),
            KeyboardButton("🎁 Получить скидку")
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
            InlineKeyboardButton("⭐ Оставить отзыв", callback_data="loyalty_review"),
        ],
        [
            InlineKeyboardButton("📦 Пакетные предложения", callback_data="loyalty_packages"),
        ],
        [
            InlineKeyboardButton("🔄 Бонус постоянного клиента", callback_data="loyalty_returning"),
        ],
        [
            InlineKeyboardButton("📊 Мои скидки", callback_data="loyalty_my_discounts"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="menu_back"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_review_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎬 Видео-отзыв (+500)", callback_data="review_video"),
        ],
        [
            InlineKeyboardButton("📝 Текст + фото (+200)", callback_data="review_text"),
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="loyalty_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_package_deals_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📱 + 3 мес подписки (-5%)", callback_data="package_app_subscription_3"),
        ],
        [
            InlineKeyboardButton("📱 + 6 мес подписки (-10%)", callback_data="package_app_subscription_6"),
        ],
        [
            InlineKeyboardButton("📱 + 12 мес подписки (-15%)", callback_data="package_app_subscription_12"),
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
        keyboard.append([InlineKeyboardButton(faq["question"], callback_data=key)])
    keyboard.append([InlineKeyboardButton("Назад в меню", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)


def get_review_moderation_keyboard(review_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{review_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{review_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
