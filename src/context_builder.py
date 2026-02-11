import logging
from typing import Optional

logger = logging.getLogger(__name__)

OBJECTION_PATTERNS = {
    "price": [
        "дорого", "дороговато", "слишком дорого", "цена кусается", "не потяну",
        "бюджет ограничен", "нет бюджета", "не хватает", "expensive", "costly",
        "много денег", "за такие деньги", "дешевле", "cheaper", "завышен",
        "переплата", "не стоит столько", "could be cheaper", "too much"
    ],
    "delay": [
        "подумаю", "надо подумать", "позже", "не сейчас", "потом",
        "через месяц", "через неделю", "на днях", "в следующий раз",
        "пока не готов", "ещё рано", "рано ещё", "think about it",
        "later", "not now", "need time", "нужно время"
    ],
    "competitor": [
        "у конкурентов", "в другом месте", "другая студия", "другие делают",
        "нашёл дешевле", "предлагают дешевле", "есть варианты", "альтернатив",
        "freelancer", "фрилансер", "на upwork", "fiverr", "конкурент",
        "competitor", "someone else", "other company"
    ],
    "doubt": [
        "не уверен", "сомневаюсь", "а точно", "гарантии", "а если не получится",
        "а вдруг", "риск", "страшно", "боюсь", "не знаю нужно ли",
        "стоит ли", "worth it", "not sure", "doubt", "guarantee",
        "а зачем", "нужно ли вообще", "может не надо"
    ],
    "trust": [
        "а вы реальные", "мошенники", "кинете", "обман", "развод",
        "можно доверять", "отзывы настоящие", "scam", "fraud", "trust",
        "кто вы", "компания настоящая", "а есть офис", "юр лицо"
    ]
}

OBJECTION_STRATEGIES = {
    "price": "СТРАТЕГИЯ_ЦЕНА: Клиент считает дорого. НЕ снижай цену! Покажи ROI и окупаемость. Разбей на составляющие. Предложи рассрочку или MVP-версию. Сравни с альтернативами (наём разработчика, потеря клиентов без приложения). Упомяни систему скидок за монеты.",
    "delay": "СТРАТЕГИЯ_ОТЛОЖИТЬ: Клиент тянет время. Создай мягкую срочность: упомяни загруженность команды, рост цен. Напомни о потерянных клиентах за каждый день без приложения. Предложи бесплатный шаг: расчёт стоимости, ТЗ.",
    "competitor": "СТРАТЕГИЯ_КОНКУРЕНТ: Клиент сравнивает. Не критикуй конкурентов! Подчеркни уникальность: специализация на Telegram Mini Apps, 7-15 дней, Apple-дизайн, нет комиссий маркетплейсов. Спроси что именно предлагают — найди слабости.",
    "doubt": "СТРАТЕГИЯ_СОМНЕНИЕ: Клиент сомневается в необходимости. Задай уточняющие вопросы. Покажи кейсы похожих бизнесов. Предложи бесплатную консультацию для оценки. Упомяни гарантию возврата предоплаты.",
    "trust": "СТРАТЕГИЯ_ДОВЕРИЕ: Клиент не доверяет. Покажи портфолио, реальные кейсы. Упомяни договор (/contract). Предложи этапную оплату (35%+65%). Скажи про гарантию 14 дней правок. Будь максимально открытым."
}


EMOTION_PATTERNS = {
    "frustrated": [
        "надоело", "устал", "бесит", "раздражает", "ужас", "кошмар",
        "плохо", "отвратительно", "невозможно", "frustrated", "annoyed",
        "disappointed", "terrible", "worst", "разочарован", "отстой",
        "не работает", "опять", "снова", "!!!", "сколько можно"
    ],
    "excited": [
        "круто", "офигенно", "вау", "потрясающе", "супер", "класс",
        "великолепно", "шикарно", "amazing", "awesome", "wow", "cool",
        "fantastic", "love it", "обалдеть", "восторг", "!!!", "🔥", "❤️",
        "топ", "бомба", "огонь"
    ],
    "confused": [
        "не понимаю", "запутался", "сложно", "непонятно", "объясните",
        "как это", "что это значит", "не ясно", "confused", "don't understand",
        "what do you mean", "unclear", "а можно проще", "не разбираюсь",
        "??", "хз", "не знаю"
    ],
    "urgent": [
        "срочно", "быстрее", "скорее", "сейчас", "немедленно",
        "urgent", "asap", "hurry", "deadline", "горит", "вчера нужно было",
        "завтра запуск", "время поджимает"
    ],
    "skeptical": [
        "верится с трудом", "сомневаюсь", "звучит как", "ну-ну",
        "да ладно", "серьёзно?", "вряд ли", "skeptical", "really?",
        "маловероятно", "ага конечно"
    ]
}

