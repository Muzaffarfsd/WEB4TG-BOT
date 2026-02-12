"""PDF Commercial Proposal (KP) Generator.

Generates personalized PDF documents based on brief data,
using Gemini AI for text and fpdf2 for PDF rendering with Cyrillic support.
"""

import io
import os
import logging
import tempfile
import time
from typing import Dict, Optional, Tuple

from fpdf import FPDF

logger = logging.getLogger(__name__)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"

PACKAGE_MAPPING = {
    "fast_cheap": "starter",
    "mvp_first": "starter",
    "balanced": "business",
    "quality": "premium",
}

PACKAGE_DATA = {
    "starter": {
        "name": "Стартер",
        "price": 150000,
        "timeline": "7-10 дней",
        "features": [
            "Каталог товаров/услуг",
            "Корзина покупок",
            "Онлайн-оплата (Telegram Stars, карты)",
            "Авторизация через Telegram",
        ],
        "not_included": [
            "Push-уведомления",
            "Программа лояльности",
            "AI чат-бот",
            "Аналитика",
        ],
        "support": "30 дней бесплатной поддержки",
        "updates": "Обновления 3 месяца",
    },
    "business": {
        "name": "Бизнес",
        "price": 250000,
        "timeline": "14-21 день",
        "features": [
            "Каталог товаров/услуг",
            "Корзина покупок",
            "Онлайн-оплата (Telegram Stars, карты, СБП)",
            "Авторизация через Telegram",
            "Push-уведомления",
            "Программа лояльности",
            "Аналитика и дашборд",
            "Кастомный дизайн",
        ],
        "not_included": [
            "AI чат-бот",
            "CRM-система",
        ],
        "support": "90 дней бесплатной поддержки",
        "updates": "Обновления 6 месяцев",
    },
    "premium": {
        "name": "Премиум",
        "price": 400000,
        "timeline": "21-30 дней",
        "features": [
            "Каталог товаров/услуг",
            "Корзина покупок",
            "Полная платёжная система",
            "Авторизация через Telegram",
            "Push-уведомления",
            "Программа лояльности",
            "Аналитика и дашборд",
            "Кастомный дизайн",
            "AI чат-бот",
            "CRM-система",
            "Персональный менеджер",
        ],
        "not_included": [],
        "support": "12 месяцев бесплатной поддержки",
        "updates": "Обновления 12 месяцев",
    },
}

PROJECT_TYPE_NAMES = {
    "shop": "Интернет-магазин",
    "restaurant": "Ресторан / Доставка еды",
    "beauty": "Салон красоты",
    "fitness": "Фитнес-клуб",
    "medical": "Медицинская клиника",
    "education": "Образовательная платформа",
    "services": "Сервис услуг",
    "custom": "Индивидуальный проект",
}

AUDIENCE_NAMES = {
    "b2c_young": "Молодёжь 18-35 лет",
    "b2c_adult": "Семейная аудитория 25-45 лет",
    "b2c_premium": "Премиум-сегмент",
    "b2c_mass": "Массовый рынок",
    "b2b": "B2B (корпоративные клиенты)",
    "mixed": "Смешанная аудитория",
}

DESIGN_NAMES = {
    "minimal": "Минимализм",
    "modern": "Современный",
    "premium": "Премиум / Люкс",
    "bright": "Яркий / Молодёжный",
    "corporate": "Корпоративный",
    "custom_design": "Индивидуальный макет",
}

TIMELINE_PHASES = {
    "starter": [
        ("Аналитика и ТЗ", "1-2 дня"),
        ("UI/UX дизайн", "2-3 дня"),
        ("Разработка", "3-4 дня"),
        ("Тестирование и запуск", "1 день"),
    ],
    "business": [
        ("Аналитика и ТЗ", "2-3 дня"),
        ("UI/UX дизайн", "3-5 дней"),
        ("Разработка frontend", "5-7 дней"),
        ("Разработка backend", "3-4 дня"),
        ("Тестирование и запуск", "1-2 дня"),
    ],
    "premium": [
        ("Аналитика и стратегия", "3-5 дней"),
        ("UI/UX дизайн (2 концепции)", "5-7 дней"),
        ("Разработка frontend", "7-10 дней"),
        ("Разработка backend + AI", "5-7 дней"),
        ("Тестирование и запуск", "1-2 дня"),
    ],
}


