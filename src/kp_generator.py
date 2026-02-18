"""PDF Commercial Proposal (KP) Generator — World-Class 2026 Design.

Multi-page premium layout inspired by Behance/Dribbble 2025-2026 trends:
- Full cover page with bold typography
- Generous white space (25mm+ margins)
- Future Dusk color palette (deep indigo/navy)
- Max 3 accent colors
- Feature cards in 2-column grid
- Dramatic price presentation
- Clean horizontal timeline
- ReportLab canvas with gradients, shadows, rounded cards
"""

import io
import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

W, H = A4

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONT_DIRS = [
    os.path.join(_PROJECT_ROOT, "fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/app/fonts",
]

FONT = "Helvetica"
FONTB = "Helvetica-Bold"
for _fd in _FONT_DIRS:
    _regular = os.path.join(_fd, "DejaVuSans.ttf")
    _bold = os.path.join(_fd, "DejaVuSans-Bold.ttf")
    if os.path.isfile(_regular) and os.path.isfile(_bold):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", _regular))
            pdfmetrics.registerFont(TTFont("DejaVuB", _bold))
            FONT = "DejaVu"
            FONTB = "DejaVuB"
            logger.info(f"DejaVu fonts loaded from {_fd}")
            break
        except Exception as e:
            logger.warning(f"Failed to register fonts from {_fd}: {e}")
else:
    logger.warning("DejaVu fonts not found in any location, PDF may lack Cyrillic support")

C_BG = HexColor("#fafbfd")
C_DARK = HexColor("#0c1222")
C_NAVY = HexColor("#1a1f3a")
C_INDIGO = HexColor("#4f46e5")
C_INDIGO_LIGHT = HexColor("#818cf8")
C_INDIGO_PALE = HexColor("#eef2ff")
C_EMERALD = HexColor("#059669")
C_EMERALD_PALE = HexColor("#ecfdf5")
C_AMBER = HexColor("#d97706")
C_AMBER_PALE = HexColor("#fffbeb")
C_ROSE = HexColor("#e11d48")
C_ROSE_PALE = HexColor("#fff1f2")
C_SLATE50 = HexColor("#f8fafc")
C_SLATE100 = HexColor("#f1f5f9")
C_SLATE200 = HexColor("#e2e8f0")
C_SLATE300 = HexColor("#cbd5e1")
C_SLATE400 = HexColor("#94a3b8")
C_SLATE500 = HexColor("#64748b")
C_SLATE600 = HexColor("#475569")
C_SLATE700 = HexColor("#334155")
C_SLATE800 = HexColor("#1e293b")
C_SLATE900 = HexColor("#0f172a")
C_WHITE = white

LM = 28 * mm
RM = 28 * mm
CW = W - LM - RM
BOTTOM = 30 * mm

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
        "timeline": "7\u201310 дней",
        "subtitle": "Быстрый запуск в Telegram",
        "features": [
            ("Каталог товаров", "Категории, фильтры, поиск"),
            ("Корзина покупок", "Полноценная корзина с подсчётом"),
            ("Онлайн-оплата", "Telegram Stars + карты"),
            ("Авторизация", "Вход через Telegram"),
        ],
        "not_included": ["Push-уведомления", "Лояльность", "AI чат-бот", "Аналитика"],
        "support": "30 дней",
        "updates": "3 мес.",
        "guarantee": "6 мес.",
    },
    "business": {
        "name": "Бизнес",
        "price": 250000,
        "timeline": "14\u201321 день",
        "subtitle": "Полный комплект для роста",
        "features": [
            ("Каталог товаров", "Категории, фильтры, поиск"),
            ("Корзина и оформление", "Checkout + история заказов"),
            ("Мультиплатёжная система", "Stars, карты, СБП"),
            ("Авторизация Telegram", "Вход + профиль клиента"),
            ("Push-уведомления", "Статусы, акции, триггеры"),
            ("Программа лояльности", "Бонусы, кэшбек, скидки"),
            ("Аналитика продаж", "Метрики, конверсии, отчёты"),
            ("Кастомный UI/UX", "Дизайн под ваш бренд"),
        ],
        "not_included": ["AI чат-бот", "CRM-система"],
        "support": "90 дней",
        "updates": "6 мес.",
        "guarantee": "12 мес.",
    },
    "premium": {
        "name": "Премиум",
        "price": 400000,
        "timeline": "21\u201330 дней",
        "subtitle": "Без компромиссов",
        "features": [
            ("Продвинутый каталог", "Рекомендации, фильтры, A/B"),
            ("Умная корзина", "Повторные заказы, шаблоны"),
            ("Все виды оплаты", "Карты, СБП, рассрочка"),
            ("Авторизация+", "Профиль + предпочтения"),
            ("Смарт-уведомления", "Триггерные сценарии"),
            ("Программа лояльности", "Многоуровневая + геймификация"),
            ("Бизнес-аналитика", "Дашборд с прогнозами"),
            ("Премиум UI/UX", "2 концепции на выбор"),
            ("AI чат-бот 24/7", "Умный помощник"),
            ("CRM-система", "Клиенты + заказы + статусы"),
            ("Персональный менеджер", "Выделенный PM"),
        ],
        "not_included": [],
        "support": "12 мес.",
        "updates": "12 мес.",
        "guarantee": "24 мес.",
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
    "b2c_young": "Молодёжь 18\u201335 лет",
    "b2c_adult": "Семейная аудитория 25\u201345 лет",
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
        ("Аналитика", "1\u20132 дня", "Исследование и ТЗ"),
        ("Дизайн", "2\u20133 дня", "UI/UX прототип"),
        ("Разработка", "3\u20134 дня", "Код + тесты"),
        ("Запуск", "1 день", "Деплой + QA"),
    ],
    "business": [
        ("Аналитика", "2\u20133 дня", "Исследование, ТЗ, CJM"),
        ("Дизайн", "3\u20135 дней", "UI/UX + прототип"),
        ("Frontend", "5\u20137 дней", "Интерфейс"),
        ("Backend", "3\u20134 дня", "Серверная часть"),
        ("Запуск", "1\u20132 дня", "Деплой + мониторинг"),
    ],
    "premium": [
        ("Стратегия", "3\u20135 дней", "Аналитика + CJM"),
        ("Дизайн", "5\u20137 дней", "2 концепции UI/UX"),
        ("Frontend", "7\u201310 дней", "Интерфейс + анимации"),
        ("Backend+AI", "5\u20137 дней", "API + ML + интеграции"),
        ("Запуск", "1\u20132 дня", "QA + деплой + SLA"),
    ],
}


