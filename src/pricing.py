"""Comprehensive pricing module for WEB4TG Studio."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

TEMPLATES = {
    "ecommerce": {
        "name": "Интернет-магазин",
        "price": 150000,
        "days": "7-10",
        "popular": True,
        "features": ["Каталог товаров", "Корзина", "Авторизация", "Оплата"],
        "desc": "Полноценный магазин с каталогом, корзиной и оплатой"
    },
    "restaurant": {
        "name": "Ресторан / Доставка",
        "price": 180000,
        "days": "10-12",
        "features": ["Меню", "Корзина", "Авторизация", "Бронирование"],
        "desc": "Меню, заказ блюд, бронирование столиков и доставка"
    },
    "fitness": {
        "name": "Фитнес-клуб",
        "price": 200000,
        "days": "12-15",
        "features": ["Бронирование", "Авторизация", "Подписки", "Прогресс"],
        "desc": "Расписание занятий, абонементы, личный кабинет"
    },
    "services": {
        "name": "Услуги / Сервис",
        "price": 170000,
        "days": "8-12",
        "features": ["Каталог услуг", "Бронирование", "Авторизация", "Оплата"],
        "desc": "Запись на услуги, онлайн-оплата, управление записями"
    }
}

FEATURES = {
    "basic": {
        "name": "Базовые функции",
        "items": {
            "catalog": ("Каталог товаров", 25000, "Витрина с категориями и фильтрами"),
            "cart": ("Корзина покупок", 20000, "Добавление, удаление, изменение"),
            "auth": ("Авторизация", 15000, "Вход через Telegram"),
            "search": ("Поиск", 20000, "Поиск с автодополнением"),
            "favorites": ("Избранное", 12000, "Сохранение понравившихся"),
            "reviews": ("Отзывы", 25000, "Рейтинги и комментарии"),
        }
    },
    "payments": {
        "name": "Платежи",
        "items": {
            "online_payment": ("Онлайн-оплата", 45000, "Карты, СБП, Telegram Stars"),
            "subscriptions": ("Подписки", 55000, "Рекуррентные платежи"),
            "installments": ("Рассрочка", 35000, "Оплата частями"),
        }
    },
    "delivery": {
        "name": "Доставка",
        "items": {
            "delivery": ("Доставка", 30000, "Адресная доставка"),
            "pickup": ("Пункты выдачи", 35000, "СДЭК, Boxberry, ПВЗ"),
            "express": ("Экспресс-доставка", 25000, "Срочная доставка"),
        }
    },
    "communications": {
        "name": "Коммуникации",
        "items": {
            "push": ("Push-уведомления", 25000, "Уведомления в Telegram"),
            "chat": ("Чат с поддержкой", 45000, "Онлайн-консультант"),
            "video": ("Видеозвонки", 60000, "Видеоконсультации"),
        }
    },
    "marketing": {
        "name": "Маркетинг",
        "items": {
            "loyalty": ("Программа лояльности", 65000, "Бонусы, кэшбек, уровни"),
            "promo": ("Промокоды", 30000, "Скидочные коды"),
            "referral": ("Реферальная система", 55000, "Приглашай друзей"),
        }
    },
    "management": {
        "name": "Управление",
        "items": {
            "analytics": ("Аналитика", 45000, "Дашборд с метриками"),
            "admin": ("Админ-панель", 75000, "Управление контентом"),
            "crm": ("CRM-система", 120000, "Клиентская база"),
            "progress": ("Трекинг прогресса", 45000, "Отслеживание показателей"),
        }
    },
    "booking": {
        "name": "Бронирование",
        "items": {
            "booking": ("Система бронирования", 55000, "Запись на услуги/занятия"),
            "queue": ("Управление очередью", 45000, "Электронная очередь"),
            "calendar": ("Синхронизация календаря", 30000, "Google/Outlook"),
        }
    },
    "ai": {
        "name": "AI и автоматизация",
        "items": {
            "ai_bot": ("AI чат-бот", 49000, "Умный ассистент"),
            "ai_recs": ("AI рекомендации", 55000, "Персональные подборки"),
            "auto_reply": ("Авто-ответы", 25000, "Автоматические ответы"),
            "smart_search": ("Умный поиск", 35000, "Поиск с пониманием контекста"),
            "voice": ("Голосовой ассистент", 75000, "Голосовые команды"),
        }
    },
    "integrations": {
        "name": "Интеграции",
        "items": {
            "tg_bot": ("Telegram бот", 35000, "Бот для уведомлений"),
            "whatsapp": ("WhatsApp", 45000, "Интеграция с WhatsApp"),
            "maps": ("Google Maps", 20000, "Карты и геолокация"),
            "sms": ("SMS-уведомления", 25000, "SMS рассылка"),
            "email": ("Email-маркетинг", 30000, "Email рассылки"),
            "1c": ("1C интеграция", 85000, "Синхронизация с 1C"),
            "api": ("API доступ", 55000, "REST API для интеграций"),
        }
    }
}

SUBSCRIPTIONS = {
    "min": {
        "name": "Минимальный",
        "price": 9900,
        "features": ["Хостинг (99% uptime)", "Минорные исправления", "Email поддержка", "Ежемесячные бэкапы"]
    },
    "std": {
        "name": "Стандартный",
        "price": 14900,
        "popular": True,
        "features": ["Всё из Минимального", "Приоритетная поддержка", "Бесплатные обновления", "Еженедельные бэкапы", "Ответ за 2 часа"]
    },
    "premium": {
        "name": "Премиум",
        "price": 24900,
        "features": ["Всё из Стандартного", "Персональный менеджер", "Бизнес-консультации", "Ежедневные бэкапы", "Приоритетные доработки", "Аналитические отчёты"]
    }
}

def format_price(price: int) -> str:
    """Format price with thousands separator."""
    return f"{price:,}".replace(",", " ") + " ₽"


def get_price_main_keyboard() -> InlineKeyboardMarkup:
    """Main pricing menu keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Шаблоны приложений", callback_data="price_templates")],
        [InlineKeyboardButton("🔧 Дополнительные функции", callback_data="price_features")],
        [InlineKeyboardButton("📅 Подписки на обслуживание", callback_data="price_subs")],
        [InlineKeyboardButton("💰 Система оплаты", callback_data="price_payment")],
        [InlineKeyboardButton("📊 Примеры расчёта", callback_data="price_examples")],
        [InlineKeyboardButton("🎁 Скидки за монеты", callback_data="price_discounts")],
        [InlineKeyboardButton("◀️ Назад в меню", callback_data="menu_back")],
    ])


