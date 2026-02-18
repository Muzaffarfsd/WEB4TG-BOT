"""Intelligent Demo Preview Generator — Visual Mock-ups of Telegram Mini Apps.

Generates high-quality Pillow-rendered images showing how a client's business
would look as a Telegram Mini App. Each business type gets a tailored UI:
- Restaurant/cafe: menu categories, dishes, delivery button
- Shop: product grid, cart, search
- Beauty salon: services, booking calendar, specialists
- Fitness: schedule, subscriptions, trainer profiles
- Services: service cards, booking, reviews
- Medical: appointments, specialists, medical records
- Education: courses, progress, schedule
- Delivery: order tracking, menu, address

The image is styled to match Telegram Mini App design language (2025-2026).
"""

import io
import os
import logging
from typing import Dict, Optional, List, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONT_PATH = os.path.join(_PROJECT_ROOT, "fonts", "DejaVuSans.ttf")
_FONT_BOLD_PATH = os.path.join(_PROJECT_ROOT, "fonts", "DejaVuSans-Bold.ttf")

W = 390
H = 844


class TGColors:
    BG = "#FFFFFF"
    HEADER_BG = "#2AABEE"
    HEADER_TEXT = "#FFFFFF"
    PRIMARY = "#2AABEE"
    PRIMARY_DARK = "#229ED9"
    ACCENT = "#34C759"
    TEXT_PRIMARY = "#1C1C1E"
    TEXT_SECONDARY = "#8E8E93"
    TEXT_MUTED = "#AEAEB2"
    CARD_BG = "#F2F2F7"
    CARD_BORDER = "#E5E5EA"
    SEPARATOR = "#E5E5EA"
    BUTTON_BG = "#2AABEE"
    BUTTON_TEXT = "#FFFFFF"
    SUCCESS = "#34C759"
    WARNING = "#FF9500"
    BADGE_RED = "#FF3B30"
    STAR = "#FFD60A"
    CATEGORY_ACTIVE = "#2AABEE"
    CATEGORY_INACTIVE = "#F2F2F7"
    NAV_BG = "#FBFBFD"
    NAV_ACTIVE = "#2AABEE"
    NAV_INACTIVE = "#8E8E93"
    PRICE_TAG = "#34C759"
    DISCOUNT = "#FF3B30"


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD_PATH if bold else _FONT_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple, radius: int, fill: str, outline: Optional[str] = None):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline)


def _draw_status_bar(draw: ImageDraw.ImageDraw, width: int):
    font_sm = _get_font(12, bold=True)
    draw.text((20, 8), "9:41", fill=TGColors.TEXT_PRIMARY, font=font_sm)
    draw.text((width - 80, 8), "100%  ▐█▌", fill=TGColors.TEXT_PRIMARY, font=font_sm)


def _draw_tg_header(draw: ImageDraw.ImageDraw, width: int, title: str, subtitle: str = ""):
    _draw_rounded_rect(draw, (0, 0, width, 90), radius=0, fill=TGColors.HEADER_BG)

    _draw_status_bar_light(draw, width)

    font_title = _get_font(18, bold=True)
    font_sub = _get_font(12)

    tw = draw.textlength(title, font=font_title)
    draw.text(((width - tw) / 2, 38), title, fill=TGColors.HEADER_TEXT, font=font_title)

    draw.text((16, 40), "← ", fill=TGColors.HEADER_TEXT, font=font_title)

    draw.text((width - 40, 42), "⋮", fill=TGColors.HEADER_TEXT, font=font_title)

    if subtitle:
        sw = draw.textlength(subtitle, font=font_sub)
        draw.text(((width - sw) / 2, 62), subtitle, fill="#D4EEFF", font=font_sub)


def _draw_status_bar_light(draw: ImageDraw.ImageDraw, width: int):
    font_sm = _get_font(12, bold=True)
    draw.text((20, 8), "9:41", fill=TGColors.HEADER_TEXT, font=font_sm)
    draw.text((width - 80, 8), "100%  ▐█▌", fill=TGColors.HEADER_TEXT, font=font_sm)


