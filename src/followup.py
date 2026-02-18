import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.database import get_connection, DATABASE_URL
from src.leads import lead_manager
from src.config import config
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

FOLLOW_UP_SCHEDULES = {
    "hot": [
        timedelta(hours=2),
        timedelta(hours=12),
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
    ],
    "warm": [
        timedelta(hours=6),
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
        timedelta(days=30),
    ],
    "cold": [
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=14),
        timedelta(days=21),
        timedelta(days=30),
        timedelta(days=45),
    ],
}

FOLLOW_UP_PROMPTS = {
    1: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Micro-value check-in (первое касание после молчания)
Клиент перестал отвечать. Твоя задача — дать МИКРО-ПОЛЬЗУ и мягко напомнить о себе.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Обратись по имени ({client_name}) в начале или середине сообщения — естественно, не натужно
- Привяжись к КОНКРЕТНОЙ теме, которую обсуждали (продукт, ниша, задача клиента)
- Дай МИКРО-ПОЛЬЗУ: конкретный факт, совет или идею, связанную с бизнесом клиента
- Создай "крючок" (open loop) — намекни на результат, но не раскрывай полностью
- НЕ спрашивай "остались ли вопросы", "как дела", "всё ли понятно" — это клише
- НЕ повторяй формулировки из предыдущих follow-up

ФОРМАТ:
- 2-3 коротких предложения
- Как сообщение от знакомого эксперта в мессенджере
- Без "Привет!" в начале (используй имя или начни с сути)
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ (разные ниши и подходы):
"{client_name}, по поводу твоего ресторана — я тут посчитал, мини-апп в среднем увеличивает средний чек на 23%. Цифры интересные, могу показать расклад"
"Забыл упомянуть — для салонов красоты есть фича с автоматической записью, экономит 2-3 часа в день администратору. Думаю, тебе зайдёт"
"Кстати, нашёл кое-что по твоей теме — один магазин увеличил повторные покупки на 41% просто добавив бонусную программу в мини-апп. Есть идея как это адаптировать для тебя"
"{client_name}, тут интересная штука — посчитал потенциальную экономию для твоего бизнеса. Результат удивил даже меня, если честно. Скинуть?"
"Наткнулся на свежее исследование по твоей нише — 67% клиентов уходят к конкуренту, если нет удобного приложения. У тебя как с этим?"

Напиши ТОЛЬКО текст, без кавычек.""",

    2: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Social proof (второе касание — доказательство через других)
Первое сообщение осталось без ответа. Задача — показать результат похожего клиента через ЭМОЦИЮ и цифры.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Расскажи про КОНКРЕТНЫЙ кейс из похожей ниши клиента
- Добавь ЭМОЦИОНАЛЬНЫЙ элемент: реакция владельца, цитата, ощущение ("он не верил", "написал нам: это изменило всё")
- Используй точные цифры (конверсии, заказы, рост, сроки)
- Свяжи кейс с КОНКРЕТНОЙ задачей/болью клиента из контекста
- Создай "крючок": "могу показать как устроено", "есть скриншоты"
- НЕ напоминай что писал раньше
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- 2-4 коротких предложения
- Конкретные цифры + эмоция владельца
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ (разные ниши и эмоции):
"{client_name}, вспомнил про тебя — мы доделали мини-апп для кофейни, владелец написал: 'Я не верил что сработает'. За месяц +38 заказов. У тебя похожая ситуация, могу показать как устроено"
"Свежий результат — фитнес-клуб запустил мини-апп, через неделю тренер написал что записи выросли на 56%. Есть скриншоты аналитики, если интересно"
"Тут один владелец доставки рассказал — раньше терял 30% заказов из-за неудобного заказа по телефону. После мини-аппа: +89 заказов за 3 недели. Думаю, для твоего бизнеса цифры будут ещё лучше"
"{client_name}, знаешь что сказал владелец салона после запуска мини-аппа? 'Администратор наконец-то занимается клиентами, а не телефоном'. Записи выросли на 43%. Могу показать демо"
"Интересный результат — интернет-магазин одежды добавил каталог в Telegram, конверсия в покупку выросла с 2% до 8.5%. Владелица была в шоке. Хочешь глянуть как это выглядит?"

Напиши ТОЛЬКО текст, без кавычек.""",

    3: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Value bomb (третье касание — бесплатная ценность)
Два сообщения без ответа. Задача — дать что-то бесплатно, снизить барьер. Покажи что ты УЖЕ вложился.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Предложи что-то БЕСПЛАТНОЕ и конкретное, привязанное к бизнесу клиента
- Покажи что ты УЖЕ сделал работу: "я уже посчитал", "уже подготовил", "уже набросал"
- Создай "крючок": намекни на результат ("цифры интересные", "есть пара неочевидных идей")
- Минимальный commitment: "2 минуты", "просто глянуть", "ни к чему не обязывает"
- Привяжи к КОНКРЕТНОЙ обсуждённой теме, не к абстрактному "проекту"
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- 2-3 предложения
- Конкретное предложение с минимальным обязательством
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ (разные предложения и ниши):
"{client_name}, я тут набросал примерный план для твоего проекта — получилось неожиданно интересно. Пара идей, до которых сам бы не додумался. Скинуть? Глянешь за 2 минуты"
"Подготовил мини-аудит — посмотрел как конкуренты в твоей нише используют мини-аппы. Нашёл 3 слабых места, на которых ты можешь выиграть. Интересно?"
"Уже прикинул для тебя расчёт — сколько клиентов можно дополнительно привлечь через Telegram. Цифры порадовали, если честно. Скинуть результат?"
"{client_name}, собрал для тебя подборку из 5 фич, которые лучше всего работают для бизнеса вроде твоего. Ни к чему не обязывает — просто идеи для вдохновения. Скинуть?"
"Провёл быстрый анализ — у твоих конкурентов нет нормального приложения в Telegram. Это окно возможностей. Подготовил короткий план, как занять эту нишу первым"

Напиши ТОЛЬКО текст, без кавычек.""",

    4: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Scarcity / Urgency (четвёртое касание — ограниченное предложение)
Три сообщения без ответа. Задача — создать ОБОСНОВАННУЮ срочность, привязанную к реальности.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Срочность должна быть ОБОСНОВАНА и КОНКРЕТНА (свободный слот, сезонность, рост цен, конкурентное окно)
- Привяжи к бизнесу клиента: "для ресторана лучше запускать до сезона", "перед Новым годом спрос вырастет"
- Покажи ПОТЕРЮ — что клиент теряет каждый день/неделю без решения
- Формулировка мягкая: информирование, а не давление
- НЕ используй шаблонные "скидка 15% до конца месяца"
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- 2-3 предложения
- Конкретная причина срочности + привязка к бизнесу
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ (разные типы срочности):
"{client_name}, у нас освободился слот — берём ещё 2 проекта в этом месяце, потом очередь 3-4 недели. Для твоего бизнеса запуск до сезона был бы идеален. Если актуально — дай знать"
"Подсчитал — каждую неделю без приложения ты теряешь примерно 15-20 потенциальных заказов. За месяц это уже ощутимая сумма. Могу показать расчёт"
"Кстати, видел что 2 твоих конкурента уже запустили мини-аппы. Пока рынок не насытился — есть шанс занять позицию первым. Потом догонять будет дороже"
"{client_name}, честно — у нас сейчас загрузка 70%, через пару недель будет 100%. Если хочешь стартовать в ближайшее время — лучше забронировать слот сейчас. Ни к чему не обязывает"
"Заметил интересный тренд — в твоей нише спрос на мини-аппы растёт на 40% в месяц. Те, кто запускаются первыми, снимают сливки. Готов помочь не упустить момент"

Напиши ТОЛЬКО текст, без кавычек.""",

    5: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Perspective shift (пятое касание — новый угол)
Четыре сообщения без ответа. Задача — зайти с НЕОЖИДАННОЙ стороны, изменить фрейм мышления.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Покажи проблему с НОВОЙ стороны, о которой клиент не думал
- Используй одну из техник: "потери" (сколько теряет без решения), "тренд" (что происходит в индустрии), "конкуренты" (что делают другие), "клиент клиента" (что хотят ЕГО клиенты)
- Добавь ЭМОЦИОНАЛЬНЫЙ элемент: удивление, осознание, страх упустить
- Факты и цифры должны быть конкретными и привязанными к нише клиента
- НЕ упоминай предыдущие сообщения
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- 2-3 предложения
- Свежий взгляд + конкретный факт + эмоция
- Без markdown, emoji (кроме одного в конце), списков

ПРИМЕРЫ СТИЛЯ (разные углы и ниши):
"{client_name}, интересная статистика — 73% клиентов ресторанов предпочитают заказывать через приложение, а не звонить. Каждый звонок, который ты принимаешь — это потерянный клиент, который не дозвонился"
"Знаешь что самое дорогое в бизнесе? Не ошибки, а упущенное время. Один наш клиент подсчитал: он терял 340 тысяч в месяц просто потому, что клиенты уходили к конкуренту с удобным приложением"
"Вот что меня удивило — опрос показал, что 68% людей готовы платить БОЛЬШЕ, если заказ можно сделать в 2 клика через телефон. Не меньше, а больше. Для твоей ниши это прямой рост выручки"
"{client_name}, тут подумал с другой стороны — ты тратишь время на рутину (звонки, записи, подтверждения), вместо того чтобы развивать бизнес. Мини-апп не просто привлекает клиентов — он освобождает тебя"
"Разговаривал с владельцем бизнеса похожего на твой. Он сказал: 'Я думал, приложение — это для больших компаний'. Через месяц после запуска перестал так думать. +200к к выручке"

Напиши ТОЛЬКО текст, без кавычек.""",

    6: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Soft breakup (шестое касание — мягкое прощание)
Пять сообщений без ответа. Задача — "психология обратного хода". Breakup-сообщения дают 25-40% ответов.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Скажи что НЕ будешь больше беспокоить — и реально перестань
- Оставь дверь ОТКРЫТОЙ: "когда будешь готов — просто напиши"
- Покажи УВАЖЕНИЕ к времени и решениям клиента
- Можно оставить "подарок": ссылку, полезный ресурс, сохранённый расчёт
- 2 предложения МАКСИМУМ — краткость = уважение
- Тон тёплый, без обиды, без пассивной агрессии, без "к сожалению"
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- СТРОГО 2 предложения максимум
- Уважительный, тёплый, короткий
- Без markdown, emoji, списков
- Без манипуляций и чувства вины

ПРИМЕРЫ СТИЛЯ (разные подходы):
"{client_name}, понимаю — сейчас видимо не до этого. Если когда-нибудь вернёшься к идее с приложением, просто напиши — помогу разобраться"
"Не хочу надоедать, так что больше не пишу. Но если появятся вопросы — я тут, в любое время"
"{client_name}, уважаю твоё время. Сохранил наши наработки по твоему проекту — когда будешь готов, всё под рукой, просто напиши"
"Видимо, сейчас другие приоритеты — это нормально. Удачи с бизнесом, и помни — я всегда на связи, если что"
"{client_name}, не буду больше отвлекать. Оставил для тебя расчёт и план — пригодятся когда решишь вернуться к этой идее"

Напиши ТОЛЬКО текст, без кавычек.""",

    7: """Ты — Алекс, живой консультант WEB4TG Studio. НЕ бот, НЕ автоответчик.

ЭТАП: Win-back (седьмое касание через 3-6 недель — возвращение)
Все предыдущие follow-up без ответа. Прошло много времени. Задача — вернуть интерес НОВОЙ ценностью, как будто пишешь впервые.

{tone_instruction}

Контекст разговора:
{context}

{client_signals}

{discussed_topic}

{prev_messages_block}

СТРАТЕГИЯ:
- Пиши как будто ЗАНОВО — без отсылок к прошлым сообщениям
- Предложи НОВУЮ ценность: свежий кейс, новая технология, отраслевой тренд, новый формат/пакет
- Минимальный commitment: "посмотри 3 минуты", "покажу демо"
- Покажи что мир изменился за это время: "у нас появилось", "запустили новый формат"
- Это ПОСЛЕДНЕЕ сообщение — сделай его максимально ценным
- НЕ повторяй формулировки предыдущих follow-up

ФОРМАТ:
- 2-3 предложения
- Свежий тон, энергия, позитив
- Без markdown, emoji (кроме одного в конце), списков
- Без упоминания прошлых сообщений или молчания

ПРИМЕРЫ СТИЛЯ (разные новости и подходы):
"{client_name}, давно не общались! У нас появилась новая фишка — делаем мини-аппы с AI-ассистентом внутри, который сам отвечает клиентам 24/7. Если интересно — покажу демо, займёт 3 минуты)"
"Вспомнил про тебя — мы запустили формат MVP за 7 дней. Один клиент окупил вложения за первую неделю. Если хочешь подробности — напиши)"
"{client_name}, у нас тут появился новый пакет — запуск мини-аппа 'под ключ' с гарантией первых заказов в первую неделю. Раньше такого не было. Интересно глянуть условия?"
"Привет! Кое-что новое — теперь делаем мини-аппы с интеграцией оплаты прямо в Telegram. Конверсия в покупку выросла в 3 раза по сравнению с сайтом. Подумал, тебе может быть актуально)"
"{client_name}, свежие данные — в твоей нише мини-аппы стали стандартом, уже 40% бизнесов используют. Мы как раз обновили портфолио — есть 3 кейса, очень похожие на твой бизнес. Глянешь?"

Напиши ТОЛЬКО текст, без кавычек.""",
}