def _fp(price: int) -> str:
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
        f"- Пакет: «{pkg['name']}» за {_fp(pkg['price'])} руб.\n\n"
        f"Разделы:\n"
        f"1. ВЫЗОВ (2-3 предложения): бизнес-проблема клиента, потерянная выручка.\n"
        f"2. РЕШЕНИЕ (3-4 предложения): как WEB4TG Studio решит задачу.\n"
        f"3. РЕЗУЛЬТАТ (2-3 предложения): измеримые результаты через 1-3 месяца с цифрами.\n"
        f"4. ПРЕИМУЩЕСТВО (2 предложения): почему WEB4TG Studio лучший выбор.\n\n"
        f"Правила:\n"
        f"- Русский язык, деловой стиль\n"
        f"- Без заголовков и нумерации — только текст абзацами\n"
        f"- Каждый раздел = один абзац, разделённый пустой строкой\n"
        f"- Объём: 500-700 символов суммарно\n"
        f"- Обращение на «вы»\n"
    )


def _t(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawString(x, y, txt)


def _tr(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawRightString(x, y, txt)


def _tc(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawCentredString(x, y, txt)


def _wrap(c, x, y, text, max_w, font=None, size=9.5, color=C_SLATE600, leading=14.5):
    f = font or FONT
    c.setFont(f, size)
    c.setFillColor(color)
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if c.stringWidth(test, f, size) > max_w:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * leading, line)
    return len(lines) * leading


def _text_height(c, text, max_w, font=None, size=9.5, leading=14.5):
    f = font or FONT
    words = text.split()
    lines = 1
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if c.stringWidth(test, f, size) > max_w:
            lines += 1
            cur = w
        else:
            cur = test
    return lines * leading


def _shadow(c, x, y, w, h, r=8):
    c.saveState()
    c.setFillColor(Color(0.06, 0.09, 0.16, alpha=0.06))
    c.roundRect(x + 2, y - 2, w, h, r, stroke=0, fill=1)
    c.restoreState()


def _card(c, x, y, w, h, fill=C_WHITE, r=8, shadow=True, border=True):
    if shadow:
        _shadow(c, x, y, w, h, r)
    c.saveState()
    c.setFillColor(fill)
    if border:
        c.setStrokeColor(C_SLATE200)
        c.setLineWidth(0.4)
        c.roundRect(x, y, w, h, r, stroke=1, fill=1)
    else:
        c.roundRect(x, y, w, h, r, stroke=0, fill=1)
    c.restoreState()


def _gradient_rect(c, x, y, w, h, c1, c2, r=0):
    c.saveState()
    if r > 0:
        p = c.beginPath()
        p.roundRect(x, y, w, h, r)
        c.clipPath(p, stroke=0)
    c.linearGradient(x, y, x, y + h, [c1, c2])
    c.restoreState()


def _accent_line(c, x, y, w, color=C_INDIGO, thickness=2.5):
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(thickness)
    c.setLineCap(1)
    c.line(x, y, x + w, y)
    c.restoreState()


def _page_footer(c, page_num):
    c.saveState()
    c.setStrokeColor(C_SLATE200)
    c.setLineWidth(0.3)
    c.line(LM, 22, W - RM, 22)
    c.restoreState()
    _tc(c, W / 2, 10, f"WEB4TG Studio  \u00b7  \u00a9 {datetime.now().year}", FONT, 6.5, C_SLATE400)
    _tr(c, W - RM, 10, str(page_num), FONT, 6.5, C_SLATE400)


def _new_page(c, page_num):
    c.showPage()
    return H - 36


def _draw_cover(c, project_type, pkg_name, timeline, kp_num, date_str, client_name):
    _gradient_rect(c, 0, 0, W, H, C_DARK, C_NAVY)

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.015))
    c.circle(W - 60, H - 80, 200, stroke=0, fill=1)
    c.circle(40, 120, 120, stroke=0, fill=1)
    c.restoreState()

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.02))
    c.rect(LM, H - 12 * mm, 60, 3, stroke=0, fill=1)
    c.restoreState()

    _t(c, LM, H - 18 * mm, "WEB4TG", FONTB, 13, C_WHITE)
    _t(c, LM + c.stringWidth("WEB4TG", FONTB, 13) + 4, H - 18 * mm, "STUDIO", FONT, 13, C_SLATE400)

    _tr(c, W - RM, H - 18 * mm, "web4tg.com", FONT, 9, C_SLATE500)

    y_title = H * 0.58
    _accent_line(c, LM, y_title + 20, 50, C_INDIGO_LIGHT, 3)

    _t(c, LM, y_title - 5, "КОММЕРЧЕСКОЕ", FONTB, 36, C_WHITE)
    _t(c, LM, y_title - 48, "ПРЕДЛОЖЕНИЕ", FONTB, 36, C_WHITE)

    _t(c, LM, y_title - 80, project_type, FONT, 14, C_INDIGO_LIGHT)

    c.saveState()
    c.setStrokeColor(Color(1, 1, 1, alpha=0.08))
    c.setLineWidth(0.5)
    c.line(LM, y_title - 95, LM + CW, y_title - 95)
    c.restoreState()

    meta_y = y_title - 120
    _t(c, LM, meta_y, f"Пакет «{pkg_name}»", FONT, 11, C_SLATE300)
    _tc(c, W / 2, meta_y, f"\u00b7   {timeline}   \u00b7", FONT, 11, C_SLATE400)
    _tr(c, W - RM, meta_y, f"№ {kp_num:05d}", FONT, 11, C_SLATE400)

    if client_name:
        _t(c, LM, meta_y - 30, "Подготовлено для", FONT, 9, C_SLATE500)
        _t(c, LM, meta_y - 48, client_name, FONTB, 16, C_WHITE)

    _t(c, LM, 40, date_str, FONT, 9, C_SLATE500)
    _tr(c, W - RM, 40, "t.me/web4_tg", FONT, 9, C_SLATE500)