def _format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


def _get_ai_kp_prompt(brief_data: Dict, package_key: str, client_name: str) -> str:
    pkg = PACKAGE_DATA[package_key]
    project_type = PROJECT_TYPE_NAMES.get(brief_data.get("project_type", ""), "Проект")
    audience = AUDIENCE_NAMES.get(brief_data.get("audience", ""), "")

    return (
        f"Ты — коммерческий директор WEB4TG Studio, эксперт по Telegram Mini Apps.\n"
        f"Напиши 3 коротких абзаца для коммерческого предложения:\n\n"
        f"1. ПОНИМАНИЕ ЗАДАЧИ (2-3 предложения): опиши задачу клиента.\n"
        f"   Клиент: {client_name}\n"
        f"   Тип проекта: {project_type}\n"
        f"   Аудитория: {audience}\n\n"
        f"2. НАШЕ РЕШЕНИЕ (3-4 предложения): как WEB4TG Studio решит задачу, "
        f"какие выгоды получит клиент от пакета «{pkg['name']}».\n\n"
        f"3. ПОЧЕМУ МЫ (2-3 предложения): преимущества WEB4TG Studio — "
        f"опыт в Telegram Mini Apps, полный цикл, поддержка.\n\n"
        f"Пиши на русском, профессионально, убедительно. "
        f"Каждый абзац начинай с новой строки. Без заголовков и маркировки. "
        f"Общий объём: 300-500 символов."
    )