FOLLOW_UP_AB_VARIANTS = {
    1: {
        "a": "СТИЛЬ: Прямой и экспертный. Начни с конкретного факта или цифры. Будь уверенным. Пример: '{name}, нашёл кое-что по твоей нише — {niche_insight}. Думаю, тебе будет полезно'",
        "b": "СТИЛЬ: Мягкий и заботливый. Начни с заботы о клиенте. Покажи что помнишь о нём. Пример: '{name}, вспомнил про наш разговор. Как продвигаются дела с {topic}? Кстати, нашёл одну интересную идею для тебя'"
    },
    2: {
        "a": "СТИЛЬ: Прямой с кейсом и цифрами. Конкретный результат. Пример: 'Свежий результат: {case_result}. У тебя похожая ситуация — можем повторить'",
        "b": "СТИЛЬ: Сторителлинг. Расскажи историю клиента эмоционально. Пример: 'Тут один владелец {similar_business} написал нам: \"Это изменило мой бизнес\". За месяц {case_result}'"
    },
    3: {
        "a": "СТИЛЬ: Конкретное предложение с дедлайном. 'Я УЖЕ подготовил для тебя {deliverable}. Могу скинуть прямо сейчас — глянешь за 2 минуты'",
        "b": "СТИЛЬ: Мягкое предложение без давления. 'Набросал пару идей для твоего проекта. Ни к чему не обязывает — просто мысли. Интересно?'"
    },
    4: {
        "a": "СТИЛЬ: Чёткая срочность с обоснованием. 'У нас освободился слот — берём 2 проекта до {deadline}. После этого очередь 3 недели'",
        "b": "СТИЛЬ: Мягкий FOMO через упущенную выгоду. 'Посчитал — каждый месяц без приложения ты теряешь примерно {lost_amount}. Просто к размышлению'"
    },
    5: {
        "a": "СТИЛЬ: Провокационный инсайт. Удиви фактом. 'Знаешь, что 78% твоих конкурентов уже используют {trend}? Вот что это значит для тебя...'",
        "b": "СТИЛЬ: Эмпатия + новый угол. 'Понимаю, сейчас много всего. Но вот что заметил — {observation}. Может стоит взглянуть с этой стороны?'"
    },
    6: {
        "a": "СТИЛЬ: Прямой breakup. 'Не буду больше писать. Если когда-нибудь решишь — просто напиши, помогу разобраться'",
        "b": "СТИЛЬ: Тёплый breakup с подарком. 'Понимаю, сейчас не до этого. Оставляю для тебя {gift} — пригодится когда будешь готов. Удачи!'"
    },
    7: {
        "a": "СТИЛЬ: Свежая новость. 'Появилось кое-что новое — {new_feature}. Думаю, это как раз то, что тебе нужно'",
        "b": "СТИЛЬ: Ностальгический. 'Давно не общались! Вспомнил наш разговор про {topic}. С тех пор у нас появилось {new_value}'"
    },
}


