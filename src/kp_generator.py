"""PDF Commercial Proposal (KP) Generator — Premium Edition 2026.

Generates world-class personalized PDF documents based on brief data,
using Gemini AI for text and fpdf2 for PDF rendering with Cyrillic support.
Premium design with gradient blocks, accent lines, modern typography.
"""

import io
import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List, Tuple

from fpdf import FPDF

logger = logging.getLogger(__name__)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"

BRAND_PRIMARY = (30, 64, 175)
BRAND_DARK = (15, 23, 42)
BRAND_ACCENT = (99, 102, 241)
BRAND_SUCCESS = (16, 185, 129)
BRAND_LIGHT_BG = (248, 250, 252)
BRAND_CARD_BG = (241, 245, 249)
BRAND_MUTED = (100, 116, 139)
BRAND_TEXT = (30, 41, 59)
BRAND_WHITE = (255, 255, 255)
BRAND_GOLD = (245, 158, 11)
BRAND_RED = (239, 68, 68)

PACKAGE_MAPPING = {
    "fast_cheap": "starter",
    "mvp_first": "starter",
    "balanced": "business",
    "quality": "premium",
}

PACKAGE_DATA = {
    "starter": {
        "name": "Стартер",
        "icon": "S",
        "price": 150000,
        "timeline": "7-10 дней",
        "subtitle": "Быстрый запуск вашего бизнеса в Telegram",
        "features": [
            ("Каталог товаров/услуг", "Удобная витрина с категориями и фильтрами"),
            ("Корзина покупок", "Полноценная корзина с подсчётом итого"),
            ("Онлайн-оплата", "Telegram Stars + банковские карты"),
            ("Авторизация Telegram", "Вход в один клик без паролей"),
        ],
        "not_included": ["Push-уведомления", "Программа лояльности", "AI чат-бот", "Аналитика"],
        "support": "30 дней",
        "updates": "3 месяца",
        "guarantee": "Гарантия работоспособности 6 месяцев",
    },
    "business": {
        "name": "Бизнес",
        "icon": "B",
        "price": 250000,
        "timeline": "14-21 день",
        "subtitle": "Полноценное приложение для роста бизнеса",
        "features": [
            ("Каталог товаров/услуг", "Витрина с категориями, фильтрами, поиском"),
            ("Корзина и оформление", "Полный checkout с историей заказов"),
            ("Мультиплатёжная система", "Telegram Stars, карты, СБП"),
            ("Авторизация Telegram", "Вход в один клик + профиль клиента"),
            ("Push-уведомления", "Статусы заказов, акции, напоминания"),
            ("Программа лояльности", "Бонусы, кэшбек, персональные скидки"),
            ("Аналитика и дашборд", "Метрики продаж, конверсии, клиентов"),
            ("Кастомный UI/UX дизайн", "Уникальный дизайн под ваш бренд"),
        ],
        "not_included": ["AI чат-бот", "CRM-система"],
        "support": "90 дней",
        "updates": "6 месяцев",
        "guarantee": "Гарантия работоспособности 12 месяцев",
    },
    "premium": {
        "name": "Премиум",
        "icon": "P",
        "price": 400000,
        "timeline": "21-30 дней",
        "subtitle": "Максимальные возможности без компромиссов",
        "features": [
            ("Каталог товаров/услуг", "Продвинутая витрина с рекомендациями"),
            ("Корзина и оформление", "Полный checkout с историей и повторами"),
            ("Полная платёжная система", "Все способы оплаты + рассрочка"),
            ("Авторизация Telegram", "Вход + полный профиль + предпочтения"),
            ("Push-уведомления", "Умные триггерные уведомления"),
            ("Программа лояльности", "Многоуровневая система с геймификацией"),
            ("Бизнес-аналитика", "Полный дашборд с прогнозами и когортами"),
            ("Премиум UI/UX дизайн", "2 дизайн-концепции на выбор"),
            ("AI чат-бот", "Умный помощник для клиентов 24/7"),
            ("CRM-система", "Управление клиентами и заказами"),
            ("Персональный менеджер", "Выделенный менеджер проекта"),
        ],
        "not_included": [],
        "support": "12 месяцев",
        "updates": "12 месяцев",
        "guarantee": "Гарантия работоспособности 24 месяца",
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
        ("Аналитика", "1-2 дня", "Исследование, ТЗ"),
        ("Дизайн", "2-3 дня", "UI/UX макеты"),
        ("Разработка", "3-4 дня", "Frontend + Backend"),
        ("Запуск", "1 день", "Тесты, деплой"),
    ],
    "business": [
        ("Аналитика", "2-3 дня", "Исследование, ТЗ, CJM"),
        ("Дизайн", "3-5 дней", "UI/UX + прототип"),
        ("Frontend", "5-7 дней", "Интерфейс приложения"),
        ("Backend", "3-4 дня", "Серверная часть, API"),
        ("Запуск", "1-2 дня", "QA, деплой, мониторинг"),
    ],
    "premium": [
        ("Стратегия", "3-5 дней", "Аналитика, CJM, ТЗ"),
        ("Дизайн", "5-7 дней", "2 концепции UI/UX"),
        ("Frontend", "7-10 дней", "Интерфейс + анимации"),
        ("Backend + AI", "5-7 дней", "API, AI, интеграции"),
        ("Запуск", "1-2 дня", "QA, деплой, обучение"),
    ],
}