def _draw_stats_bar(c, y):
    stats = [
        ("50+", "реализованных\nпроектов"),
        ("3 года", "на рынке\nTelegram Mini Apps"),
        ("98%", "клиентов\nрекомендуют нас"),
        ("24/7", "техническая\nподдержка"),
    ]
    card_h = 22 * mm
    _card(c, LM, y - card_h, CW, card_h, C_SLATE50, r=10, shadow=True, border=False)

    n = len(stats)
    col_w = CW / n
    for i, (val, label) in enumerate(stats):
        cx = LM + col_w * i + col_w / 2
        _tc(c, cx, y - card_h + 48, val, FONTB, 18, C_INDIGO)

        label_lines = label.split("\n")
        for j, line in enumerate(label_lines):
            _tc(c, cx, y - card_h + 32 - j * 11, line, FONT, 7.5, C_SLATE500)

        if i < n - 1:
            sx = LM + col_w * (i + 1)
            c.saveState()
            c.setStrokeColor(C_SLATE200)
            c.setLineWidth(0.3)
            c.line(sx, y - card_h + 14, sx, y - 10)
            c.restoreState()

    return y - card_h - 10


def _draw_section_title(c, y, label, title):
    _accent_line(c, LM, y, 40, C_INDIGO, 2.5)
    _t(c, LM, y - 16, label, FONTB, 8, C_INDIGO)
    _t(c, LM, y - 34, title, FONTB, 16, C_SLATE900)
    return y - 50


