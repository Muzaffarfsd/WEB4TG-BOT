import logging
import re
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

_context_cache = {}
_CACHE_TTL = 30

def _cached_get(key, fetcher):
    now = time.time()
    if key in _context_cache:
        val, ts = _context_cache[key]
        if now - ts < _CACHE_TTL:
            return val
    try:
        result = fetcher()
    except Exception:
        result = None
    _context_cache[key] = (result, now)
    if len(_context_cache) > 500:
        cutoff = now - _CACHE_TTL * 2
        _context_cache.clear()
    return result


OBJECTION_PATTERNS = {
    "price": [
        "дорого", "дороговато", "слишком дорого", "цена кусается", "не потяну",
        "бюджет ограничен", "нет бюджета", "не хватает", "expensive", "costly",
        "много денег", "за такие деньги", "дешевле", "cheaper", "завышен",
        "переплата", "не стоит столько", "could be cheaper", "too much",
        "нет таких денег", "не по карману", "дороговат"
    ],
    "delay": [
        "подумаю", "надо подумать", "позже", "не сейчас", "потом",
        "через месяц", "через неделю", "на днях", "в следующий раз",
        "пока не готов", "ещё рано", "рано ещё", "think about it",
        "later", "not now", "need time", "нужно время", "не спешу"
    ],
    "competitor": [
        "у конкурентов", "в другом месте", "другая студия", "другие делают",
        "нашёл дешевле", "предлагают дешевле", "есть варианты", "альтернатив",
        "freelancer", "фрилансер", "на upwork", "fiverr", "конкурент",
        "competitor", "someone else", "other company", "другой разработчик"
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
    ],
    "free": [
        "бесплатно", "без денег", "за 0", "free", "no cost",
        "бесплатный", "сделать самому бесплатно", "без вложений",
        "есть бесплатные", "конструктор", "tilda", "тильда", "wix"
    ],
    "diy": [
        "сам сделаю", "сами сделаем", "своими силами", "in-house",
        "у нас есть разработчик", "наш программист", "сами разработаем",
        "найму фрилансера", "сам напишу", "no-code", "ноу-код"
    ],
    "timing": [
        "не сезон", "кризис", "сейчас не время", "после нового года",
        "после лета", "когда будут деньги", "когда раскрутимся",
        "бизнес только начинается", "ещё не запустились"
    ]
}

OBJECTION_STRATEGIES = {
    "price": "СТРАТЕГИЯ_ЦЕНА: НЕ снижай цену! Трёхступенчатый подход:\n1) ПЕРЕФОРМУЛИРУЙ: Не \"150к расход\", а \"инвестиция с окупаемостью за 25-45 дней\". Переведи в цену одного дня: 150к ÷ 365 = 411₽/день.\n2) ПОКАЖИ ПОТЕРИ: \"Без приложения вы теряете [3 заказа/день × средний чек × 30] = Xк/мес. За 3 месяца раздумий потери = стоимость 2 приложений.\"\n3) ЯКОРЬ: Сначала назови полный пакет (369к), потом предложи MVP (150к) — MVP выглядит выгодно.\nРассрочка: предоплата 52 500₽ (35%) — меньше, чем месячная зарплата стажёра.\nМонеты: напомни про скидки до 25% через систему бонусов.\nКейс: Radiance — 200к инвестиция, окупилась за 25 дней.",
    "delay": "СТРАТЕГИЯ_ОТЛОЖИТЬ: Трёхступенчатый подход:\n1) ПОСЧИТАЙ ПОТЕРИ: \"Каждый день без приложения = [3 упущенных заказа × средний чек]. За месяц раздумий вы теряете [сумму]. За 3 месяца — стоимость самого приложения.\"\n2) КОНТРАСТ ВРЕМЕНИ: \"Через 10 дней у вас уже работающее приложение, которое принимает заказы 24/7. Или через 10 дней — та же ситуация, что сейчас.\"\n3) ДЕФИЦИТ: \"Сейчас команда может начать сразу. Через 2 недели — очередь минимум на месяц.\"\nМикро-обязательство: Предложи бесплатный шаг — \"Давайте просто прикинем ТЗ — ни к чему не обязывает, а вы увидите весь объём работ.\"",
    "competitor": "СТРАТЕГИЯ_КОНКУРЕНТ: Не критикуй! Задавай уточняющие вопросы и подчеркни разницу:\n1) ВОПРОС: \"Что именно предлагают? Интересно сравнить\" — часто клиент сам видит разницу.\n2) СПЕЦИАЛИЗАЦИЯ: \"Мы делаем только Telegram Mini Apps — поэтому 7-15 дней вместо 2-3 месяцев.\"\n3) СЧИТАЙ: Штатный разработчик = 150-250к/мес × 3 мес = 450-750к. Фрилансер = дешевле, но нет договора, сроки плывут, поддержки нет. Наш проект = разовая инвестиция + договор + гарантия.\n4) ЭКОНОМИКА: В Telegram нет комиссий 15-25% маркетплейсов. DeluxeDine экономит 35к/мес = 420к/год.\nКейс: TimeElite — начали в понедельник, через 8 дней уже принимали заказы.",
    "doubt": "СТРАТЕГИЯ_СОМНЕНИЕ: Нормализуй + доказательства:\n1) НОРМАЛИЗУЙ: \"Это нормально — такие решения не принимаются за 5 минут. Давайте разберём что именно смущает.\"\n2) КЕЙС ИЗ НИШИ: \"[Имя клиента из похожей ниши] тоже сомневался. Через месяц: [конкретные цифры результата].\"\n3) УБЕРИ РИСК: Гарантия возврата предоплаты. Платите 65% только когда увидите готовый результат.\n4) БЕСПЛАТНЫЙ ШАГ: \"Давайте просто посчитаем стоимость — ни к чему не обязывает. Или запишу на бесплатную консультацию.\"\nСтатистика: \"87% наших клиентов окупают вложения за 2-3 месяца. Мы считаем ROI до старта — если не вижу окупаемости, честно скажу.\"",
    "trust": "СТРАТЕГИЯ_ДОВЕРИЕ: Максимальная прозрачность:\n1) ФАКТЫ: 20+ завершённых проектов с реальными скриншотами в портфолио. Юридический договор с реквизитами.\n2) БЕЗОПАСНОСТЬ ОПЛАТЫ: 35% предоплата → дизайн и прототип. 65% → только когда вы одобрите результат. Не устроит — возврат.\n3) ПОСЛЕПРОДАЖНОЕ: 14 дней бесплатных правок. Чат с командой. Подписка на поддержку от 9.9к/мес.\n4) ДЕМО: \"Могу показать рабочие проекты прямо в Telegram — увидите качество своими глазами.\"\nКейс: MedLine — провели 3 созвона перед стартом, показали демо. Результат: заполняемость +30%, no-show -50%.",
    "free": "СТРАТЕГИЯ_БЕСПЛАТНОЕ: Не обесценивай, покажи разницу через цифры:\n1) КОНВЕРСИЯ: \"Конструктор (Tilda) = сайт, куда клиент УХОДИТ из Telegram. Потеря 60-70% конверсии. Mini App = клиент остаётся в мессенджере, покупка в 2 клика.\"\n2) ВРЕМЯ: \"Бесплатное решение = 2-4 месяца вашего времени + ограниченный функционал + без поддержки. Цена вашего времени — ?к/мес.\"\n3) СКРЫТЫЕ РАСХОДЫ: \"Бесплатный конструктор: хостинг 3-5к/мес + домен + SSL + самостоятельная настройка оплаты. За год = 60к+ и ваше время.\"\n4) ДОСТУПНЫЙ ВХОД: Шаблон магазина от 150к с рассрочкой. Предоплата 52 500₽ — меньше месячной зарплаты стажёра.",
    "diy": "СТРАТЕГИЯ_САМИ: Уважай решение, покажи экономику:\n1) СЧИТАЙ: Штатный разработчик 150-250к/мес × 3-4 месяца = 450к-1М. Наш проект = 150-250к разовая инвестиция, готово за 7-15 дней.\n2) ТЕХНОЛОГИЯ: \"No-code платформы не поддерживают Telegram Mini Apps API нативно. Нужны React/Vue + серверная часть.\"\n3) АЛЬТЕРНАТИВНЫЕ РАСХОДЫ: \"Пока разработчик делает Mini App 3 месяца — вы теряете [3 заказа/день × чек × 90 дней] = Xк потенциальной выручки.\"\nValue-first: \"Давайте бесплатно составлю ТЗ — пригодится в любом случае, даже если будете делать сами.\"",
    "timing": "СТРАТЕГИЯ_ВРЕМЯ: Покажи стоимость ожидания в рублях:\n1) ПОТЕРИ: \"Каждый месяц без приложения = [кол-во упущенных заказов × средний чек]. Посчитаем вместе?\"\n2) КОНКУРЕНТЫ: \"70% бизнесов в вашей нише планируют Mini App в 2026. Кто первый — забирает аудиторию.\"\n3) СЕЗОННОСТЬ: \"До [ближайший пик продаж] осталось N недель. Если начнём сейчас — запустим к пику.\"\n4) СКОРОСТЬ: \"Разработка 7-15 дней. Начнём сегодня — к [дата через 2 недели] уже принимаете заказы.\"\nМикро-обязательство: \"Давайте просто обсудим идею за 15 минут — ни к чему не обязывает.\""
}


EMOTION_PATTERNS = {
    "frustrated": [
        "надоело", "устал", "бесит", "раздражает", "ужас", "кошмар",
        "плохо", "отвратительно", "невозможно", "frustrated", "annoyed",
        "disappointed", "terrible", "worst", "разочарован", "отстой",
        "не работает", "опять", "снова", "сколько можно"
    ],
    "excited": [
        "круто", "офигенно", "вау", "потрясающе", "супер", "класс",
        "великолепно", "шикарно", "amazing", "awesome", "wow", "cool",
        "fantastic", "love it", "обалдеть", "восторг",
        "топ", "бомба", "огонь", "отлично"
    ],
    "confused": [
        "не понимаю", "запутался", "сложно", "непонятно", "объясните",
        "как это", "что это значит", "не ясно", "confused", "don't understand",
        "what do you mean", "unclear", "а можно проще", "не разбираюсь",
        "хз", "не знаю"
    ],
    "urgent": [
        "срочно", "быстрее", "скорее", "сейчас", "немедленно",
        "urgent", "asap", "hurry", "deadline", "горит", "вчера нужно было",
        "завтра запуск", "время поджимает"
    ],
    "skeptical": [
        "верится с трудом", "сомневаюсь", "звучит как", "ну-ну",
        "да ладно", "серьёзно?", "вряд ли", "skeptical", "really?",
        "маловероятно", "ага конечно", "слишком хорошо"
    ]
}

EMOTION_HINTS = {
    "frustrated": "ТОН: Клиент раздражён. Модель трёх мозгов: обратись к рептильному (убери угрозу — \"Понимаю, это неприятно\"), потом к эмоциональному (эмпатия — \"Давайте я помогу решить это\"), потом к рациональному (конкретный план). НЕ оправдывайся.",
    "excited": "ТОН: Клиент воодушевлён! Используй момент: поддержи энергию и сразу предложи микро-обязательство — конкретный следующий шаг (\"Давайте прямо сейчас посчитаем стоимость?\"). Foot-in-the-door: маленькое \"да\" ведёт к большому.",
    "confused": "ТОН: Клиент запутан. Упрости максимально. Используй аналогии из реальной жизни (\"Это как витрина магазина, но прямо в Telegram\"). Один тезис за раз. Спроси что именно непонятно.",
    "urgent": "ТОН: У клиента срочность. Действуй быстро: конкретные сроки (\"Запустим за 7-10 дней\"), конкретные шаги (\"Оставьте заявку сейчас — начнём завтра\"). Без лишних вопросов.",
    "skeptical": "ТОН: Клиент скептичен. Только факты и доказательства. Социальное доказательство: конкретные кейсы с цифрами. Честность: \"Не буду обещать чудес, но вот реальные результаты наших клиентов...\""
}


