import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


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


DYNAMIC_BUTTONS_BY_STAGE = {
    "awareness": [
        ("Хочу узнать цены", "smart_prices"),
        ("Покажите примеры", "smart_portfolio"),
    ],
    "interest": [
        ("Рассчитать мой проект", "smart_calc"),
        ("Покажите примеры", "smart_portfolio"),
    ],
    "consideration": [
        ("Посчитать окупаемость", "smart_roi"),
        ("Какие есть скидки?", "smart_discount"),
    ],
    "decision": [
        ("Хочу оставить заявку", "smart_lead"),
        ("Давайте составим ТЗ", "smart_brief"),
    ],
    "action": [
        ("Как оплатить?", "smart_payment"),
        ("Хочу оставить заявку", "smart_lead"),
    ]
}


def should_show_buttons(user_message: str, ai_response: str, message_count: int) -> bool:
    if message_count <= 1:
        return False

    msg_lower = user_message.lower().strip().rstrip('.!,')

    skip_signals = [
        'спасибо', 'понял', 'ок', 'ладно', 'хорошо', 'ясно',
        'угу', 'ага', 'да', 'нет', 'не надо', 'потом',
        'пока', 'до свидания', 'bye'
    ]
    if msg_lower in skip_signals:
        return False

    show_signals = [
        'цен', 'стоимост', 'сколько', 'прайс', 'тариф',
        'пример', 'портфолио', 'кейс', 'работ',
        'заказ', 'заявк', 'начать', 'хочу', 'готов',
        'оплат', 'договор', 'счёт', 'счет',
        'скидк', 'акци', 'бонус',
        'калькулятор', 'рассчитать', 'посчитать',
        'окупаем', 'roi', 'выгод',
    ]
    for signal in show_signals:
        if signal in msg_lower:
            return True

    resp_lower = ai_response.lower()
    cta_signals = ['напишите', 'расскажите', 'оставьте заявку', 'рассчитаем', 'давайте']
    for signal in cta_signals:
        if signal in resp_lower:
            return True

    return message_count % 4 == 0


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
            events = lead_manager.get_events(user_id) if hasattr(lead_manager, 'get_events') else []
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


def build_client_context(user_id: int, username: str = None, first_name: str = None) -> str:
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


def build_full_context(user_id: int, user_message: str, username: str = None, first_name: str = None, message_count: int = 0) -> Optional[str]:
    parts = []

    try:
        from src.rag import get_relevant_knowledge
        rag_context = get_relevant_knowledge(user_message, limit=5)
        if rag_context:
            parts.append(rag_context)
    except Exception as e:
        logger.debug(f"RAG knowledge retrieval skipped: {e}")

    client_ctx = build_client_context(user_id, username, first_name)
    if client_ctx:
        parts.append(client_ctx)

    client_style = detect_client_style(user_message, message_count)
    if client_style:
        parts.append(f"\n[СТИЛЬ КЛИЕНТА]\n{client_style}")

    funnel_stage = detect_funnel_stage(user_id, user_message, message_count)
    stage_info = FUNNEL_STAGE_SIGNALS.get(funnel_stage, {})
    if stage_info.get("instruction"):
        parts.append(f"\n[СТАДИЯ ВОРОНКИ]\n{stage_info['instruction']}")

    try:
        from src.propensity import propensity_scorer
        score = propensity_scorer.get_score(user_id)
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


def get_dynamic_buttons(user_id: int, user_message: str, message_count: int = 0, ai_response: str = "") -> list:
    if not should_show_buttons(user_message, ai_response, message_count):
        return []
    stage = detect_funnel_stage(user_id, user_message, message_count)
    buttons = DYNAMIC_BUTTONS_BY_STAGE.get(stage, DYNAMIC_BUTTONS_BY_STAGE["awareness"])
    return buttons[:2]


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
