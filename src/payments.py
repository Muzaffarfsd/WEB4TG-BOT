"""Payment information module for WEB4TG Studio bot."""

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from src.analytics import analytics, FunnelEvent
from src.bot_api import copy_text_button, styled_button_api_kwargs
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


def _init_payment_requests_table():
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS payment_requests (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        payment_type VARCHAR(20),
                        created_at TIMESTAMP DEFAULT NOW(),
                        reminded BOOLEAN DEFAULT FALSE,
                        confirmed BOOLEAN DEFAULT FALSE
                    )
                """)
        logger.info("payment_requests table initialized")
    except Exception as e:
        logger.error(f"Failed to init payment_requests table: {e}")


_init_payment_requests_table()


def _init_star_payments_table():
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS star_payments (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        payload VARCHAR(200),
                        amount INTEGER NOT NULL,
                        paid_at TIMESTAMP DEFAULT NOW()
                    )
                """)
        logger.info("star_payments table initialized")
    except Exception as e:
        logger.error(f"Failed to init star_payments table: {e}")

_init_star_payments_table()


def record_payment_request(user_id: int, payment_type: str) -> None:
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO payment_requests (user_id, payment_type)
                    VALUES (%s, %s)
                """, (user_id, payment_type))
    except Exception as e:
        logger.error(f"Failed to record payment request: {e}")


def get_pending_payment_reminders(hours: int = 24) -> list:
    if not DATABASE_URL:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT user_id FROM payment_requests
                    WHERE confirmed = FALSE
                      AND reminded = FALSE
                      AND created_at < NOW() - make_interval(hours => %s)
                """, (hours,))
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get pending payment reminders: {e}")
        return []


def mark_payment_reminded(user_id: int) -> None:
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE payment_requests
                    SET reminded = TRUE
                    WHERE user_id = %s AND confirmed = FALSE
                """, (user_id,))
    except Exception as e:
        logger.error(f"Failed to mark payment reminded: {e}")


def confirm_payment(user_id: int) -> None:
    if not DATABASE_URL:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE payment_requests
                    SET confirmed = TRUE
                    WHERE user_id = %s AND confirmed = FALSE
                """, (user_id,))
    except Exception as e:
        logger.error(f"Failed to confirm payment: {e}")

CONTRACT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "contract.pdf")

CARD_NUMBER = os.environ.get("PAYMENT_CARD_NUMBER", "")
CARD_NUMBER_PLAIN = CARD_NUMBER.replace(" ", "")

BANK_DETAILS = {
    "recipient": os.environ.get("PAYMENT_RECIPIENT", ""),
    "inn": os.environ.get("PAYMENT_INN", ""),
    "account": os.environ.get("PAYMENT_ACCOUNT", ""),
    "bank_name": os.environ.get("PAYMENT_BANK_NAME", ""),
    "bank_address": os.environ.get("PAYMENT_BANK_ADDRESS", ""),
    "bik": os.environ.get("PAYMENT_BIK", ""),
    "bank_inn": os.environ.get("PAYMENT_BANK_INN", ""),
}


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Get payment options keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Оплата через Stars", callback_data="payment_stars")],
        [InlineKeyboardButton("💳 Оплата картой Visa", callback_data="pay_card")],
        [InlineKeyboardButton("🏦 Банковский перевод", callback_data="pay_bank")],
        [InlineKeyboardButton("📄 Скачать договор", callback_data="pay_contract")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="pay_confirm")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")],
    ])


def get_card_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for card payment with one-tap copy button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Скопировать номер карты",
            callback_data="copy_card_fallback",
            **copy_text_button("copy", CARD_NUMBER_PLAIN)
        )],
        [InlineKeyboardButton(
            "✅ Я оплатил", callback_data="pay_confirm",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("◀️ Назад в способы оплаты", callback_data="payment")],
    ])