def _draw_ai_section(c, y, ai_text):
    blocks = [
        ("ВЫЗОВ", C_ROSE, C_ROSE_PALE),
        ("РЕШЕНИЕ", C_INDIGO, C_INDIGO_PALE),
        ("РЕЗУЛЬТАТ", C_EMERALD, C_EMERALD_PALE),
        ("ПРЕИМУЩЕСТВО", C_AMBER, C_AMBER_PALE),
    ]
    paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]

    for i, para in enumerate(paragraphs[:4]):
        if y < BOTTOM + 40:
            c.showPage()
            y = H - 36

        label, accent, bg = blocks[i] if i < len(blocks) else ("", C_SLATE500, C_SLATE50)

        c.setFont(FONT, 9.5)
        th = _text_height(c, para, CW - 36, FONT, 9.5, 14.5)
        card_h = th + 32

        _card(c, LM, y - card_h, CW, card_h, bg, r=10, shadow=False, border=False)

        c.saveState()
        c.setFillColor(accent)
        c.roundRect(LM, y - card_h, 4, card_h, 2, stroke=0, fill=1)
        c.restoreState()

        pill_w = c.stringWidth(label, FONTB, 7) + 16
        c.saveState()
        c.setFillColor(accent)
        c.roundRect(LM + 16, y - 18, pill_w, 14, 3, stroke=0, fill=1)
        c.restoreState()
        _tc(c, LM + 16 + pill_w / 2, y - 15, label, FONTB, 7, C_WHITE)

        _wrap(c, LM + 16, y - 30, para, CW - 36, FONT, 9.5, C_SLATE700, 14.5)

        y -= card_h + 6

    return y


def _draw_features_grid(c, y, features, not_included, pkg_name, pkg_subtitle):
    col_gap = 10
    col_w = (CW - col_gap) / 2

    for idx in range(0, len(features), 2):
        if y < BOTTOM + 40:
            c.showPage()
            y = H - 36

        row_h = 54
        for j in range(2):
            if idx + j >= len(features):
                break
            name, desc = features[idx + j]
            fx = LM + j * (col_w + col_gap)

            _card(c, fx, y - row_h, col_w, row_h, C_WHITE, r=8, shadow=True, border=True)

            c.saveState()
            c.setFillColor(C_EMERALD)
            c.circle(fx + 18, y - 16, 8, stroke=0, fill=1)
            c.restoreState()
            _tc(c, fx + 18, y - 20, "\u2713", FONTB, 9, C_WHITE)

            _t(c, fx + 32, y - 19, name, FONTB, 9.5, C_SLATE800)
            _t(c, fx + 14, y - 38, desc, FONT, 8, C_SLATE500)

        y -= row_h + 6

    if not_included:
        if y < BOTTOM + 30:
            c.showPage()
            y = H - 36
        for idx in range(0, len(not_included), 2):
            row_h = 36
            for j in range(2):
                if idx + j >= len(not_included):
                    break
                name = not_included[idx + j]
                fx = LM + j * (col_w + col_gap)

                c.saveState()
                c.setStrokeColor(C_SLATE200)
                c.setLineWidth(0.4)
                c.setDash(3, 3)
                c.roundRect(fx, y - row_h, col_w, row_h, 8, stroke=1, fill=0)
                c.restoreState()

                c.saveState()
                c.setStrokeColor(C_SLATE300)
                c.setLineWidth(0.5)
                c.circle(fx + 18, y - row_h / 2, 8, stroke=1, fill=0)
                c.restoreState()

                _t(c, fx + 32, y - row_h / 2 - 4, name, FONT, 9, C_SLATE400)

            y -= row_h + 6

    return y