def _draw_bottom_nav(draw: ImageDraw.ImageDraw, y: int, width: int, items: List[Tuple[str, str]], active: int = 0):
    _draw_rounded_rect(draw, (0, y, width, y + 65), radius=0, fill=TGColors.NAV_BG)
    draw.line([(0, y), (width, y)], fill=TGColors.SEPARATOR, width=1)

    item_w = width // len(items)
    font_nav = _get_font(10)
    font_icon = _get_font(20)

    for i, (icon, label) in enumerate(items):
        cx = item_w * i + item_w // 2
        color = TGColors.NAV_ACTIVE if i == active else TGColors.NAV_INACTIVE

        iw = draw.textlength(icon, font=font_icon)
        draw.text((cx - iw / 2, y + 8), icon, fill=color, font=font_icon)

        lw = draw.textlength(label, font=font_nav)
        draw.text((cx - lw / 2, y + 35), label, fill=color, font=font_nav)


def _draw_search_bar(draw: ImageDraw.ImageDraw, y: int, width: int, placeholder: str = "Поиск..."):
    _draw_rounded_rect(draw, (16, y, width - 16, y + 40), radius=12, fill=TGColors.CARD_BG)
    font = _get_font(14)
    draw.text((44, y + 10), placeholder, fill=TGColors.TEXT_MUTED, font=font)
    draw.text((24, y + 9), "🔍", fill=TGColors.TEXT_MUTED, font=_get_font(15))


def _draw_category_pills(draw: ImageDraw.ImageDraw, y: int, width: int, categories: List[str], active: int = 0):
    x = 16
    font = _get_font(13, bold=False)
    for i, cat in enumerate(categories):
        tw = draw.textlength(cat, font=font)
        pill_w = int(tw + 24)
        bg = TGColors.CATEGORY_ACTIVE if i == active else TGColors.CATEGORY_INACTIVE
        text_color = TGColors.HEADER_TEXT if i == active else TGColors.TEXT_SECONDARY
        _draw_rounded_rect(draw, (x, y, x + pill_w, y + 32), radius=16, fill=bg)
        draw.text((x + 12, y + 7), cat, fill=text_color, font=font)
        x += pill_w + 8
        if x > width - 40:
            break


def _draw_product_card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                       title: str, price: str, emoji: str = "📦", old_price: str = "", rating: str = ""):
    _draw_rounded_rect(draw, (x, y, x + w, y + h), radius=16, fill=TGColors.CARD_BG, outline=TGColors.CARD_BORDER)

    img_h = int(h * 0.50)
    _draw_rounded_rect(draw, (x + 4, y + 4, x + w - 4, y + img_h), radius=12, fill="#E8E8ED")
    emoji_font = _get_font(36)
    ew = draw.textlength(emoji, font=emoji_font)
    draw.text((x + (w - ew) / 2, y + img_h / 2 - 22), emoji, fill=TGColors.TEXT_PRIMARY, font=emoji_font)

    font_title = _get_font(12, bold=True)
    font_price = _get_font(13, bold=True)
    font_old = _get_font(11)
    font_rating = _get_font(10)

    title_lines = []
    words = title.split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font_title) > w - 16:
            title_lines.append(line)
            line = word
        else:
            line = test
    if line:
        title_lines.append(line)

    ty = y + img_h + 6
    for tl in title_lines[:2]:
        draw.text((x + 8, ty), tl, fill=TGColors.TEXT_PRIMARY, font=font_title)
        ty += 16

    py = y + h - 28
    draw.text((x + 8, py), price, fill=TGColors.PRICE_TAG, font=font_price)

    if old_price:
        px = x + 8 + draw.textlength(price, font=font_price) + 6
        draw.text((px, py + 2), old_price, fill=TGColors.TEXT_MUTED, font=font_old)
        ow = draw.textlength(old_price, font=font_old)
        draw.line([(px, py + 9), (px + ow, py + 9)], fill=TGColors.DISCOUNT, width=1)

    if rating:
        draw.text((x + w - 40, py + 2), f"⭐ {rating}", fill=TGColors.STAR, font=font_rating)