def get_price_back_keyboard() -> InlineKeyboardMarkup:
    """Back to pricing menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад к ценам", callback_data="price_main")],
    ])


def get_features_categories_keyboard() -> InlineKeyboardMarkup:
    """Features categories keyboard."""
    buttons = []
    for cat_id, cat in FEATURES.items():
        buttons.append([InlineKeyboardButton(cat["name"], callback_data=f"price_cat_{cat_id}")])
    buttons.append([InlineKeyboardButton("◀️ Назад к ценам", callback_data="price_main")])
    return InlineKeyboardMarkup(buttons)


def get_price_main_text() -> str:
    """Main pricing page text."""
    return """💰 **Прайс-лист WEB4TG Studio**

Выберите раздел:

📦 **Шаблоны** — готовые решения для бизнеса
🔧 **Функции** — дополнительные модули
📅 **Подписки** — ежемесячное обслуживание
💰 **Оплата** — этапы и условия
📊 **Примеры** — расчёт стоимости
🎁 **Скидки** — за заработанные монеты"""


def get_templates_text() -> str:
    """Templates pricing text."""
    text = "📦 **Шаблоны приложений**\n\n"
    for tid, t in TEMPLATES.items():
        popular = " ⭐ Популярный" if t.get("popular") else ""
        text += f"**{t['name']}**{popular}\n"
        text += f"💵 {format_price(t['price'])} • ⏱ {t['days']} дней\n"
        text += f"_{t['desc']}_\n\n"
    return text


def get_subscriptions_text() -> str:
    """Subscriptions pricing text."""
    text = "📅 **Подписки на обслуживание**\n\n"
    text += "_После запуска приложения:_\n\n"
    for sid, s in SUBSCRIPTIONS.items():
        popular = " ⭐" if s.get("popular") else ""
        text += f"**{s['name']}** — {format_price(s['price'])}/мес{popular}\n"
        for f in s["features"][:3]:
            text += f"• {f}\n"
        if len(s["features"]) > 3:
            text += f"• _...и ещё {len(s['features'])-3} пункта_\n"
        text += "\n"
    return text


def get_payment_system_text() -> str:
    """Payment system text."""
    return """💰 **Система оплаты**