def _draw_guarantees(c, y, guarantee, support, updates):
    if y < BOTTOM + 30:
        c.showPage()
        y = H - 36

    items = [
        ("\u2605", "Гарантия", guarantee, C_AMBER),
        ("\u2605", "Поддержка", f"бесплатно {support}", C_EMERALD),
        ("\u2605", "Обновления", f"бесплатно {updates}", C_INDIGO),
    ]
    col_gap = 10
    col_w = (CW - col_gap * 2) / 3
    row_h = 60

    for i, (icon, title, val, color) in enumerate(items):
        fx = LM + i * (col_w + col_gap)
        _card(c, fx, y - row_h, col_w, row_h, C_WHITE, r=8, shadow=True, border=True)

        c.saveState()
        c.setFillColor(color)
        c.roundRect(fx + 12, y - 22, 22, 16, 4, stroke=0, fill=1)
        c.restoreState()
        _tc(c, fx + 23, y - 18, icon, FONT, 9, C_WHITE)

        _t(c, fx + 40, y - 18, title, FONTB, 9, C_SLATE800)
        _t(c, fx + 14, y - 42, val, FONT, 8.5, C_SLATE600)

    return y - row_h - 10


def _draw_price_block(c, y, price, discount_pct, pkg_name):
    if discount_pct > 0:
        card_h = 48 * mm
    else:
        card_h = 38 * mm

    if y - card_h < BOTTOM:
        c.showPage()
        y = H - 36

    _gradient_rect(c, LM, y - card_h, CW, card_h, C_DARK, C_NAVY, r=12)

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.02))
    c.circle(W - RM - 20, y - card_h + 30, 80, stroke=0, fill=1)
    c.restoreState()

    top = y - 14

    _t(c, LM + 24, top, f"Пакет «{pkg_name}»", FONT, 10, C_SLATE400)

    if discount_pct > 0:
        final = int(price * (100 - discount_pct) / 100)
        savings = price - final

        _t(c, LM + 24, top - 24, f"Стандартная цена: {_fp(price)} \u20bd", FONT, 10, C_SLATE500)

        c.saveState()
        c.setStrokeColor(Color(1, 1, 1, alpha=0.15))
        c.setLineWidth(1)
        line_w = c.stringWidth(f"{_fp(price)} \u20bd", FONT, 10)
        start_x = LM + 24 + c.stringWidth("Стандартная цена: ", FONT, 10)
        c.line(start_x, top - 20, start_x + line_w, top - 20)
        c.restoreState()

        pill_w = 100
        c.saveState()
        c.setFillColor(C_EMERALD)
        c.roundRect(LM + 24, top - 52, pill_w, 20, 5, stroke=0, fill=1)
        c.restoreState()
        _tc(c, LM + 24 + pill_w / 2, top - 46, f"VIP скидка \u2212{discount_pct}%", FONTB, 9, C_WHITE)

        _t(c, LM + 24 + pill_w + 12, top - 46, f"Экономия: {_fp(savings)} \u20bd", FONT, 9, C_EMERALD)

        _t(c, LM + 24, top - 82, f"{_fp(final)}", FONTB, 38, C_WHITE)
        _t(c, LM + 24 + c.stringWidth(f"{_fp(final)}", FONTB, 38) + 6, top - 82, "\u20bd", FONTB, 28, C_SLATE400)

        _t(c, LM + 24, top - card_h + 30, "Скидка по вашему VIP-статусу применена автоматически", FONT, 7.5, C_SLATE500)
    else:
        _t(c, LM + 24, top - 40, f"{_fp(price)}", FONTB, 42, C_WHITE)
        _t(c, LM + 24 + c.stringWidth(f"{_fp(price)}", FONTB, 42) + 6, top - 40, "\u20bd", FONTB, 30, C_SLATE400)

        _t(c, LM + 24, top - 62, "Фиксированная стоимость  \u00b7  Без скрытых платежей", FONT, 9, C_SLATE500)

    return y - card_h - 10