def _draw_action_button(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                        text: str, bg: str = TGColors.BUTTON_BG, text_color: str = TGColors.BUTTON_TEXT):
    _draw_rounded_rect(draw, (x, y, x + w, y + h), radius=h // 2, fill=bg)
    font = _get_font(15, bold=True)
    tw = draw.textlength(text, font=font)
    draw.text((x + (w - tw) / 2, y + (h - 16) / 2), text, fill=text_color, font=font)


def _draw_list_item(draw: ImageDraw.ImageDraw, y: int, width: int,
                    emoji: str, title: str, subtitle: str, right_text: str = "",
                    right_color: str = TGColors.TEXT_SECONDARY):
    font_title = _get_font(14, bold=True)
    font_sub = _get_font(12)
    font_right = _get_font(13, bold=True)
    font_emoji = _get_font(22)

    draw.text((20, y + 4), emoji, fill=TGColors.TEXT_PRIMARY, font=font_emoji)
    draw.text((52, y + 4), title, fill=TGColors.TEXT_PRIMARY, font=font_title)
    draw.text((52, y + 22), subtitle, fill=TGColors.TEXT_SECONDARY, font=font_sub)

    if right_text:
        rw = draw.textlength(right_text, font=font_right)
        draw.text((width - 20 - rw, y + 10), right_text, fill=right_color, font=font_right)

    draw.line([(52, y + 43), (width - 16, y + 43)], fill=TGColors.SEPARATOR, width=1)


def _draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, bg: str = TGColors.BADGE_RED):
    font = _get_font(10, bold=True)
    tw = draw.textlength(text, font=font)
    bw = max(int(tw + 10), 20)
    _draw_rounded_rect(draw, (x, y, x + bw, y + 18), radius=9, fill=bg)
    draw.text((x + (bw - tw) / 2, y + 2), text, fill="#FFFFFF", font=font)