def _get_bank_copy_text() -> str:
    """Format bank details as plain text for one-tap copy."""
    parts = []
    if BANK_DETAILS['recipient']:
        parts.append(f"Получатель: {BANK_DETAILS['recipient']}")
    if BANK_DETAILS['inn']:
        parts.append(f"ИНН: {BANK_DETAILS['inn']}")
    if BANK_DETAILS['account']:
        parts.append(f"Счёт: {BANK_DETAILS['account']}")
    if BANK_DETAILS['bank_name']:
        parts.append(f"Банк: {BANK_DETAILS['bank_name']}")
    if BANK_DETAILS['bik']:
        parts.append(f"БИК: {BANK_DETAILS['bik']}")
    return "\n".join(parts)


def get_bank_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for bank transfer with one-tap copy button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📋 Скопировать реквизиты",
            callback_data="copy_bank_fallback",
            **copy_text_button("copy", _get_bank_copy_text())
        )],
        [InlineKeyboardButton(
            "✅ Я оплатил", callback_data="pay_confirm",
            **styled_button_api_kwargs(style="constructive")
        )],
        [InlineKeyboardButton("◀️ Назад в способы оплаты", callback_data="payment")],
    ])


def get_payment_main_text() -> str:
    """Get main payment information text."""
    return """💰 **Оплата услуг WEB4TG Studio**

Выберите удобный способ оплаты:

💳 **Карта Visa** — быстрый перевод на карту
🏦 **Банковский перевод** — для юридических лиц

После оплаты нажмите "Я оплатил" и отправьте скриншот чека."""


def get_card_payment_text() -> str:
    """Get card payment details."""
    return f"""💳 **Оплата на карту Visa**

Номер карты:
`{CARD_NUMBER}`

Получатель: {BANK_DETAILS['recipient']}
Банк: {BANK_DETAILS['bank_name']}

📱 **Как оплатить:**
1. Откройте приложение вашего банка
2. Выберите "Перевод на карту"
3. Введите номер карты выше
4. Укажите сумму
5. Подтвердите перевод

⚠️ Комиссия зависит от вашего банка

После оплаты нажмите "Я оплатил" и отправьте скриншот чека."""


def get_bank_transfer_text() -> str:
    """Get bank transfer details."""
    return f"""🏦 **Банковский перевод**

**Получатель:**
`{BANK_DETAILS['recipient']}`

**ИНН получателя:**
`{BANK_DETAILS['inn']}`

**Счёт получателя:**
`{BANK_DETAILS['account']}`

**Банк получателя:**
{BANK_DETAILS['bank_name']}

**Адрес банка:**
{BANK_DETAILS['bank_address']}

**БИК:** `{BANK_DETAILS['bik']}`
**ИНН банка:** `{BANK_DETAILS['bank_inn']}`

После оплаты нажмите "Я оплатил" и отправьте скриншот чека."""


def get_copy_card_text() -> str:
    """Text for easy card number copy."""
    return f"""`{CARD_NUMBER_PLAIN}`

☝️ Нажмите на номер чтобы скопировать

Получатель: {BANK_DETAILS['recipient']}"""


def get_copy_bank_text() -> str:
    """Text for easy bank details copy."""
    return f"""**Реквизиты для копирования:**

Получатель: `{BANK_DETAILS['recipient']}`
ИНН: `{BANK_DETAILS['inn']}`
Счёт: `{BANK_DETAILS['account']}`
Банк: {BANK_DETAILS['bank_name']}
БИК: `{BANK_DETAILS['bik']}`"""


def get_payment_confirm_text() -> str:
    """Text after user confirms payment."""
    return """✅ **Спасибо!**

Пожалуйста, отправьте скриншот или фото чека об оплате.

Наш менеджер проверит платёж и свяжется с вами в течение 24 часов.

Если у вас есть вопросы — просто напишите!"""


STARS_PRODUCTS = {
    "consultation": {
        "title": "Консультация WEB4TG",
        "description": "60 минут персональной консультации по разработке Telegram Mini App",
        "price_stars": 500,
        "price_label": "500 ⭐",
    },
    "express_design": {
        "title": "Экспресс-дизайн",
        "description": "Дизайн-макет вашего приложения за 48 часов", 
        "price_stars": 2000,
        "price_label": "2000 ⭐",
    },
    "audit": {
        "title": "Аудит приложения",
        "description": "Полный технический и UX аудит существующего Mini App",
        "price_stars": 1000,
        "price_label": "1000 ⭐",
    }
}