def _draw_timeline(c, y, phases, total_timeline):
    n = len(phases)

    needed = 90
    if y - needed < BOTTOM:
        c.showPage()
        y = H - 36

    bar_y = y - 24
    bar_h = 6

    c.saveState()
    c.setFillColor(C_SLATE100)
    c.roundRect(LM, bar_y - bar_h / 2, CW, bar_h, 3, stroke=0, fill=1)
    c.restoreState()

    filled_w = CW * 0.85
    _gradient_rect(c, LM, bar_y - bar_h / 2, filled_w, bar_h, C_INDIGO, C_INDIGO_LIGHT, r=3)

    col_w = CW / n
    for i, phase_data in enumerate(phases):
        name = phase_data[0]
        duration = phase_data[1]
        detail = phase_data[2] if len(phase_data) > 2 else ""

        cx = LM + col_w * i + col_w / 2
        dot_r = 10

        is_last = i == n - 1
        color = C_EMERALD if is_last else C_INDIGO

        c.saveState()
        c.setFillColor(C_WHITE)
        c.circle(cx, bar_y, dot_r + 3, stroke=0, fill=1)
        c.restoreState()

        c.saveState()
        c.setFillColor(color)
        c.circle(cx, bar_y, dot_r, stroke=0, fill=1)
        c.restoreState()
        _tc(c, cx, bar_y - 3.5, str(i + 1), FONTB, 9, C_WHITE)

        _tc(c, cx, bar_y - dot_r - 16, name, FONTB, 8, C_SLATE800)
        _tc(c, cx, bar_y - dot_r - 28, duration, FONT, 7.5, color)
        if detail:
            _tc(c, cx, bar_y - dot_r - 40, detail, FONT, 6.5, C_SLATE400)

    y = bar_y - dot_r - 52

    pill_w = c.stringWidth(f"  Итого: {total_timeline}  ", FONTB, 9) + 24
    c.saveState()
    c.setFillColor(C_INDIGO_PALE)
    c.roundRect(W / 2 - pill_w / 2, y - 8, pill_w, 20, 5, stroke=0, fill=1)
    c.restoreState()
    _tc(c, W / 2, y - 2, f"Итого: {total_timeline}", FONTB, 9, C_INDIGO)

    return y - 18


def _draw_payment(c, y, price, discount_pct):
    final = int(price * (100 - discount_pct) / 100) if discount_pct else price
    prepay = int(final * 0.35)
    remainder = final - prepay

    col_gap = 12
    col_w = (CW - col_gap) / 2
    card_h = 70

    if y - card_h < BOTTOM:
        c.showPage()
        y = H - 36

    _card(c, LM, y - card_h, col_w, card_h, C_WHITE, r=10, shadow=True, border=True)
    c.saveState()
    c.setFillColor(C_INDIGO)
    c.roundRect(LM + 14, y - 22, 8, 8, 2, stroke=0, fill=1)
    c.restoreState()
    _t(c, LM + 28, y - 22, "Этап 1", FONTB, 8, C_INDIGO)
    _t(c, LM + 14, y - 40, f"{_fp(prepay)} \u20bd", FONTB, 18, C_SLATE900)
    _t(c, LM + 14, y - 56, "35%  \u00b7  Предоплата", FONT, 8, C_SLATE500)

    x2 = LM + col_w + col_gap
    _card(c, x2, y - card_h, col_w, card_h, C_WHITE, r=10, shadow=True, border=True)
    c.saveState()
    c.setFillColor(C_EMERALD)
    c.roundRect(x2 + 14, y - 22, 8, 8, 2, stroke=0, fill=1)
    c.restoreState()
    _t(c, x2 + 28, y - 22, "Этап 2", FONTB, 8, C_EMERALD)
    _t(c, x2 + 14, y - 40, f"{_fp(remainder)} \u20bd", FONTB, 18, C_SLATE900)
    _t(c, x2 + 14, y - 56, "65%  \u00b7  После приёмки", FONT, 8, C_SLATE500)

    y -= card_h + 8
    _tc(c, W / 2, y, "Банковский перевод  \u00b7  Карта  \u00b7  СБП  \u00b7  Telegram Stars", FONT, 7.5, C_SLATE400)
    return y - 14


def _draw_steps(c, y):
    steps = [
        ("Согласование", "Утверждаем ТЗ и подписываем договор"),
        ("Предоплата", "Оплата 35% — старт работы"),
        ("Демо", "Промежуточная демонстрация прогресса"),
        ("Сдача", "Финальная приёмка и оплата остатка"),
        ("Запуск", "Деплой + поддержка"),
    ]

    if y - len(steps) * 26 < BOTTOM:
        c.showPage()
        y = H - 36

    for i, (title, desc) in enumerate(steps):
        is_last = i == len(steps) - 1
        color = C_EMERALD if is_last else C_INDIGO

        c.saveState()
        c.setFillColor(color)
        c.circle(LM + 10, y - 4, 10, stroke=0, fill=1)
        c.restoreState()
        _tc(c, LM + 10, y - 8, str(i + 1), FONTB, 8, C_WHITE)

        _t(c, LM + 26, y - 5, title, FONTB, 9.5, C_SLATE800)

        desc_x = LM + 120
        _t(c, desc_x, y - 5, desc, FONT, 8.5, C_SLATE500)

        if not is_last:
            c.saveState()
            c.setStrokeColor(C_SLATE200)
            c.setLineWidth(0.6)
            c.setDash(2, 3)
            c.line(LM + 10, y - 14, LM + 10, y - 24)
            c.restoreState()

        y -= 28

    return y