def _get_client_name(user_id: int) -> str:
    """Get client's first name for personalization."""
    try:
        lead = lead_manager.get_lead(user_id)
        if lead and lead.first_name:
            return lead.first_name
        if lead and lead.username:
            return lead.username
    except Exception:
        pass
    return ""


def _get_discussed_topic(user_id: int) -> str:
    """Extract key discussed topics from conversation history."""
    try:
        messages = lead_manager.get_conversation_history(user_id, limit=15)
        if not messages:
            return ""

        topics = []
        lead = lead_manager.get_lead(user_id)
        if lead:
            if lead.business_type:
                topics.append(f"бизнес клиента: {lead.business_type}")
            if lead.budget:
                topics.append(f"обсуждали бюджет: {lead.budget}")

        try:
            from src.session import get_client_profile
            profile = get_client_profile(user_id)
            if profile:
                if profile.get("discussed_products"):
                    topics.append(f"обсуждали продукты: {profile['discussed_products']}")
                if profile.get("project_type"):
                    topics.append(f"тип проекта: {profile['project_type']}")
                if profile.get("pain_points"):
                    topics.append(f"боли клиента: {profile['pain_points']}")
                if profile.get("goals"):
                    topics.append(f"цели: {profile['goals']}")
        except Exception:
            pass

        for msg in messages:
            if msg.role == "user":
                content_lower = msg.content.lower()
                if any(kw in content_lower for kw in ["магазин", "shop", "товар", "каталог"]):
                    topics.append("интересовался: интернет-магазин / каталог товаров")
                elif any(kw in content_lower for kw in ["ресторан", "кафе", "еда", "доставк", "меню"]):
                    topics.append("интересовался: ресторан / доставка еды")
                elif any(kw in content_lower for kw in ["салон", "красот", "запис", "бьюти"]):
                    topics.append("интересовался: салон красоты / запись онлайн")
                elif any(kw in content_lower for kw in ["фитнес", "спорт", "трениров", "зал"]):
                    topics.append("интересовался: фитнес / спорт")
                elif any(kw in content_lower for kw in ["клиник", "врач", "медиц", "стоматолог"]):
                    topics.append("интересовался: медицина / клиника")
                elif any(kw in content_lower for kw in ["курс", "обучен", "школ", "образован"]):
                    topics.append("интересовался: образование / курсы")
                if any(kw in content_lower for kw in ["сколько стоит", "цена", "стоимость", "бюджет", "прайс"]):
                    topics.append("спрашивал про цены/стоимость")
                if any(kw in content_lower for kw in ["сроки", "когда", "как быстро", "сколько времени"]):
                    topics.append("спрашивал про сроки")
                break

        unique_topics = list(dict.fromkeys(topics))[:5]
        if unique_topics:
            return "Что обсуждали с клиентом:\n" + "\n".join(f"- {t}" for t in unique_topics)
    except Exception:
        pass
    return "Что обсуждали: нет данных (используй контекст разговора выше)"