async def create_stars_invoice(bot, chat_id: int, product_id: str) -> bool:
    product = STARS_PRODUCTS.get(product_id)
    if not product:
        return False
    
    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=product["title"],
            description=product["description"],
            payload=f"stars_{product_id}_{chat_id}",
            currency="XTR",
            prices=[{"label": product["title"], "amount": product["price_stars"]}],
            provider_token="",
        )
        record_payment_request(chat_id, f"stars_{product_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to create Stars invoice: {e}")
        return False


def _validate_payment_amount(payload: str, total_amount: int) -> bool:
    if total_amount <= 0:
        return False
    parts = payload.split("_")
    if len(parts) >= 2:
        product_id = parts[1]
        product = STARS_PRODUCTS.get(product_id)
        if product and product["price_stars"] != total_amount:
            return False
    return True

async def handle_successful_payment(user_id: int, payload: str, total_amount: int) -> str:
    if total_amount <= 0:
        logger.warning(f"Invalid payment amount: user={user_id}, amount={total_amount}")
        return "❌ Ошибка: некорректная сумма платежа."

    if not _validate_payment_amount(payload, total_amount):
        logger.warning(f"Payment amount mismatch: user={user_id}, payload={payload}, amount={total_amount}")
        return "❌ Ошибка: сумма платежа не соответствует выбранному продукту."

    try:
        if DATABASE_URL:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO star_payments (user_id, payload, amount, paid_at)
                        VALUES (%s, %s, %s, NOW())
                    """, (user_id, payload, total_amount))
        
        logger.info(f"Stars payment received: user={user_id}, payload={payload}, amount={total_amount}")
        return f"✅ Оплата {total_amount} ⭐ получена! Спасибо за покупку. Менеджер свяжется с вами в ближайшее время."
    except Exception as e:
        logger.error(f"Failed to record Stars payment: {e}")
        return "✅ Оплата получена! Менеджер скоро свяжется с вами."


async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle payment-related callbacks."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if action == "payment":
        analytics.track(user_id, FunnelEvent.PAYMENT_VIEW)
        await query.edit_message_text(
            get_payment_main_text(),
            reply_markup=get_payment_keyboard(),
            parse_mode="Markdown"
        )
    elif action == "pay_card":
        try:
            record_payment_request(user_id, "card")
        except Exception as e:
            logger.error(f"Failed to record card payment request: {e}")
        await query.edit_message_text(
            get_card_payment_text(),
            reply_markup=get_card_keyboard(),
            parse_mode="Markdown"
        )
    elif action == "pay_bank":
        try:
            record_payment_request(user_id, "bank")
        except Exception as e:
            logger.error(f"Failed to record bank payment request: {e}")
        await query.edit_message_text(
            get_bank_transfer_text(),
            reply_markup=get_bank_keyboard(),
            parse_mode="Markdown"
        )
    elif action == "copy_card":
        await query.answer("Номер карты ниже — нажмите чтобы скопировать", show_alert=False)
        await query.message.reply_text(
            get_copy_card_text(),
            parse_mode="Markdown"
        )
    elif action == "copy_bank":
        await query.answer("Реквизиты ниже — нажмите чтобы скопировать", show_alert=False)
        await query.message.reply_text(
            get_copy_bank_text(),
            parse_mode="Markdown"
        )
    elif action == "pay_contract":
        await query.answer("Отправляю договор...")
        try:
            with open(CONTRACT_PATH, "rb") as contract_file:
                await query.message.reply_document(
                    document=contract_file,
                    filename="Договор_WEB4TG_Studio.pdf",
                    caption="📄 **Договор на разработку ПО**\n\nОзнакомьтесь с условиями сотрудничества. Если есть вопросы — пишите!",
                    parse_mode="Markdown"
                )
        except FileNotFoundError:
            await query.message.reply_text(
                "Договор временно недоступен. Свяжитесь с менеджером для получения.",
                parse_mode="Markdown"
            )
    
    elif action == "pay_confirm":
        try:
            confirm_payment(user_id)
        except Exception as e:
            logger.error(f"Failed to confirm payment: {e}")
        await query.edit_message_text(
            get_payment_confirm_text(),
            parse_mode="Markdown"
        )
