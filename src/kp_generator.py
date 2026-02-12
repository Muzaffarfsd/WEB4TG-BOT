"""PDF Commercial Proposal (KP) Generator — Ultra Premium 2026.

Uses ReportLab for world-class PDF design with gradients, shadows,
rounded cards, modern typography, and Gemini AI personalization.
"""

import io
import os
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List, Tuple

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
W, H = A4

try:
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuB", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
    FONT = "DejaVu"
    FONTB = "DejaVuB"
except Exception:
    FONT = "Helvetica"
    FONTB = "Helvetica-Bold"
    logger.warning("DejaVu fonts not available")

C_DARK = HexColor("#0f172a")
C_PRIMARY = HexColor("#3b82f6")
C_PRIMARY_DEEP = HexColor("#1e40af")
C_ACCENT = HexColor("#6366f1")
C_SUCCESS = HexColor("#10b981")
C_SUCCESS_LIGHT = HexColor("#d1fae5")
C_WARN = HexColor("#f59e0b")
C_RED = HexColor("#ef4444")
C_RED_LIGHT = HexColor("#fef2f2")
C_SLATE50 = HexColor("#f8fafc")
C_SLATE100 = HexColor("#f1f5f9")
C_SLATE200 = HexColor("#e2e8f0")
C_SLATE300 = HexColor("#cbd5e1")
C_SLATE400 = HexColor("#94a3b8")
C_SLATE500 = HexColor("#64748b")
C_SLATE700 = HexColor("#334155")
C_SLATE800 = HexColor("#1e293b")
C_SLATE900 = HexColor("#0f172a")
C_WHITE = white
C_INDIGO50 = HexColor("#eef2ff")
C_INDIGO100 = HexColor("#e0e7ff")
C_BLUE50 = HexColor("#eff6ff")

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
        "subtitle": "Быстрый запуск вашего бизнеса в Telegram",
        "features": [
            ("Каталог товаров/услуг", "Витрина с категориями и фильтрами"),
            ("Корзина покупок", "Полноценная корзина с подсчётом"),
            ("Онлайн-оплата", "Telegram Stars + банковские карты"),
            ("Авторизация Telegram", "Вход в один клик"),
        ],
        "not_included": ["Push-уведомления", "Программа лояльности", "AI чат-бот", "Аналитика"],
        "support": "30 дней",
        "updates": "3 мес.",
        "guarantee": "6 мес.",
    },
    "business": {
        "name": "Бизнес",
        "price": 250000,
        "timeline": "14\u201321 день",
        "subtitle": "Полноценное приложение для роста бизнеса",
        "features": [
            ("Каталог товаров/услуг", "Витрина с категориями, фильтрами, поиском"),
            ("Корзина и оформление", "Checkout с историей заказов"),
            ("Мультиплатёжная система", "Telegram Stars, карты, СБП"),
            ("Авторизация Telegram", "Вход в один клик + профиль"),
            ("Push-уведомления", "Статусы заказов, акции"),
            ("Программа лояльности", "Бонусы, кэшбек, скидки"),
            ("Аналитика", "Метрики продаж и конверсии"),
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
        "subtitle": "Максимальные возможности без компромиссов",
        "features": [
            ("Каталог товаров/услуг", "Продвинутая витрина с рекомендациями"),
            ("Корзина и оформление", "Checkout с историей и повторами"),
            ("Полная платёжная система", "Все способы + рассрочка"),
            ("Авторизация Telegram", "Вход + профиль + предпочтения"),
            ("Push-уведомления", "Умные триггерные уведомления"),
            ("Программа лояльности", "Многоуровневая с геймификацией"),
            ("Бизнес-аналитика", "Дашборд с прогнозами и когортами"),
            ("Премиум UI/UX", "2 дизайн-концепции на выбор"),
            ("AI чат-бот", "Умный помощник 24/7"),
            ("CRM-система", "Управление клиентами и заказами"),
            ("Персональный менеджер", "Выделенный менеджер проекта"),
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
        ("Аналитика", "1\u20132 дня"),
        ("Дизайн", "2\u20133 дня"),
        ("Разработка", "3\u20134 дня"),
        ("Запуск", "1 день"),
    ],
    "business": [
        ("Аналитика", "2\u20133 дня"),
        ("Дизайн", "3\u20135 дней"),
        ("Frontend", "5\u20137 дней"),
        ("Backend", "3\u20134 дня"),
        ("Запуск", "1\u20132 дня"),
    ],
    "premium": [
        ("Стратегия", "3\u20135 дней"),
        ("Дизайн", "5\u20137 дней"),
        ("Frontend", "7\u201310 дней"),
        ("Backend+AI", "5\u20137 дней"),
        ("Запуск", "1\u20132 дня"),
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
        f"1. ВЫЗОВ (2-3 предложения): бизнес-проблема клиента.\n"
        f"2. РЕШЕНИЕ (3-4 предложения): как WEB4TG Studio решит задачу.\n"
        f"3. РЕЗУЛЬТАТ (2-3 предложения): измеримые результаты через 1-3 месяца.\n"
        f"4. ПРЕИМУЩЕСТВО (2 предложения): почему WEB4TG Studio.\n\n"
        f"Правила:\n"
        f"- Русский язык, деловой стиль\n"
        f"- Без заголовков и нумерации — только текст\n"
        f"- Каждый раздел = один абзац через пустую строку\n"
        f"- Объём: 500-700 символов\n"
        f"- Обращение на «вы»\n"
    )


def _shadow(c, x, y, w, h, r=6):
    c.saveState()
    c.setFillColor(Color(0, 0, 0, alpha=0.04))
    c.roundRect(x + 1.5, y - 1.5, w, h, r, stroke=0, fill=1)
    c.restoreState()


def _grad_rect(c, x, y, w, h, c1, c2, r=0):
    c.saveState()
    c.clipPath(c.beginPath().roundRect(x, y, w, h, r) if r else c.beginPath().rect(x, y, w, h))
    c.linearGradient(x, y, x + w, y + h, [c1, c2])
    c.restoreState()


def _card(c, x, y, w, h, fill=C_WHITE, r=6, shadow=True):
    if shadow:
        _shadow(c, x, y, w, h, r)
    c.saveState()
    c.setFillColor(fill)
    c.setStrokeColor(C_SLATE200)
    c.setLineWidth(0.3)
    c.roundRect(x, y, w, h, r, stroke=1, fill=1)
    c.restoreState()


def _text(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawString(x, y, txt)


def _text_r(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawRightString(x, y, txt)


def _text_c(c, x, y, txt, font=None, size=10, color=C_SLATE700):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    c.drawCentredString(x, y, txt)


def _wrap_text(c, x, y, text, max_w, font=None, size=9.5, color=C_SLATE700, leading=14):
    c.setFont(font or FONT, size)
    c.setFillColor(color)
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if c.stringWidth(test, font or FONT, size) > max_w:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * leading, line)
    return len(lines) * leading


LM = 20 * mm
RM = 20 * mm
CW = W - LM - RM


def _draw_header(c):
    c.saveState()
    c.setFillColor(C_PRIMARY)
    c.rect(0, H - 3, W, 3, stroke=0, fill=1)
    c.restoreState()

    _text(c, LM, H - 18, "WEB4TG STUDIO", FONTB, 11, C_PRIMARY_DEEP)
    _text_r(c, W - RM, H - 18, "web4tg.com  |  t.me/web4_tg", FONT, 7, C_SLATE400)


def _draw_footer(c, page_num, total=""):
    c.saveState()
    c.setStrokeColor(C_SLATE200)
    c.setLineWidth(0.3)
    c.line(LM, 18, W - RM, 18)
    c.restoreState()
    _text_c(c, W / 2, 8, f"WEB4TG Studio  \u00b7  Коммерческое предложение  \u00b7  {page_num}", FONT, 6, C_SLATE400)


def _draw_hero(c, y, project_type, pkg_name, timeline, kp_num, date_str, client_name):
    hero_h = 62 * mm
    hero_y = y - hero_h

    c.saveState()
    p = c.beginPath()
    p.roundRect(LM, hero_y, CW, hero_h, 8)
    c.clipPath(p, stroke=0)
    c.linearGradient(LM, hero_y, LM, hero_y + hero_h, [HexColor("#1e3a5f"), C_DARK])
    c.restoreState()

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.03))
    c.circle(W - RM - 30, hero_y + hero_h - 10, 80, stroke=0, fill=1)
    c.circle(LM + 20, hero_y + 10, 40, stroke=0, fill=1)
    c.restoreState()

    top = hero_y + hero_h
    _text(c, LM + 14, top - 16, f"№ КП-{kp_num:05d}  |  {date_str}", FONT, 7.5, C_SLATE400)

    _text(c, LM + 14, top - 36, "КОММЕРЧЕСКОЕ", FONTB, 22, C_WHITE)
    _text(c, LM + 14, top - 55, "ПРЕДЛОЖЕНИЕ", FONTB, 22, C_WHITE)

    _text(c, LM + 14, top - 72, f"{project_type}  \u00b7  Пакет «{pkg_name}»  \u00b7  {timeline}", FONT, 8.5, C_SLATE300)

    if client_name:
        badge_y = hero_y + 10
        bw = c.stringWidth(f"  Для: {client_name}  ", FONT, 8) + 16
        c.saveState()
        c.setFillColor(Color(1, 1, 1, alpha=0.1))
        c.roundRect(LM + 14, badge_y, bw, 18, 4, stroke=0, fill=1)
        c.restoreState()
        _text(c, LM + 22, badge_y + 5, f"Для: {client_name}", FONT, 8.5, C_WHITE)

    return hero_y - 6


def _draw_stats(c, y):
    stats = [("50+", "проектов"), ("3 года", "на рынке"), ("98%", "довольных"), ("24/7", "поддержка")]
    card_h = 18 * mm
    _card(c, LM, y - card_h, CW, card_h, C_SLATE50, 6, shadow=True)

    n = len(stats)
    col = CW / n
    for i, (val, label) in enumerate(stats):
        cx = LM + col * i + col / 2
        _text_c(c, cx, y - card_h + 30, val, FONTB, 14, C_PRIMARY_DEEP)
        _text_c(c, cx, y - card_h + 16, label, FONT, 7.5, C_SLATE500)

        if i < n - 1:
            sx = LM + col * (i + 1)
            c.saveState()
            c.setStrokeColor(C_SLATE200)
            c.setLineWidth(0.3)
            c.line(sx, y - card_h + 8, sx, y - 8)
            c.restoreState()

    return y - card_h - 8


def _draw_section_header(c, y, num, title):
    pill_w = 28
    pill_h = 16
    c.saveState()
    c.setFillColor(C_PRIMARY)
    c.roundRect(LM, y - pill_h + 3, pill_w, pill_h, 4, stroke=0, fill=1)
    c.restoreState()
    _text_c(c, LM + pill_w / 2, y - pill_h + 7, num, FONTB, 8, C_WHITE)
    _text(c, LM + pill_w + 6, y - pill_h + 6, title, FONTB, 11, C_SLATE800)
    return y - pill_h - 8


def _draw_ai_blocks(c, y, ai_text):
    labels_colors = [
        ("ВЫЗОВ", C_RED, C_RED_LIGHT),
        ("РЕШЕНИЕ", C_PRIMARY, C_BLUE50),
        ("РЕЗУЛЬТАТ", C_SUCCESS, C_SUCCESS_LIGHT),
        ("ПРЕИМУЩЕСТВО", C_WARN, C_INDIGO50),
    ]
    paragraphs = [p.strip() for p in ai_text.split("\n") if p.strip()]

    for i, para in enumerate(paragraphs[:4]):
        if y < 60:
            c.showPage()
            _draw_header(c)
            y = H - 35

        label, accent, bg = labels_colors[i] if i < len(labels_colors) else ("", C_SLATE500, C_SLATE50)

        c.setFont(FONT, 9)
        text_h = _estimate_text_height(c, para, CW - 28, 9, 13)
        card_h = text_h + 26

        _card(c, LM, y - card_h, CW, card_h, bg, 5, shadow=False)

        c.saveState()
        c.setFillColor(accent)
        c.roundRect(LM, y - card_h, 3, card_h, 1.5, stroke=0, fill=1)
        c.restoreState()

        _text(c, LM + 12, y - 14, label, FONTB, 7.5, accent)

        _wrap_text(c, LM + 12, y - 26, para, CW - 28, FONT, 9, C_SLATE700, 13)

        y -= card_h + 4

    return y


def _estimate_text_height(c, text, max_w, size, leading):
    words = text.split()
    lines = 1
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if c.stringWidth(test, FONT, size) > max_w:
            lines += 1
            current = word
        else:
            current = test
    return lines * leading


def _draw_features(c, y, features, not_included):
    for name, desc in features:
        if y < 50:
            c.showPage()
            _draw_header(c)
            y = H - 35

        row_h = 22
        _card(c, LM, y - row_h, CW, row_h, C_WHITE, 4, shadow=False)

        c.saveState()
        c.setFillColor(C_SUCCESS)
        c.roundRect(LM + 8, y - row_h + 5, 12, 12, 3, stroke=0, fill=1)
        c.restoreState()
        _text_c(c, LM + 14, y - row_h + 8, "\u2713", FONTB, 8, C_WHITE)

        _text(c, LM + 26, y - row_h + 7, name, FONTB, 9, C_SLATE800)
        _text_r(c, W - RM - 8, y - row_h + 7, desc, FONT, 7.5, C_SLATE500)

        y -= row_h + 2

    for name in not_included:
        if y < 50:
            c.showPage()
            _draw_header(c)
            y = H - 35

        row_h = 20
        c.saveState()
        c.setStrokeColor(C_SLATE200)
        c.setLineWidth(0.3)
        c.setDash(2, 2)
        c.roundRect(LM, y - row_h, CW, row_h, 4, stroke=1, fill=0)
        c.restoreState()

        c.saveState()
        c.setStrokeColor(C_SLATE300)
        c.setLineWidth(0.5)
        c.roundRect(LM + 8, y - row_h + 4, 12, 12, 3, stroke=1, fill=0)
        c.restoreState()

        _text(c, LM + 26, y - row_h + 6, name, FONT, 8.5, C_SLATE400)
        _text_r(c, W - RM - 8, y - row_h + 6, "в старших пакетах", FONT, 7, C_SLATE400)

        y -= row_h + 2

    return y


def _draw_guarantees(c, y, guarantee, support, updates):
    items = [
        ("\u2605  Гарантия", guarantee),
        ("\u2605  Поддержка", f"бесплатно {support}"),
        ("\u2605  Обновления", f"бесплатно {updates}"),
    ]
    card_h = 20 * mm
    _card(c, LM, y - card_h, CW, card_h, C_INDIGO50, 5, shadow=False)

    col = CW / 3
    for i, (title, val) in enumerate(items):
        cx = LM + col * i + 10
        _text(c, cx, y - card_h + 36, title, FONTB, 8, C_WARN)
        _text(c, cx, y - card_h + 22, val, FONT, 8, C_SLATE700)

        if i < 2:
            sx = LM + col * (i + 1)
            c.saveState()
            c.setStrokeColor(C_SLATE200)
            c.setLineWidth(0.3)
            c.line(sx, y - card_h + 12, sx, y - 8)
            c.restoreState()

    return y - card_h - 6


def _draw_price(c, y, price, discount_pct, pkg_name):
    card_h = 34 * mm if discount_pct else 28 * mm

    if y - card_h < 40:
        c.showPage()
        _draw_header(c)
        y = H - 35

    c.saveState()
    p = c.beginPath()
    p.roundRect(LM, y - card_h, CW, card_h, 8)
    c.clipPath(p, stroke=0)
    c.linearGradient(LM, y - card_h, W - RM, y, [C_DARK, HexColor("#1a2744")])
    c.restoreState()

    c.saveState()
    c.setFillColor(Color(1, 1, 1, alpha=0.03))
    c.circle(W - RM, y - card_h + 20, 60, stroke=0, fill=1)
    c.restoreState()

    top = y
    _text(c, LM + 16, top - 18, f"Пакет «{pkg_name}»", FONT, 8, C_SLATE400)

    if discount_pct > 0:
        final = int(price * (100 - discount_pct) / 100)
        savings = price - final

        _text(c, LM + 16, top - 36, f"Базовая цена:  {_fp(price)} руб.", FONT, 9, C_SLATE400)

        bw = 90
        c.saveState()
        c.setFillColor(C_SUCCESS)
        c.roundRect(LM + 16, top - 58, bw, 16, 4, stroke=0, fill=1)
        c.restoreState()
        _text_c(c, LM + 16 + bw / 2, top - 54, f"VIP скидка \u2212{discount_pct}%", FONTB, 8, C_WHITE)

        _text(c, LM + 16 + bw + 10, top - 54, f"\u2212{_fp(savings)} руб.", FONTB, 9, C_SUCCESS)

        _text(c, LM + 16, top - 80, f"{_fp(final)} руб.", FONTB, 26, C_WHITE)

        _text(c, LM + 16, top - card_h + 10, "Скидка по VIP-статусу применена автоматически", FONT, 7, C_SLATE400)
    else:
        _text(c, LM + 16, top - 48, f"{_fp(price)} руб.", FONTB, 28, C_WHITE)
        _text(c, LM + 16, top - 64, "Фиксированная стоимость  \u00b7  Без скрытых платежей", FONT, 8, C_SLATE400)

    return y - card_h - 6


def _draw_timeline(c, y, phases, total):
    n = len(phases)
    col = (CW - 20) / n
    dot_r = 12

    if y - 60 < 40:
        c.showPage()
        _draw_header(c)
        y = H - 35

    line_y = y - 20
    c.saveState()
    c.setStrokeColor(C_SLATE200)
    c.setLineWidth(1.5)
    c.line(LM + col / 2, line_y, LM + col * (n - 1) + col / 2, line_y)
    c.restoreState()

    for i, (name, duration) in enumerate(phases):
        cx = LM + 10 + col * i + col / 2

        c.saveState()
        gradient_colors = [C_PRIMARY, C_ACCENT] if i < n - 1 else [C_SUCCESS, HexColor("#059669")]
        c.setFillColor(gradient_colors[0])
        c.circle(cx, line_y, dot_r, stroke=0, fill=1)
        c.restoreState()

        _text_c(c, cx, line_y - 3.5, str(i + 1), FONTB, 9, C_WHITE)

        _text_c(c, cx, line_y - dot_r - 12, name, FONTB, 7.5, C_SLATE800)
        _text_c(c, cx, line_y - dot_r - 24, duration, FONT, 7, C_PRIMARY)

    y = line_y - dot_r - 34

    pill_w = 80
    c.saveState()
    c.setFillColor(C_SLATE100)
    c.roundRect(W / 2 - pill_w / 2, y - 12, pill_w, 16, 4, stroke=0, fill=1)
    c.restoreState()
    _text_c(c, W / 2, y - 8, f"Итого: {total}", FONTB, 8, C_PRIMARY)

    return y - 20


def _draw_payment(c, y, price, discount_pct):
    final = int(price * (100 - discount_pct) / 100) if discount_pct else price
    prepay = int(final * 0.35)
    remainder = final - prepay
    card_h = 24 * mm
    card_w = (CW - 8) / 2

    if y - card_h < 40:
        c.showPage()
        _draw_header(c)
        y = H - 35

    _card(c, LM, y - card_h, card_w, card_h, C_WHITE, 5, shadow=True)
    _text(c, LM + 12, y - 16, "Этап 1: Предоплата", FONTB, 8.5, C_PRIMARY)
    _text(c, LM + 12, y - 34, f"{_fp(prepay)} руб.", FONTB, 16, C_SLATE900)
    _text(c, LM + 12, y - 50, "35% — до начала работ", FONT, 7.5, C_SLATE500)

    x2 = LM + card_w + 8
    _card(c, x2, y - card_h, card_w, card_h, C_WHITE, 5, shadow=True)
    _text(c, x2 + 12, y - 16, "Этап 2: После сдачи", FONTB, 8.5, C_SUCCESS)
    _text(c, x2 + 12, y - 34, f"{_fp(remainder)} руб.", FONTB, 16, C_SLATE900)
    _text(c, x2 + 12, y - 50, "65% — после приёмки", FONT, 7.5, C_SLATE500)

    y -= card_h + 6
    _text_c(c, W / 2, y, "Банковский перевод  \u00b7  Карта  \u00b7  СБП  \u00b7  Telegram Stars", FONT, 7.5, C_SLATE400)
    return y - 10


def _draw_steps(c, y):
    steps = [
        ("Согласование", "Утверждаем ТЗ и подписываем договор"),
        ("Предоплата", "Оплата 35% и старт работы"),
        ("Демо", "Промежуточная демонстрация прогресса"),
        ("Сдача", "Финальная приёмка и оплата остатка"),
        ("Запуск", "Деплой, мониторинг и поддержка"),
    ]
    for i, (title, desc) in enumerate(steps):
        if y < 40:
            c.showPage()
            _draw_header(c)
            y = H - 35

        c.saveState()
        clr = C_SUCCESS if i == len(steps) - 1 else C_PRIMARY
        c.setFillColor(clr)
        c.roundRect(LM, y - 14, 16, 16, 4, stroke=0, fill=1)
        c.restoreState()
        _text_c(c, LM + 8, y - 10, str(i + 1), FONTB, 8, C_WHITE)

        _text(c, LM + 22, y - 10, title, FONTB, 9, C_SLATE800)
        _text(c, LM + 90, y - 10, desc, FONT, 8, C_SLATE500)

        if i < len(steps) - 1:
            c.saveState()
            c.setStrokeColor(C_SLATE200)
            c.setLineWidth(0.5)
            c.setDash(1, 2)
            c.line(LM + 8, y - 14, LM + 8, y - 22)
            c.restoreState()

        y -= 22

    return y


def _draw_cta(c, y):
    if y < 50:
        c.showPage()
        _draw_header(c)
        y = H - 35

    cta_h = 28 * mm
    c.saveState()
    p = c.beginPath()
    p.roundRect(LM, y - cta_h, CW, cta_h, 8)
    c.clipPath(p, stroke=0)
    c.linearGradient(LM, y - cta_h, W - RM, y, [C_PRIMARY_DEEP, C_ACCENT])
    c.restoreState()

    _text(c, LM + 16, y - 18, "Готовы обсудить проект?", FONTB, 14, C_WHITE)
    _text(c, LM + 16, y - 34, "Ответим в течение 30 минут в рабочее время", FONT, 8.5, HexColor("#c7d2fe"))
    _text(c, LM + 16, y - 52, "Telegram: @web4_tg   \u00b7   web4tg.com", FONTB, 9, C_WHITE)

    return y - cta_h - 6


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

    page = 1
    kp_num = kp_number or int(time.time()) % 100000
    date_str = datetime.now().strftime("%d.%m.%Y")

    _draw_header(c)
    y = H - 28

    y = _draw_hero(c, y, project_type, pkg["name"], pkg["timeline"], kp_num, date_str, client_name)
    y = _draw_stats(c, y)

    y = _draw_section_header(c, y, "01", "О проекте")
    if ai_text:
        y = _draw_ai_blocks(c, y, ai_text)
    else:
        h = _wrap_text(c, LM + 4, y, (
            f"Разработка Telegram Mini App типа «{project_type}» "
            f"с полным комплексом функций для успешного запуска и роста вашего бизнеса."
        ), CW - 8, FONT, 9.5, C_SLATE700, 13)
        y -= h + 6

    y = _draw_section_header(c, y, "02", f"Пакет «{pkg['name']}» — {pkg['subtitle']}")
    y = _draw_features(c, y, pkg["features"], pkg["not_included"])
    y = _draw_guarantees(c, y, pkg["guarantee"], pkg["support"], pkg["updates"])

    y = _draw_section_header(c, y, "03", "Стоимость")
    y = _draw_price(c, y, pkg["price"], discount_pct, pkg["name"])

    y = _draw_section_header(c, y, "04", "Сроки реализации")
    phases = TIMELINE_PHASES.get(pkg_key, TIMELINE_PHASES["business"])
    y = _draw_timeline(c, y, phases, pkg["timeline"])

    y = _draw_section_header(c, y, "05", "Порядок оплаты")
    y = _draw_payment(c, y, pkg["price"], discount_pct)

    y = _draw_section_header(c, y, "06", "Следующие шаги")
    y = _draw_steps(c, y)

    _draw_cta(c, y)

    total_pages = c.getPageNumber()
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
                "\ud83d\udcc4 <b>Ваше персональное коммерческое предложение</b>\n\n"
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