SOCIAL_PROOF_TRIGGERS = {
    "doubt": [
        "CleanPro (клининг) — владелец тоже сомневался. Через месяц: конверсия из заявки в заказ +40%, повторные заказы +25%. Сказал: \"Клиенты заказывают уборку в два клика, без звонков — я зря тянул полгода\".",
        "Radiance (магазин одежды) — запустили за 10 дней. Первая неделя: 200+ заказов, конверсия из Telegram в покупку 12%. Вложения 200к окупились за 25 дней.",
        "У 87% наших клиентов приложение окупается за 2-3 месяца. Мы считаем ROI ДО старта — если не вижу окупаемости, честно скажу.",
        "GlowSpa (салон красоты) — no-show упал на 45%, загрузка мастеров выросла до 90%. Владелица: \"Пустые кресла стоили мне 30-40к в месяц — теперь их нет\"."
    ],
    "competitor": [
        "Мы делаем только Telegram Mini Apps. Не сайты, не мобильные приложения — только Telegram. Поэтому 7-15 дней вместо 2-3 месяцев, и качество выше, чем у универсалов.",
        "В Telegram Mini App нет комиссий 15-25% как у маркетплейсов. DeluxeDine экономит 35к/мес только на комиссиях — за год это 420к.",
        "Фрилансер предложит дешевле, но вот реальность: нет договора, сроки плывут, поддержки нет. У нас — юридический договор, предоплата 35%+65%, 14 дней правок, поддержка после запуска.",
        "Конструкторы (Tilda, Wix) не работают нативно внутри Telegram — клиенту нужно переходить на сайт. Это теряет 60-70% конверсии. Mini App открывается мгновенно, без перехода."
    ],
    "trust": [
        "20+ завершённых проектов: Radiance, TimeElite, GlowSpa, DeluxeDine, MedLine, CleanPro, SkillUp. Каждый можно посмотреть в портфолио с реальными скриншотами.",
        "Работаем по договору с юрлицом. Предоплата 35% — дизайн и прототип. 65% — только когда вы одобрите готовый результат. Не устроит — вернём предоплату.",
        "14 дней бесплатных правок после сдачи. Мы не исчезаем после оплаты — у каждого клиента есть чат с командой.",
        "MedLine (клиника) — прежде чем начать, провели 3 созвона. Врачи задавали вопросы, мы показали демо. Результат: заполняемость +30%, no-show -50%."
    ],
    "price": [
        "Штатный разработчик: 150-250к/мес × 3 месяца = 450-750к. Наш проект: разовая инвестиция от 150к, готово через 7-15 дней. Разница = 3-5x.",
        "Radiance при среднем чеке 4 500₽ и 15 доп. заказах/день: +240к/мес выручки. Вложения 200к окупились за 25 дней.",
        "Рассрочка: предоплата 52 500₽ (35%) за магазин. Остальные 97 500₽ — когда увидите работающий результат и скажете \"ок\".",
        "Потери без приложения: 3 упущенных заказа/день × средний чек 2 000₽ × 30 дней = 180к/мес. За 3 месяца раздумий потери = стоимость 2 приложений."
    ],
    "timing": [
        "TimeElite начали проект в понедельник — через 8 дней уже принимали заказы. Владелец: \"Я думал это на месяцы, а тут неделя\".",
        "Каждый день без приложения = упущенные заказы. При 3 потерянных заказах/день по 2 000₽ — за месяц раздумий теряете 180к. Это стоимость самого приложения.",
        "Сейчас команда свободна и может начать на этой неделе. Через 2 недели — очередь минимум на месяц."
    ]
}


FUNNEL_STAGE_SIGNALS = {
    "awareness": {
        "keywords": [
            "привет", "здравствуйте", "добрый", "hello", "hi",
            "что вы делаете", "чем занимаетесь", "что такое",
            "расскажите о себе", "кто вы"
        ],
        "max_messages": 3,
        "instruction": "СТАДИЯ: ЗНАКОМСТВО (Awareness)\nЗадача: Установить контакт и понять бизнес клиента.\nSPIN-фаза: Situation — задавай открытые вопросы о бизнесе.\nТон: Тёплый, дружелюбный, любопытный.\nЦель вопроса: Узнать тип бизнеса и текущую ситуацию.\nПример: \"Расскажите, какой у вас бизнес? Чем занимаетесь?\"\nМикро-обязательство: Вовлечь в разговор."
    },
    "interest": {
        "keywords": [
            "цена", "стоимость", "сколько", "прайс", "тариф",
            "сроки", "сколько времени", "когда будет готово",
            "функции", "возможности", "что умеет", "можно ли",
            "price", "cost", "how much", "features"
        ],
        "max_messages": 8,
        "instruction": "СТАДИЯ: ИНТЕРЕС (Interest)\nЗадача: Дать конкретику и выявить боль.\nSPIN-фаза: Problem — ищи проблему клиента (\"С какими сложностями сталкиваетесь в продажах?\").\nТон: Экспертный, но не перегружай.\nЦель вопроса: Понять проблему и потребность.\nИнструменты: calculate_price, show_portfolio.\nМикро-обязательство: \"Хотите посчитаю стоимость под ваши задачи?\""
    },
    "consideration": {
        "keywords": [
            "сравнить", "альтернатив", "конкурент", "другие",
            "а если", "гарантии", "а точно", "подумаю", "думаю",
            "сомневаюсь", "не уверен", "риск", "compare"
        ],
        "max_messages": 15,
        "instruction": "СТАДИЯ: РАССМОТРЕНИЕ (Consideration)\nЗадача: Снять сомнения и показать ценность.\nSPIN-фаза: Implication — усиль боль бездействия (\"Сколько клиентов вы теряете каждый день без приложения?\").\nТон: Уверенный, с социальными доказательствами.\nЦель вопроса: Подвести к осознанию стоимости бездействия.\nИнструменты: calculate_roi, compare_plans, check_discount.\nМикро-обязательство: \"Давайте покажу, как это решается за 10 дней?\"\nВизуализация: \"Представьте: через 2 недели ваши клиенты заказывают прямо в Telegram.\""
    },
    "decision": {
        "keywords": [
            "заказ", "оформить", "давайте", "начинаем", "договор",
            "контракт", "когда начнём", "готов", "хочу заказать",
            "записаться", "консультация", "созвон", "let's start",
            "бриф", "ТЗ", "техническое задание"
        ],
        "max_messages": 999,
        "instruction": "СТАДИЯ: РЕШЕНИЕ (Decision)\nЗадача: Закрыть сделку, зафиксировать договорённости.\nSPIN-фаза: Need-Payoff — клиент сам видит ценность (\"Как изменятся ваши продажи с приложением?\").\nТон: Деловой, конкретный, без лишних слов.\nЦель вопроса: Получить обязательство на конкретный шаг.\nИнструменты: generate_brief, schedule_consultation, create_lead.\nМикро-обязательство: \"Когда удобно обсудить детали — сегодня или завтра?\""
    },
    "action": {
        "keywords": [
            "оплат", "оплачу", "реквизиты", "перевод", "карта",
            "счёт", "invoice", "pay", "payment", "рассрочка"
        ],
        "max_messages": 999,
        "instruction": "СТАДИЯ: ОПЛАТА (Action)\nЗадача: Упростить процесс оплаты.\nТон: Поддерживающий, чёткий.\nИнструменты: show_payment_info.\nНапомни: рассрочка 35%+65%, договор до оплаты.\nУбери последние сомнения: \"14 дней правок бесплатно, гарантия возврата предоплаты.\""
    }
}


MOMENTUM_PATTERNS = {
    "low_engagement": [
        "ок", "ok", "угу", "ага", "да", "нет", "понял", "ясно",
        "хорошо", "ладно", "мм", "ну", "fine", "sure", "yeah"
    ],
    "topic_drift": [
        "а кстати", "вообще", "by the way", "кстати",
        "не связано", "другой вопрос", "а ещё"
    ]
}

MOMENTUM_STRATEGIES = {
    "low_engagement": "MOMENTUM НИЗКИЙ: Клиент даёт короткие ответы — теряет интерес. Смени тактику:\n• Задай провокационный вопрос (\"А вы знали, что 70% клиентов уходят к конкурентам из-за неудобного заказа?\")\n• Используй контраст (\"Сейчас vs через 10 дней с приложением\")\n• Предложи конкретный визуальный пример\n• Или прямо спроси: \"Что для вас сейчас самое важное?\"",
    "topic_drift": "MOMENTUM ДРЕЙФ: Клиент уходит от темы. Мягко верни:\n• Ответь кратко на отвлечённый вопрос\n• Свяжи его с основной темой\n• \"Кстати, возвращаясь к вашему проекту...\""
}



VALID_BUTTON_ACTIONS = {
    'smart_prices', 'smart_portfolio', 'smart_faq', 'smart_calc',
    'smart_roi', 'smart_discount', 'smart_brief', 'smart_lead',
    'smart_payment', 'smart_contract'
}


def parse_ai_buttons(ai_response: str) -> tuple:
    import re
    pattern = r'\[BUTTONS:\s*(.+?)\]\s*$'
    match = re.search(pattern, ai_response, re.DOTALL)

    if not match:
        clean = re.sub(r'\[BUTTONS:.*', '', ai_response, flags=re.DOTALL).rstrip()
        return clean, []

    clean_response = ai_response[:match.start()].rstrip()

    buttons_str = match.group(1).strip()
    buttons = []

    for part in buttons_str.split(','):
        part = part.strip()
        if '|' not in part:
            continue
        action_id, button_text = part.split('|', 1)
        action_id = action_id.strip()
        button_text = button_text.strip()

        if action_id in VALID_BUTTON_ACTIONS and button_text and len(button_text) <= 40:
            buttons.append((button_text, action_id))

    return clean_response, buttons[:2]


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


def detect_momentum(text: str) -> Optional[str]:
    text_lower = text.strip().lower()
    if len(text_lower) <= 15:
        for pattern in MOMENTUM_PATTERNS["low_engagement"]:
            if text_lower == pattern or text_lower.rstrip(".!,") == pattern:
                return "low_engagement"
    for pattern in MOMENTUM_PATTERNS["topic_drift"]:
        if pattern in text_lower:
            return "topic_drift"
    return None


SEMANTIC_INTENT_PATTERNS = {
    "action": [
        "хочу оплатить", "готов оплатить", "выставьте счёт", "куда переводить",
        "как оплатить", "давайте к оплате", "оплачу сегодня", "присылайте реквизиты",
        "хочу купить", "беру", "оформляю"
    ],
    "decision": [
        "давайте начнём", "хочу заказать", "готов начать", "мне нужно это",
        "когда сможете начать", "сделайте мне", "я решил", "берём",
        "нужно сделать", "хочу такое же", "мне подходит", "записывайте",
        "автоматизировать заказы", "нужно приложение", "хочу приложение",
        "нужен бот", "сделайте приложение", "закажу",
        "нужно автоматизировать", "хочу автоматизировать",
        "нужна запись онлайн", "хочу онлайн-магазин",
        "хочу принимать заказы", "нужен каталог",
        "подключить оплату", "нужна доставка в приложении"
    ],
    "consideration": [
        "а если сравнить", "какие гарантии", "а вдруг не получится",
        "стоит ли", "окупится ли", "имеет ли смысл", "не уверен что нужно",
        "а что если", "чем отличается", "какая разница между",
        "может подождать", "надо подумать", "посоветуюсь",
        "а что будет если", "насколько надёжно", "а вы точно сделаете",
        "а есть отзывы", "покажите результаты", "долго ли делать"
    ],
    "interest": [
        "сколько это стоит", "какие цены", "какие сроки", "что входит",
        "расскажите подробнее", "какие функции", "что умеет",
        "можно ли сделать", "есть примеры", "покажите работы",
        "как выглядит", "интересно узнать", "а можно", "а есть",
        "из чего складывается цена", "что включено в стоимость",
        "какие варианты есть", "а можно дешевле", "есть рассрочка"
    ]
}

BACKSLIDE_PATTERNS = [
    "подумаю", "не уверен", "дорого", "позже", "не сейчас",
    "сомневаюсь", "не готов", "рано ещё", "другие варианты",
    "нужно посоветоваться", "не знаю нужно ли", "пока не надо",
    "передумал", "отложим", "не актуально", "пока нет",
    "нужно обсудить с партнёром", "посоветуюсь с командой",
    "может потом", "не сегодня", "вернусь позже"
]