BUSINESS_CONFIGS: Dict[str, dict] = {
    "restaurant": {
        "title_tpl": "{name}",
        "subtitle": "Доставка и самовывоз",
        "categories": ["🔥 Хиты", "🍕 Пицца", "🍔 Бургеры", "🥗 Салаты", "🍰 Десерты"],
        "items": [
            {"emoji": "🍕", "title": "Маргарита", "price": "490₽", "old_price": "650₽", "rating": "4.9"},
            {"emoji": "🍔", "title": "Чизбургер Классик", "price": "390₽", "rating": "4.8"},
            {"emoji": "🥗", "title": "Цезарь с курицей", "price": "420₽", "rating": "4.7"},
            {"emoji": "🍰", "title": "Тирамису", "price": "350₽", "old_price": "450₽", "rating": "4.9"},
        ],
        "nav": [("🏠", "Главная"), ("📋", "Меню"), ("🛒", "Корзина"), ("👤", "Профиль")],
        "cta": "🛒  Корзина · 2 товара · 880₽",
        "cta_color": TGColors.ACCENT,
    },
    "shop": {
        "title_tpl": "{name}",
        "subtitle": "Интернет-магазин",
        "categories": ["Всё", "👕 Одежда", "👟 Обувь", "👜 Сумки", "💎 Акции"],
        "items": [
            {"emoji": "👕", "title": "Футболка Premium", "price": "2 490₽", "old_price": "3 990₽", "rating": "4.8"},
            {"emoji": "👟", "title": "Кроссовки Air", "price": "7 990₽", "rating": "4.9"},
            {"emoji": "👜", "title": "Рюкзак City", "price": "3 490₽", "rating": "4.7"},
            {"emoji": "🧢", "title": "Кепка Classic", "price": "1 290₽", "old_price": "1 890₽", "rating": "4.6"},
        ],
        "nav": [("🏠", "Главная"), ("🔍", "Каталог"), ("❤️", "Избранное"), ("🛒", "Корзина"), ("👤", "Профиль")],
        "cta": "🛒  В корзину",
        "cta_color": TGColors.BUTTON_BG,
    },
    "beauty": {
        "title_tpl": "{name}",
        "subtitle": "Запись онлайн",
        "categories": ["💇‍♀️ Стрижки", "💅 Маникюр", "💆 Массаж", "🧖 СПА"],
        "items_list": [
            {"emoji": "💇‍♀️", "title": "Женская стрижка", "sub": "45 мин · Мастер Анна", "price": "2 500₽"},
            {"emoji": "💅", "title": "Маникюр + покрытие", "sub": "60 мин · Мастер Елена", "price": "1 800₽"},
            {"emoji": "💆", "title": "Массаж спины", "sub": "30 мин · Мастер Игорь", "price": "2 200₽"},
            {"emoji": "🧖", "title": "СПА-программа", "sub": "120 мин · Все мастера", "price": "5 500₽"},
        ],
        "nav": [("🏠", "Главная"), ("📋", "Услуги"), ("📅", "Запись"), ("💰", "Бонусы"), ("👤", "Профиль")],
        "cta": "📅  Записаться онлайн",
        "cta_color": "#E91E63",
    },
    "fitness": {
        "title_tpl": "{name}",
        "subtitle": "Фитнес-клуб",
        "categories": ["📅 Сегодня", "🏋️ Зал", "🧘 Групповые", "🏊 Бассейн"],
        "items_list": [
            {"emoji": "🏋️", "title": "Силовая тренировка", "sub": "10:00 – 11:00 · Тренер Дмитрий", "price": ""},
            {"emoji": "🧘", "title": "Йога для начинающих", "sub": "12:00 – 13:00 · Тренер Мария", "price": ""},
            {"emoji": "🚴", "title": "Сайклинг", "sub": "14:00 – 14:45 · 5 мест", "price": ""},
            {"emoji": "🏊", "title": "Аквааэробика", "sub": "16:00 – 17:00 · 8 мест", "price": ""},
        ],
        "nav": [("🏠", "Главная"), ("📅", "Расписание"), ("🎫", "Абонемент"), ("📊", "Прогресс"), ("👤", "Профиль")],
        "cta": "🎫  Купить абонемент от 3 900₽/мес",
        "cta_color": "#FF6B00",
    },
    "services": {
        "title_tpl": "{name}",
        "subtitle": "Услуги и сервис",
        "categories": ["⭐ Популярные", "🔧 Ремонт", "🧹 Клининг", "📦 Доставка"],
        "items_list": [
            {"emoji": "🔧", "title": "Мастер на час", "sub": "Мелкий ремонт · от 30 мин", "price": "от 1 500₽"},
            {"emoji": "🧹", "title": "Уборка квартиры", "sub": "Генеральная · от 2 часов", "price": "от 3 000₽"},
            {"emoji": "📦", "title": "Курьерская доставка", "sub": "По городу · 1-3 часа", "price": "от 300₽"},
            {"emoji": "🔌", "title": "Электрик", "sub": "Диагностика + работа", "price": "от 2 000₽"},
        ],
        "nav": [("🏠", "Главная"), ("📋", "Услуги"), ("📅", "Заказы"), ("⭐", "Отзывы"), ("👤", "Профиль")],
        "cta": "📋  Оставить заявку",
        "cta_color": TGColors.BUTTON_BG,
    },
    "medical": {
        "title_tpl": "{name}",
        "subtitle": "Медицинский центр",
        "categories": ["🏥 Приём", "🔬 Анализы", "💊 Аптека", "📋 Записи"],
        "items_list": [
            {"emoji": "👨‍⚕️", "title": "Терапевт", "sub": "Ближайшая запись: завтра 10:00", "price": "2 000₽"},
            {"emoji": "🦷", "title": "Стоматолог", "sub": "Ближайшая запись: завтра 14:00", "price": "3 500₽"},
            {"emoji": "👁️", "title": "Офтальмолог", "sub": "Ближайшая запись: 20 фев", "price": "2 500₽"},
            {"emoji": "🔬", "title": "Общий анализ крови", "sub": "Результат за 1 день", "price": "800₽"},
        ],
        "nav": [("🏠", "Главная"), ("📅", "Запись"), ("📋", "Мои записи"), ("📊", "Анализы"), ("👤", "Профиль")],
        "cta": "📅  Записаться к врачу",
        "cta_color": "#00BCD4",
    },
    "education": {
        "title_tpl": "{name}",
        "subtitle": "Онлайн-обучение",
        "categories": ["🔥 Новые", "💻 IT", "🎨 Дизайн", "📈 Бизнес"],
        "items": [
            {"emoji": "💻", "title": "Python с нуля", "price": "4 990₽", "old_price": "9 990₽", "rating": "4.9"},
            {"emoji": "🎨", "title": "UI/UX Дизайн", "price": "6 990₽", "rating": "4.8"},
            {"emoji": "📈", "title": "Маркетинг", "price": "3 990₽", "old_price": "7 990₽", "rating": "4.7"},
            {"emoji": "🤖", "title": "AI для бизнеса", "price": "7 990₽", "rating": "4.9"},
        ],
        "nav": [("🏠", "Главная"), ("📚", "Курсы"), ("📊", "Прогресс"), ("💬", "Чат"), ("👤", "Профиль")],
        "cta": "📚  Начать обучение",
        "cta_color": "#6C63FF",
    },
    "delivery": {
        "title_tpl": "{name}",
        "subtitle": "Доставка еды",
        "categories": ["🔥 Хиты", "🍣 Суши", "🍕 Пицца", "🥡 Вок", "🍰 Десерты"],
        "items": [
            {"emoji": "🍣", "title": "Сет Филадельфия", "price": "1 290₽", "old_price": "1 590₽", "rating": "4.9"},
            {"emoji": "🍕", "title": "Пепперони XL", "price": "690₽", "rating": "4.8"},
            {"emoji": "🥡", "title": "Вок с курицей", "price": "490₽", "rating": "4.7"},
            {"emoji": "🍰", "title": "Чизкейк NY", "price": "390₽", "old_price": "490₽", "rating": "4.8"},
        ],
        "nav": [("🏠", "Главная"), ("📋", "Меню"), ("🛒", "Корзина"), ("🚚", "Доставки"), ("👤", "Профиль")],
        "cta": "🛒  Корзина · 3 товара · 2 470₽",
        "cta_color": TGColors.ACCENT,
    },
}


