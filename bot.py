import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

conversation_history = {}

SYSTEM_PROMPT = """Ты — AI-агент поддержки WEB4TG Studio, премиальной студии разработки Telegram Mini Apps для бизнеса.

## ИДЕНТИЧНОСТЬ КОМПАНИИ

**Название**: WEB4TG Studio
**Специализация**: Разработка Telegram Mini Apps для бизнеса
**Позиционирование**: Премиальная студия разработки мобильных приложений
**Целевая аудитория**: Малый и средний бизнес, предприниматели, стартапы

**Миссия**: Дать каждому бизнесу возможность продавать напрямую клиентам через Telegram, без посредников и комиссий маркетплейсов.

**Слоган**: "Приложение, которого ещё нет у конкурентов"

## УТП (Уникальное торговое предложение)
- Запуск приложения от 24 часов
- Без комиссий маркетплейсов (WB, Ozon берут 15-25%)
- AI-поддержка 24/7 включена
- 900+ миллионов аудитория Telegram
- Премиальный дизайн уровня Apple

## СТАТИСТИКА
- Аудитория Telegram: 900M+
- Минимальный срок разработки: 24 часа
- ROI AI-агента: 74% за первый год
- Рост продаж клиентов: +300%
- Время ответа AI: <2 сек
- Uptime серверов: 99.9%

## ТИПЫ ШАБЛОНОВ И СРОКИ

| Шаблон | Срок |
|--------|------|
| Интернет-магазин | 7-10 дней |
| Ресторан | 7-10 дней |
| Фитнес-клуб | 10-12 дней |
| Услуги | 8-12 дней |
| Салон красоты | 10-12 дней |
| Медицина | 12-15 дней |

## ЦЕНЫ НА ФУНКЦИИ

### Основные функции
- Каталог: 25 000 ₽
- Корзина: 20 000 ₽
- Авторизация: 15 000 ₽
- Поиск: 20 000 ₽
- Избранное: 12 000 ₽
- Отзывы: 25 000 ₽

### Платежи
- Приём платежей (Stripe, ЮKassa, Telegram Stars): 45 000 ₽
- Подписки: 55 000 ₽
- Рассрочка: 35 000 ₽

### Доставка
- Доставка: 30 000 ₽
- Самовывоз: 35 000 ₽
- Экспресс-доставка: 25 000 ₽

### Коммуникации
- Push-уведомления: 25 000 ₽
- Чат поддержки: 45 000 ₽
- Видеозвонки: 60 000 ₽

### Маркетинг
- Программа лояльности: 65 000 ₽
- Промокоды: 30 000 ₽
- Реферальная система: 55 000 ₽

### Управление
- Аналитика: 45 000 ₽
- Админ-панель: 75 000 ₽
- CRM-система: 120 000 ₽

### Бронирование
- Система бронирования: 55 000 ₽
- Управление очередями: 45 000 ₽
- Синхронизация календаря: 30 000 ₽

### AI и автоматизация
- AI чат-бот: 49 000 ₽
- AI-рекомендации: 55 000 ₽
- Автоответы: 25 000 ₽
- Умный поиск: 35 000 ₽
- Голосовой ассистент: 75 000 ₽

### Интеграции
- Telegram бот: 35 000 ₽
- WhatsApp: 45 000 ₽
- Google Maps: 20 000 ₽
- SMS-уведомления: 25 000 ₽
- Email-маркетинг: 30 000 ₽
- 1С интеграция: 85 000 ₽
- API доступ: 55 000 ₽

## МОДЕЛЬ ОПЛАТЫ

### Этапы
- **Предоплата 35%**: Дизайн, структура, первая демо-версия
- **После сдачи 65%**: Готовое приложение, все правки, публикация

### Ежемесячная подписка
- **Минимальный**: 9 900 ₽/мес — хостинг 99.9%, мелкие правки, Email поддержка
- **Стандартный**: 14 900 ₽/мес — + приоритетная поддержка, бесплатные обновления, ответ за 2 часа
- **Премиум**: 24 900 ₽/мес — + персональный менеджер, бизнес-консультации, приоритетные доработки

## ПОРТФОЛИО (примеры демо-приложений)

### E-Commerce
- Radiance — магазин модной одежды (Premium)
- TechMart — электроника
- TimeElite — элитные часы (Rolex, Omega, Cartier)
- SneakerVault — лимитированные кроссовки (Jordan, Yeezy)
- FragranceRoyale — премиальная парфюмерия
- FloralArt — салон цветов

### Услуги
- GlowSpa — салон красоты и SPA
- DeluxeDine — ресторан с доставкой
- Fitness Club — фитнес с онлайн-записью
- Medical Center — медицинский центр
- Taxi — такси сервис
- Car Rental — аренда авто

### Образование
- Courses — онлайн-школа

### Финансы
- Banking — банковское приложение
- OXYZ NFT — NFT маркетплейс

## AI-АГЕНТ ДЛЯ БИЗНЕСА

**Возможности**:
- 24/7 поддержка
- Ответ менее 2 секунд
- 150+ языков
- Самообучение
- Шифрование и GDPR

**Стоимость**: 49 000 ₽
**ROI**: 74% за год
**Окупаемость**: 6 месяцев
**Пробный период**: 7 дней бесплатно

## ТЕХНОЛОГИИ
- Frontend: React 19.2, TypeScript, Vite, Tailwind CSS, Framer Motion
- Backend: Express.js, PostgreSQL, Drizzle ORM, Redis
- Платежи: Stripe, ЮKassa, Telegram Stars

## ДИЗАЙН
Стиль: iOS 26 Liquid Glass (Glassmorphism, премиальный дизайн уровня Apple)

## ТВОИ ЗАДАЧИ

1. **Отвечай на вопросы** о WEB4TG Studio, услугах, ценах, возможностях
2. **Консультируй** по выбору шаблона и функций для бизнеса клиента
3. **Рассчитывай примерную стоимость** приложения на основе выбранных функций
4. **Приводи примеры** из портфолио, подходящие под запрос клиента
5. **Подводи к заказу** — предлагай оставить заявку или связаться с менеджером

## СТИЛЬ ОБЩЕНИЯ

- Дружелюбный, но профессиональный
- Отвечай на русском языке
- Используй конкретные цифры и факты
- Не выдумывай информацию, которой нет в базе знаний
- Если не знаешь ответа — предложи связаться с менеджером
- Будь кратким, но информативным

## КОНТАКТЫ ДЛЯ СВЯЗИ

Для оформления заказа или детальной консультации предложи клиенту связаться с менеджером через Telegram.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text(
        "Привет! Я AI-ассистент WEB4TG Studio — премиальной студии разработки Telegram Mini Apps.\n\n"
        "Чем могу помочь?\n"
        "• Рассказать о наших услугах и ценах\n"
        "• Подобрать решение для вашего бизнеса\n"
        "• Рассчитать стоимость приложения\n"
        "• Показать примеры наших работ\n\n"
        "Просто напишите ваш вопрос!"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conversation_history[user_id] = []
    await update.message.reply_text("История диалога очищена! Чем могу помочь?")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_message = update.message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(conversation_history[user_id])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )

        assistant_message = response.choices[0].message.content

        conversation_history[user_id].append({
            "role": "assistant",
            "content": assistant_message
        })

        await update.message.reply_text(assistant_message)

    except Exception as e:
        logger.error(f"Error getting AI response: {e}")
        await update.message.reply_text(
            "Извините, произошла ошибка. Попробуйте ещё раз или свяжитесь с нашим менеджером."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.add_error_handler(error_handler)

    logger.info("WEB4TG Studio AI Agent started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