def _draw_cta(c, y):
    if y - 32 * mm < BOTTOM - 10:
        c.showPage()
        y = H - 36

    cta_h = 32 * mm
    _gradient_rect(c, LM, y - cta_h, CW, cta_h, C_INDIGO, HexColor("#7c3aed"), r=12)

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.04))
    c.circle(W - RM - 20, y - cta_h + 20, 60, stroke=0, fill=1)
    c.restoreState()

    mid = y - cta_h / 2
    _t(c, LM + 24, mid + 14, "Готовы обсудить проект?", FONTB, 16, C_WHITE)
    _t(c, LM + 24, mid - 6, "Ответим в течение 30 минут в рабочее время", FONT, 9, HexColor("#c7d2fe"))

    _t(c, LM + 24, mid - 30, "Telegram: @web4_tg", FONTB, 10, C_WHITE)
    _tc(c, W / 2, mid - 30, "\u00b7", FONT, 10, HexColor("#a5b4fc"))
    _tr(c, W - RM - 24, mid - 30, "web4tg.com", FONTB, 10, C_WHITE)

    return y - cta_h - 8


def _determine_package(brief_answers: Dict) -> str:
    return PACKAGE_MAPPING.get(brief_answers.get("budget_timeline", "balanced"), "business")


def build_kp_pdf(
    brief_answers: Dict,
    client_name: str = "",
    ai_text: str = "",
    discount_pct: int = 0,
    kp_number: Optional[int] = None,
) -> bytes:
    pkg_key = _determine_package(brief_answers)
    pkg = PACKAGE_DATA[pkg_key]
    project_type = PROJECT_TYPE_NAMES.get(brief_answers.get("project_type", ""), "Проект")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Коммерческое предложение — WEB4TG Studio")
    c.setAuthor("WEB4TG Studio")

    kp_num = kp_number or int(time.time()) % 100000
    date_str = datetime.now().strftime("%d.%m.%Y")
    page = 1

    _draw_cover(c, project_type, pkg["name"], pkg["timeline"], kp_num, date_str, client_name)
    c.showPage()
    page += 1

    y = H - 24

    y = _draw_stats_bar(c, y)
    y -= 4
    y = _draw_section_title(c, y, "01  \u00b7  О ПРОЕКТЕ", "Анализ и решение")

    if ai_text:
        y = _draw_ai_section(c, y, ai_text)
    else:
        h = _wrap(c, LM, y, (
            f"Разработка Telegram Mini App типа «{project_type}» "
            f"с полным комплексом функций для успешного запуска вашего бизнеса."
        ), CW, FONT, 10, C_SLATE600, 15)
        y -= h + 10

    if y < BOTTOM + 120:
        c.showPage()
        page += 1
        y = H - 24

    y -= 6
    y = _draw_section_title(c, y, "02  \u00b7  РЕШЕНИЕ", f"Пакет «{pkg['name']}» — {pkg['subtitle']}")
    y = _draw_features_grid(c, y, pkg["features"], pkg["not_included"], pkg["name"], pkg["subtitle"])
    y = _draw_guarantees(c, y, pkg["guarantee"], pkg["support"], pkg["updates"])

    _page_footer(c, page)

    if y < BOTTOM + 200:
        c.showPage()
        page += 1
        y = H - 24

    y -= 4
    y = _draw_section_title(c, y, "03  \u00b7  ИНВЕСТИЦИИ", "Стоимость проекта")
    y = _draw_price_block(c, y, pkg["price"], discount_pct, pkg["name"])

    y -= 4
    y = _draw_section_title(c, y, "04  \u00b7  СРОКИ", "Этапы реализации")
    phases = TIMELINE_PHASES.get(pkg_key, TIMELINE_PHASES["business"])
    y = _draw_timeline(c, y, phases, pkg["timeline"])

    steps_needed = 50 + 28 * 5 + 32 * mm + 40
    payment_needed = 70 + 60 + 50

    if y < BOTTOM + payment_needed + steps_needed:
        _page_footer(c, page)
        c.showPage()
        page += 1
        y = H - 24

    y -= 4
    y = _draw_section_title(c, y, "05  \u00b7  ОПЛАТА", "Порядок расчётов")
    y = _draw_payment(c, y, pkg["price"], discount_pct)

    if y < BOTTOM + steps_needed:
        _page_footer(c, page)
        c.showPage()
        page += 1
        y = H - 24

    y -= 4
    y = _draw_section_title(c, y, "06  \u00b7  СТАРТ", "Следующие шаги")
    y = _draw_steps(c, y)

    _draw_cta(c, y)

    _page_footer(c, page)

    c.save()
    buf.seek(0)
    return buf.read()