def detect_funnel_stage(user_id: int, user_message: str, message_count: int = 0) -> str:
    text_lower = user_message.lower()

    lead_score = 0
    lead_actions = set()
    lead_tags = set()
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead:
            lead_score = lead.score or 0
            if lead.tags:
                lead_tags = set(lead.tags)
            events: list = []
            if hasattr(lead_manager, 'get_events'):
                events = lead_manager.get_events(user_id)  # type: ignore[attr-defined]
            for ev in events:
                event_type = ev.get("event_type", "") if isinstance(ev, dict) else ""
                lead_actions.add(event_type)
    except Exception:
        pass

    has_backslide = any(bp in text_lower for bp in BACKSLIDE_PATTERNS)

    keyword_stage = _keyword_stage(text_lower, lead_actions, message_count)
    semantic_stage = _semantic_stage(text_lower)
    score_stage = _score_stage(lead_score)

    stage_priority = {"awareness": 0, "interest": 1, "consideration": 2, "decision": 3, "action": 4}

    candidates = [keyword_stage, semantic_stage, score_stage]
    best = max(candidates, key=lambda s: stage_priority.get(s, 0))

    if has_backslide and stage_priority.get(best, 0) >= 3:
        best = "consideration"
    elif has_backslide and stage_priority.get(best, 0) >= 2:
        best = "interest"

    if "ready_to_buy" in lead_tags and not has_backslide:
        if stage_priority.get(best, 0) < 3:
            best = "decision"

    return best


def _keyword_stage(text_lower: str, lead_actions: set, message_count: int) -> str:
    if any(kw in text_lower for kw in FUNNEL_STAGE_SIGNALS["action"]["keywords"]):
        return "action"
    if any(kw in text_lower for kw in FUNNEL_STAGE_SIGNALS["decision"]["keywords"]):
        return "decision"
    if any("payment" in a or "lead" in a or "contact" in a for a in lead_actions):
        return "decision"
    if any(kw in text_lower for kw in FUNNEL_STAGE_SIGNALS["consideration"]["keywords"]):
        return "consideration"
    if any("calc" in a or "portfolio" in a or "price" in a for a in lead_actions):
        return "consideration"
    if any(kw in text_lower for kw in FUNNEL_STAGE_SIGNALS["interest"]["keywords"]):
        return "interest"
    if message_count > FUNNEL_STAGE_SIGNALS["awareness"]["max_messages"]:
        return "interest"
    return "awareness"


def _semantic_stage(text_lower: str) -> str:
    for stage in ["action", "decision", "consideration", "interest"]:
        patterns = SEMANTIC_INTENT_PATTERNS.get(stage, [])
        matches = sum(1 for p in patterns if p in text_lower)
        if matches >= 1:
            return stage
    return "awareness"


def _score_stage(lead_score: int) -> str:
    if lead_score >= 60:
        return "action"
    if lead_score >= 40:
        return "decision"
    if lead_score >= 20:
        return "consideration"
    if lead_score >= 5:
        return "interest"
    return "awareness"


def detect_client_style(user_message: str, message_count: int = 0) -> Optional[str]:
    text = user_message.strip()
    word_count = len(text.split())

    if word_count <= 5 and message_count > 2:
        return "СТИЛЬ: Лаконичный. Клиент пишет коротко — отвечай так же: 1-2 предложения, суть без воды. Не задавай лишних вопросов."

    if word_count >= 50:
        return "СТИЛЬ: Развёрнутый. Клиент пишет подробно — можешь дать более детальный ответ (до 150 слов). Покажи, что внимательно прочитал."

    has_formal = any(w in text.lower() for w in ["уважаемый", "прошу", "будьте добры", "не могли бы", "соблаговолите"])
    if has_formal:
        return "СТИЛЬ: Формальный. Клиент общается официально — будь вежливее, на \"вы\", без разговорных оборотов и )."

    has_casual = any(w in text.lower() for w in ["чё", "ваще", "норм", "ок", "го", "хз", "кста", "чел", "тип"])
    if has_casual:
        return "СТИЛЬ: Неформальный. Клиент общается свободно — будь проще, используй ), мессенджерный стиль."

    return None


PROACTIVE_VALUE_BY_INDUSTRY = {
    "shop": "ЦЕННОСТЬ: Для интернет-магазинов — средний рост конверсии при переходе на Mini App составляет 35-45%, потому что клиент не уходит из Telegram. Предложи: \"Хотите, прикину сколько дополнительных заказов это даст при вашем трафике?\"",
    "restaurant": "ЦЕННОСТЬ: Для ресторанов — Mini App убирает комиссию агрегаторов (15-30%). При 100 заказах/мес по 1500₽ экономия = 22-45к/мес. Предложи: \"Давайте посчитаю, сколько вы отдаёте агрегаторам — цифры обычно удивляют\"",
    "beauty": "ЦЕННОСТЬ: Для салонов красоты — автоматическая запись через Mini App сокращает no-show на 40% (напоминания в Telegram). Предложи: \"Знаете, сколько денег теряется на отменах и неявках? Могу прикинуть.\"",
    "fitness": "ЦЕННОСТЬ: Для фитнеса — трекинг прогресса и расписание в приложении удерживает клиентов на 60% дольше (LTV растёт). Предложи: \"Хотите, покажу как другие клубы увеличили retention?\"",
    "medical": "ЦЕННОСТЬ: Для клиник — онлайн-запись через Telegram увеличивает заполняемость на 25%. Удобство пациента = лояльность. Предложи: \"Давайте прикинем, сколько пациентов вы теряете из-за неудобной записи?\"",
    "ai": "ЦЕННОСТЬ: AI-бот обрабатывает 70-80% типовых вопросов без участия человека, 24/7. Экономия на 1 сотруднике поддержки = 80-120к/мес. Предложи: \"Могу показать демо AI-бота из похожей ниши\"",
    "services": "ЦЕННОСТЬ: Для сервисных компаний — онлайн-запись через Mini App убирает 60% звонков. Клиенты бронируют сами 24/7, вы не теряете заказы в нерабочее время. Предложи: \"Давайте прикинем, сколько заказов вы теряете из-за занятого телефона?\"",
    "education": "ЦЕННОСТЬ: Для образования — Mini App с расписанием и напоминаниями повышает доходимость на 40-55%. Оплата прямо в Telegram без ухода на сайт. Предложи: \"Хотите, покажу как другие школы увеличили доходимость?\"",
    "delivery": "ЦЕННОСТЬ: Для доставки — собственный Mini App вместо агрегатора экономит 15-30% комиссий. При 200 заказах/мес экономия = 45-90к/мес. Предложи: \"Давайте посчитаю, сколько вы отдаёте агрегаторам — цифры обычно удивляют\"",
}

PROACTIVE_VALUE_BY_STAGE = {
    "awareness": "Подготовил для вас мини-чек-лист \"5 вопросов перед запуском Mini App\" — помогает понять что нужно. Показать?",
    "interest": "У нас есть бесплатный расчёт стоимости — указываете функции, получаете точную цифру. Хотите попробовать?",
    "consideration": "Могу подготовить для вас персональное сравнение: ваши затраты сейчас vs. с Mini App. Это бесплатно и ни к чему не обязывает.",
    "decision": "Могу прямо сейчас набросать для вас предварительное ТЗ — это бесплатно и даст понимание всего объёма работ.",
}


def get_proactive_value(user_id: int, funnel_stage: str) -> str:
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead and lead.tags:
            for tag in lead.tags:
                if tag in PROACTIVE_VALUE_BY_INDUSTRY:
                    return f"[ПРОАКТИВНАЯ ЦЕННОСТЬ]\n{PROACTIVE_VALUE_BY_INDUSTRY[tag]}"
    except Exception:
        pass

    if funnel_stage in PROACTIVE_VALUE_BY_STAGE:
        return f"[ПРОАКТИВНАЯ ЦЕННОСТЬ]\n{PROACTIVE_VALUE_BY_STAGE[funnel_stage]}"
    return ""


INDUSTRY_CASE_STUDIES = {
    "shop": {
        "name": "Radiance",
        "desc": "магазин премиум-одежды",
        "result": "200+ заказов за первую неделю, конверсия из Telegram в покупку 12%. Средний чек 4 500₽. Шаблон магазина 150к + доп. функции = 200к. Окупилось за 25 дней",
        "quote": "Жалею что не сделал раньше — за месяц окупилось дважды. Клиенты покупают прямо в чате, без регистрации",
        "metrics": {"investment": 200000, "payback_days": 25, "monthly_revenue_increase": 240000}
    },
    "restaurant": {
        "name": "DeluxeDine",
        "desc": "ресторан с доставкой, 150+ заказов/мес",
        "result": "Ушли с агрегатора. Шаблон ресторана 180к + доп. функции = 230к. Экономия 35к/мес на комиссиях (420к/год). +47 новых заказов в первый месяц при среднем чеке 1 800₽",
        "quote": "Агрегаторы забирали 25% с каждого заказа — теперь вся маржа наша. За год экономия покрыла стоимость приложения дважды",
        "metrics": {"investment": 230000, "payback_days": 45, "monthly_savings": 35000}
    },
    "beauty": {
        "name": "GlowSpa",
        "desc": "салон красоты, 8 мастеров",
        "result": "No-show упал с 22% до 12% (на 45%). Загрузка мастеров выросла с 65% до 90%. Это +150к/мес выручки при среднем чеке 3 200₽",
        "quote": "Пустые кресла стоили мне 30-40к в месяц. Клиенты теперь записываются сами, даже в 2 часа ночи",
        "metrics": {"investment": 200000, "payback_days": 40, "monthly_revenue_increase": 150000, "noshow_reduction": "45%"}
    },
    "fitness": {
        "name": "FitPro",
        "desc": "фитнес-клуб, 400 активных членов",
        "result": "Retention вырос на 35% — клиенты продлевают абонементы. LTV клиента вырос с 18к до 28к. Прирост выручки +120к/мес",
        "quote": "Трекинг прогресса — главная фишка. Люди видят результат и остаются. Раньше 67% уходили через 3 месяца",
        "metrics": {"investment": 230000, "payback_days": 58, "ltv_increase": "55%", "retention_boost": "35%"}
    },
    "medical": {
        "name": "MedLine",
        "desc": "многопрофильная клиника, 12 врачей",
        "result": "Заполняемость слотов +30% (с 68% до 88%). No-show -50%. Администраторы освободили 3 часа/день. Доп. выручка +280к/мес",
        "quote": "Пациенты записываются сами через Telegram. Администраторы наконец занимаются сервисом, а не телефоном",
        "metrics": {"investment": 250000, "payback_days": 27, "monthly_revenue_increase": 280000, "admin_hours_saved": 3}
    },
    "services": {
        "name": "CleanPro",
        "desc": "клининговый сервис, 25 заказов/день",
        "result": "Конверсия из заявки в заказ +40%. Повторные заказы +25%. Звонков стало на 60% меньше. Прирост выручки +95к/мес",
        "quote": "Клиенты заказывают уборку в два клика. Мы перестали терять заказы из-за занятой линии",
        "metrics": {"investment": 170000, "payback_days": 54, "repeat_order_increase": "25%", "calls_reduction": "60%"}
    },
    "education": {
        "name": "SkillUp",
        "desc": "онлайн-школа, 200+ учеников",
        "result": "Доходимость до конца курса +55% (с 35% до 54%). Средний чек +20%. Возвраты снизились на 40%. Доп. выручка +180к/мес",
        "quote": "Ученики не забывают про занятия — напоминания прямо в Telegram. Меньше возвратов, больше сарафана",
        "metrics": {"investment": 195000, "payback_days": 33, "completion_rate_increase": "55%", "refund_reduction": "40%"}
    },
    "delivery": {
        "name": "FreshBox",
        "desc": "доставка продуктов, 200 заказов/мес",
        "result": "Убрали комиссию агрегатора 22%. Экономия 66к/мес (792к/год). Повторные заказы +30% за счёт push-уведомлений",
        "quote": "Агрегатор забирал пятую часть выручки. Теперь клиенты заказывают напрямую, и мы знаем каждого по имени",
        "metrics": {"investment": 215000, "payback_days": 98, "monthly_savings": 66000, "repeat_increase": "30%"}
    },
}