STATS = [
    ("50+", "проектов"),
    ("3 года", "на рынке"),
    ("98%", "довольных клиентов"),
    ("24/7", "поддержка"),
]


def _format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


def _get_ai_kp_prompt(brief_data: Dict, package_key: str, client_name: str) -> str:
    pkg = PACKAGE_DATA[package_key]
    project_type = PROJECT_TYPE_NAMES.get(brief_data.get("project_type", ""), "Проект")
    audience = AUDIENCE_NAMES.get(brief_data.get("audience", ""), "")
    design = DESIGN_NAMES.get(brief_data.get("design_pref", ""), "")

    return (
        f"Ты — ведущий коммерческий директор WEB4TG Studio, эксперт мирового уровня по Telegram Mini Apps.\n"
        f"Напиши 4 раздела для премиального коммерческого предложения.\n"
        f"Каждый раздел отдели пустой строкой.\n\n"
        f"Данные клиента:\n"
        f"- Имя: {client_name}\n"
        f"- Тип проекта: {project_type}\n"
        f"- Аудитория: {audience}\n"
        f"- Стиль дизайна: {design}\n"
        f"- Пакет: «{pkg['name']}» за {_format_price(pkg['price'])} руб.\n\n"
        f"Разделы:\n"
        f"1. ВЫЗОВ (2-3 предложения): опиши бизнес-проблему клиента, "
        f"которую решит Telegram Mini App. Покажи понимание отрасли «{project_type}». "
        f"Используй конкретику: потеря клиентов, неэффективные процессы, упущенная выручка.\n\n"
        f"2. РЕШЕНИЕ (3-4 предложения): как именно WEB4TG Studio решит задачу. "
        f"Упомяни 2-3 конкретные функции из пакета «{pkg['name']}». "
        f"Покажи бизнес-выгоды: рост конверсии, автоматизация, снижение затрат.\n\n"
        f"3. РЕЗУЛЬТАТ (2-3 предложения): какие измеримые результаты получит клиент "
        f"через 1-3 месяца после запуска. Используй реалистичные цифры: "
        f"+20-40% конверсия, экономия X часов в неделю, ROI.\n\n"
        f"4. ПРЕИМУЩЕСТВО (2 предложения): почему WEB4TG Studio — лучший выбор. "
        f"Кратко: экспертиза, полный цикл, гарантии.\n\n"
        f"Правила:\n"
        f"- Русский язык, профессиональный деловой стиль\n"
        f"- Без заголовков, нумерации и маркировки — только текст\n"
        f"- Каждый раздел = один абзац, отделённый пустой строкой\n"
        f"- Общий объём: 500-700 символов\n"
        f"- Обращайся на «вы» (без имени)\n"
    )