def _get_tone_instruction(user_id: int) -> str:
    """Get tone instruction based on client's communication style."""
    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile and profile.get("communication_style"):
            style = profile["communication_style"].lower()
            if "формальн" in style or "вежлив" in style or "официальн" in style:
                return "АДАПТАЦИЯ ТОНА: Клиент общается ФОРМАЛЬНО. Используй 'Вы' вместо 'ты'. Тон уважительный, деловой. Не фамильярничай. Пример: 'Добрый день! Подготовил для Вас...' вместо 'Слушай, тут такое дело...'"
            elif "дружеск" in style or "неформальн" in style or "разговорн" in style:
                return "АДАПТАЦИЯ ТОНА: Клиент общается НЕФОРМАЛЬНО. Используй 'ты', лёгкий дружеский тон. Можно шутить. Пример: 'Слушай, тут такая штука...' вместо 'Добрый день, хотел бы обратить Ваше внимание...'"
            elif "краткий" in style or "лаконичн" in style or "по делу" in style:
                return "АДАПТАЦИЯ ТОНА: Клиент предпочитает КРАТКОСТЬ. Максимум 2 предложения. Без воды, сразу к делу. Факт + вопрос."
            elif "эмоцион" in style or "восторж" in style:
                return "АДАПТАЦИЯ ТОНА: Клиент ЭМОЦИОНАЛЬНЫЙ. Используй восклицания, энтузиазм, яркие описания результатов."

        messages = lead_manager.get_conversation_history(user_id, limit=5)
        if messages:
            formal_markers = 0
            informal_markers = 0
            for msg in messages:
                if msg.role == "user":
                    text = msg.content.lower()
                    if any(w in text for w in ["здравствуйте", "добрый день", "уважаемый", "пожалуйста", "будьте добры", "не могли бы вы"]):
                        formal_markers += 1
                    if any(w in text for w in ["привет", "хай", "ок", "круто", "норм", "чё", "ваще", "кста"]):
                        informal_markers += 1

            if formal_markers > informal_markers:
                return "АДАПТАЦИЯ ТОНА: По сообщениям клиента определено: он общается ФОРМАЛЬНО. Используй 'Вы', деловой тон."
            elif informal_markers > formal_markers:
                return "АДАПТАЦИЯ ТОНА: По сообщениям клиента определено: он общается НЕФОРМАЛЬНО. Используй 'ты', дружеский тон."
    except Exception:
        pass
    return "АДАПТАЦИЯ ТОНА: Стиль клиента не определён. Используй нейтральный дружелюбный тон на 'ты'."


def _get_prev_followup_messages(user_id: int) -> str:
    """Get previous follow-up messages to prevent repetition."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT follow_up_number, message_text FROM follow_ups
                    WHERE user_id = %s AND status IN ('sent', 'responded')
                    AND message_text IS NOT NULL AND message_text != ''
                    ORDER BY sent_at DESC LIMIT 3
                """, (user_id,))
                rows = cur.fetchall()
                if rows:
                    prev = []
                    for row in rows:
                        text_preview = row[1][:150] if row[1] else ""
                        prev.append(f"Follow-up #{row[0]}: \"{text_preview}...\"")
                    return "ПРЕДЫДУЩИЕ FOLLOW-UP (НЕ ПОВТОРЯЙ эти формулировки, придумай НОВЫЕ):\n" + "\n".join(prev)
    except Exception:
        pass
    return ""