EMOTION_HINTS = {
    "frustrated": "ТОН: Клиент раздражён/расстроен. Будь максимально эмпатичным. Признай проблему. Не оправдывайся — предложи конкретное решение. Покажи что понимаешь.",
    "excited": "ТОН: Клиент в восторге/воодушевлён. Поддержи энергию! Используй момент для продвижения к следующему шагу. Предложи конкретное действие прямо сейчас.",
    "confused": "ТОН: Клиент запутан/не понимает. Объясняй максимально просто. Используй аналогии из реальной жизни. Разбей информацию на маленькие шаги. Спроси что именно непонятно.",
    "urgent": "ТОН: У клиента срочность. Действуй быстро и конкретно. Без лишних вопросов — сразу решение. Предложи ускоренные варианты. Покажи что понимаешь важность сроков.",
    "skeptical": "ТОН: Клиент скептичен. Приводи конкретные факты и цифры. Покажи реальные кейсы. Будь честным про ограничения. Не пытайся впечатлить — убеждай доказательствами."
}


def detect_emotions(text: str) -> list:
    text_lower = text.lower()
    detected = []
    for emotion, patterns in EMOTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                detected.append(emotion)
                break
    return detected


def detect_objections(text: str) -> list:
    text_lower = text.lower()
    detected = []
    for obj_type, patterns in OBJECTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                detected.append(obj_type)
                break
    return detected


def build_client_context(user_id: int, username: str = None, first_name: str = None) -> str:
    context_parts = []
    
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead:
            context_parts.append(f"[ПРОФИЛЬ КЛИЕНТА]")
            context_parts.append(f"Имя: {lead.first_name or first_name or 'неизвестно'}")
            if lead.score and lead.score > 0:
                context_parts.append(f"Лид-скор: {lead.score}/100")
            if lead.priority:
                priority_map = {"cold": "холодный", "warm": "тёплый", "hot": "горячий", "vip": "VIP"}
                context_parts.append(f"Температура: {priority_map.get(lead.priority.value, lead.priority.value)}")
            if lead.tags:
                context_parts.append(f"Теги: {', '.join(lead.tags)}")
            if hasattr(lead, 'message_count') and lead.message_count:
                context_parts.append(f"Сообщений: {lead.message_count}")
    except Exception as e:
        logger.debug(f"Failed to get lead data: {e}")
    
    try:
        from src.tasks_tracker import tasks_tracker
        progress = tasks_tracker.get_user_progress(user_id)
        if progress and progress.total_coins > 0:
            context_parts.append(f"Монеты: {progress.total_coins} (скидка {progress.get_discount_percent()}%)")
    except Exception as e:
        logger.debug(f"Failed to get coins data: {e}")
    
    try:
        from src.loyalty import loyalty_system
        if loyalty_system.is_returning_customer(user_id):
            context_parts.append("Статус: постоянный клиент (+5% скидка)")
        reviews = loyalty_system.get_user_reviews(user_id)
        if reviews:
            context_parts.append(f"Оставил {len(reviews)} отзывов")
    except Exception as e:
        logger.debug(f"Failed to get loyalty data: {e}")
    
    try:
        from src.referrals import referral_system
        referrals = referral_system.get_referrals_list(user_id)
        if referrals:
            context_parts.append(f"Привёл {len(referrals)} рефералов")
    except Exception as e:
        logger.debug(f"Failed to get referral data: {e}")
    
    try:
        from src.leads import lead_manager
        events = lead_manager.get_events(user_id) if hasattr(lead_manager, 'get_events') else []
        if events:
            actions = set()
            for ev in events:
                event_type = ev.get("event_type", "") if isinstance(ev, dict) else ""
                if "calc" in event_type:
                    actions.add("считал стоимость")
                elif "portfolio" in event_type:
                    actions.add("смотрел портфолио")
                elif "price" in event_type:
                    actions.add("смотрел цены")
                elif "payment" in event_type:
                    actions.add("интересовался оплатой")
                elif "lead" in event_type or "contact" in event_type:
                    actions.add("оставлял заявку")
            if actions:
                context_parts.append(f"Действия: {', '.join(actions)}")
    except Exception as e:
        logger.debug(f"Failed to get event data: {e}")
    
    if context_parts:
        return "\n".join(context_parts)
    return ""


def build_objection_hint(user_message: str) -> str:
    objections = detect_objections(user_message)
    if not objections:
        return ""
    
    hints = []
    for obj in objections:
        if obj in OBJECTION_STRATEGIES:
            hints.append(OBJECTION_STRATEGIES[obj])
    
    return "\n".join(hints)


def build_emotion_hint(user_message: str) -> str:
    emotions = detect_emotions(user_message)
    if not emotions:
        return ""
    
    hints = []
    for emo in emotions:
        if emo in EMOTION_HINTS:
            hints.append(EMOTION_HINTS[emo])
    
    return "\n".join(hints)


def build_full_context(user_id: int, user_message: str, username: str = None, first_name: str = None) -> Optional[str]:
    parts = []
    
    client_ctx = build_client_context(user_id, username, first_name)
    if client_ctx:
        parts.append(client_ctx)
    
    objection_hint = build_objection_hint(user_message)
    if objection_hint:
        parts.append(f"\n[ОБНАРУЖЕНО ВОЗРАЖЕНИЕ]\n{objection_hint}")
    
    emotion_hint = build_emotion_hint(user_message)
    if emotion_hint:
        parts.append(f"\n[ЭМОЦИОНАЛЬНЫЙ ТОН]\n{emotion_hint}")
    
    if parts:
        return "\n".join(parts)
    return None