class KPDocument(FPDF):

    def __init__(self):
        super().__init__()
        self._load_fonts()
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 10, 15)

    def _load_fonts(self):
        sans = os.path.join(FONT_DIR, "DejaVuSans.ttf")
        sans_bold = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
        if os.path.exists(sans) and os.path.exists(sans_bold):
            self.add_font("DejaVu", "", sans, uni=True)
            self.add_font("DejaVu", "B", sans_bold, uni=True)
            self._ff = "DejaVu"
        else:
            self._ff = "Helvetica"
            logger.warning("DejaVu fonts not found, Cyrillic unavailable")

    def _f(self, style="", size=10):
        self.set_font(self._ff, style, size)

    def _tc(self, color):
        self.set_text_color(*color)

    def _fc(self, color):
        self.set_fill_color(*color)

    def _dc(self, color):
        self.set_draw_color(*color)

    def _rounded_rect(self, x, y, w, h, r, color, style="F"):
        self._fc(color)
        self._dc(color)
        if r > 0:
            self.set_line_width(0.1)
            self.rect(x + r, y, w - 2 * r, h, style)
            self.rect(x, y + r, w, h - 2 * r, style)
            self.ellipse(x, y, 2 * r, 2 * r, style)
            self.ellipse(x + w - 2 * r, y, 2 * r, 2 * r, style)
            self.ellipse(x, y + h - 2 * r, 2 * r, 2 * r, style)
            self.ellipse(x + w - 2 * r, y + h - 2 * r, 2 * r, 2 * r, style)
        else:
            self.rect(x, y, w, h, style)

    def header(self):
        self._fc(BRAND_DARK)
        self.rect(0, 0, 210, 3, "F")

        self._f("B", 13)
        self._tc(BRAND_PRIMARY)
        self.set_y(8)
        self.cell(0, 8, "WEB4TG STUDIO", align="L")

        self._f("", 7)
        self._tc(BRAND_MUTED)
        self.cell(0, 8, "web4tg.com  |  t.me/web4_tg", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self._dc((226, 232, 240))
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)
        self._f("", 6.5)
        self._tc(BRAND_MUTED)
        self.cell(
            0, 8,
            f"WEB4TG Studio  \u00b7  \u041a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435  \u00b7  \u0421\u0442\u0440. {self.page_no()}/{{nb}}",
            align="C"
        )

    def _hero_block(self, title: str, subtitle: str, kp_num: int, date_str: str, client_name: str):
        y = self.get_y()
        self._rounded_rect(15, y, 180, 48, 3, BRAND_DARK)

        self._fc((35, 70, 180))
        self.ellipse(150, y - 5, 60, 60, "F")

        self.set_y(y + 6)
        self._f("", 8)
        self._tc((148, 163, 184))
        self.set_x(22)
        self.cell(0, 5, f"\u2116 \u041a\u041f-{kp_num:05d}  |  {date_str}", new_x="LMARGIN", new_y="NEXT")

        self.set_x(22)
        self._f("B", 18)
        self._tc(BRAND_WHITE)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")

        self.set_x(22)
        self._f("", 9)
        self._tc((148, 163, 184))
        self.cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")

        if client_name:
            self.set_x(22)
            self.ln(2)
            self._f("", 8)
            self._tc(BRAND_WHITE)
            self.cell(0, 5, f"\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u043e \u0434\u043b\u044f: {client_name}", new_x="LMARGIN", new_y="NEXT")

        self.set_y(y + 52)

    def _stats_bar(self):
        y = self.get_y()
        col_w = 180 / len(STATS)

        self._rounded_rect(15, y, 180, 22, 2, BRAND_CARD_BG)

        for i, (value, label) in enumerate(STATS):
            x = 15 + i * col_w
            self.set_xy(x, y + 3)
            self._f("B", 12)
            self._tc(BRAND_PRIMARY)
            self.cell(col_w, 7, value, align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_xy(x, y + 11)
            self._f("", 7)
            self._tc(BRAND_MUTED)
            self.cell(col_w, 5, label, align="C")

            if i < len(STATS) - 1:
                sep_x = x + col_w
                self._dc((203, 213, 225))
                self.set_line_width(0.3)
                self.line(sep_x, y + 4, sep_x, y + 18)

        self.set_y(y + 26)

    def _section_header(self, number: str, title: str):
        self.ln(4)
        y = self.get_y()

        self._rounded_rect(15, y, 22, 8, 2, BRAND_PRIMARY)
        self._f("B", 8)
        self._tc(BRAND_WHITE)
        self.set_xy(15, y + 0.5)
        self.cell(22, 7, number, align="C")

        self._f("B", 11)
        self._tc(BRAND_DARK)
        self.set_xy(40, y)
        self.cell(0, 8, title)

        self.set_y(y + 11)

    def _ai_section(self, label: str, text: str, accent_color=None):
        if not accent_color:
            accent_color = BRAND_PRIMARY
        y = self.get_y()

        self._dc(accent_color)
        self.set_line_width(0.8)
        self.line(15, y, 15, y + 4)

        self._f("B", 8)
        self._tc(accent_color)
        self.set_x(19)
        self.cell(0, 5, label.upper(), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

        self._f("", 9.5)
        self._tc(BRAND_TEXT)
        self.set_x(19)
        self.multi_cell(171, 5.5, text)
        self.ln(3)

    def _feature_card(self, name: str, description: str, included: bool = True):
        y = self.get_y()
        if y > 265:
            self.add_page()
            y = self.get_y()

        row_h = 10
        self._rounded_rect(15, y, 180, row_h, 1, BRAND_CARD_BG if included else BRAND_WHITE)

        if included:
            self._rounded_rect(17, y + 2, 6, 6, 1, BRAND_SUCCESS)
            self._f("B", 7)
            self._tc(BRAND_WHITE)
            self.set_xy(17, y + 2)
            self.cell(6, 6, chr(10004), align="C")
        else:
            self._dc((203, 213, 225))
            self.set_line_width(0.3)
            self.rect(17, y + 2, 6, 6)
            self._f("", 7)
            self._tc((203, 213, 225))
            self.set_xy(17, y + 2)
            self.cell(6, 6, chr(8211), align="C")

        self._f("B" if included else "", 9)
        self._tc(BRAND_TEXT if included else BRAND_MUTED)
        self.set_xy(26, y)
        self.cell(70, row_h, name)

        self._f("", 7.5)
        self._tc(BRAND_MUTED)
        self.set_xy(96, y)
        self.cell(99, row_h, description if included else "")

        self.set_y(y + row_h + 1.5)

    def _price_card(self, price: int, discount_pct: int = 0, package_name: str = ""):
        y = self.get_y()
        card_h = 50 if discount_pct else 40

        self._rounded_rect(15, y, 180, card_h, 3, BRAND_DARK)

        if package_name:
            self.set_xy(22, y + 5)
            self._f("", 8)
            self._tc((148, 163, 184))
            self.cell(0, 5, f"\u041f\u0430\u043a\u0435\u0442 \u00ab{package_name}\u00bb")

        if discount_pct > 0:
            final_price = int(price * (100 - discount_pct) / 100)
            savings = price - final_price

            self.set_xy(22, y + 12)
            self._f("", 9)
            self._tc((148, 163, 184))
            self.cell(50, 6, f"\u0411\u0430\u0437\u043e\u0432\u0430\u044f \u0446\u0435\u043d\u0430:")

            self._f("", 9)
            self._tc((100, 116, 139))
            self.cell(40, 6, f"{_format_price(price)} \u0440\u0443\u0431.")

            self._rounded_rect(130, y + 11, 55, 8, 2, BRAND_SUCCESS)
            self._f("B", 8)
            self._tc(BRAND_WHITE)
            self.set_xy(130, y + 11)
            self.cell(55, 8, f"VIP \u0441\u043a\u0438\u0434\u043a\u0430 \u2212{discount_pct}%", align="C")

            self.set_xy(22, y + 24)
            self._f("B", 22)
            self._tc(BRAND_WHITE)
            self.cell(100, 12, f"{_format_price(final_price)} \u0440\u0443\u0431.")

            self._f("", 8)
            self._tc(BRAND_SUCCESS)
            self.cell(60, 12, f"\u042d\u043a\u043e\u043d\u043e\u043c\u0438\u044f: {_format_price(savings)} \u0440\u0443\u0431.")

            self.set_xy(22, y + 38)
            self._f("", 7)
            self._tc((148, 163, 184))
            self.cell(0, 5, "\u0421\u043a\u0438\u0434\u043a\u0430 \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0430 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u043f\u043e \u0432\u0430\u0448\u0435\u043c\u0443 VIP-\u0441\u0442\u0430\u0442\u0443\u0441\u0443")
        else:
            self.set_xy(22, y + (14 if package_name else 8))
            self._f("B", 24)
            self._tc(BRAND_WHITE)
            self.cell(0, 14, f"{_format_price(price)} \u0440\u0443\u0431.")

            self.set_xy(22, y + (29 if package_name else 23))
            self._f("", 8)
            self._tc((148, 163, 184))
            self.cell(0, 5, "\u0424\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u00b7 \u0411\u0435\u0437 \u0441\u043a\u0440\u044b\u0442\u044b\u0445 \u043f\u043b\u0430\u0442\u0435\u0436\u0435\u0439")

        self.set_y(y + card_h + 4)

    def _timeline_modern(self, phases: list, total_timeline: str):
        y = self.get_y()
        n = len(phases)
        step_w = 170 / n

        for i, (name, duration, desc) in enumerate(phases):
            x = 20 + i * step_w
            cx = x + step_w / 2

            circle_r = 5
            if i < n - 1:
                self._dc((203, 213, 225))
                self.set_line_width(0.5)
                line_y = y + circle_r
                self.line(cx + circle_r, line_y, cx + step_w - circle_r, line_y)

            self._rounded_rect(cx - circle_r, y, circle_r * 2, circle_r * 2, circle_r, BRAND_PRIMARY)
            self._f("B", 7)
            self._tc(BRAND_WHITE)
            self.set_xy(cx - circle_r, y)
            self.cell(circle_r * 2, circle_r * 2, str(i + 1), align="C")

            self.set_xy(x, y + circle_r * 2 + 2)
            self._f("B", 7.5)
            self._tc(BRAND_DARK)
            self.cell(step_w, 4, name, align="C", new_x="LMARGIN", new_y="NEXT")

            self.set_xy(x, y + circle_r * 2 + 7)
            self._f("", 7)
            self._tc(BRAND_PRIMARY)
            self.cell(step_w, 4, duration, align="C", new_x="LMARGIN", new_y="NEXT")

            self.set_xy(x, y + circle_r * 2 + 12)
            self._f("", 6)
            self._tc(BRAND_MUTED)
            self.cell(step_w, 3.5, desc, align="C")

        self.set_y(y + circle_r * 2 + 20)

        ty = self.get_y()
        self._rounded_rect(60, ty, 90, 10, 2, BRAND_CARD_BG)
        self._f("B", 8)
        self._tc(BRAND_PRIMARY)
        self.set_xy(60, ty)
        self.cell(90, 10, f"\u0418\u0442\u043e\u0433\u043e: {total_timeline}", align="C")
        self.set_y(ty + 14)

    def _payment_cards(self, price: int, discount_pct: int = 0):
        final = int(price * (100 - discount_pct) / 100) if discount_pct else price
        prepay = int(final * 0.35)
        remainder = final - prepay

        y = self.get_y()
        card_w = 87

        self._rounded_rect(15, y, card_w, 32, 2, BRAND_CARD_BG)
        self.set_xy(20, y + 4)
        self._f("B", 9)
        self._tc(BRAND_PRIMARY)
        self.cell(0, 5, "\u042d\u0442\u0430\u043f 1: \u041f\u0440\u0435\u0434\u043e\u043f\u043b\u0430\u0442\u0430")
        self.set_xy(20, y + 11)
        self._f("B", 14)
        self._tc(BRAND_DARK)
        self.cell(0, 8, f"{_format_price(prepay)} \u0440\u0443\u0431.")
        self.set_xy(20, y + 21)
        self._f("", 7.5)
        self._tc(BRAND_MUTED)
        self.cell(0, 5, "35% \u2014 \u0434\u043e \u043d\u0430\u0447\u0430\u043b\u0430 \u0440\u0430\u0431\u043e\u0442")

        x2 = 15 + card_w + 6
        self._rounded_rect(x2, y, card_w, 32, 2, BRAND_CARD_BG)
        self.set_xy(x2 + 5, y + 4)
        self._f("B", 9)
        self._tc(BRAND_SUCCESS)
        self.cell(0, 5, "\u042d\u0442\u0430\u043f 2: \u041f\u043e\u0441\u043b\u0435 \u0441\u0434\u0430\u0447\u0438")
        self.set_xy(x2 + 5, y + 11)
        self._f("B", 14)
        self._tc(BRAND_DARK)
        self.cell(0, 8, f"{_format_price(remainder)} \u0440\u0443\u0431.")
        self.set_xy(x2 + 5, y + 21)
        self._f("", 7.5)
        self._tc(BRAND_MUTED)
        self.cell(0, 5, "65% \u2014 \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u0438\u0451\u043c\u043a\u0438 \u0440\u0430\u0431\u043e\u0442\u044b")

        self.set_y(y + 36)
        self._f("", 7.5)
        self._tc(BRAND_MUTED)
        self.cell(0, 5, "\u0421\u043f\u043e\u0441\u043e\u0431\u044b \u043e\u043f\u043b\u0430\u0442\u044b: \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0432\u043e\u0434  \u00b7  \u041a\u0430\u0440\u0442\u0430  \u00b7  \u0421\u0411\u041f  \u00b7  Telegram Stars", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def _steps_block(self):
        steps = [
            ("\u0421\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u0438\u0435", "\u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u043c \u0422\u0417 \u0438 \u043f\u043e\u0434\u043f\u0438\u0441\u044b\u0432\u0430\u0435\u043c \u0434\u043e\u0433\u043e\u0432\u043e\u0440"),
            ("\u041f\u0440\u0435\u0434\u043e\u043f\u043b\u0430\u0442\u0430", "\u041e\u043f\u043b\u0430\u0442\u0430 35% \u0438 \u0441\u0442\u0430\u0440\u0442 \u0440\u0430\u0431\u043e\u0442\u044b"),
            ("\u0414\u0435\u043c\u043e", "\u041f\u0440\u043e\u043c\u0435\u0436\u0443\u0442\u043e\u0447\u043d\u0430\u044f \u0434\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0430\u0446\u0438\u044f \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441\u0430"),
            ("\u0421\u0434\u0430\u0447\u0430", "\u0424\u0438\u043d\u0430\u043b\u044c\u043d\u0430\u044f \u043f\u0440\u0438\u0451\u043c\u043a\u0430 \u0438 \u043e\u043f\u043b\u0430\u0442\u0430 \u043e\u0441\u0442\u0430\u0442\u043a\u0430"),
            ("\u0417\u0430\u043f\u0443\u0441\u043a", "\u0414\u0435\u043f\u043b\u043e\u0439 + \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430"),
        ]
        for i, (title, desc) in enumerate(steps):
            y = self.get_y()
            if y > 270:
                self.add_page()
                y = self.get_y()

            self._rounded_rect(15, y, 7, 7, 2, BRAND_PRIMARY if i < 4 else BRAND_SUCCESS)
            self._f("B", 7)
            self._tc(BRAND_WHITE)
            self.set_xy(15, y)
            self.cell(7, 7, str(i + 1), align="C")

            self._f("B", 9)
            self._tc(BRAND_DARK)
            self.set_xy(26, y)
            self.cell(35, 7, title)

            self._f("", 8)
            self._tc(BRAND_MUTED)
            self.set_xy(62, y)
            self.cell(0, 7, desc)

            if i < len(steps) - 1:
                self._dc((226, 232, 240))
                self.set_line_width(0.3)
                self.line(18.5, y + 7, 18.5, y + 10)

            self.set_y(y + 10)

    def _cta_block(self):
        y = self.get_y()
        if y > 245:
            self.add_page()
            y = self.get_y()

        self.ln(3)
        y = self.get_y()
        self._rounded_rect(15, y, 180, 35, 3, BRAND_PRIMARY)

        self.set_xy(22, y + 5)
        self._f("B", 14)
        self._tc(BRAND_WHITE)
        self.cell(0, 8, "\u0413\u043e\u0442\u043e\u0432\u044b \u043e\u0431\u0441\u0443\u0434\u0438\u0442\u044c \u043f\u0440\u043e\u0435\u043a\u0442?")

        self.set_xy(22, y + 15)
        self._f("", 9)
        self._tc((199, 210, 254))
        self.cell(0, 6, "\u041e\u0442\u0432\u0435\u0442\u0438\u043c \u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435 30 \u043c\u0438\u043d\u0443\u0442 \u0432 \u0440\u0430\u0431\u043e\u0447\u0435\u0435 \u0432\u0440\u0435\u043c\u044f", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(22, y + 23)
        self._f("B", 9)
        self._tc(BRAND_WHITE)
        self.cell(0, 6, "Telegram: @web4_tg   \u00b7   web4tg.com   \u00b7   +7 (XXX) XXX-XX-XX")

        self.set_y(y + 40)

    def _guarantees_block(self, guarantee: str, support: str, updates: str):
        y = self.get_y()
        if y > 255:
            self.add_page()
            y = self.get_y()

        items = [
            (chr(9733), "\u0413\u0430\u0440\u0430\u043d\u0442\u0438\u044f", guarantee),
            (chr(9733), "\u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430", f"\u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e {support}"),
            (chr(9733), "\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f", f"\u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e {updates}"),
        ]
        col_w = 60
        for i, (icon, title, desc) in enumerate(items):
            x = 15 + i * col_w
            self.set_xy(x, y)
            self._f("B", 9)
            self._tc(BRAND_GOLD)
            self.cell(8, 6, icon)
            self._tc(BRAND_DARK)
            self.cell(col_w - 8, 6, title)
            self.set_xy(x + 8, y + 6)
            self._f("", 7.5)
            self._tc(BRAND_MUTED)
            self.cell(col_w - 8, 5, desc)

        self.set_y(y + 14)


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
    project_type = PROJECT_TYPE_NAMES.get(brief_answers.get("project_type", ""), "\u041f\u0440\u043e\u0435\u043a\u0442")

    pdf = KPDocument()
    pdf.alias_nb_pages()
    pdf.add_page()

    kp_num = kp_number or int(time.time()) % 100000
    date_str = datetime.now().strftime("%d.%m.%Y")

    pdf._hero_block(
        title=f"\u041a\u041e\u041c\u041c\u0415\u0420\u0427\u0415\u0421\u041a\u041e\u0415 \u041f\u0420\u0415\u0414\u041b\u041e\u0416\u0415\u041d\u0418\u0415",
        subtitle=f"{project_type}  \u00b7  \u041f\u0430\u043a\u0435\u0442 \u00ab{pkg['name']}\u00bb  \u00b7  {pkg['timeline']}",
        kp_num=kp_num,
        date_str=date_str,
        client_name=client_name,
    )

    pdf._stats_bar()

    if ai_text:
        pdf._section_header("01", "\u041e \u043f\u0440\u043e\u0435\u043a\u0442\u0435")
        paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]
        labels = [
            ("\u0412\u044b\u0437\u043e\u0432", BRAND_RED),
            ("\u0420\u0435\u0448\u0435\u043d\u0438\u0435", BRAND_PRIMARY),
            ("\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442", BRAND_SUCCESS),
            ("\u041f\u0440\u0435\u0438\u043c\u0443\u0449\u0435\u0441\u0442\u0432\u043e", BRAND_GOLD),
        ]
        for i, para in enumerate(paragraphs[:4]):
            if i < len(labels):
                label, color = labels[i]
                pdf._ai_section(label, para, color)
            else:
                pdf._ai_section("", para)
    else:
        pdf._section_header("01", "\u041e \u043f\u0440\u043e\u0435\u043a\u0442\u0435")
        pdf._f("", 9.5)
        pdf._tc(BRAND_TEXT)
        pdf.multi_cell(0, 5.5, (
            f"\u0420\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u043a\u0430 Telegram Mini App \u0442\u0438\u043f\u0430 \u00ab{project_type}\u00bb "
            f"\u0441 \u043f\u043e\u043b\u043d\u044b\u043c \u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0441\u043e\u043c \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u044b\u0445 \u0444\u0443\u043d\u043a\u0446\u0438\u0439 "
            f"\u0434\u043b\u044f \u0443\u0441\u043f\u0435\u0448\u043d\u043e\u0433\u043e \u0437\u0430\u043f\u0443\u0441\u043a\u0430 \u0438 \u0440\u043e\u0441\u0442\u0430 \u0432\u0430\u0448\u0435\u0433\u043e \u0431\u0438\u0437\u043d\u0435\u0441\u0430."
        ))
        pdf.ln(3)

    pdf._section_header("02", f"\u041f\u0430\u043a\u0435\u0442 \u00ab{pkg['name']}\u00bb \u2014 {pkg['subtitle']}")

    for feat_name, feat_desc in pkg["features"]:
        pdf._feature_card(feat_name, feat_desc, included=True)
    for feat_name in pkg["not_included"]:
        pdf._feature_card(feat_name, "\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0432 \u0441\u0442\u0430\u0440\u0448\u0438\u0445 \u043f\u0430\u043a\u0435\u0442\u0430\u0445", included=False)

    pdf.ln(2)
    pdf._guarantees_block(pkg["guarantee"], pkg["support"], pkg["updates"])

    pdf._section_header("03", "\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c")
    pdf._price_card(pkg["price"], discount_pct, pkg["name"])

    pdf._section_header("04", f"\u0421\u0440\u043e\u043a\u0438 \u0440\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438")
    phases = TIMELINE_PHASES.get(package_key, TIMELINE_PHASES["business"])
    pdf._timeline_modern(phases, pkg["timeline"])

    pdf._section_header("05", "\u041f\u043e\u0440\u044f\u0434\u043e\u043a \u043e\u043f\u043b\u0430\u0442\u044b")
    pdf._payment_cards(pkg["price"], discount_pct)

    pdf._section_header("06", "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0435 \u0448\u0430\u0433\u0438")
    pdf._steps_block()

    pdf._cta_block()

    return pdf.output()


def get_kp_prompt_for_brief(brief_answers: Dict, client_name: str = "") -> str:
    package_key = _determine_package(brief_answers)
    return _get_ai_kp_prompt(brief_answers, package_key, client_name or "\u041a\u043b\u0438\u0435\u043d\u0442")


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
                "\ud83d\udcc4 <b>\u0412\u0430\u0448\u0435 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u043e\u0435 \u043a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435</b>\n\n"
                "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u0430, \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c, "
                "\u0441\u0440\u043e\u043a\u0438 \u0438 \u043f\u043e\u0440\u044f\u0434\u043e\u043a \u0440\u0430\u0431\u043e\u0442\u044b.\n\n"
                "\u041f\u0435\u0440\u0435\u0448\u043b\u0438\u0442\u0435 \u0435\u0433\u043e \u043a\u043e\u043b\u043b\u0435\u0433\u0430\u043c \u0434\u043b\u044f \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u0438\u044f!"
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
            text="\u041f\u0440\u043e\u0438\u0437\u043e\u0448\u043b\u0430 \u043e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438 PDF. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u043f\u043e\u0437\u0436\u0435.",
        )
        return False