def get_relevant_case_study(user_id: int) -> str:
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead and lead.tags:
            for tag in lead.tags:
                if tag in INDUSTRY_CASE_STUDIES:
                    cs = INDUSTRY_CASE_STUDIES[tag]
                    metrics = cs.get("metrics", {})
                    metrics_line = ""
                    if metrics:
                        parts = []
                        if "investment" in metrics:
                            parts.append(f"Инвестиция: {metrics['investment']//1000}к")
                        if "payback_days" in metrics:
                            parts.append(f"Окупаемость: {metrics['payback_days']} дней")
                        if "monthly_revenue_increase" in metrics:
                            parts.append(f"Прирост выручки: +{metrics['monthly_revenue_increase']//1000}к/мес")
                        if "monthly_savings" in metrics:
                            parts.append(f"Экономия: {metrics['monthly_savings']//1000}к/мес")
                        if parts:
                            metrics_line = f"\nМетрики: {', '.join(parts)}"
                    return (
                        f"[РЕЛЕВАНТНЫЙ КЕЙС — {cs['name']}]\n"
                        f"Проект: {cs['name']} ({cs['desc']})\n"
                        f"Результат: {cs['result']}\n"
                        f"Отзыв клиента: \"{cs['quote']}\""
                        f"{metrics_line}"
                    )
    except Exception:
        pass
    return ""


def get_social_proof(objections: list, funnel_stage: str) -> str:
    proofs = []
    for obj in objections:
        if obj in SOCIAL_PROOF_TRIGGERS:
            import random
            proof = random.choice(SOCIAL_PROOF_TRIGGERS[obj])
            proofs.append(proof)

    if not proofs and funnel_stage in ("consideration", "decision"):
        import random
        all_proofs = []
        for v in SOCIAL_PROOF_TRIGGERS.values():
            all_proofs.extend(v)
        if all_proofs:
            proofs.append(random.choice(all_proofs))

    if proofs:
        return "[СОЦИАЛЬНОЕ ДОКАЗАТЕЛЬСТВО — используй естественно в ответе]\n" + "\n".join(proofs)
    return ""