def _resolve_business_type(raw_type: str) -> str:
    raw = raw_type.lower().strip()
    aliases = {
        "кофейня": "restaurant", "кафе": "restaurant", "ресторан": "restaurant",
        "бар": "restaurant", "столовая": "restaurant", "пекарня": "restaurant",
        "магазин": "shop", "бутик": "shop", "интернет-магазин": "shop",
        "маркетплейс": "shop", "гипермаркет": "shop", "супермаркет": "shop",
        "салон": "beauty", "парикмахерская": "beauty", "барбершоп": "beauty",
        "спа": "beauty", "nail": "beauty", "косметология": "beauty",
        "фитнес": "fitness", "спортзал": "fitness", "тренажёрный": "fitness",
        "йога": "fitness", "пилатес": "fitness", "кроссфит": "fitness",
        "сервис": "services", "ремонт": "services", "клининг": "services",
        "автосервис": "services", "химчистка": "services",
        "клиника": "medical", "больница": "medical", "стоматология": "medical",
        "аптека": "medical", "лаборатория": "medical",
        "курсы": "education", "школа": "education", "обучение": "education",
        "университет": "education", "репетитор": "education",
        "доставка": "delivery", "суши": "delivery", "пицца": "delivery",
        "еда": "delivery", "food": "delivery",
    }
    if raw in aliases:
        return aliases[raw]
    for key, val in aliases.items():
        if key in raw:
            return val
    if raw in BUSINESS_CONFIGS:
        return raw
    return "shop"