def _build_client_signals(user_id: int) -> str:
    signals = []

    try:
        lead = lead_manager.get_lead(user_id)
        if lead:
            if lead.score and lead.score >= 50:
                signals.append("СИГНАЛ: Горячий лид (высокий интерес)")
            elif lead.score and lead.score >= 25:
                signals.append("СИГНАЛ: Тёплый лид (средний интерес)")

            if lead.business_type:
                signals.append(f"НИША клиента: {lead.business_type}")

            if lead.budget:
                signals.append(f"БЮДЖЕТ: {lead.budget}")

            tags = getattr(lead, 'tags', None)
            if tags:
                signals.append(f"ТЕГИ: {tags}")
    except Exception:
        pass

    try:
        from src.session import get_client_profile
        profile = get_client_profile(user_id)
        if profile:
            if profile.get("business_type"):
                signals.append(f"ТИП БИЗНЕСА: {profile['business_type']}")
            if profile.get("pain_points"):
                signals.append(f"БОЛИ: {profile['pain_points']}")
            if profile.get("communication_style"):
                signals.append(f"СТИЛЬ ОБЩЕНИЯ: {profile['communication_style']}")
    except Exception:
        pass

    try:
        from src.propensity import propensity_scorer
        score = propensity_scorer.get_score(user_id)
        if score is not None and score > 0:
            signals.append(f"PROPENSITY SCORE: {score}/100")
    except Exception:
        pass

    if signals:
        return "Сигналы о клиенте:\n" + "\n".join(signals)
    return "Сигналы о клиенте: нет данных (используй общий подход)"