def build_client_context(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> str:
    context_parts = []

    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead:
            context_parts.append("[ПРОФИЛЬ КЛИЕНТА]")
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
        from src.handlers.utils import loyalty_system
        if loyalty_system.is_returning_customer(user_id):
            context_parts.append("Статус: постоянный клиент (+5% скидка)")
        reviews = loyalty_system.get_user_reviews(user_id)
        if reviews:
            context_parts.append(f"Оставил {len(reviews)} отзывов")
    except Exception as e:
        logger.debug(f"Failed to get loyalty data: {e}")

    try:
        from src.referrals import referral_manager
        referrals = referral_manager.get_referrals_list(user_id)
        if referrals:
            context_parts.append(f"Привёл {len(referrals)} рефералов")
    except Exception as e:
        logger.debug(f"Failed to get referral data: {e}")

    try:
        from src.leads import lead_manager
        events: list = []
        if hasattr(lead_manager, 'get_events'):
            events = lead_manager.get_events(user_id)  # type: ignore[attr-defined]
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

    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile:
            profile_parts = []
            if profile.get("industry"):
                profile_parts.append(f"Отрасль: {profile['industry']}")
            if profile.get("budget_range"):
                profile_parts.append(f"Бюджет: {profile['budget_range']}")
            if profile.get("timeline"):
                profile_parts.append(f"Сроки: {profile['timeline']}")
            if profile.get("needs"):
                profile_parts.append(f"Потребности: {profile['needs']}")
            if profile.get("objections"):
                profile_parts.append(f"Возражения: {profile['objections']}")
            if profile.get("business_name"):
                profile_parts.append(f"Бизнес: {profile['business_name']}")
            if profile.get("city"):
                profile_parts.append(f"Город: {profile['city']}")
            if profile_parts:
                context_parts.append("[ДОЛГОСРОЧНЫЙ ПРОФИЛЬ]\n" + "\n".join(profile_parts))
    except Exception as e:
        logger.debug(f"Failed to get client profile: {e}")

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


BANT_BUDGET_PATTERNS = [
    (r'бюджет\s+(\d[\d\s]*\d?)\s*(к|тыс|руб|₽|р)', True),
    (r'готов[аы]?\s+заплатить\s+(\d[\d\s]*\d?)\s*(к|тыс|руб|₽|р)', True),
    (r'до\s+(\d[\d\s]*\d?)\s*(к|тыс|руб|₽|р)', True),
    (r'(\d{2,})\s*(к|тыс|руб|₽|р)', True),
    (r'(\d[\d\s]*\d?)\s*рублей', True),
    (r'есть\s+(\d[\d\s]*\d?)\s*(к|тыс)', True),
    (r'выделил[иа]?\s+(\d[\d\s]*\d?)', True),
]

BANT_LPR_PATTERNS = [
    "я решаю", "мой бизнес", "мой магазин", "я владелец", "я собственник",
    "мой проект", "я директор", "я основатель", "моя компания", "я предприниматель",
    "сам решаю", "моя студия", "мой салон", "моё кафе", "мой ресторан",
]

BANT_NON_LPR_PATTERNS = [
    "посоветуюсь", "покажу директору", "мне поручили", "надо обсудить",
    "покажу руководству", "согласовать с", "одобрение руководства",
    "спрошу у шефа", "уточню у начальства", "покажу боссу",
    "отправлю руководителю", "мне дали задачу", "нас попросили",
]

BANT_URGENCY_HIGH = [
    "срочно", "быстрее", "скорее", "сейчас", "немедленно", "горит",
    "вчера нужно было", "время поджимает", "asap", "urgent", "дедлайн",
    "запуск скоро", "к запуску", "нужно вчера",
]

BANT_URGENCY_MEDIUM = [
    "планируем", "хотим сделать", "рассматриваем", "думаем о",
    "присматриваемся", "изучаем варианты", "в ближайшее время",
]

BANT_TIMELINE_PATTERNS = [
    (r'к\s+(лету|осени|зиме|весне)', 'к сезону'),
    (r'через\s+(месяц|два|три|неделю|пару\s+недель)', 'через указанный срок'),
    (r'до\s+конца\s+(года|месяца|квартала)', 'до конца периода'),
    (r'в\s+(январ|феврал|март|апрел|ма[йе]|июн|июл|август|сентябр|октябр|ноябр|декабр)', 'к конкретному месяцу'),
    (r'срочно|как\s+можно\s+скорее|asap', 'срочно'),
    (r'на\s+следующей\s+неделе', 'на следующей неделе'),
    (r'в\s+этом\s+месяце', 'в этом месяце'),
]


def detect_bant_signals(text: str, user_id: int) -> dict:
    text_lower = text.lower()
    result = {
        "budget_detected": False,
        "budget_amount": None,
        "authority_detected": None,
        "is_lpr": None,
        "need_urgency": "low",
        "timeline_detected": None,
    }

    for pattern, _ in BANT_BUDGET_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            result["budget_detected"] = True
            result["budget_amount"] = match.group(0).strip()
            break

    for p in BANT_LPR_PATTERNS:
        if p in text_lower:
            result["authority_detected"] = "lpr"
            result["is_lpr"] = True
            break

    if result["is_lpr"] is None:
        for p in BANT_NON_LPR_PATTERNS:
            if p in text_lower:
                result["authority_detected"] = "non_lpr"
                result["is_lpr"] = False
                break

    if any(w in text_lower for w in BANT_URGENCY_HIGH):
        result["need_urgency"] = "high"
    elif any(w in text_lower for w in BANT_URGENCY_MEDIUM):
        result["need_urgency"] = "medium"

    for pattern, label in BANT_TIMELINE_PATTERNS:
        if re.search(pattern, text_lower):
            result["timeline_detected"] = label
            break

    return result


def _format_bant_context(bant: dict) -> Optional[str]:
    parts = []
    if bant["budget_detected"]:
        parts.append(f"💰 Бюджет обнаружен: {bant['budget_amount']}")
    if bant["is_lpr"] is True:
        parts.append("👤 ЛПР: Да — клиент принимает решения сам. Можно обсуждать цены и закрытие сделки напрямую.")
    elif bant["is_lpr"] is False:
        parts.append("👤 ЛПР: Нет — клиент не принимает решение сам. Подготовь материалы, которые он покажет руководству. Дай чёткое КП.")
    if bant["need_urgency"] == "high":
        parts.append("🔥 Срочность: ВЫСОКАЯ — предлагай быстрые решения, конкретные сроки, не затягивай диалог.")
    elif bant["need_urgency"] == "medium":
        parts.append("⏳ Срочность: СРЕДНЯЯ — клиент активно рассматривает. Показывай ценность, не дави.")
    if bant["timeline_detected"]:
        parts.append(f"📅 Таймлайн: {bant['timeline_detected']}")
    if not parts:
        return None
    return "[BANT-АНАЛИЗ]\n" + "\n".join(parts)


DECISION_MAKER_LPR = [
    "я владелец", "мой магазин", "я решаю", "мой бизнес", "я собственник",
    "я директор", "моя компания", "сам решаю", "я основатель", "я предприниматель",
    "моё заведение", "мой салон", "моё кафе", "мой ресторан", "мой проект",
]

DECISION_MAKER_NON_LPR = [
    "мне поручили", "надо обсудить с директором", "покажу руководству",
    "посоветуюсь", "согласовать с руководством", "покажу директору",
    "уточню у начальства", "мне дали задание", "спрошу у шефа",
    "нас попросили найти", "подготовлю презентацию для",
]


def detect_decision_maker(text: str) -> Optional[str]:
    text_lower = text.lower()
    for p in DECISION_MAKER_LPR:
        if p in text_lower:
            return "[ЛПР-ДЕТЕКТ]\nКлиент — лицо, принимающее решение. Обсуждай цены, сроки и закрытие сделки напрямую. Предлагай конкретные следующие шаги: бриф, созвон, предоплата."
    for p in DECISION_MAKER_NON_LPR:
        if p in text_lower:
            return "[ЛПР-ДЕТЕКТ]\nКлиент НЕ является ЛПР. Стратегия: 1) Подготовь краткое КП с цифрами ROI, которое легко переслать. 2) Предложи созвон с ЛПР. 3) Дай аргументы, которые клиент может использовать для внутренней продажи. 4) Не дави на закрытие — помоги 'продать' идею внутри компании."
    budget_patterns = [r'\d+\s*(к|тыс|руб|₽)', r'бюджет']
    for p in budget_patterns:
        if re.search(p, text_lower):
            return "[ЛПР-ДЕТЕКТ]\nКлиент обсуждает бюджет — вероятно, имеет полномочия. Действуй как с ЛПР, но уточни: 'Вы принимаете решение по этому проекту?'"
    return None


NEGOTIATION_HARD_PATTERNS = [
    "или я ухожу", "последнее предложение", "либо скидка либо",
    "у конкурентов дешевле", "не буду платить столько", "снижайте цену",
    "ультиматум", "или делайте скидку", "иначе найду другого",
    "мне предложили дешевле", "максимум могу", "больше не дам",
]

NEGOTIATION_ANALYTICAL_PATTERNS = [
    "сравнить", "в чём разница", "какие метрики", "статистика",
    "покажите данные", "какой roi", "окупаемость", "сравнение",
    "детальный расчёт", "а если разложить", "из чего складывается",
    "какие kpi", "benchmarks", "аналитика",
]

NEGOTIATION_EMOTIONAL_PATTERNS = [
    "у меня проблема", "так устал от", "мечтаю о", "боюсь что",
    "это моя мечта", "наконец-то", "надоело мучиться", "хочу чтобы",
    "представляете", "вы не поверите", "ужас что творится",
    "так рад", "невероятно", "история такая",
]

NEGOTIATION_SOFT_PATTERNS = [
    "наверное", "может быть", "не уверен", "не знаю стоит ли",
    "возможно позже", "надо подумать", "не хотелось бы", "как бы",
    "вроде бы", "не совсем", "ну не знаю",
]

NEGOTIATION_HINTS = {
    "hard": "[СТИЛЬ ПЕРЕГОВОРОВ: ЖЁСТКИЙ]\nКлиент давит, требует скидки или угрожает уходом. Стратегия:\n• НЕ поддавайся на давление и НЕ снижай цену сразу\n• Покажи ценность: 'Я понимаю, вы хотите лучшую цену. Давайте посмотрим, что входит в эту стоимость...'\n• Предложи альтернативу вместо скидки: рассрочка, бонусы, расширенная поддержка\n• Если клиент сравнивает — попроси конкретику: 'Что именно предлагают? Давайте сравним функционал'",
    "analytical": "[СТИЛЬ ПЕРЕГОВОРОВ: АНАЛИТИЧЕСКИЙ]\nКлиент хочет данные и детали. Стратегия:\n• Давай цифры, ROI, кейсы с конкретными метриками\n• Предложи детальный расчёт: calculate_price, calculate_roi\n• Не торопи — дай время на анализ\n• Структурируй информацию: списки, сравнения, таблицы",
    "emotional": "[СТИЛЬ ПЕРЕГОВОРОВ: ЭМОЦИОНАЛЬНЫЙ]\nКлиент делится историей/эмоциями. Стратегия:\n• Прояви эмпатию: 'Понимаю, это действительно важно для вас'\n• Используй storytelling — расскажи похожий кейс клиента\n• Визуализируй результат: 'Представьте, через 2 недели ваши клиенты...'\n• Поддерживай эмоциональный контакт, не переходи резко к цифрам",
    "soft": "[СТИЛЬ ПЕРЕГОВОРОВ: МЯГКИЙ]\nКлиент сомневается, избегает прямых решений. Стратегия:\n• Убери давление: 'Никуда не торопимся, давайте разберёмся'\n• Предлагай микро-шаги: бесплатный расчёт, просто посмотреть портфолио\n• Задавай уточняющие вопросы: 'Что именно смущает?'\n• Используй foot-in-the-door: маленькое 'да' ведёт к большому",
}


def detect_negotiation_stance(text: str) -> Optional[str]:
    text_lower = text.lower()
    scores = {"hard": 0, "analytical": 0, "emotional": 0, "soft": 0}
    for p in NEGOTIATION_HARD_PATTERNS:
        if p in text_lower:
            scores["hard"] += 1
    for p in NEGOTIATION_ANALYTICAL_PATTERNS:
        if p in text_lower:
            scores["analytical"] += 1
    for p in NEGOTIATION_EMOTIONAL_PATTERNS:
        if p in text_lower:
            scores["emotional"] += 1
    for p in NEGOTIATION_SOFT_PATTERNS:
        if p in text_lower:
            scores["soft"] += 1
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return None
    return NEGOTIATION_HINTS[best]


def analyze_conversation_velocity(user_id: int, message_count: int, session=None) -> Optional[str]:
    if message_count < 3:
        return None
    try:
        if session and hasattr(session, 'created_at') and hasattr(session, 'last_activity'):
            elapsed = session.last_activity - session.created_at
            if elapsed > 0 and message_count > 0:
                avg_interval = elapsed / message_count
                if avg_interval < 30:
                    return "[VELOCITY: ВЫСОКАЯ]\nКлиент отвечает быстро (<30 сек) — высокая вовлечённость. Используй момент: предлагай конкретные следующие шаги, не затягивай ответы. Можно push'ить к решению."
                elif avg_interval < 120:
                    return None
                elif avg_interval > 300:
                    return "[VELOCITY: НИЗКАЯ]\nКлиент отвечает медленно (>5 мин) — возможно теряет интерес. Смени тактику: задай интригующий вопрос, предложи новый ракурс, дай value-бомбу (кейс, расчёт ROI)."
        if session and hasattr(session, 'messages') and len(session.messages) >= 4:
            user_msgs = [m for m in session.messages if m.get('role') == 'user']
            if len(user_msgs) >= 2:
                recent = user_msgs[-3:]
                short_count = sum(1 for m in recent if len(m.get('parts', [{}])[0].get('text', '')) < 10)
                if short_count >= 2:
                    return "[VELOCITY: ЗАТУХАНИЕ]\nПоследние сообщения клиента становятся всё короче — признак потери интереса. Задай открытый вопрос или предложи конкретный визуальный пример."
    except Exception as e:
        logger.debug(f"Velocity analysis error: {e}")
    return None


POSITIVE_WORDS = [
    "круто", "отлично", "супер", "класс", "здорово", "нравится", "интересно",
    "хорошо", "да", "давайте", "согласен", "подходит", "то что нужно",
    "впечатляет", "wow", "amazing", "great", "perfect", "cool", "огонь",
]

NEGATIVE_WORDS = [
    "плохо", "дорого", "не нравится", "не подходит", "сомневаюсь", "нет",
    "не уверен", "не хочу", "не надо", "не интересно", "отстой", "ужас",
    "разочарован", "обман", "мошенники", "не верю", "не устраивает",
]


def detect_sentiment_trajectory(messages_history: list) -> Optional[str]:
    if not messages_history or len(messages_history) < 4:
        return None
    try:
        user_messages = [m for m in messages_history if m.get('role') == 'user']
        if len(user_messages) < 4:
            return None
        half = len(user_messages) // 2
        first_half = user_messages[:half]
        second_half = user_messages[half:]

        def score_messages(msgs):
            pos, neg = 0, 0
            for m in msgs:
                text = m.get('parts', [{}])[0].get('text', '').lower()
                pos += sum(1 for w in POSITIVE_WORDS if w in text)
                neg += sum(1 for w in NEGATIVE_WORDS if w in text)
            return pos, neg

        pos1, neg1 = score_messages(first_half)
        pos2, neg2 = score_messages(second_half)

        if pos2 > pos1 + 1 and neg2 <= neg1:
            return "[ТРАЕКТОРИЯ НАСТРОЕНИЯ: УЛУЧШАЕТСЯ ↑]\nНастроение клиента улучшается — позитивных сигналов становится больше. Поддерживай текущий подход, усиливай momentum. Хороший момент для предложения следующего шага."
        elif neg2 > neg1 + 1 and pos2 <= pos1:
            return "[ТРАЕКТОРИЯ НАСТРОЕНИЯ: УХУДШАЕТСЯ ↓]\nНастроение клиента ухудшается — негативных сигналов становится больше. СРОЧНО: обратись к проблеме напрямую ('Чувствую, что-то смущает — расскажите?'). Смени тактику, покажи заботу, дай конкретную ценность."
        elif abs(pos2 - pos1) <= 1 and abs(neg2 - neg1) <= 1 and len(user_messages) > 6:
            return "[ТРАЕКТОРИЯ НАСТРОЕНИЯ: СТАБИЛЬНАЯ →]\nНастроение не меняется — клиент 'застрял'. Попробуй новый подход: неожиданный кейс, провокационный вопрос, визуализацию результата."
    except Exception as e:
        logger.debug(f"Sentiment trajectory error: {e}")
    return None


def analyze_question_density(text: str) -> Optional[str]:
    question_marks = text.count('?')
    question_words = sum(1 for w in ["как", "что", "почему", "зачем", "сколько", "когда", "какой", "какие", "можно ли", "а если", "где", "кто"] if w in text.lower())
    total_questions = max(question_marks, question_words)
    if total_questions >= 3:
        return "[ПЛОТНОСТЬ ВОПРОСОВ: ВЫСОКАЯ]\nКлиент задаёт много вопросов — высокий интерес! Дай исчерпывающие ответы на каждый вопрос по пунктам. Не упускай ни одного вопроса. После ответов предложи следующий шаг."
    elif total_questions == 0 and len(text.split()) > 5:
        return "[ПЛОТНОСТЬ ВОПРОСОВ: НУЛЕВАЯ]\nКлиент не задаёт вопросов — пассивный режим. Вовлеки: задай ему интересный вопрос о бизнесе или предложи интерактив (калькулятор, портфолио, кейс)."
    return None


BUDGET_EXPLICIT_PATTERNS = [
    (r'(\d[\d\s]*)\s*(к|тыс|руб|₽|р)\b', 'explicit'),
    (r'бюджет\s+(\d[\d\s]*)', 'explicit'),
    (r'от\s+(\d[\d\s]*)\s*до\s+(\d[\d\s]*)\s*(к|тыс|руб|₽)', 'range'),
]

BUDGET_IMPLICIT_SIGNALS = {
    "budget_low": ["недорого", "бюджетно", "экономно", "подешевле", "минимально", "самый дешёвый", "самое простое", "без лишнего"],
    "budget_high": ["премиум", "не жалко денег", "лучшее", "максимум функций", "всё включено", "под ключ", "vip", "топовый"],
    "budget_uncertain": ["ещё не решил", "зависит от", "надо посчитать", "сколько обычно", "какой диапазон"],
}


def detect_budget_signals(text: str) -> Optional[str]:
    text_lower = text.lower()
    for pattern, sig_type in BUDGET_EXPLICIT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            if sig_type == 'range':
                return f"[БЮДЖЕТ-СИГНАЛ]\nКлиент назвал диапазон бюджета: {match.group(0)}. Предложи оптимальный пакет в этом диапазоне. Покажи что входит. Если бюджет ниже минимального — предложи MVP или рассрочку."
            return f"[БЮДЖЕТ-СИГНАЛ]\nКлиент обозначил бюджет: {match.group(0)}. Подбери подходящий пакет. Если бюджет достаточный — подтверди что входит. Если недостаточный — предложи рассрочку или MVP-версию."

    for level, patterns in BUDGET_IMPLICIT_SIGNALS.items():
        for p in patterns:
            if p in text_lower:
                if level == "budget_low":
                    return "[БЮДЖЕТ-СИГНАЛ: ЭКОНОМНЫЙ]\nКлиент ищет бюджетное решение. НЕ обесценивай: покажи шаблон магазина (150к) как инвестицию с окупаемостью. Рассрочка: 52 500₽ предоплата. Монеты: скидки до 25%."
                elif level == "budget_high":
                    return "[БЮДЖЕТ-СИГНАЛ: ПРЕМИУМ]\nКлиент готов инвестировать в лучшее. Предлагай Premium/Enterprise пакеты с максимальным функционалом. Подчеркни эксклюзивность, персональный подход, расширенную поддержку."
                elif level == "budget_uncertain":
                    return "[БЮДЖЕТ-СИГНАЛ: НЕ ОПРЕДЕЛЁН]\nКлиент не определился с бюджетом. Предложи калькулятор цен (calculate_price). Покажи диапазон: от 150к (шаблон) до 369к (полный пакет). Помоги определиться через вопросы о функциях."
    return None


UPSELL_BY_INDUSTRY = {
    "shop": [
        {"trigger": "interest", "upsell": "AI-чат-бот для автоматической обработки вопросов о наличии, размерах и доставке — экономит 2-3 часа/день"},
        {"trigger": "decision", "upsell": "Push-уведомления о новых поступлениях и акциях — увеличивают повторные покупки на 30%"},
    ],
    "restaurant": [
        {"trigger": "interest", "upsell": "Программа лояльности с накопительными бонусами — увеличивает средний чек на 15%"},
        {"trigger": "decision", "upsell": "Интеграция с кухней: автоматическая отправка заказа на принтер — экономит время официантов"},
    ],
    "beauty": [
        {"trigger": "interest", "upsell": "Автоматические напоминания о записи за 24ч — снижает no-show на 45%"},
        {"trigger": "decision", "upsell": "Онлайн-витрина косметики с заказом прямо в приложении — дополнительные продажи до 50к/мес"},
    ],
    "fitness": [
        {"trigger": "interest", "upsell": "Трекинг прогресса с фото и метриками — удерживает клиентов на 60% дольше"},
        {"trigger": "decision", "upsell": "Автоматическое продление абонементов через Telegram Pay — снижает отток на 25%"},
    ],
    "medical": [
        {"trigger": "interest", "upsell": "Телемедицина через Mini App — консультации без визита, +20% к выручке"},
        {"trigger": "decision", "upsell": "Электронная медкарта пациента — экономит 15 мин на приёме, повышает лояльность"},
    ],
    "services": [
        {"trigger": "interest", "upsell": "Геолокация исполнителей в реальном времени — клиент видит где мастер, меньше звонков"},
        {"trigger": "decision", "upsell": "Автоматический расчёт стоимости по параметрам — убирает 80% вопросов 'сколько стоит?'"},
    ],
    "education": [
        {"trigger": "interest", "upsell": "Геймификация обучения: баллы, рейтинги, достижения — доходимость +40%"},
        {"trigger": "decision", "upsell": "Автоматическая выдача сертификатов после курса — экономит время и повышает ценность"},
    ],
}


def get_smart_upsell(user_id: int, funnel_stage: str) -> Optional[str]:
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if not lead or not lead.tags:
            return None

        events: list = []
        if hasattr(lead_manager, 'get_events'):
            events = lead_manager.get_events(user_id)  # type: ignore[attr-defined]
        discussed_topics = set()
        for ev in events:
            if isinstance(ev, dict):
                discussed_topics.add(ev.get("event_type", ""))

        for tag in lead.tags:
            if tag in UPSELL_BY_INDUSTRY:
                for item in UPSELL_BY_INDUSTRY[tag]:
                    stage_match = (
                        (item["trigger"] == "interest" and funnel_stage in ("interest", "consideration")) or
                        (item["trigger"] == "decision" and funnel_stage in ("decision", "action"))
                    )
                    if stage_match:
                        upsell_key = f"upsell_{tag}_{item['trigger']}"
                        if upsell_key not in discussed_topics:
                            return f"[SMART UPSELL — предложи ОДИН раз, мягко]\n{item['upsell']}\nПодача: 'Кстати, для вашей ниши хорошо работает ещё одна вещь...' — НЕ навязывай, упомяни один раз."
    except Exception as e:
        logger.debug(f"Smart upsell error: {e}")
    return None


def check_response_diversity(user_id: int) -> Optional[str]:
    try:
        from src.session import session_manager
        if user_id not in session_manager._sessions:
            return None
        session = session_manager._sessions[user_id]
        model_msgs = [m for m in session.messages if m.get('role') == 'model']
        if len(model_msgs) < 4:
            return None
        recent = model_msgs[-5:]
        openings = []
        for m in recent:
            text = m.get('parts', [{}])[0].get('text', '')
            first_line = text.split('\n')[0][:50] if text else ''
            openings.append(first_line.lower().strip())
        if len(openings) >= 3:
            unique_starts = set(o[:15] for o in openings if o)
            if len(unique_starts) <= 2:
                return "[РАЗНООБРАЗИЕ ОТВЕТОВ: НИЗКОЕ]\nПоследние ответы начинаются одинаково — клиент заметит шаблонность. ОБЯЗАТЕЛЬНО начни этот ответ по-другому: с вопроса, с факта, с кейса, с цифры, с комплимента бизнесу клиента."
    except Exception as e:
        logger.debug(f"Response diversity check error: {e}")
    return None


COMPETITOR_PATTERNS = {
    "botmother": {
        "patterns": ["botmother", "ботмазер", "бот мазер"],
        "response": "[КОНКУРЕНТ: Botmother]\nBotmother — конструктор ботов, НЕ Mini Apps. Ключевые отличия:\n• Botmother = чат-бот с кнопками, НЕ полноценное веб-приложение\n• Mini App = нативный UI внутри Telegram (каталог, корзина, оплата в 2 клика)\n• Конверсия Mini App в 3-5x выше чем у бота с кнопками\n• У нас: договор, дизайн, поддержка после запуска"
    },
    "flutterflow": {
        "patterns": ["flutterflow", "флаттерфлоу", "flutter flow"],
        "response": "[КОНКУРЕНТ: FlutterFlow]\nFlutterFlow — no-code для мобильных приложений. Отличия:\n• FlutterFlow = отдельное приложение (нужна установка из App Store/Google Play)\n• Mini App = работает прямо в Telegram, 900M+ аудитория, без установки\n• Стоимость разработки на FlutterFlow = 300-500к+ (дизайн, бэкенд, публикация)\n• Наш Mini App = от 150к, готово за 7-15 дней"
    },
    "tilda": {
        "patterns": ["tilda", "тильда"],
        "response": "[КОНКУРЕНТ: Tilda]\nTilda — конструктор сайтов, не Telegram Mini App. Отличия:\n• Tilda = сайт, куда клиент УХОДИТ из Telegram → потеря 60-70% конверсии\n• Mini App = клиент остаётся в мессенджере, покупка в 2 клика\n• Tilda: хостинг + домен + SSL = 3-5к/мес скрытых расходов\n• Mini App: нулевые расходы на инфраструктуру, всё внутри Telegram"
    },
    "wix": {
        "patterns": ["wix", "викс"],
        "response": "[КОНКУРЕНТ: Wix]\nWix — конструктор сайтов. Отличия:\n• Wix = отдельный сайт, клиент уходит из Telegram → теряете конверсию\n• Подписка Wix Business: от 23$/мес = 27к/год\n• Mini App: разовая инвестиция, нет ежемесячных платежей\n• В Telegram 900M+ пользователей — ваши клиенты УЖЕ там"
    },
    "freelancer": {
        "patterns": ["фрилансер", "freelancer", "фриланс", "freelance", "upwork", "fiverr", "kwork"],
        "response": "[КОНКУРЕНТ: Фрилансер]\nФрилансер vs наша команда:\n• Фрилансер: нет договора, сроки плывут, поддержки нет, пропадает\n• Мы: юридический договор, предоплата 35%+65%, гарантия возврата\n• Фрилансер: 2-4 месяца, результат непредсказуем\n• Мы: 7-15 дней, 20+ завершённых проектов, 14 дней правок бесплатно"
    },
    "agency": {
        "patterns": ["агентство", "студия разработки", "веб-студия", "agency", "другая компания", "другая студия"],
        "response": "[КОНКУРЕНТ: Агентство/Студия]\nАгентство vs мы:\n• Агентство: 300-800к, 2-4 месяца, делают ВСЁ (сайты, приложения, боты) — нет специализации\n• Мы: ТОЛЬКО Telegram Mini Apps — поэтому быстрее (7-15 дней) и дешевле (от 150к)\n• Агентство: менеджер-посредник между вами и разработчиком\n• Мы: прямой контакт с командой, быстрые правки"
    },
}


def detect_competitor_mention(text: str) -> Optional[str]:
    text_lower = text.lower()
    for competitor, data in COMPETITOR_PATTERNS.items():
        for pattern in data["patterns"]:
            if pattern in text_lower:
                return data["response"]
    return None


def build_winback_context(user_id: int) -> Optional[str]:
    try:
        from src.session import session_manager
        if user_id in session_manager._sessions:
            session = session_manager._sessions[user_id]
            if hasattr(session, 'last_activity'):
                days_since = (time.time() - session.last_activity) / 86400
                if days_since >= 7:
                    try:
                        from src.leads import lead_manager
                        lead = lead_manager.get_lead(user_id)
                        name = lead.first_name if lead and lead.first_name else "друг"
                        industry = ""
                        if lead and lead.tags:
                            for tag in lead.tags:
                                if tag in INDUSTRY_CASE_STUDIES:
                                    cs = INDUSTRY_CASE_STUDIES[tag]
                                    industry = f"\nНовый кейс: {cs['name']} — {cs['result'][:80]}..."
                    except Exception:
                        name = "друг"
                        industry = ""
                    days_int = int(days_since)
                    return (
                        f"[WIN-BACK КОНТЕКСТ — клиент вернулся через {days_int} дней]\n"
                        f"Клиент {name} давно не писал. Стратегия win-back:\n"
                        f"• Тёплое приветствие: 'Рад вас снова видеть! Как продвигается проект?'\n"
                        f"• НЕ начинай с продажи — сначала покажи заботу\n"
                        f"• Предложи что-то новое: свежий кейс, новую функцию, актуальную акцию\n"
                        f"• Напомни о прошлом разговоре, если есть контекст"
                        f"{industry}"
                    )
    except Exception as e:
        logger.debug(f"Winback context error: {e}")
    return None


DECISION_FATIGUE_PATTERNS = [
    "не знаю что выбрать", "слишком много вариантов", "какой лучше",
    "запутался в вариантах", "все одинаковые", "сложно выбрать",
    "помогите определиться", "что порекомендуете", "какой посоветуете",
    "не могу решить", "глаза разбегаются", "всё нравится",
    "а может проще", "давайте без вариантов", "скажите что взять",
]


def detect_decision_fatigue(text: str, message_count: int) -> Optional[str]:
    text_lower = text.lower()
    has_fatigue_pattern = any(p in text_lower for p in DECISION_FATIGUE_PATTERNS)

    if has_fatigue_pattern:
        return "[DECISION FATIGUE — УСТАЛОСТЬ ОТ ВЫБОРА]\nКлиент перегружен вариантами. Стратегия:\n• УПРОСТИ: 'Для вашего случая я бы рекомендовал один конкретный вариант — [название]. Вот почему...'\n• Дай ОДНУ чёткую рекомендацию с обоснованием\n• НЕ предлагай больше 2 вариантов\n• Используй: 'Большинство клиентов в вашей нише выбирают...' — социальное доказательство снимает стресс выбора"

    if message_count > 10 and ("какой" in text_lower or "что выбрать" in text_lower):
        return "[DECISION FATIGUE — ДЛИННЫЙ ДИАЛОГ]\nДиалог затянулся, клиент всё ещё выбирает. Пора сузить выбор:\n• Задай финальный квалифицирующий вопрос: 'Что для вас важнее — скорость запуска или максимум функций?'\n• На основе ответа — ОДНА конкретная рекомендация\n• Предложи: 'Давайте я просто составлю вам оптимальный план — это бесплатно'"
    return None


BUYING_SIGNAL_STRONG = [
    "когда можно начать", "как оплатить", "выставьте счёт", "давайте начнём",
    "готов оплатить", "куда переводить", "хочу заказать", "оформляйте",
    "берём", "подписываю", "присылайте договор", "реквизиты",
    "когда будет готово", "начинаем", "погнали", "стартуем",
    "хочу такое же", "мне подходит", "записывайте",
]

BUYING_SIGNAL_MEDIUM = [
    "а можно рассрочку", "какая предоплата", "а если оплатить сейчас",
    "сколько предоплата", "есть рассрочка", "а скидка будет",
    "а если заказать два", "а оптом дешевле", "когда ближайший слот",
    "покажите договор", "как выглядит процесс", "что нужно с моей стороны",
    "а поддержка входит", "а правки бесплатные",
]

BUYING_SIGNAL_IMAGINING = [
    "а можно будет потом добавить", "а если клиентов станет больше",
    "а как это будет выглядеть", "представляю как", "когда запустим",
    "мои клиенты смогут", "а можно кастомизировать", "а если нам нужно будет",
    "а что если трафик вырастет", "а мы сможем",
]


def detect_buying_signals(text: str) -> Optional[str]:
    text_lower = text.lower()
    strong = sum(1 for p in BUYING_SIGNAL_STRONG if p in text_lower)
    medium = sum(1 for p in BUYING_SIGNAL_MEDIUM if p in text_lower)
    imagining = sum(1 for p in BUYING_SIGNAL_IMAGINING if p in text_lower)

    if strong >= 1:
        return "[BUYING SIGNAL: СИЛЬНЫЙ]\nКлиент готов покупать СЕЙЧАС. Стратегия (Assumptive Close):\n• НЕ продолжай продавать — переходи к оформлению\n• 'Отлично! Давайте зафиксируем детали: [конкретный следующий шаг]'\n• Предложи schedule_consultation или generate_brief\n• Убери последние барьеры: 'Предоплата 35%, 14 дней правок бесплатно'"
    if medium >= 1:
        return "[BUYING SIGNAL: СРЕДНИЙ]\nКлиент изучает условия покупки — высокий интерес. Стратегия:\n• Отвечай на вопросы конкретно и быстро\n• После ответа — мягкий push: 'Хотите, составлю предварительный план?'\n• Подчеркни безопасность: рассрочка, договор, гарантия возврата"
    if imagining >= 1:
        return "[BUYING SIGNAL: ВООБРАЖЕНИЕ ВЛАДЕНИЯ]\nКлиент уже представляет себя с продуктом (Эффект владения по Канеману). Стратегия:\n• Поддержи визуализацию: 'Да, именно так! И ещё ваши клиенты смогут...'\n• Усиль чувство владения конкретными деталями\n• Мягко к закрытию: 'Давайте прикинем сроки — чтобы это заработало к [дата]?'"
    return None


CIALDINI_CONTEXT = {
    "reciprocity": {
        "triggers": ["спасибо за", "полезно", "помогли", "благодарю", "ценная информация"],
        "hint": "[CIALDINI: ВЗАИМНОСТЬ]\nКлиент благодарит — активирована норма взаимности. Момент для микро-просьбы:\n• 'Рад что помогло! Кстати, если интересно — могу сделать бесплатный расчёт под ваш проект'\n• Или: 'Могу поделиться ещё кейсом из вашей ниши — показать?'"
    },
    "commitment": {
        "triggers": ["да интересно", "покажите", "расскажите", "хочу узнать", "давайте", "ок покажите"],
        "hint": "[CIALDINI: ПОСЛЕДОВАТЕЛЬНОСТЬ]\nКлиент сказал маленькое 'да' — используй foot-in-the-door:\n• Каждое следующее предложение чуть больше предыдущего\n• 'Раз уже посмотрели цены — давайте прикину ROI для вашего бизнеса? 2 минуты'\n• Цепочка: посмотреть → посчитать → обсудить → заказать"
    },
    "scarcity": {
        "triggers": ["ещё есть места", "успею", "сколько осталось", "акция", "скидка действует"],
        "hint": "[CIALDINI: ДЕФИЦИТ]\nКлиент реагирует на ограниченность. Используй честно:\n• Реальные ограничения: загрузка команды, сезонные акции\n• 'Сейчас есть слот на этой неделе — обычно очередь 2-3 недели'\n• НЕ создавай ложный дефицит — только реальные ограничения"
    },
    "authority": {
        "triggers": ["а вы эксперты", "давно работаете", "какой опыт", "сертификаты", "квалификация"],
        "hint": "[CIALDINI: АВТОРИТЕТ]\nКлиент проверяет экспертизу. Покажи авторитет через:\n• Конкретные кейсы с результатами из базы знаний\n• Специализацию: 'Мы делаем ТОЛЬКО Telegram Mini Apps'\n• Количество проектов и отзывы клиентов"
    },
    "unity": {
        "triggers": ["мы из", "наша команда", "наш бизнес", "у нас в городе", "в нашей нише"],
        "hint": "[CIALDINI: ЕДИНСТВО]\nКлиент идентифицирует себя с группой. Используй:\n• 'Да, для [ниша] это особенно актуально — вот кейс коллеги из вашей сферы'\n• Подчеркни общие ценности и цели\n• 'Мы тоже предприниматели — понимаем как важно...' "
    },
}


def detect_cialdini_triggers(text: str) -> Optional[str]:
    text_lower = text.lower()
    for principle, data in CIALDINI_CONTEXT.items():
        for trigger in data["triggers"]:
            if trigger in text_lower:
                return data["hint"]
    return None


COMM_VISUAL_PATTERNS = [
    "покажите", "как выглядит", "скриншот", "картинк", "пример визуал",
    "дизайн", "цвета", "видел", "смотрел", "вижу", "выглядит",
    "показать", "фото", "демо", "интерфейс", "ui", "макет",
]

COMM_AUDITORY_PATTERNS = [
    "расскажите", "объясните", "звучит", "слышал", "поговорить",
    "обсудить", "созвон", "позвонить", "голосов", "аудио",
    "послушать", "как звучит", "говорите",
]

COMM_KINESTHETIC_PATTERNS = [
    "попробовать", "потрогать", "пощупать", "протестировать",
    "демо-доступ", "тест", "пилот", "попробую", "потыкать",
    "руками", "на практике", "в деле", "ощущение",
]


def detect_communication_preference(text: str) -> Optional[str]:
    text_lower = text.lower()
    scores = {
        "visual": sum(1 for p in COMM_VISUAL_PATTERNS if p in text_lower),
        "auditory": sum(1 for p in COMM_AUDITORY_PATTERNS if p in text_lower),
        "kinesthetic": sum(1 for p in COMM_KINESTHETIC_PATTERNS if p in text_lower),
    }
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return None
    hints = {
        "visual": "[КОММУНИКАЦИЯ: ВИЗУАЛ]\nКлиент мыслит образами. Стратегия:\n• Используй слова: 'Посмотрите', 'Представьте', 'Вот как это выглядит'\n• Предлагай портфолио, скриншоты, демо\n• Описывай результат визуально: 'Ваши клиенты увидят каталог с фото, корзину, кнопку оплаты'",
        "auditory": "[КОММУНИКАЦИЯ: АУДИАЛ]\nКлиент предпочитает слушать/обсуждать. Стратегия:\n• Используй слова: 'Расскажу', 'Звучит как', 'Давайте обсудим'\n• Предлагай созвон: schedule_consultation\n• Объясняй процесс пошагово, как историю",
        "kinesthetic": "[КОММУНИКАЦИЯ: КИНЕСТЕТИК]\nКлиент хочет попробовать. Стратегия:\n• Используй слова: 'Попробуйте', 'Протестируйте', 'Почувствуйте разницу'\n• Предлагай демо-доступ, тестовый период\n• 'Давайте я покажу рабочий проект — сами потыкаете и поймёте'",
    }
    return hints[best]


MULTI_INTENT_MARKERS = {
    "price_and_timeline": {
        "patterns": [("сколько", "когда"), ("цена", "срок"), ("стоимость", "время"), ("прайс", "готов")],
        "hint": "Клиент спрашивает о цене И сроках — высокий интерес. Ответь на ОБА вопроса конкретно."
    },
    "features_and_comparison": {
        "patterns": [("функции", "сравн"), ("возможности", "отличи"), ("что умеет", "а у")],
        "hint": "Клиент сравнивает — хочет понять функции И разницу. Дай структурированное сравнение."
    },
    "doubt_and_interest": {
        "patterns": [("сомневаюсь", "интересно"), ("не уверен", "хочу"), ("боюсь", "нравится")],
        "hint": "Клиент одновременно заинтересован И сомневается. Сначала сними сомнение, потом усиль интерес."
    },
}


def detect_multi_intent(text: str) -> Optional[str]:
    text_lower = text.lower()
    detected = []
    for intent_name, data in MULTI_INTENT_MARKERS.items():
        for pair in data["patterns"]:
            if all(kw in text_lower for kw in pair):
                detected.append(data["hint"])
                break
    if detected:
        return "[МУЛЬТИ-ИНТЕНТ — несколько вопросов/намерений]\n" + "\n".join(f"• {h}" for h in detected) + "\nОтветь на ВСЕ намерения, не упусти ни одного."
    return None


CONFIDENCE_DATA_SOURCES = {
    "price_list": ["цена", "стоимость", "сколько стоит", "прайс", "тариф", "пакет", "рассрочка"],
    "case_study": ["кейс", "пример", "результат", "клиент", "отзыв", "портфолио"],
    "timeline": ["срок", "сколько времени", "когда будет готово", "дней", "недель"],
    "guarantee": ["гарантия", "возврат", "договор", "правки", "поддержка"],
}

SPECULATIVE_TOPICS = [
    "рынок", "тренд", "прогноз", "будущее", "конкурент", "рост", "статистика",
    "исследование", "процент", "доля рынка", "аналитика",
]


def assess_confidence_level(text: str) -> Optional[str]:
    text_lower = text.lower()
    has_verified = any(
        any(kw in text_lower for kw in keywords)
        for keywords in CONFIDENCE_DATA_SOURCES.values()
    )
    has_speculative = any(t in text_lower for t in SPECULATIVE_TOPICS)

    if has_speculative and not has_verified:
        return "[CONFIDENCE: ОСТОРОЖНО]\nВопрос касается прогнозов/рынка — данных в базе может не быть. Стратегия:\n• Отвечай на основе кейсов и прайса (search_knowledge_base)\n• НЕ изобретай статистику\n• 'По нашему опыту с клиентами...' вместо 'По статистике...'\n• Если не знаешь — честно скажи и предложи разобраться"
    return None


JOLT_INDECISION_PATTERNS = [
    "не могу определиться", "трудно выбрать", "всё нравится но",
    "боюсь ошибиться", "а вдруг не то выберу", "не хочу пожалеть",
    "слишком ответственно", "серьёзный шаг", "большое решение",
    "нужно всё взвесить", "хочу быть уверен на 100",
    "а если выберу не то", "страшно ошибиться", "не уверен какой",
    "сложно решиться", "никак не решусь", "колеблюсь",
    "и тот и тот хорош", "оба варианта", "каждый по-своему",
]


def detect_jolt_indecision(text: str, message_count: int = 0) -> Optional[str]:
    text_lower = text.lower()
    has_indecision = any(p in text_lower for p in JOLT_INDECISION_PATTERNS)
    has_price_objection = any(p in text_lower for p in ["дорого", "бюджет", "денег нет", "не потяну"])

    if has_indecision and not has_price_objection:
        return "[JOLT: НЕРЕШИТЕЛЬНОСТЬ — это НЕ возражение!]\nКлиент ХОЧЕТ купить, но боится принять решение. Стратегия JOLT:\n• J — Judge: уровень нерешительности ВЫСОКИЙ, клиент нуждается в помощи\n• O — Offer: 'На основе вашей ситуации я рекомендую [конкретный вариант]. Вот почему: [1-2 причины]'\n• L — Limit: 'Из всех вариантов для вас оптимальны только 2. Давайте сравним'\n• T — Take risk off: 'Предоплата 35%, 14 дней правок, возврат если не устроит — риск нулевой'\nНЕ давай больше вариантов! Сузь выбор и дай ОДНУ рекомендацию"

    if message_count > 12 and any(w in text_lower for w in ["какой", "который", "выбрать", "определиться"]):
        return "[JOLT: ЗАТЯНУВШИЙСЯ ВЫБОР]\nКлиент выбирает слишком долго — признак скрытой нерешительности. Стратегия:\n• Дай одну чёткую рекомендацию: 'Для вашего бизнеса я бы выбрал [X]. Причина: [факт]'\n• Убери риск: 'Начнём с этого, и если понадобится — добавим остальное позже'\n• Социальное доказательство: 'Большинство клиентов в вашей нише выбирают именно этот вариант'"
    return None


RISK_AVERSION_PATTERNS = [
    "а что если не сработает", "а если не окупится", "боюсь потерять деньги",
    "не хочу рисковать", "это рискованно", "а если провалится",
    "страшно вкладывать", "а вдруг зря", "а если не зайдёт",
    "деньги на ветер", "выброшенные деньги", "не хочу выбросить",
    "а если клиентам не понравится", "а если не будет заказов",
    "слишком большой риск", "рисковать не готов", "опасаюсь",
]


def detect_risk_aversion(text: str) -> Optional[str]:
    text_lower = text.lower()
    risk_count = sum(1 for p in RISK_AVERSION_PATTERNS if p in text_lower)
    if risk_count == 0:
        return None

    if risk_count >= 2:
        return "[РИСК-АВЕРСИЯ: ВЫСОКАЯ]\nКлиент сильно боится потерять деньги. Максимальная стратегия снятия рисков:\n• Этапная оплата: '35% предоплата → вы видите дизайн → одобряете → 65% только после'\n• Гарантия: 'Возврат предоплаты, если результат не устроит. 14 дней правок бесплатно'\n• ROI до старта: 'Давайте вместе посчитаем окупаемость ДО начала. Если не вижу ROI — честно скажу'\n• Кейс с цифрами: покажи клиента из похожей ниши через search_knowledge_base\n• NEPQ: 'А что будет через полгода, если ничего не менять? Сколько будете терять?'"
    return "[РИСК-АВЕРСИЯ: УМЕРЕННАЯ]\nКлиент осторожен — нормальная реакция на инвестицию. Стратегия:\n• Подчеркни безопасность: этапная оплата, договор, гарантии\n• Социальное доказательство: кейс из ниши клиента\n• Минимизируй первый шаг: 'Давайте начнём с бесплатного расчёта — увидите полную картину'"


MICRO_COMMITMENT_POSITIVE = [
    "интересно", "расскажите", "покажите", "а можно", "давайте",
    "хочу узнать", "хорошо", "звучит неплохо", "логично",
    "согласен", "правильно", "верно", "точно", "именно",
    "да", "ок", "окей", "понял", "ясно", "продолжайте",
    "круто", "класс", "нравится", "подходит", "то что нужно",
]


def track_micro_commitments(text: str, message_count: int = 0, session=None) -> Optional[str]:
    text_lower = text.lower()
    current_positives = sum(1 for p in MICRO_COMMITMENT_POSITIVE if p in text_lower)

    session_positives = 0
    if session and hasattr(session, 'messages'):
        user_msgs = [m for m in session.messages if m.get('role') == 'user']
        for m in user_msgs[-5:]:
            msg_text = m.get('parts', [{}])[0].get('text', '').lower()
            session_positives += sum(1 for p in MICRO_COMMITMENT_POSITIVE if p in msg_text)

    total = current_positives + session_positives

    if total >= 8:
        return "[MICRO-COMMITMENTS: ВЫСОКИЙ УРОВЕНЬ СОГЛАСИЯ]\nКлиент накопил много маленьких 'да' — идеальный момент для перехода к действию (Persuasive Cascading).\n• Предложи конкретный следующий шаг: бриф, расчёт, созвон\n• 'Раз вам всё подходит — давайте зафиксируем? Что удобнее: обсудить детали сейчас или назначить созвон?'"
    if total >= 5 and message_count >= 5:
        return "[MICRO-COMMITMENTS: НАБИРАЕТСЯ MOMENTUM]\nКлиент даёт позитивные сигналы. Продолжай строить цепочку согласий:\n• Задай вопрос, на который легко ответить 'да'\n• 'Вам ведь важно, чтобы клиенты могли заказывать 24/7, верно?'"
    return None


TRUST_POSITIVE_SIGNALS = [
    "спасибо", "благодарю", "полезно", "помогли", "отлично объяснили",
    "хороший вопрос", "логично", "убедили", "верю", "доверяю",
    "профессионально", "видно что разбираетесь", "компетентно",
    "нравится подход", "приятно общаться", "толковый",
]

TRUST_NEGATIVE_SIGNALS = [
    "не верю", "сомневаюсь", "звучит слишком", "мошенники", "обман",
    "развод", "кинете", "не доверяю", "слишком красиво", "подвох",
    "вы реальные", "а есть офис", "а есть отзывы настоящие",
]


def score_trust_velocity(text: str, session=None) -> Optional[str]:
    text_lower = text.lower()

    current_positive = sum(1 for p in TRUST_POSITIVE_SIGNALS if p in text_lower)
    current_negative = sum(1 for p in TRUST_NEGATIVE_SIGNALS if p in text_lower)

    if current_negative >= 2:
        return "[TRUST VELOCITY: ПАДАЕТ]\nДоверие клиента снижается — несколько негативных сигналов. СРОЧНО:\n• Максимальная прозрачность: покажи портфолио, договор, отзывы\n• Accusation Audit: 'Понимаю, вы можете думать — вот, ещё один...'\n• Предложи конкретное доказательство: демо, рабочий проект, созвон с командой"

    session_positive = 0
    if session and hasattr(session, 'messages'):
        user_msgs = [m for m in session.messages if m.get('role') == 'user']
        for m in user_msgs[-6:]:
            msg_text = m.get('parts', [{}])[0].get('text', '').lower()
            session_positive += sum(1 for p in TRUST_POSITIVE_SIGNALS if p in msg_text)

    total_positive = current_positive + session_positive

    if total_positive >= 4:
        return "[TRUST VELOCITY: ВЫСОКАЯ]\nКлиент демонстрирует растущее доверие. Хороший момент для:\n• Углубления отношений: предложи персональный разбор его бизнеса\n• Мягкого перехода к сделке: 'Раз мы на одной волне — давайте двинемся дальше?'\n• Upsell: можно предложить расширенный пакет"
    if current_positive >= 2:
        return "[TRUST VELOCITY: РАСТЁТ]\nПоложительные сигналы доверия. Поддерживай:\n• Продолжай давать ценность и экспертизу\n• Покажи заботу: 'Хочу убедиться, что вы получите именно то, что нужно'"
    return None


def build_full_context(user_id: int, user_message: str, username: Optional[str] = None, first_name: Optional[str] = None, message_count: int = 0) -> Optional[str]:
    parts = []

    try:
        from src.rag import get_relevant_knowledge
        import hashlib as _hl
        rag_key = f"rag:{_hl.md5(user_message.encode()).hexdigest()}"
        rag_context = _cached_get(rag_key, lambda: get_relevant_knowledge(user_message, limit=5))
        if rag_context:
            parts.append(rag_context)
    except Exception as e:
        logger.debug(f"RAG knowledge retrieval skipped: {e}")

    client_ctx = _cached_get(f"client_ctx:{user_id}", lambda: build_client_context(user_id, username, first_name))
    if client_ctx:
        parts.append(client_ctx)

    bant = detect_bant_signals(user_message, user_id)
    bant_ctx = _format_bant_context(bant)
    if bant_ctx:
        parts.append(f"\n{bant_ctx}")

    dm_hint = detect_decision_maker(user_message)
    if dm_hint:
        parts.append(f"\n{dm_hint}")

    neg_stance = detect_negotiation_stance(user_message)
    if neg_stance:
        parts.append(f"\n{neg_stance}")

    client_style = detect_client_style(user_message, message_count)
    if client_style:
        parts.append(f"\n[СТИЛЬ КЛИЕНТА]\n{client_style}")

    funnel_stage = detect_funnel_stage(user_id, user_message, message_count)
    stage_info = FUNNEL_STAGE_SIGNALS.get(funnel_stage, {})
    if stage_info.get("instruction"):
        parts.append(f"\n[СТАДИЯ ВОРОНКИ]\n{stage_info['instruction']}")

    try:
        from src.propensity import propensity_scorer
        score = _cached_get(f"propensity:{user_id}", lambda: propensity_scorer.get_score(user_id))
        if score is not None:
            if score >= 70:
                parts.append(f"\n[PROPENSITY SCORE: {score}/100 — ГОРЯЧИЙ]\nКлиент с высокой вероятностью покупки. Действуй решительно: предлагай конкретные следующие шаги (бриф, оплата, созвон).")
            elif score >= 40:
                parts.append(f"\n[PROPENSITY SCORE: {score}/100 — ТЁПЛЫЙ]\nКлиент заинтересован. Усиливай ценность, показывай кейсы, предлагай калькулятор.")
            elif score >= 20:
                parts.append(f"\n[PROPENSITY SCORE: {score}/100 — ПРОГРЕВАЕТСЯ]\nКлиент изучает. Давай полезную информацию, не дави.")
    except Exception as e:
        logger.debug(f"Propensity scoring skipped: {e}")

    objections = detect_objections(user_message)
    objection_hint = build_objection_hint(user_message)
    if objection_hint:
        parts.append(f"\n[ОБНАРУЖЕНО ВОЗРАЖЕНИЕ]\n{objection_hint}")

    social_proof = get_social_proof(objections, funnel_stage)
    if social_proof:
        parts.append(f"\n{social_proof}")

    relevant_case = get_relevant_case_study(user_id)
    if relevant_case and funnel_stage in ("consideration", "decision"):
        parts.append(f"\n{relevant_case}")

    emotion_hint = build_emotion_hint(user_message)
    if emotion_hint:
        parts.append(f"\n[ЭМОЦИОНАЛЬНЫЙ ТОН]\n{emotion_hint}")

    momentum = detect_momentum(user_message)
    if momentum and momentum in MOMENTUM_STRATEGIES:
        parts.append(f"\n[MOMENTUM]\n{MOMENTUM_STRATEGIES[momentum]}")

    competitor_ctx = detect_competitor_mention(user_message)
    if competitor_ctx:
        parts.append(f"\n{competitor_ctx}")

    budget_ctx = detect_budget_signals(user_message)
    if budget_ctx:
        parts.append(f"\n{budget_ctx}")

    question_ctx = analyze_question_density(user_message)
    if question_ctx:
        parts.append(f"\n{question_ctx}")

    fatigue_ctx = detect_decision_fatigue(user_message, message_count)
    if fatigue_ctx:
        parts.append(f"\n{fatigue_ctx}")

    upsell_ctx = get_smart_upsell(user_id, funnel_stage)
    if upsell_ctx:
        parts.append(f"\n{upsell_ctx}")

    diversity_ctx = check_response_diversity(user_id)
    if diversity_ctx:
        parts.append(f"\n{diversity_ctx}")

    session = None
    try:
        from src.session import session_manager
        if user_id in session_manager._sessions:
            session = session_manager._sessions[user_id]
    except Exception:
        pass

    velocity_ctx = analyze_conversation_velocity(user_id, message_count, session)
    if velocity_ctx:
        parts.append(f"\n{velocity_ctx}")

    if session and hasattr(session, 'messages'):
        sentiment_ctx = detect_sentiment_trajectory(session.messages)
        if sentiment_ctx:
            parts.append(f"\n{sentiment_ctx}")

    winback_ctx = build_winback_context(user_id)
    if winback_ctx:
        parts.append(f"\n{winback_ctx}")

    buying_ctx = detect_buying_signals(user_message)
    if buying_ctx:
        parts.append(f"\n{buying_ctx}")

    cialdini_ctx = detect_cialdini_triggers(user_message)
    if cialdini_ctx:
        parts.append(f"\n{cialdini_ctx}")

    comm_ctx = detect_communication_preference(user_message)
    if comm_ctx:
        parts.append(f"\n{comm_ctx}")

    multi_ctx = detect_multi_intent(user_message)
    if multi_ctx:
        parts.append(f"\n{multi_ctx}")

    confidence_ctx = assess_confidence_level(user_message)
    if confidence_ctx:
        parts.append(f"\n{confidence_ctx}")

    jolt_ctx = detect_jolt_indecision(user_message, message_count)
    if jolt_ctx:
        parts.append(f"\n{jolt_ctx}")

    risk_ctx = detect_risk_aversion(user_message)
    if risk_ctx:
        parts.append(f"\n{risk_ctx}")

    micro_ctx = track_micro_commitments(user_message, message_count, session)
    if micro_ctx:
        parts.append(f"\n{micro_ctx}")

    trust_ctx = score_trust_velocity(user_message, session)
    if trust_ctx:
        parts.append(f"\n{trust_ctx}")

    proactive = get_proactive_value(user_id, funnel_stage)
    if proactive:
        parts.append(f"\n{proactive}")

    try:
        from src.ab_testing import ab_testing
        dialog_variant = ab_testing.get_variant(user_id, "response_style")
        if dialog_variant == "b":
            parts.append("\n[A/B СТИЛЬ: CASUAL]\nОтвечай неформально, используй ) и мессенджерный стиль, как общение с другом.")
        cta_variant = ab_testing.get_variant(user_id, "cta_style")
        if cta_variant == "b":
            parts.append("\n[A/B CTA: SOFT]\nНе предлагай действия напрямую. Вместо 'Давайте рассчитаю' → 'Кстати, могу прикинуть стоимость, если интересно'.")
        objection_variant = ab_testing.get_variant(user_id, "objection_handling")
        if objection_variant == "b":
            parts.append("\n[A/B ВОЗРАЖЕНИЯ: DATA-FIRST]\nПри возражениях начинай с цифр и фактов, а не с эмпатии. Пример: 'По статистике, 87% клиентов окупают вложения за 3 месяца' вместо 'Понимаю ваши сомнения'.")
        pricing_variant = ab_testing.get_variant(user_id, "pricing_reveal")
        if pricing_variant == "b":
            parts.append("\n[A/B ЦЕНЫ: VALUE-FIRST]\nНе называй цену сразу. Сначала покажи ценность: кейс, ROI, выгоды. Цену — только когда клиент спросит повторно или попросит конкретику.")
        followup_variant = ab_testing.get_variant(user_id, "followup_tone")
        if followup_variant == "b":
            parts.append("\n[A/B ТОНАЛЬНОСТЬ: FRIENDLY]\nОбщайся как добрый знакомый, а не как продавец. Меньше формальности, больше заботы: 'Как у вас дела с проектом?' вместо 'Хотели бы вы продолжить обсуждение?'.")
    except Exception as e:
        logger.debug(f"A/B dialog testing skipped: {e}")

    try:
        from src.feedback_loop import feedback_loop
        adaptive_ctx = feedback_loop.get_adaptive_instructions(user_id, user_message, funnel_stage)
        if adaptive_ctx:
            parts.append(f"\n{adaptive_ctx}")
    except Exception as e:
        logger.debug(f"Self-learning context skipped: {e}")

    social_keywords = ['соцсет', 'инстаграм', 'тикток', 'ютуб', 'youtube', 'instagram', 'tiktok', 'подпис', 'монет', 'задан', 'бонус', 'скидк']
    if any(kw in user_message.lower() for kw in social_keywords) or funnel_stage in ('awareness', 'interest'):
        try:
            from src.social_links import get_social_context_for_ai
            parts.append(f"\n{get_social_context_for_ai()}")
        except Exception:
            pass

    if parts:
        return "\n".join(parts)
    return None



def is_returning_user(user_id: int) -> bool:
    try:
        from src.leads import lead_manager
        lead = lead_manager.get_lead(user_id)
        if lead and hasattr(lead, 'message_count') and lead.message_count and lead.message_count > 5:
            return True
    except Exception:
        pass
    return False


def get_returning_context(user_id: int) -> Optional[str]:
    try:
        from src.session import session_manager
        if user_id in session_manager._sessions:
            session = session_manager._sessions[user_id]
            if session._summary:
                return session._summary
    except Exception:
        pass

    try:
        import os
        DATABASE_URL = os.environ.get("DATABASE_URL")
        if DATABASE_URL:
            from src.database import execute_one
            row = execute_one(
                "SELECT summary FROM conversation_summaries WHERE telegram_id = %s",
                (user_id,), dict_cursor=True
            )
            if row and row.get("summary"):
                return row["summary"]
    except Exception:
        pass
    return None