**Этап 1: Предоплата — 35%**
✓ Дизайн интерфейса
✓ Структура приложения
✓ Первая демо-версия
_Когда: до начала работ_

**Этап 2: После сдачи — 65%**
✓ Готовое приложение
✓ Правки включены
✓ Публикация в Telegram
_Когда: после приёмки работы_"""


def get_examples_text() -> str:
    """Pricing examples text."""
    return """📊 **Примеры расчёта**

**Простой магазин:**
Шаблон: 150 000 ₽
+ Поиск: 20 000 ₽
+ Промокоды: 30 000 ₽
─────────────
**Итого: 200 000 ₽**
Предоплата: 70 000 ₽

**Ресторан с AI:**
Шаблон: 180 000 ₽
+ Оплата: 45 000 ₽
+ Доставка: 30 000 ₽
+ AI бот: 49 000 ₽
+ Лояльность: 65 000 ₽
─────────────
**Итого: 369 000 ₽**
Предоплата: 129 150 ₽"""


def get_discounts_text() -> str:
    """Discounts for coins text."""
    return """🎁 **Скидки за монеты**

Конвертируйте заработанные монеты в скидку:

| Монеты | Скидка |
|--------|--------|
| 0-499 | 0% |
| 500-999 | 5% |
| 1000-1499 | 10% |
| 1500-1999 | 15% |
| 2000-2499 | 20% |
| 2500+ | 25% |

**Пример:**
Заказ: 200 000 ₽
Монеты: 1500 → Скидка: 15%
─────────────
**Итого: 170 000 ₽**
Экономия: 30 000 ₽

Зарабатывайте монеты через /referral и задания!"""


def get_category_text(cat_id: str) -> str:
    """Get features for specific category."""
    if cat_id not in FEATURES:
        return "Категория не найдена"
    
    cat = FEATURES[cat_id]
    text = f"🔧 **{cat['name']}**\n\n"
    for fid, (name, price, desc) in cat["items"].items():
        text += f"**{name}** — {format_price(price)}\n"
        text += f"_{desc}_\n\n"
    return text


async def handle_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle pricing callbacks."""
    query = update.callback_query
    await query.answer()
    
    if action == "price_main":
        await query.edit_message_text(
            get_price_main_text(),
            parse_mode="Markdown",
            reply_markup=get_price_main_keyboard()
        )
    elif action == "price_templates":
        await query.edit_message_text(
            get_templates_text(),
            parse_mode="Markdown",
            reply_markup=get_price_back_keyboard()
        )
    elif action == "price_features":
        await query.edit_message_text(
            "🔧 **Дополнительные функции**\n\nВыберите категорию:",
            parse_mode="Markdown",
            reply_markup=get_features_categories_keyboard()
        )
    elif action == "price_subs":
        subs_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Минимальный 9 900₽/мес", callback_data="sub_min")],
            [InlineKeyboardButton("⭐ Стандартный 14 900₽/мес", callback_data="sub_std")],
            [InlineKeyboardButton("👑 Премиум 24 900₽/мес", callback_data="sub_premium")],
            [InlineKeyboardButton("◀️ Назад к ценам", callback_data="price_main")]
        ])
        await query.edit_message_text(
            get_subscriptions_text(),
            parse_mode="Markdown",
            reply_markup=subs_keyboard
        )
    elif action == "price_payment":
        await query.edit_message_text(
            get_payment_system_text(),
            parse_mode="Markdown",
            reply_markup=get_price_back_keyboard()
        )
    elif action == "price_examples":
        await query.edit_message_text(
            get_examples_text(),
            parse_mode="Markdown",
            reply_markup=get_price_back_keyboard()
        )
    elif action == "price_discounts":
        await query.edit_message_text(
            get_discounts_text(),
            parse_mode="Markdown",
            reply_markup=get_price_back_keyboard()
        )
    elif action.startswith("price_cat_"):
        cat_id = action[10:]
        await query.edit_message_text(
            get_category_text(cat_id),
            parse_mode="Markdown",
            reply_markup=get_features_categories_keyboard()
        )