def generate_preview(
    business_type: str,
    business_name: str = "",
    custom_subtitle: str = "",
) -> io.BytesIO:
    btype = _resolve_business_type(business_type)
    cfg = BUSINESS_CONFIGS.get(btype, BUSINESS_CONFIGS["shop"])

    name = business_name or "Ваш бизнес"
    title = cfg["title_tpl"].format(name=name)
    subtitle = custom_subtitle or cfg.get("subtitle", "")

    img = Image.new("RGB", (W, H), _hex_to_rgb(TGColors.BG))
    draw = ImageDraw.Draw(img)

    _draw_tg_header(draw, W, title, subtitle)

    y = 98

    if "items" in cfg:
        _draw_search_bar(draw, y, W, "Поиск в каталоге...")
        y += 50
        _draw_category_pills(draw, y, W, cfg["categories"], active=0)
        y += 45

        items = cfg["items"]
        card_w = (W - 48) // 2
        card_h = 195
        for i, item in enumerate(items[:4]):
            col = i % 2
            row = i // 2
            cx = 16 + col * (card_w + 16)
            cy = y + row * (card_h + 12)
            _draw_product_card(
                draw, cx, cy, card_w, card_h,
                title=item["title"],
                price=item["price"],
                emoji=item["emoji"],
                old_price=item.get("old_price", ""),
                rating=item.get("rating", ""),
            )

    elif "items_list" in cfg:
        _draw_category_pills(draw, y, W, cfg["categories"], active=0)
        y += 45

        for item in cfg["items_list"][:4]:
            _draw_list_item(
                draw, y, W,
                emoji=item["emoji"],
                title=item["title"],
                subtitle=item["sub"],
                right_text=item.get("price", ""),
                right_color=TGColors.PRICE_TAG if item.get("price") else TGColors.TEXT_SECONDARY,
            )
            y += 48

    cta_y = H - 135
    cta_text = cfg.get("cta", "Далее")
    cta_color = cfg.get("cta_color", TGColors.BUTTON_BG)
    _draw_action_button(draw, 16, cta_y, W - 32, 48, cta_text, bg=cta_color)

    if btype in ("restaurant", "delivery"):
        _draw_badge(draw, W - 52, cta_y - 16, "2", bg=TGColors.BADGE_RED)

    nav_items = cfg.get("nav", [("🏠", "Главная"), ("📋", "Каталог"), ("🛒", "Корзина"), ("👤", "Профиль")])
    _draw_bottom_nav(draw, H - 65, W, nav_items, active=0)

    font_watermark = _get_font(10)
    wm_text = "Preview · WEB4TG Studio"
    wm_w = draw.textlength(wm_text, font=font_watermark)
    draw.text(((W - wm_w) / 2, H - 78), wm_text, fill=TGColors.TEXT_MUTED, font=font_watermark)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def generate_preview_for_ai(
    business_type: str,
    business_name: str = "",
) -> Tuple[io.BytesIO, str, str]:
    btype = _resolve_business_type(business_type)
    name = business_name or "Ваш бизнес"
    buf = generate_preview(btype, name)

    cfg = BUSINESS_CONFIGS.get(btype, BUSINESS_CONFIGS["shop"])
    nav_labels = [item[1] for item in cfg.get("nav", [])]
    features = ", ".join(nav_labels)

    caption = (
        f"📱 *Вот как может выглядеть Mini App для «{name}»*\n\n"
        f"Это интерактивный превью с реальными элементами интерфейса: "
        f"{features}.\n\n"
        f"Хотите обсудить детали или добавить функции? "
        f"Я могу рассчитать точную стоимость."
    )

    return buf, caption, btype