class FollowUpManager:
    def __init__(self):
        self._init_db()
        self._register_ab_tests()

    def _register_ab_tests(self):
        try:
            from src.ab_testing import WELCOME_TESTS, ABTest
            for i in range(1, 8):
                test_name = f"followup_step_{i}"
                if test_name not in WELCOME_TESTS:
                    descriptions = {
                        1: "Follow-up #1: прямой vs мягкий",
                        2: "Follow-up #2: кейс-цифры vs сторителлинг",
                        3: "Follow-up #3: конкретное предложение vs мягкое",
                        4: "Follow-up #4: срочность vs упущенная выгода",
                        5: "Follow-up #5: провокация vs эмпатия",
                        6: "Follow-up #6: прямой breakup vs тёплый",
                        7: "Follow-up #7: новость vs ностальгия",
                    }
                    WELCOME_TESTS[test_name] = ABTest(
                        name=test_name,
                        variant_a="a",
                        variant_b="b",
                        description=descriptions.get(i, f"Follow-up #{i} A/B test")
                    )
        except Exception as e:
            logger.debug(f"Failed to register followup A/B tests: {e}")

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, follow-ups disabled")
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS follow_ups (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            follow_up_number INTEGER DEFAULT 1,
                            status VARCHAR(20) DEFAULT 'scheduled',
                            scheduled_at TIMESTAMP NOT NULL,
                            sent_at TIMESTAMP,
                            message_text TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_user_id ON follow_ups(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_status ON follow_ups(status)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_followups_scheduled ON follow_ups(scheduled_at)
                    """)

                    cur.execute("ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS ab_variant VARCHAR(5)")
                    cur.execute("ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS cta_clicked BOOLEAN DEFAULT FALSE")
                    cur.execute("ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS click_timestamp TIMESTAMP")

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS successful_followups (
                            id SERIAL PRIMARY KEY,
                            follow_up_number INTEGER,
                            message_text TEXT,
                            ab_variant VARCHAR(5),
                            niche VARCHAR(50),
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
            logger.info("Follow-up table initialized")
        except Exception as e:
            logger.error(f"Failed to init follow-up table: {e}")

    def _get_avg_response_time(self, user_id: int) -> Optional[float]:
        """Average seconds between bot message and user reply."""
        if not DATABASE_URL:
            return None
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT AVG(EXTRACT(EPOCH FROM (u.created_at - b.created_at)))
                        FROM conversations b
                        JOIN conversations u ON u.user_id = b.user_id 
                            AND u.role = 'user' 
                            AND u.created_at > b.created_at
                            AND u.created_at < b.created_at + INTERVAL '7 days'
                        WHERE b.user_id = %s AND b.role = 'assistant'
                        ORDER BY b.created_at DESC
                        LIMIT 20
                    """, (user_id,))
                    result = cur.fetchone()
                    return result[0] if result and result[0] else None
        except:
            return None

    def _count_consecutive_no_response(self, user_id: int) -> int:
        """Count consecutive follow-ups without user response."""
        if not DATABASE_URL:
            return 0
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM follow_ups 
                        WHERE user_id = %s AND status = 'sent'
                        AND id > COALESCE(
                            (SELECT MAX(id) FROM follow_ups WHERE user_id = %s AND status = 'responded'),
                            0
                        )
                    """, (user_id, user_id))
                    result = cur.fetchone()
                    return result[0] if result else 0
        except:
            return 0

    def _calculate_adaptive_delay(self, user_id: int, follow_up_number: int, base_priority: str) -> Optional[timedelta]:
        base_schedule = FOLLOW_UP_SCHEDULES[base_priority]
        if follow_up_number > len(base_schedule):
            return None
        base_delay = base_schedule[follow_up_number - 1]

        multiplier = 1.0

        try:
            from src.propensity import propensity_scorer
            score = propensity_scorer.get_score(user_id)
            if score and score >= 70:
                multiplier *= 0.7
            elif score and score >= 40:
                multiplier *= 0.85
            elif score and score < 20:
                multiplier *= 1.3
        except:
            pass

        try:
            avg_response_time = self._get_avg_response_time(user_id)
            if avg_response_time:
                if avg_response_time < 300:
                    multiplier *= 0.8
                elif avg_response_time > 86400:
                    multiplier *= 1.4
        except:
            pass

        consecutive_no_response = self._count_consecutive_no_response(user_id)
        if consecutive_no_response >= 3:
            fatigue_factor = 1.5 ** (consecutive_no_response - 2)
            multiplier *= min(fatigue_factor, 4.0)

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT cta_clicked FROM follow_ups 
                        WHERE user_id = %s AND status = 'sent'
                        ORDER BY sent_at DESC LIMIT 1
                    """, (user_id,))
                    row = cur.fetchone()
                    if row and row[0]:
                        multiplier *= 0.6
                        logger.info(f"CTA click detected for {user_id}, accelerating next follow-up")
        except:
            pass

        adjusted_seconds = base_delay.total_seconds() * multiplier
        return timedelta(seconds=adjusted_seconds)

    def schedule_follow_up(self, user_id: int) -> bool:
        if not DATABASE_URL:
            return False

        try:
            lead = lead_manager.get_lead(user_id)
            if not lead:
                return False

            if lead.message_count < 2:
                return False

            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id FROM follow_ups 
                        WHERE user_id = %s AND status = 'paused'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

                    sent_count = 0
                    cur.execute("""
                        SELECT COUNT(*) as cnt FROM follow_ups 
                        WHERE user_id = %s AND status = 'sent'
                    """, (user_id,))
                    sent_row = cur.fetchone()
                    if sent_row:
                        sent_count = sent_row['cnt']

                    next_number = sent_count + 1

                    score = lead.score or 0
                    if score >= 50:
                        priority = "hot"
                    elif score >= 25:
                        priority = "warm"
                    else:
                        priority = "cold"

                    if next_number > 7:
                        return False

                    delay = self._calculate_adaptive_delay(user_id, next_number, priority)
                    if delay is None:
                        return False

                    scheduled_at = datetime.now() + delay

                    try:
                        from src.session import get_client_profile
                        profile = get_client_profile(user_id)
                        if profile and profile.get("timezone_offset") is not None:
                            tz_offset = profile["timezone_offset"]
                            client_hour = (scheduled_at.hour + tz_offset) % 24
                            if client_hour < 9:
                                scheduled_at += timedelta(hours=(9 - client_hour))
                            elif client_hour > 20:
                                scheduled_at += timedelta(hours=(24 - client_hour + 9))
                    except Exception:
                        pass

                    cur.execute("""
                        SELECT id FROM follow_ups 
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    if cur.fetchone():
                        return False

                    cur.execute("""
                        INSERT INTO follow_ups (user_id, follow_up_number, status, scheduled_at)
                        VALUES (%s, %s, 'scheduled', %s)
                    """, (user_id, next_number, scheduled_at))

            logger.info(f"Scheduled follow-up #{next_number} for user {user_id} at {scheduled_at} (priority: {priority})")
            return True
        except Exception as e:
            logger.error(f"Failed to schedule follow-up for user {user_id}: {e}")
            return False

    def cancel_follow_ups(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'cancelled'
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    cancelled = cur.rowcount

            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} follow-ups for user {user_id}")

            self.mark_responded(user_id)
            return cancelled
        except Exception as e:
            logger.error(f"Failed to cancel follow-ups for user {user_id}: {e}")
            return 0

    def cancel_for_blocked_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'cancelled'
                        WHERE user_id = %s AND status IN ('scheduled', 'paused')
                    """, (user_id,))
                    cancelled = cur.rowcount
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} follow-ups for blocked user {user_id}")
            return cancelled
        except Exception as e:
            logger.error(f"Failed to cancel follow-ups for blocked user {user_id}: {e}")
            return 0

    def get_due_follow_ups(self) -> List[Dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT f.id, f.user_id, f.follow_up_number, f.scheduled_at, f.ab_variant
                        FROM follow_ups f
                        JOIN leads l ON f.user_id = l.user_id
                        LEFT JOIN bot_users bu ON f.user_id = bu.user_id
                        WHERE f.status = 'scheduled'
                          AND f.scheduled_at <= NOW()
                          AND (l.last_activity IS NULL OR l.last_activity < NOW() - INTERVAL '2 hours')
                          AND (bu.is_blocked IS NULL OR bu.is_blocked = FALSE)
                        ORDER BY f.scheduled_at ASC
                        LIMIT 20
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get due follow-ups: {e}")
            return []

    def mark_sent(self, follow_up_id: int, message_text: str, ab_variant: str = "") -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'sent', sent_at = NOW(), message_text = %s, ab_variant = %s
                        WHERE id = %s
                    """, (message_text, ab_variant, follow_up_id))
            return True
        except Exception as e:
            logger.error(f"Failed to mark follow-up {follow_up_id} as sent: {e}")
            return False

    def mark_responded(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'responded'
                        WHERE user_id = %s AND status = 'sent'
                    """, (user_id,))
                    count = cur.rowcount

                    try:
                        cur.execute("""
                            SELECT follow_up_number, message_text, ab_variant FROM follow_ups
                            WHERE user_id = %s AND status = 'responded'
                            ORDER BY sent_at DESC LIMIT 1
                        """, (user_id,))
                        row = cur.fetchone()
                        if row:
                            self._save_successful_followup(user_id, row[0], row[1] or "", row[2] or "")
                    except:
                        pass

                    return count
        except Exception as e:
            logger.error(f"Failed to mark responded for user {user_id}: {e}")
            return 0

    def track_cta_click(self, user_id: int) -> bool:
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET cta_clicked = TRUE, click_timestamp = NOW()
                        WHERE id = (
                            SELECT id FROM follow_ups
                            WHERE user_id = %s AND status = 'sent'
                            AND cta_clicked = FALSE
                            ORDER BY sent_at DESC
                            LIMIT 1
                        )
                    """, (user_id,))
                    return cur.rowcount > 0
        except:
            return False

    def get_step_analytics(self) -> Dict:
        """Get conversion rate analytics per follow-up step."""
        if not DATABASE_URL:
            return {}
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            follow_up_number,
                            ab_variant,
                            COUNT(*) as total_sent,
                            COUNT(*) FILTER (WHERE status = 'responded') as responses,
                            COUNT(*) FILTER (WHERE cta_clicked = TRUE) as cta_clicks,
                            ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'responded') / NULLIF(COUNT(*), 0), 1) as response_rate,
                            ROUND(100.0 * COUNT(*) FILTER (WHERE cta_clicked = TRUE) / NULLIF(COUNT(*), 0), 1) as click_rate
                        FROM follow_ups
                        WHERE status IN ('sent', 'responded')
                        GROUP BY follow_up_number, ab_variant
                        ORDER BY follow_up_number, ab_variant
                    """)
                    rows = cur.fetchall()
                    analytics = {}
                    for row in rows:
                        step = row['follow_up_number']
                        variant = row['ab_variant'] or 'unknown'
                        if step not in analytics:
                            analytics[step] = {}
                        analytics[step][variant] = {
                            'sent': row['total_sent'],
                            'responses': row['responses'],
                            'cta_clicks': row['cta_clicks'],
                            'response_rate': float(row['response_rate'] or 0),
                            'click_rate': float(row['click_rate'] or 0)
                        }
                    return analytics
        except Exception as e:
            logger.error(f"Failed to get step analytics: {e}")
            return {}

    def _save_successful_followup(self, user_id: int, follow_up_number: int, message_text: str, ab_variant: str = ""):
        """Save follow-up that got a response for future AI learning."""
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    niche = ""
                    try:
                        lead = lead_manager.get_lead(user_id)
                        if lead and lead.business_type:
                            niche = lead.business_type
                    except:
                        pass

                    cur.execute("""
                        INSERT INTO successful_followups (follow_up_number, message_text, ab_variant, niche)
                        VALUES (%s, %s, %s, %s)
                    """, (follow_up_number, message_text[:1000], ab_variant, niche))

                    cur.execute("""
                        DELETE FROM successful_followups 
                        WHERE id NOT IN (
                            SELECT id FROM successful_followups ORDER BY created_at DESC LIMIT 200
                        )
                    """)
        except Exception as e:
            logger.debug(f"Failed to save successful followup: {e}")

    def get_successful_examples(self, follow_up_number: int, niche: str = "", limit: int = 3) -> str:
        """Get successful follow-up examples for AI prompt injection."""
        if not DATABASE_URL:
            return ""
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if niche:
                        cur.execute("""
                            SELECT message_text FROM successful_followups
                            WHERE follow_up_number = %s AND niche = %s
                            ORDER BY created_at DESC LIMIT %s
                        """, (follow_up_number, niche, limit))
                        rows = cur.fetchall()
                        if rows:
                            examples = "\n".join([f"• \"{r['message_text'][:200]}\"" for r in rows])
                            return f"\nПРИМЕРЫ УСПЕШНЫХ FOLLOW-UP (получили ответ):\n{examples}"

                    cur.execute("""
                        SELECT message_text FROM successful_followups
                        WHERE follow_up_number = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (follow_up_number, limit))
                    rows = cur.fetchall()
                    if rows:
                        examples = "\n".join([f"• \"{r['message_text'][:200]}\"" for r in rows])
                        return f"\nПРИМЕРЫ УСПЕШНЫХ FOLLOW-UP (получили ответ):\n{examples}"
        except:
            pass
        return ""

    def handle_silent_activity(self, user_id: int, activity_type: str = "bot_visit") -> bool:
        """Handle when user visits bot or clicks button without texting.
        Reschedule follow-up sequence from relevant step instead of resetting."""
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT MAX(follow_up_number) as last_step, 
                               MAX(CASE WHEN status = 'scheduled' THEN id END) as pending_id
                        FROM follow_ups WHERE user_id = %s
                    """, (user_id,))
                    row = cur.fetchone()

                    if not row or not row['last_step']:
                        return False

                    last_step = row['last_step']

                    if row['pending_id']:
                        cur.execute("""
                            UPDATE follow_ups 
                            SET scheduled_at = NOW() + INTERVAL '1 hour'
                            WHERE id = %s AND scheduled_at > NOW() + INTERVAL '1 hour'
                        """, (row['pending_id'],))
                        if cur.rowcount > 0:
                            logger.info(f"Accelerated follow-up for user {user_id} due to {activity_type}")
                            return True
                    else:
                        restart_step = min(last_step + 1, 7)

                        if last_step < 7:
                            cur.execute("""
                                INSERT INTO follow_ups (user_id, follow_up_number, status, scheduled_at)
                                VALUES (%s, %s, 'scheduled', NOW() + INTERVAL '2 hours')
                                ON CONFLICT DO NOTHING
                            """, (user_id, restart_step))
                            if cur.rowcount > 0:
                                logger.info(f"Re-engaged user {user_id} with step {restart_step} due to {activity_type}")
                                return True
            return False
        except Exception as e:
            logger.debug(f"Silent activity handling failed: {e}")
            return False

    async def generate_follow_up_message(self, user_id: int, follow_up_number: int) -> tuple:
        """Generate follow-up message. Returns (message_text, ab_variant)."""
        variant = ""
        client_name = _get_client_name(user_id)
        try:
            messages = lead_manager.get_conversation_history(user_id, limit=10)

            context_parts = []
            for msg in messages[-8:]:
                role_label = "Клиент" if msg.role == "user" else "Алекс"
                context_parts.append(f"{role_label}: {msg.content[:300]}")

            context = "\n".join(context_parts) if context_parts else "Клиент начал диалог, но разговор был коротким."

            client_signals = _build_client_signals(user_id)
            discussed_topic = _get_discussed_topic(user_id)
            tone_instruction = _get_tone_instruction(user_id)
            prev_messages_block = _get_prev_followup_messages(user_id)

            prompt_template = FOLLOW_UP_PROMPTS.get(follow_up_number, FOLLOW_UP_PROMPTS[1])
            prompt = prompt_template.format(
                context=context,
                client_signals=client_signals,
                client_name=client_name if client_name else "клиент",
                discussed_topic=discussed_topic,
                tone_instruction=tone_instruction,
                prev_messages_block=prev_messages_block
            )

            try:
                from src.ab_testing import ab_testing
                variant = ab_testing.get_variant(user_id, f"followup_step_{follow_up_number}")
            except Exception:
                variant = "a"
            style_hint = FOLLOW_UP_AB_VARIANTS.get(follow_up_number, {}).get(variant, "")
            if style_hint:
                prompt += f"\n\n{style_hint}"

            niche = ""
            try:
                lead = lead_manager.get_lead(user_id)
                if lead and lead.business_type:
                    niche = lead.business_type
            except:
                pass

            successful_examples = self.get_successful_examples(follow_up_number, niche)
            if successful_examples:
                prompt += successful_examples

            from src.ai_client import ai_client
            result = await ai_client.generate_response(
                messages=[{"role": "user", "parts": [{"text": prompt}]}],
                thinking_level="low"
            )

            if result:
                text = result.strip().strip('"').strip("'")
                if len(text) > 20:
                    return text, variant

        except Exception as e:
            logger.error(f"Failed to generate follow-up message for user {user_id}: {e}")

        name = client_name if client_name else "Привет"
        fallback_messages = {
            1: f"{name}, по поводу твоего проекта — мини-аппы в среднем увеличивают конверсию на 35%. Уже посчитал примерные цифры для тебя — могу показать расклад",
            2: f"{name}, свежий результат — сделали Mini App для похожего бизнеса, владелец написал: 'Не ожидал такого эффекта'. +47 заказов за первый месяц. Могу показать как устроено",
            3: f"{name}, уже подготовил примерный план для твоего проекта — получилось интересно. Глянешь за 2 минуты, ни к чему не обязывает",
            4: f"{name}, у нас освободился слот — берём ещё 2 проекта в этом месяце, потом очередь 3-4 недели. Для твоего бизнеса это может быть актуально",
            5: f"{name}, интересный факт — 73% клиентов предпочитают заказывать через приложение. Каждый день без него — это потерянные заказы. Посчитать сколько именно?",
            6: f"{name}, не хочу надоедать, больше не пишу. Но если появятся вопросы — я тут, в любое время",
            7: f"{name}, давно не общались! У нас появился новый формат — MVP за 7 дней с гарантией первых заказов. Один клиент окупил за первую неделю. Интересно?)",
        }
        return fallback_messages.get(follow_up_number, fallback_messages[1]), variant

    def pause_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'paused'
                        WHERE user_id = %s AND status = 'scheduled'
                    """, (user_id,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Failed to pause follow-ups for user {user_id}: {e}")
            return 0

    def resume_user(self, user_id: int) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE follow_ups 
                        SET status = 'scheduled'
                        WHERE user_id = %s AND status = 'paused'
                    """, (user_id,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Failed to resume follow-ups for user {user_id}: {e}")
            return 0

    def get_user_follow_up_stats(self) -> List[Dict]:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            f.user_id,
                            l.first_name,
                            l.username,
                            COUNT(*) FILTER (WHERE f.status = 'scheduled') as pending,
                            COUNT(*) FILTER (WHERE f.status = 'sent') as sent,
                            COUNT(*) FILTER (WHERE f.status = 'responded') as responded,
                            COUNT(*) FILTER (WHERE f.status = 'paused') as paused,
                            MAX(f.follow_up_number) as max_followup
                        FROM follow_ups f
                        LEFT JOIN leads l ON f.user_id = l.user_id
                        GROUP BY f.user_id, l.first_name, l.username
                        ORDER BY pending DESC, sent DESC
                        LIMIT 20
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user follow-up stats: {e}")
            return []

    def get_stats(self) -> Dict:
        if not DATABASE_URL:
            return {
                "total": 0, "scheduled": 0, "sent": 0,
                "responded": 0, "cancelled": 0, "paused": 0,
                "sent_today": 0
            }

        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE status = 'scheduled') as scheduled,
                            COUNT(*) FILTER (WHERE status = 'sent') as sent,
                            COUNT(*) FILTER (WHERE status = 'responded') as responded,
                            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                            COUNT(*) FILTER (WHERE status = 'paused') as paused,
                            COUNT(*) FILTER (WHERE status = 'sent' AND sent_at >= CURRENT_DATE) as sent_today
                        FROM follow_ups
                    """)
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            logger.error(f"Failed to get follow-up stats: {e}")

        return {
            "total": 0, "scheduled": 0, "sent": 0,
            "responded": 0, "cancelled": 0, "paused": 0,
            "sent_today": 0
        }


follow_up_manager = FollowUpManager()
