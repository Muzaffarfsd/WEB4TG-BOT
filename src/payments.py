"""Payment information module for WEB4TG Studio bot."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

CARD_NUMBER = "4177 4901 1819 6304"
CARD_NUMBER_PLAIN = "4177490118196304"

BANK_DETAILS = {
    "recipient": "МУЗАПАРОВ МУЗАФФАР ШЕРЗОДОВИЧ",
    "inn": "22908199900907",
    "account": "1030220226371390",
    "bank_name": "ОАО \"Мбанк\"",
    "bank_address": "Кыргызская Республика, г. Бишкек, ул. Горького, 1/2",
    "bik": "103002",
    "bank_inn": "02712199110068",
}


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Get payment options keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплата картой Visa", callback_data="pay_card")],
        [InlineKeyboardButton("🏦 Банковский перевод", callback_data="pay_bank")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="pay_confirm")],
        [InlineKeyboardButton("◀️ Назад", callback_data="menu")],
    ])


def get_card_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for card payment."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Скопировать номер карты", callback_data="copy_card")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="pay_confirm")],
        [InlineKeyboardButton("◀️ Назад в способы оплаты", callback_data="payment")],
    ])


def get_bank_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for bank transfer."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Скопировать реквизиты", callback_data="copy_bank")],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="pay_confirm")],
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


async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """Handle payment-related callbacks."""
    query = update.callback_query
    await query.answer()
    
    if action == "payment":
        await query.edit_message_text(
            get_payment_main_text(),
            reply_markup=get_payment_keyboard(),
            parse_mode="Markdown"
        )
    elif action == "pay_card":
        await query.edit_message_text(
            get_card_payment_text(),
            reply_markup=get_card_keyboard(),
            parse_mode="Markdown"
        )
    elif action == "pay_bank":
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
    elif action == "pay_confirm":
        await query.edit_message_text(
            get_payment_confirm_text(),
            parse_mode="Markdown"
        )
