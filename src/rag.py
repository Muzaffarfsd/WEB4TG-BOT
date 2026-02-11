import logging
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self):
        self._init_db()
        self.seed_knowledge()

    def _init_db(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set, RAG knowledge base disabled")
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS knowledge_chunks (
                            id SERIAL PRIMARY KEY,
                            category VARCHAR(50) NOT NULL,
                            title VARCHAR(200) NOT NULL,
                            content TEXT NOT NULL,
                            tags TEXT[] DEFAULT '{}',
                            priority INT DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_chunks(category)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_tags ON knowledge_chunks USING GIN(tags)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_priority ON knowledge_chunks(priority DESC)
                    """)
            logger.info("Knowledge chunks table initialized")
        except Exception as e:
            logger.error(f"Failed to init knowledge_chunks table: {e}")

    def seed_knowledge(self):
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM knowledge_chunks")
                    count = cur.fetchone()[0]
                    if count > 0:
                        logger.info(f"Knowledge base already has {count} chunks, skipping seed")
                        return

                    chunks = self._get_seed_data()
                    for chunk in chunks:
                        cur.execute("""
                            INSERT INTO knowledge_chunks (category, title, content, tags, priority)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (chunk['category'], chunk['title'], chunk['content'],
                              chunk['tags'], chunk['priority']))

            logger.info(f"Seeded {len(chunks)} knowledge chunks")
        except Exception as e:
            logger.error(f"Failed to seed knowledge base: {e}")

    def _get_seed_data(self):
        chunks = []

        chunks.append({
            'category': 'pricing', 'priority': 10,
            'title': 'Шаблон: Интернет-магазин',
            'content': '150 000₽, 7-10 дней. Включает: каталог товаров, корзина, авторизация пользователей, онлайн-оплата. Готовый шаблон для запуска интернет-магазина в Telegram Mini App.',
            'tags': ['pricing', 'shop', 'template']
        })
        chunks.append({
            'category': 'pricing', 'priority': 10,
            'title': 'Шаблон: Ресторан/Доставка',
            'content': '180 000₽, 10-12 дней. Включает: меню с категориями, бронирование столиков, система доставки. Идеально для ресторанов, кафе, доставки еды.',
            'tags': ['pricing', 'restaurant', 'template']
        })
        chunks.append({
            'category': 'pricing', 'priority': 10,
            'title': 'Шаблон: Фитнес-клуб',
            'content': '200 000₽, 12-15 дней. Включает: расписание занятий, абонементы и подписки, трекинг прогресса. Для фитнес-клубов, спортзалов, йога-студий.',
            'tags': ['pricing', 'fitness', 'template']
        })
        chunks.append({
            'category': 'pricing', 'priority': 10,
            'title': 'Шаблон: Услуги/Сервис',
            'content': '170 000₽, 8-12 дней. Включает: онлайн-запись, оплата услуг, управление записями. Для салонов красоты, клиник, сервисных компаний.',
            'tags': ['pricing', 'services', 'template']
        })

        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Базовые функции',
            'content': 'Каталог товаров — 25 000₽, корзина — 20 000₽, авторизация — 15 000₽, поиск — 20 000₽, избранное — 12 000₽, отзывы — 25 000₽.',
            'tags': ['features', 'basic']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Платёжные функции',
            'content': 'Онлайн-оплата — 45 000₽, подписки и рекуррентные платежи — 55 000₽, рассрочка — 35 000₽.',
            'tags': ['features', 'payments']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Доставка',
            'content': 'Адресная доставка — 30 000₽, пункты выдачи (ПВЗ) — 35 000₽, экспресс-доставка — 25 000₽.',
            'tags': ['features', 'delivery']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Связь и коммуникация',
            'content': 'Push-уведомления — 25 000₽, чат-поддержка — 45 000₽, видеозвонки — 60 000₽.',
            'tags': ['features', 'communication']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Маркетинг',
            'content': 'Программа лояльности — 65 000₽, промокоды — 30 000₽, реферальная система — 55 000₽.',
            'tags': ['features', 'marketing']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Управление',
            'content': 'Аналитика — 45 000₽, админ-панель — 75 000₽, CRM-система — 120 000₽, трекинг заказов — 45 000₽.',
            'tags': ['features', 'management']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Бронирование',
            'content': 'Онлайн-запись — 55 000₽, электронная очередь — 45 000₽, календарь событий — 30 000₽.',
            'tags': ['features', 'booking']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'AI-функции',
            'content': 'AI чат-бот — 49 000₽, рекомендации — 55 000₽, авто-ответы — 25 000₽, умный поиск — 35 000₽, голосовой ассистент — 75 000₽.',
            'tags': ['features', 'ai']
        })
        chunks.append({
            'category': 'feature', 'priority': 5,
            'title': 'Интеграции',
            'content': 'Telegram бот — 35 000₽, WhatsApp — 45 000₽, Google Maps — 20 000₽, SMS-уведомления — 25 000₽, Email — 30 000₽, 1C — 85 000₽, REST API — 55 000₽.',
            'tags': ['features', 'integrations']
        })

        chunks.append({
            'category': 'process', 'priority': 8,
            'title': 'Оплата и условия',
            'content': '35% предоплата после согласования ТЗ → 65% после сдачи проекта. 14 дней бесплатных правок после запуска. Договор на разработку. Возврат предоплаты, если результат не устроит.',
            'tags': ['process', 'payment']
        })
        chunks.append({
            'category': 'process', 'priority': 8,
            'title': 'Сроки разработки',
            'content': 'Простой проект (магазин, визитка) — 7-10 дней. Средний (ресторан, услуги) — 10-15 дней. Сложный (с AI, маркетплейс) — 15-20 дней. Индивидуальный проект — 20-30 дней.',
            'tags': ['process', 'timeline']
        })
        chunks.append({
            'category': 'subscription', 'priority': 7,
            'title': 'Подписки на обслуживание',
            'content': 'Мини — 9 900₽/мес (хостинг, мелкие правки). Стандарт — 14 900₽/мес (обновления, поддержка 2ч). Премиум — 24 900₽/мес (персональный менеджер, приоритет). Можно и без подписки — просто хостинг.',
            'tags': ['pricing', 'subscription']
        })
        chunks.append({
            'category': 'discount', 'priority': 7,
            'title': 'Система скидок',
            'content': 'Скидки за монеты: 500 монет → 5%, 1000 → 10%, 1500 → 15%, 2000 → 20%, 2500 → 25%. Монеты можно заработать через задания (подписки, лайки), рефералы (200 монет за друга), отзывы (до 500 монет за видео-отзыв).',
            'tags': ['discount', 'loyalty']
        })

        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: Radiance',
            'content': 'Премиум магазин одежды. Telegram Mini App с каталогом, примеркой, онлайн-оплатой. Увеличение продаж через мобильный канал.',
            'tags': ['case_study', 'shop']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: DeluxeDine',
            'content': 'Ресторан с доставкой. Меню, бронирование столиков, система доставки в Telegram. Рост заказов на доставку.',
            'tags': ['case_study', 'restaurant']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: GlowSpa',
            'content': 'Салон красоты. Онлайн-запись, каталог услуг, программа лояльности. Сокращение времени на бронирование.',
            'tags': ['case_study', 'beauty']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: FitPro',
            'content': 'Фитнес-клуб. Расписание тренировок, абонементы, трекинг прогресса в Telegram Mini App.',
            'tags': ['case_study', 'fitness']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: MedLine',
            'content': 'Медицинская клиника. Запись к врачу, история приёмов, напоминания. Удобство для пациентов.',
            'tags': ['case_study', 'medical']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: CleanPro',
            'content': 'Клининг и услуги. Заказ уборки, выбор времени, оплата онлайн. Автоматизация приёма заявок.',
            'tags': ['case_study', 'services']
        })
        chunks.append({
            'category': 'case_study', 'priority': 6,
            'title': 'Кейс: SkillUp',
            'content': 'Онлайн-образование. Курсы, уроки, прогресс обучения, сертификаты в Telegram Mini App.',
            'tags': ['case_study', 'education']
        })

        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Сроки разработки',
            'content': 'Сколько времени занимает разработка? Простой проект (магазин, визитка) — 7-10 дней. Средний (ресторан, услуги) — 10-15 дней. Сложный (с AI, маркетплейс) — 15-20 дней. Точные сроки после обсуждения задачи.',
            'tags': ['faq', 'timing']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Стоимость разработки',
            'content': 'Сколько стоит разработка? Интернет-магазин — от 150 000₽. Ресторан/доставка — от 180 000₽. Фитнес-клуб — от 200 000₽. Услуги/сервис — от 170 000₽. Дополнительные функции — от 12 000₽ каждая. Используйте /calc для точного расчёта.',
            'tags': ['faq', 'price']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Оплата',
            'content': 'Как происходит оплата? 35% предоплата после согласования ТЗ. 65% после сдачи готового приложения. Принимаем карты и банковский перевод.',
            'tags': ['faq', 'payment']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Гарантия',
            'content': 'Есть ли гарантия? Бесплатные правки в течение 14 дней после сдачи. Подписка на обслуживание — от 9 900₽/мес. Договор на разработку. Возврат предоплаты, если результат не устроит.',
            'tags': ['faq', 'guarantee']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Технологии',
            'content': 'На чём разрабатываете? Telegram Mini Apps — веб-приложения внутри Telegram. Frontend: React, Vue.js. Backend: Node.js, Python. Облачные серверы с 99% uptime. Всё работает прямо в Telegram, без скачивания.',
            'tags': ['faq', 'stack']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Процесс разработки',
            'content': 'Как проходит процесс? 1) Обсуждение задачи и ТЗ. 2) Дизайн и прототип — 2-3 дня. 3) Разработка — основной этап. 4) Тестирование и правки. 5) Публикация в Telegram. На каждом этапе показываем прогресс.',
            'tags': ['faq', 'process']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Поддержка после запуска',
            'content': 'Что после запуска? Подписки на обслуживание: Мини 9 900₽/мес (хостинг, мелкие правки), Стандарт 14 900₽/мес (обновления, поддержка 2ч), Премиум 24 900₽/мес (персональный менеджер). Можно и без подписки.',
            'tags': ['faq', 'support']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Скидки',
            'content': 'Как получить скидку? Задания — подписки, лайки → монеты → скидка до 25%. Рефералы — 200 монет за друга (/referral). Отзывы — до 500 монет за видео-отзыв. Повторный заказ — +5% скидка. Максимальная скидка — 25%. Подробнее: /bonus',
            'tags': ['faq', 'discount']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: Telegram Mini Apps',
            'content': 'Что такое Telegram Mini Apps? Полноценные приложения внутри Telegram. Работают без скачивания из App Store. 900+ млн аудитория Telegram. Оплата прямо в мессенджере. Без комиссий маркетплейсов (экономия 15-25%). По сути — ваш мобильный магазин в Telegram.',
            'tags': ['faq', 'telegram_apps']
        })
        chunks.append({
            'category': 'faq', 'priority': 7,
            'title': 'FAQ: AI-агент',
            'content': 'Что умеет AI-агент? Отвечает клиентам 24/7. Понимает контекст и помнит историю. Обучается на ваших данных. Стоимость — 49 000₽. AI-агент поможет автоматизировать поддержку и продажи.',
            'tags': ['faq', 'ai']
        })

        chunks.append({
            'category': 'limitation', 'priority': 9,
            'title': 'Ограничения и правила',
            'content': 'ЗАПРЕЩЕНО: давать скидки от себя (только через монеты /bonus), обещать сроки быстрее прайса, предлагать бесплатные модули, гарантировать точные даты без менеджера, обещать возврат кроме предоплаты, гарантировать 100% uptime. МОЖНО: предлагать монеты, MVP вместо полного проекта, рассрочку, бесплатную консультацию, 14 дней правок.',
            'tags': ['limitations', 'rules']
        })

        chunks.append({
            'category': 'faq', 'priority': 8,
            'title': 'Что такое Telegram Mini Apps',
            'content': 'Telegram Mini Apps — это веб-приложения, работающие прямо внутри мессенджера Telegram. Не нужно скачивать из App Store или Google Play. Доступ к аудитории 900+ млн пользователей Telegram. Встроенная оплата через Telegram Payments. Нет комиссий маркетплейсов (экономия 15-25%). Мгновенный запуск — пользователь открывает приложение в один клик. WEB4TG Studio специализируется на разработке Telegram Mini Apps под ключ.',
            'tags': ['faq', 'technology']
        })

        return chunks

    def search(self, query: str, limit: int = 5) -> list:
        if not DATABASE_URL:
            return []

        try:
            query_lower = query.lower()

            intent_map = {
                'pricing': ['цена', 'стоимость', 'сколько', 'прайс', 'тариф'],
                'features': ['функци', 'модул', 'доп', 'возможност'],
                'case_study': ['кейс', 'пример', 'портфолио', 'проект', 'работ'],
                'faq': ['faq', 'вопрос', 'частый'],
                'process': ['срок', 'время', 'когда', 'этап', 'процесс'],
                'discount': ['скидк', 'бонус', 'монет', 'акци'],
                'guarantee': ['гарант', 'возврат', 'договор'],
                'subscription': ['подписк', 'обслуж', 'поддержк'],
            }

            detected_tags = []
            for tag, keywords in intent_map.items():
                for kw in keywords:
                    if kw in query_lower:
                        detected_tags.append(tag)
                        break

            results = []

            with get_connection() as conn:
                with conn.cursor() as cur:
                    if detected_tags:
                        placeholders = ','.join(['%s'] * len(detected_tags))
                        cur.execute(f"""
                            SELECT id, category, title, content, priority
                            FROM knowledge_chunks
                            WHERE tags && ARRAY[{placeholders}]::text[]
                            ORDER BY priority DESC
                        """, detected_tags)
                        for row in cur.fetchall():
                            results.append({
                                'id': row[0], 'category': row[1],
                                'title': row[2], 'content': row[3],
                                'priority': row[4]
                            })

                    words = [w for w in query_lower.split() if len(w) > 2]
                    if words:
                        conditions = []
                        params = []
                        for word in words[:5]:
                            conditions.append("(LOWER(title) LIKE %s OR LOWER(content) LIKE %s)")
                            params.extend([f'%{word}%', f'%{word}%'])

                        cur.execute(f"""
                            SELECT id, category, title, content, priority
                            FROM knowledge_chunks
                            WHERE {' OR '.join(conditions)}
                            ORDER BY priority DESC
                        """, params)
                        for row in cur.fetchall():
                            results.append({
                                'id': row[0], 'category': row[1],
                                'title': row[2], 'content': row[3],
                                'priority': row[4]
                            })

            seen_ids = set()
            unique_results = []
            for r in results:
                if r['id'] not in seen_ids:
                    seen_ids.add(r['id'])
                    unique_results.append(r)

            unique_results.sort(key=lambda x: x['priority'], reverse=True)

            return [
                {'title': r['title'], 'content': r['content'], 'category': r['category']}
                for r in unique_results[:limit]
            ]

        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []

    def get_by_category(self, category: str) -> list:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT title, content, category
                        FROM knowledge_chunks
                        WHERE category = %s
                        ORDER BY priority DESC
                    """, (category,))
                    return [
                        {'title': row[0], 'content': row[1], 'category': row[2]}
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            logger.error(f"Failed to get chunks by category '{category}': {e}")
            return []

    def update_chunk(self, chunk_id: int, content: str):
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE knowledge_chunks
                        SET content = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (content, chunk_id))
            logger.info(f"Updated knowledge chunk {chunk_id}")
        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id}: {e}")

    def add_chunk(self, category: str, title: str, content: str, tags: list, priority: int = 0):
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO knowledge_chunks (category, title, content, tags, priority)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (category, title, content, tags, priority))
            logger.info(f"Added knowledge chunk: {title}")
        except Exception as e:
            logger.error(f"Failed to add chunk '{title}': {e}")


knowledge_base_rag = KnowledgeBase()


def get_relevant_knowledge(user_message: str, limit: int = 5) -> str:
    try:
        results = knowledge_base_rag.search(user_message, limit=limit)
        if not results:
            return ""

        parts = ["[БАЗА ЗНАНИЙ — используй для ответа]\n"]
        for r in results:
            parts.append(f"## {r['title']}\n{r['content']}\n")

        return "\n".join(parts)
    except Exception as e:
        logger.error(f"Failed to get relevant knowledge: {e}")
        return ""