def get_kp_prompt_for_brief(brief_answers: Dict, client_name: str = "") -> str:
    pkg_key = _determine_package(brief_answers)
    return _get_ai_kp_prompt(brief_answers, pkg_key, client_name or "Клиент")


async def generate_and_send_kp(
    update,
    context,
    brief_answers: Dict,
    client_name: str = "",
    ai_text: str = "",
    discount_pct: int = 0,
):
    from telegram import InputFile
    chat_id = update.effective_chat.id
    try:
        if ai_text is None:
            ai_text = ""
        if not isinstance(ai_text, str):
            ai_text = str(ai_text)
        if not isinstance(client_name, str):
            client_name = str(client_name) if client_name else ""

        logger.info(
            f"Building KP PDF: client={client_name!r}, ai_text_len={len(ai_text)}, "
            f"discount={discount_pct}%, brief_keys={list(brief_answers.keys())}, "
            f"font={FONT}, font_dirs_checked={_FONT_DIRS}"
        )

        pdf_bytes = build_kp_pdf(
            brief_answers=brief_answers,
            client_name=client_name,
            ai_text=ai_text,
            discount_pct=discount_pct,
        )

        logger.info(f"KP PDF built: {len(pdf_bytes)} bytes")

        project_type = brief_answers.get("project_type", "project")
        safe_name = project_type.replace(" ", "_").replace("/", "_")
        filename = f"KP_WEB4TG_{safe_name}.pdf"

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
        logger.error(
            f"Failed to generate/send KP PDF: {type(e).__name__}: {e} | "
            f"client={client_name!r}, ai_text_len={len(ai_text) if ai_text else 0}, "
            f"discount={discount_pct}, brief={brief_answers}, font={FONT}",
            exc_info=True
        )

        try:
            logger.info("Retrying KP PDF without AI text (fallback)")
            fallback_pdf = build_kp_pdf(
                brief_answers=brief_answers,
                client_name=client_name if client_name else "",
                ai_text="",
                discount_pct=discount_pct,
            )
            project_type = brief_answers.get("project_type", "project")
            safe_name = project_type.replace(" ", "_").replace("/", "_")
            filename = f"KP_WEB4TG_{safe_name}.pdf"
            await context.bot.send_document(
                chat_id=chat_id,
                document=InputFile(io.BytesIO(fallback_pdf), filename=filename),
                caption=(
                    "\ud83d\udcc4 <b>\u0412\u0430\u0448\u0435 \u043a\u043e\u043c\u043c\u0435\u0440\u0447\u0435\u0441\u043a\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435</b>\n\n"
                    "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0441\u043e\u0434\u0435\u0440\u0436\u0438\u0442 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u0430, \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u0438 \u0441\u0440\u043e\u043a\u0438."
                ),
                parse_mode="HTML",
            )
            logger.info(f"Fallback KP PDF sent to user {update.effective_user.id}")
            return True
        except Exception as fallback_err:
            logger.error(f"Fallback KP PDF also failed: {type(fallback_err).__name__}: {fallback_err}", exc_info=True)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "\u26a0\ufe0f \u041f\u0440\u043e\u0438\u0437\u043e\u0448\u043b\u0430 \u043e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438 PDF.\n\n"
                    "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0435\u0449\u0451 \u0440\u0430\u0437 \u0438\u043b\u0438 \u043d\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u043d\u0430\u043c @web4_tg \u2014 \u043c\u044b \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u043c \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0432\u0440\u0443\u0447\u043d\u0443\u044e."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("\ud83d\udd04 \u041f\u043e\u043f\u0440\u043e\u0431\u043e\u0432\u0430\u0442\u044c \u0435\u0449\u0451 \u0440\u0430\u0437", callback_data="generate_kp")],
                    [InlineKeyboardButton("\ud83d\udc68\u200d\ud83d\udcbc \u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440\u0443", callback_data="brief_send_manager")],
                    [InlineKeyboardButton("\u25c0\ufe0f \u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e", callback_data="menu_back")],
                ]),
            )
        except Exception:
            pass
        return False