class KPDocument(FPDF):

    def __init__(self):
        super().__init__()
        self._load_fonts()
        self.set_auto_page_break(auto=True, margin=25)

    def _load_fonts(self):
        sans = os.path.join(FONT_DIR, "DejaVuSans.ttf")
        sans_bold = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
        if os.path.exists(sans) and os.path.exists(sans_bold):
            self.add_font("DejaVu", "", sans, uni=True)
            self.add_font("DejaVu", "B", sans_bold, uni=True)
            self._font_family = "DejaVu"
        else:
            self._font_family = "Helvetica"
            logger.warning("DejaVu fonts not found, using Helvetica (no Cyrillic)")

    def _set_font(self, style="", size=10):
        self.set_font(self._font_family, style, size)

    def header(self):
        self._set_font("B", 16)
        self.set_text_color(41, 98, 255)
        self.cell(0, 10, "WEB4TG Studio", align="L")

        self._set_font("", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "web4tg.com | @web4_tg", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(41, 98, 255)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-20)
        self._set_font("", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"WEB4TG Studio | Коммерческое предложение | Стр. {self.page_no()}/{{nb}}", align="C")

    def _section_title(self, title: str):
        self.ln(3)
        self._set_font("B", 12)
        self.set_text_color(41, 98, 255)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_text_color(40, 40, 40)

    def _body_text(self, text: str):
        self._set_font("", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def _feature_item(self, text: str, included: bool = True):
        self._set_font("", 10)
        marker = chr(10004) if included else chr(10006)
        color = (34, 139, 34) if included else (180, 180, 180)
        self.set_text_color(*color)
        self.cell(8, 6, marker)
        self.set_text_color(50, 50, 50)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")

    def _price_block(self, price: int, discount_pct: int = 0):
        self.ln(3)
        self.set_fill_color(245, 247, 255)
        self.rect(10, self.get_y(), 190, 30 if discount_pct else 22, style="F")

        y_start = self.get_y() + 3
        self.set_y(y_start)

        if discount_pct > 0:
            final_price = int(price * (100 - discount_pct) / 100)

            self._set_font("", 9)
            self.set_text_color(150, 150, 150)
            self.cell(95, 6, f"Базовая стоимость: {_format_price(price)} руб.", align="R")

            self._set_font("B", 9)
            self.set_text_color(34, 139, 34)
            self.cell(95, 6, f"  Ваша скидка: -{discount_pct}%", new_x="LMARGIN", new_y="NEXT")

            self._set_font("B", 14)
            self.set_text_color(41, 98, 255)
            self.cell(0, 10, f"ИТОГО: {_format_price(final_price)} руб.", align="C", new_x="LMARGIN", new_y="NEXT")
        else:
            self._set_font("B", 14)
            self.set_text_color(41, 98, 255)
            self.cell(0, 14, f"Стоимость: {_format_price(price)} руб.", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(5)

    def _timeline_block(self, phases: list):
        col_w = 170 / len(phases)
        x_start = 20
        self.ln(2)

        for i, (phase, duration) in enumerate(phases):
            x = x_start + i * col_w
            self.set_fill_color(41, 98, 255)
            self.rect(x, self.get_y(), col_w - 3, 4, style="F")

            if i > 0:
                self.set_draw_color(41, 98, 255)
                self.set_line_width(0.5)
                arrow_y = self.get_y() + 2
                self.line(x - 3, arrow_y, x, arrow_y)

        y_after_bars = self.get_y() + 6
        self.set_y(y_after_bars)

        for i, (phase, duration) in enumerate(phases):
            x = x_start + i * col_w
            self.set_xy(x, y_after_bars)
            self._set_font("B", 7)
            self.set_text_color(50, 50, 50)
            self.cell(col_w - 3, 4, phase, align="C")

        self.set_y(y_after_bars + 5)
        for i, (phase, duration) in enumerate(phases):
            x = x_start + i * col_w
            self.set_xy(x, self.get_y())
            self._set_font("", 7)
            self.set_text_color(120, 120, 120)
            self.cell(col_w - 3, 4, duration, align="C")

        self.set_y(self.get_y() + 8)

    def _payment_block(self, price: int, discount_pct: int = 0):
        final = int(price * (100 - discount_pct) / 100) if discount_pct else price
        prepay = int(final * 0.35)
        remainder = final - prepay

        self._set_font("", 10)
        self.set_text_color(50, 50, 50)

        self.cell(5, 6, "1.")
        self._set_font("B", 10)
        self.cell(50, 6, f"Предоплата 35%:")
        self._set_font("", 10)
        self.cell(0, 6, f"{_format_price(prepay)} руб.", new_x="LMARGIN", new_y="NEXT")

        self.cell(5, 6, "2.")
        self._set_font("B", 10)
        self.cell(50, 6, f"После сдачи 65%:")
        self._set_font("", 10)
        self.cell(0, 6, f"{_format_price(remainder)} руб.", new_x="LMARGIN", new_y="NEXT")

        self.ln(2)
        self._set_font("", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "Оплата: банковский перевод, карта, Telegram Stars", new_x="LMARGIN", new_y="NEXT")


def _determine_package(brief_answers: Dict) -> str:
    budget = brief_answers.get("budget_timeline", "balanced")
    return PACKAGE_MAPPING.get(budget, "business")


def build_kp_pdf(
    brief_answers: Dict,
    client_name: str = "",
    ai_text: str = "",
    discount_pct: int = 0,
    kp_number: Optional[int] = None,
) -> bytes:
    package_key = _determine_package(brief_answers)
    pkg = PACKAGE_DATA[package_key]
    project_type = PROJECT_TYPE_NAMES.get(brief_answers.get("project_type", ""), "Проект")

    pdf = KPDocument()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf._set_font("B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf._set_font("", 9)
    pdf.set_text_color(120, 120, 120)
    kp_num = kp_number or int(time.time()) % 100000
    from datetime import datetime
    date_str = datetime.now().strftime("%d.%m.%Y")
    pdf.cell(0, 6, f"No КП-{kp_num:05d} от {date_str}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if client_name:
        pdf._set_font("", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 6, f"Для: {client_name}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf._section_title(f"Проект: {project_type}")

    if ai_text:
        paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]
        subtitles = ["Понимание задачи", "Наше решение", "Почему мы"]
        for i, para in enumerate(paragraphs[:3]):
            if i < len(subtitles):
                pdf._set_font("B", 10)
                pdf.set_text_color(70, 70, 70)
                pdf.cell(0, 6, subtitles[i], new_x="LMARGIN", new_y="NEXT")
            pdf._body_text(para)
    else:
        pdf._body_text(
            f"Разработка Telegram Mini App типа «{project_type}» "
            f"с полным комплексом необходимых функций."
        )

    pdf._section_title(f"Пакет «{pkg['name']}» — что входит")

    for feat in pkg["features"]:
        pdf._feature_item(feat, included=True)
    for feat in pkg["not_included"]:
        pdf._feature_item(feat, included=False)

    pdf.ln(2)
    pdf._set_font("", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"Поддержка: {pkg['support']} | {pkg['updates']}", new_x="LMARGIN", new_y="NEXT")

    pdf._section_title("Стоимость")
    pdf._price_block(pkg["price"], discount_pct)

    pdf._section_title(f"Сроки реализации: {pkg['timeline']}")
    phases = TIMELINE_PHASES.get(package_key, TIMELINE_PHASES["business"])
    pdf._timeline_block(phases)

    pdf._section_title("Порядок оплаты")
    pdf._payment_block(pkg["price"], discount_pct)

    pdf._section_title("Следующие шаги")
    steps = [
        "Согласование ТЗ и подписание договора",
        "Предоплата 35% и старт работы",
        "Промежуточная демонстрация прогресса",
        "Финальная сдача и оплата остатка",
        "Запуск и поддержка",
    ]
    for i, step in enumerate(steps, 1):
        pdf._set_font("", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(8, 6, f"{i}.")
        pdf.cell(0, 6, step, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_fill_color(41, 98, 255)
    y_block = pdf.get_y()
    if y_block > 250:
        pdf.add_page()
        y_block = pdf.get_y()

    pdf.rect(10, y_block, 190, 25, style="F")
    pdf.set_y(y_block + 3)
    pdf._set_font("B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, "Готовы обсудить проект?", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf._set_font("", 9)
    pdf.cell(0, 6, "Telegram: @web4_tg  |  web4tg.com  |  Ответим в течение 30 минут", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)

    return pdf.output()


def get_kp_prompt_for_brief(brief_answers: Dict, client_name: str = "") -> str:
    package_key = _determine_package(brief_answers)
    return _get_ai_kp_prompt(brief_answers, package_key, client_name or "Клиент")


async def generate_and_send_kp(
    update,
    context,
    brief_answers: Dict,
    client_name: str = "",
    ai_text: str = "",
    discount_pct: int = 0,
):
    from telegram import InputFile
    try:
        pdf_bytes = build_kp_pdf(
            brief_answers=brief_answers,
            client_name=client_name,
            ai_text=ai_text,
            discount_pct=discount_pct,
        )

        project_type = PROJECT_TYPE_NAMES.get(brief_answers.get("project_type", ""), "project")
        filename = f"KP_WEB4TG_{project_type.replace(' ', '_').replace('/', '_')}.pdf"

        chat_id = update.effective_chat.id
        await context.bot.send_document(
            chat_id=chat_id,
            document=InputFile(io.BytesIO(pdf_bytes), filename=filename),
            caption=(
                "📄 <b>Ваше персональное коммерческое предложение</b>\n\n"
                "Документ содержит описание проекта, стоимость, "
                "сроки и порядок работы.\n\n"
                "Перешлите его коллегам для согласования!"
            ),
            parse_mode="HTML",
        )
        logger.info(f"KP PDF sent to user {update.effective_user.id}")
        return True

    except Exception as e:
        logger.error(f"Failed to generate/send KP PDF: {e}", exc_info=True)
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при генерации PDF. Попробуйте позже.",
        )
        return False
