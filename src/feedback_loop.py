"""Self-Learning Feedback Loop v2 — learns from outcomes and adapts AI behavior.

v1: passive tracking (log responses + outcomes)
v2: active learning:
  - Tags each AI response with detected closing technique + business niche
  - Aggregates conversion rates per technique/niche/style (30-day rolling window)
  - Generates concise adaptive instructions for AI prompt injection
  - Minimum sample sizes to avoid noise (Wilson score confidence)
  - Cached summaries (TTL 5 min) to avoid DB pressure
"""
import logging
import re
import time
import math
from typing import Optional, Dict, List, Tuple

from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

CLOSING_TECHNIQUES: Dict[str, Dict[str, str]] = {
    "trial_close": {
        "label": "Trial close",
        "patterns": r"если бы мы могли|если бы это было возможно|а если бы|предположим.{0,30}начать|допустим.{0,30}запуст",
    },
    "assumptive_close": {
        "label": "Assumptive close",
        "patterns": r"давайте определимся|определимся с|какой вариант вам ближе|шаблон.*подходит или|итак.*оформляем",
    },
    "alternative_close": {
        "label": "Альтернативный",
        "patterns": r"вам удобнее.{0,20}или|первый вариант.{0,15}второй|вариант А.{0,15}вариант Б|на этой неделе или на следующей|начать с.{0,20}или с",
    },
    "ben_franklin_close": {
        "label": "Ben Franklin close",
        "patterns": r"давайте.*плюс.*минус|за и против|преимуществ|взвесим|разберём.*за и|плюсы.*минусы",
    },
    "puppy_dog_close": {
        "label": "Puppy dog close",
        "patterns": r"бесплатн\w* расчёт|без обязательств|просто посмотрите|ноль обязательств|ни к чему не обязывает|бесплатн\w* аудит",
    },
    "summary_close": {
        "label": "Summary close",
        "patterns": r"итак.*договорились|подведём итог|резюмирую|давайте подведём|мы обсудили.*следующий шаг|подытож",
    },
    "inversion_close": {
        "label": "Inversion close (Sandler)",
        "patterns": r"может.*вам.*не нужно|может.*это.*не для вас|давайте честно разберёмся|если это не ваше|возможно.*не подходит",
    },
    "takeaway_close": {
        "label": "Takeaway close",
        "patterns": r"можем пока не включать|начнёте с базы|без.*модуля|можно обойтись без|пока не добавлять|не обязательно брать",
    },
    "future_pacing": {
        "label": "Future pacing (NLP)",
        "patterns": r"представьте|через.*недел\w.*клиент|через.*месяц|вообразите|а теперь представьте|через.*дней.*ваш",
    },
    "sharp_angle_close": {
        "label": "Sharp angle close",
        "patterns": r"если я.*добавлю|если мы.*включим|если.*бесплатный месяц|если.*скидку.*начнём|при условии.*начинаем",
    },
    "jolt_close": {
        "label": "JOLT close",
        "patterns": r"я рекомендую именно|вот почему.*риск нулевой|моя рекомендация|как эксперт.*советую|предоплата.*правк.*возврат",
    },
    "negative_reverse_close": {
        "label": "Negative reverse close",
        "patterns": r"вам это вообще не нужно|может.*не стоит|какую задачу.*пытаетесь решить|давайте.*честно.*нужно ли",
    },
    "nepq_close": {
        "label": "NEPQ commitment close",
        "patterns": r"если бы мы могли решить|это было бы полезно для|помогло бы.*бизнес|решить.*проблему.*за.*дней",
    },
}

NICHE_PATTERNS: Dict[str, Dict[str, str]] = {
    "restaurant": {
        "label": "Рестораны/Кафе",
        "patterns": r"рестор|кафе|кофейн|бар|столов|пекарн|еда|food|кухн|повар|меню|блюд",
    },
    "shop": {
        "label": "Магазины/E-commerce",
        "patterns": r"магазин|бутик|интернет-магазин|маркетплейс|товар|продаж|каталог|ассортимент|склад|опт|розниц",
    },
    "beauty": {
        "label": "Бьюти/Салоны",
        "patterns": r"салон|парикмахер|барбершоп|маникюр|косметолог|визаж|спа|spa|nail|красот|стрижк",
    },
    "fitness": {
        "label": "Фитнес/Спорт",
        "patterns": r"фитнес|спортзал|тренажёр|йога|пилатес|кроссфит|тренер|бассейн|спорт|зал",
    },
    "medical": {
        "label": "Медицина/Клиники",
        "patterns": r"клиник|больниц|стоматолог|аптек|лаборатор|врач|медиц|здоров|диагност|анализ",
    },
    "education": {
        "label": "Образование/Курсы",
        "patterns": r"курс|школ|обучен|университет|репетитор|образован|урок|студент|лекци|тренинг",
    },
    "delivery": {
        "label": "Доставка",
        "patterns": r"доставк|курьер|суши|пицц|food delivery|логистик|перевоз",
    },
    "services": {
        "label": "Услуги/Сервис",
        "patterns": r"услуг|ремонт|клининг|автосервис|химчистк|мастер|сервис|монтаж|установк",
    },
    "realestate": {
        "label": "Недвижимость",
        "patterns": r"недвижимост|квартир|дом|аренд|риэлтор|жильё|ипотек|застройщик",
    },
    "travel": {
        "label": "Туризм/Путешествия",
        "patterns": r"тур|путешеств|отель|гостиниц|бронирован|экскурси|авиабилет|travel|отдых",
    },
}

STYLE_PATTERNS: Dict[str, str] = {
    "formal": r"уважаем\w+|прошу.*рассмотр|благодар\w+|официальн|договор|юридическ|ООО|ИП\s",
    "casual": r"\)\s*$|хах|ахах|лол|ок\b|прив|здаров|чел\b|го\b|норм\b|кст|оч\b",
    "analytical": r"сравнит|аналитик|ROI|метрик|конверси|статистик|данн\w+|показател|KPI|процент",
    "emotional": r"мечта|хочу|нравится|круто|вау|офигенно|обожаю|супер|класс|восторг|потрясающе",
    "skeptical": r"сомнева|не уверен|а вдруг|гарантии|рисков|обман|развод|кидал|не верю|докажите",
}

_insights_cache: Dict[str, Tuple[float, object]] = {}
_CACHE_TTL = 300


def _wilson_score(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    adjustment = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - adjustment) / denominator


class FeedbackLoop:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        if not DATABASE_URL:
            return

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS response_outcomes (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            message_text TEXT,
                            response_text TEXT,
                            response_variant VARCHAR(20),
                            funnel_stage VARCHAR(30),
                            propensity_score INT,
                            outcome_type VARCHAR(30) NULL,
                            outcome_at TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_response_outcomes_user_id ON response_outcomes(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_response_outcomes_outcome_type ON response_outcomes(outcome_type)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_response_outcomes_created_at ON response_outcomes(created_at)")

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS response_tags (
                            id SERIAL PRIMARY KEY,
                            response_id INT NOT NULL REFERENCES response_outcomes(id) ON DELETE CASCADE,
                            tag_type VARCHAR(20) NOT NULL,
                            tag_value VARCHAR(50) NOT NULL,
                            confidence REAL DEFAULT 1.0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_response_tags_response_id ON response_tags(response_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_response_tags_type_value ON response_tags(tag_type, tag_value)")

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS niche_style_memory (
                            id SERIAL PRIMARY KEY,
                            niche VARCHAR(30) NOT NULL,
                            preferred_style VARCHAR(30),
                            preferred_techniques TEXT,
                            avoid_techniques TEXT,
                            custom_hint TEXT,
                            sample_size INT DEFAULT 0,
                            conversion_rate REAL DEFAULT 0.0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(niche)
                        )
                    """)
            logger.info("Self-Learning Loop v2 tables initialized")
        except Exception as e:
            logger.error(f"Failed to init feedback tables: {e}")

    def log_response(self, user_id: int, message_text: str, response_text: str,
                     variant: Optional[str] = None, funnel_stage: Optional[str] = None,
                     propensity_score: Optional[int] = None) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO response_outcomes
                        (user_id, message_text, response_text, response_variant, funnel_stage, propensity_score)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user_id, message_text, response_text, variant, funnel_stage, propensity_score))
                    result = cur.fetchone()
                    response_id = result[0] if result else 0

            if response_id > 0:
                self._auto_tag_response(response_id, message_text or "", response_text or "")

            return response_id
        except Exception as e:
            logger.error(f"Failed to log response: {e}")
            return 0

    def _auto_tag_response(self, response_id: int, user_message: str, ai_response: str):
        try:
            combined = f"{user_message} {ai_response}".lower()
            tags: List[Tuple[str, str, float]] = []

            for tech_id, tech_info in CLOSING_TECHNIQUES.items():
                if re.search(tech_info["patterns"], ai_response, re.IGNORECASE):
                    tags.append(("technique", tech_id, 0.85))

            for niche_id, niche_info in NICHE_PATTERNS.items():
                if re.search(niche_info["patterns"], user_message, re.IGNORECASE):
                    tags.append(("niche", niche_id, 0.9))

            for style_id, pattern in STYLE_PATTERNS.items():
                if re.search(pattern, user_message, re.IGNORECASE):
                    tags.append(("style", style_id, 0.7))

            if not tags:
                return

            with get_connection() as conn:
                with conn.cursor() as cur:
                    for tag_type, tag_value, confidence in tags:
                        cur.execute("""
                            INSERT INTO response_tags (response_id, tag_type, tag_value, confidence)
                            VALUES (%s, %s, %s, %s)
                        """, (response_id, tag_type, tag_value, confidence))
        except Exception as e:
            logger.debug(f"Auto-tagging skipped: {e}")

    def record_outcome(self, user_id: int, outcome_type: str) -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE response_outcomes
                        SET outcome_type = %s, outcome_at = NOW()
                        WHERE id = (
                            SELECT id FROM response_outcomes
                            WHERE user_id = %s AND outcome_type IS NULL
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                    """, (outcome_type, user_id))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to record outcome for user {user_id}: {e}")
            return False

    def record_outcome_by_id(self, response_id: int, outcome_type: str) -> bool:
        if not DATABASE_URL:
            return False

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE response_outcomes
                        SET outcome_type = %s, outcome_at = NOW()
                        WHERE id = %s
                    """, (outcome_type, response_id))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to record outcome for response {response_id}: {e}")
            return False

    def get_best_techniques(self, niche: Optional[str] = None,
                            days: int = 30, min_samples: int = 10) -> List[Dict]:
        cache_key = f"best_techniques:{niche}:{days}"
        cached = _insights_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            return cached[1]  # type: ignore

        if not DATABASE_URL:
            return []

        try:
            niche_filter = ""
            params: list = [days]
            if niche:
                niche_filter = """
                    AND ro.id IN (
                        SELECT rt2.response_id FROM response_tags rt2
                        WHERE rt2.tag_type = 'niche' AND rt2.tag_value = %s
                    )
                """
                params.append(niche)

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT
                            rt.tag_value AS technique,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted,
                            ROUND(COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_tags rt
                        JOIN response_outcomes ro ON rt.response_id = ro.id
                        WHERE rt.tag_type = 'technique'
                          AND ro.created_at >= NOW() - %s * INTERVAL '1 day'
                          {niche_filter}
                        GROUP BY rt.tag_value
                        HAVING COUNT(*) >= {min_samples}
                        ORDER BY rate DESC
                    """, params)

                    results = []
                    for row in cur.fetchall():
                        tech_id = row[0]
                        total = row[1]
                        converted = row[2]
                        raw_rate = float(row[3])
                        wilson = round(_wilson_score(converted, total) * 100, 1)
                        tech_info = CLOSING_TECHNIQUES.get(tech_id, {})
                        results.append({
                            "technique_id": tech_id,
                            "label": tech_info.get("label", tech_id),
                            "total": total,
                            "converted": converted,
                            "raw_rate": raw_rate,
                            "wilson_score": wilson,
                        })

                    results.sort(key=lambda x: x["wilson_score"], reverse=True)

            _insights_cache[cache_key] = (time.time(), results)
            return results
        except Exception as e:
            logger.error(f"Failed to get best techniques: {e}")
            return []

    def get_niche_insights(self, niche: str, days: int = 30,
                           min_samples: int = 5) -> Optional[Dict]:
        cache_key = f"niche_insights:{niche}:{days}"
        cached = _insights_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            return cached[1]  # type: ignore

        if not DATABASE_URL:
            return None

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            rt_style.tag_value AS style,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted
                        FROM response_tags rt_niche
                        JOIN response_outcomes ro ON rt_niche.response_id = ro.id
                        JOIN response_tags rt_style ON rt_style.response_id = ro.id AND rt_style.tag_type = 'style'
                        WHERE rt_niche.tag_type = 'niche'
                          AND rt_niche.tag_value = %s
                          AND ro.created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY rt_style.tag_value
                        HAVING COUNT(*) >= %s
                        ORDER BY COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) DESC
                        LIMIT 3
                    """, (niche, days, min_samples))
                    style_rows = cur.fetchall()

                    cur.execute("""
                        SELECT
                            rt_tech.tag_value AS technique,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted
                        FROM response_tags rt_niche
                        JOIN response_outcomes ro ON rt_niche.response_id = ro.id
                        JOIN response_tags rt_tech ON rt_tech.response_id = ro.id AND rt_tech.tag_type = 'technique'
                        WHERE rt_niche.tag_type = 'niche'
                          AND rt_niche.tag_value = %s
                          AND ro.created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY rt_tech.tag_value
                        HAVING COUNT(*) >= %s
                        ORDER BY COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) DESC
                        LIMIT 3
                    """, (niche, days, min_samples))
                    tech_rows = cur.fetchall()

                    cur.execute("""
                        SELECT
                            rt_tech.tag_value AS technique,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted
                        FROM response_tags rt_niche
                        JOIN response_outcomes ro ON rt_niche.response_id = ro.id
                        JOIN response_tags rt_tech ON rt_tech.response_id = ro.id AND rt_tech.tag_type = 'technique'
                        WHERE rt_niche.tag_type = 'niche'
                          AND rt_niche.tag_value = %s
                          AND ro.created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY rt_tech.tag_value
                        HAVING COUNT(*) >= %s
                          AND COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) < 0.05
                        ORDER BY COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) ASC
                        LIMIT 2
                    """, (niche, days, min_samples))
                    avoid_rows = cur.fetchall()

            if not style_rows and not tech_rows:
                _insights_cache[cache_key] = (time.time(), None)
                return None

            niche_info = NICHE_PATTERNS.get(niche, {})
            result = {
                "niche": niche,
                "niche_label": niche_info.get("label", niche),
                "best_styles": [
                    {"style": r[0], "total": r[1], "converted": r[2],
                     "rate": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0}
                    for r in style_rows
                ],
                "best_techniques": [
                    {"technique": r[0],
                     "label": CLOSING_TECHNIQUES.get(r[0], {}).get("label", r[0]),
                     "total": r[1], "converted": r[2],
                     "rate": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0}
                    for r in tech_rows
                ],
                "avoid_techniques": [
                    {"technique": r[0],
                     "label": CLOSING_TECHNIQUES.get(r[0], {}).get("label", r[0]),
                     "total": r[1], "converted": r[2]}
                    for r in avoid_rows
                ],
            }

            _insights_cache[cache_key] = (time.time(), result)
            return result
        except Exception as e:
            logger.error(f"Failed to get niche insights: {e}")
            return None

    def get_adaptive_instructions(self, user_id: int,
                                  user_message: str,
                                  funnel_stage: Optional[str] = None) -> Optional[str]:
        cache_key = f"adaptive:{user_id}"
        cached = _insights_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < 120:
            return cached[1]  # type: ignore

        parts: List[str] = []

        detected_niche = None
        msg_lower = user_message.lower()
        for niche_id, niche_info in NICHE_PATTERNS.items():
            if re.search(niche_info["patterns"], msg_lower):
                detected_niche = niche_id
                break

        if not detected_niche:
            detected_niche = self._get_user_niche(user_id)

        best_global = self.get_best_techniques(niche=None, days=30, min_samples=10)
        if best_global and len(best_global) >= 2:
            top2 = best_global[:2]
            labels = [f"{t['label']} ({t['wilson_score']}%)" for t in top2]
            parts.append(
                f"[САМООБУЧЕНИЕ] Лучшие техники закрытия (по данным за 30 дней): {', '.join(labels)}. "
                f"Приоритизируй их, когда уместно."
            )

        if detected_niche:
            niche_data = self.get_niche_insights(detected_niche, days=30, min_samples=5)
            if niche_data:
                niche_parts = []
                if niche_data["best_techniques"]:
                    tech_labels = [t["label"] for t in niche_data["best_techniques"][:2]]
                    niche_parts.append(f"лучшие техники: {', '.join(tech_labels)}")
                if niche_data["best_styles"]:
                    style = niche_data["best_styles"][0]["style"]
                    style_labels = {
                        "formal": "формальный",
                        "casual": "неформальный",
                        "analytical": "аналитический",
                        "emotional": "эмоциональный",
                        "skeptical": "осторожный",
                    }
                    niche_parts.append(f"предпочитаемый стиль: {style_labels.get(style, style)}")
                if niche_data["avoid_techniques"]:
                    avoid_labels = [t["label"] for t in niche_data["avoid_techniques"]]
                    niche_parts.append(f"избегай: {', '.join(avoid_labels)}")

                if niche_parts:
                    niche_label = niche_data["niche_label"]
                    parts.append(
                        f"[НИША: {niche_label}] Накопленный опыт: {'; '.join(niche_parts)}."
                    )

        if not parts:
            _insights_cache[cache_key] = (time.time(), None)
            return None

        result = "\n".join(parts)
        _insights_cache[cache_key] = (time.time(), result)
        return result

    def _get_user_niche(self, user_id: int) -> Optional[str]:
        if not DATABASE_URL:
            return None

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT rt.tag_value, COUNT(*) as cnt
                        FROM response_tags rt
                        JOIN response_outcomes ro ON rt.response_id = ro.id
                        WHERE ro.user_id = %s AND rt.tag_type = 'niche'
                        GROUP BY rt.tag_value
                        ORDER BY cnt DESC
                        LIMIT 1
                    """, (user_id,))
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception:
            return None

    def refresh_niche_memory(self, days: int = 30, min_samples: int = 10):
        if not DATABASE_URL:
            return

        try:
            for niche_id in NICHE_PATTERNS:
                insights = self.get_niche_insights(niche_id, days, min_samples)
                if not insights:
                    continue

                best_techs = ",".join([t["technique"] for t in insights.get("best_techniques", [])])
                avoid_techs = ",".join([t["technique"] for t in insights.get("avoid_techniques", [])])
                best_style = insights["best_styles"][0]["style"] if insights.get("best_styles") else None
                total = sum(t["total"] for t in insights.get("best_techniques", []))
                converted = sum(t["converted"] for t in insights.get("best_techniques", []))
                rate = round(converted / total * 100, 1) if total > 0 else 0.0

                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO niche_style_memory (niche, preferred_style, preferred_techniques,
                                avoid_techniques, sample_size, conversion_rate, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (niche) DO UPDATE SET
                                preferred_style = EXCLUDED.preferred_style,
                                preferred_techniques = EXCLUDED.preferred_techniques,
                                avoid_techniques = EXCLUDED.avoid_techniques,
                                sample_size = EXCLUDED.sample_size,
                                conversion_rate = EXCLUDED.conversion_rate,
                                updated_at = NOW()
                        """, (niche_id, best_style, best_techs, avoid_techs, total, rate))

            logger.info("Niche memory refreshed")
        except Exception as e:
            logger.error(f"Failed to refresh niche memory: {e}")

    def get_successful_patterns(self, outcome_type: str = 'lead_created',
                                limit: int = 20) -> list:
        if not DATABASE_URL:
            return []

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT message_text, response_text, funnel_stage, response_variant
                        FROM response_outcomes
                        WHERE outcome_type = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (outcome_type, limit))
                    rows = cur.fetchall()
                    return [
                        {
                            "message_text": row[0],
                            "response_text": row[1],
                            "funnel_stage": row[2],
                            "response_variant": row[3],
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Failed to get successful patterns: {e}")
            return []

    def get_conversion_rate(self, days: int = 30) -> dict:
        if not DATABASE_URL:
            return {}

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS with_outcome
                        FROM response_outcomes
                        WHERE created_at >= NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    row = cur.fetchone()
                    total_responses = row[0] if row else 0
                    with_outcome = row[1] if row else 0
                    conversion_rate = round((with_outcome / total_responses * 100), 2) if total_responses > 0 else 0.0

                    cur.execute("""
                        SELECT outcome_type, COUNT(*) AS cnt
                        FROM response_outcomes
                        WHERE outcome_type IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY outcome_type
                    """, (days,))
                    by_outcome = {r[0]: r[1] for r in cur.fetchall()}

                    cur.execute("""
                        SELECT
                            funnel_stage,
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS converted
                        FROM response_outcomes
                        WHERE funnel_stage IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY funnel_stage
                    """, (days,))
                    by_stage = {r[0]: {"total": r[1], "converted": r[2]} for r in cur.fetchall()}

                    cur.execute("""
                        SELECT
                            response_variant,
                            COUNT(*) AS total,
                            COUNT(outcome_type) AS converted
                        FROM response_outcomes
                        WHERE response_variant IS NOT NULL
                          AND created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY response_variant
                    """, (days,))
                    by_variant = {r[0]: {"total": r[1], "converted": r[2]} for r in cur.fetchall()}

                    cur.execute("""
                        SELECT
                            rt.tag_value AS technique,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted,
                            ROUND(COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_tags rt
                        JOIN response_outcomes ro ON rt.response_id = ro.id
                        WHERE rt.tag_type = 'technique'
                          AND ro.created_at >= NOW() - %s * INTERVAL '1 day'
                        GROUP BY rt.tag_value
                        ORDER BY rate DESC
                    """, (days,))
                    by_technique = {}
                    for r in cur.fetchall():
                        tech_info = CLOSING_TECHNIQUES.get(r[0], {})
                        by_technique[tech_info.get("label", r[0])] = {
                            "total": r[1], "converted": r[2], "rate": float(r[3])
                        }

                    return {
                        "total_responses": total_responses,
                        "with_outcome": with_outcome,
                        "conversion_rate": conversion_rate,
                        "by_outcome": by_outcome,
                        "by_stage": by_stage,
                        "by_variant": by_variant,
                        "by_technique": by_technique,
                    }
        except Exception as e:
            logger.error(f"Failed to get conversion rate: {e}")
            return {}

    def get_learning_insights(self, limit: int = 10) -> str:
        if not DATABASE_URL:
            return "Database not configured"

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT funnel_stage,
                               COUNT(*) AS total,
                               COUNT(outcome_type) AS converted,
                               ROUND(COUNT(outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_outcomes
                        WHERE funnel_stage IS NOT NULL
                        GROUP BY funnel_stage
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    stage_rows = cur.fetchall()

                    cur.execute("""
                        SELECT response_variant,
                               COUNT(*) AS total,
                               COUNT(outcome_type) AS converted,
                               ROUND(COUNT(outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_outcomes
                        WHERE response_variant IS NOT NULL
                        GROUP BY response_variant
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    variant_rows = cur.fetchall()

                    cur.execute("""
                        SELECT
                            rt.tag_value AS technique,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted,
                            ROUND(COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_tags rt
                        JOIN response_outcomes ro ON rt.response_id = ro.id
                        WHERE rt.tag_type = 'technique'
                        GROUP BY rt.tag_value
                        HAVING COUNT(*) >= 5
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    technique_rows = cur.fetchall()

                    cur.execute("""
                        SELECT
                            rt.tag_value AS niche,
                            COUNT(*) AS total,
                            COUNT(ro.outcome_type) AS converted,
                            ROUND(COUNT(ro.outcome_type)::numeric / NULLIF(COUNT(*), 0) * 100, 1) AS rate
                        FROM response_tags rt
                        JOIN response_outcomes ro ON rt.response_id = ro.id
                        WHERE rt.tag_type = 'niche'
                        GROUP BY rt.tag_value
                        HAVING COUNT(*) >= 5
                        ORDER BY rate DESC
                        LIMIT %s
                    """, (limit,))
                    niche_rows = cur.fetchall()

            lines = ["📊 Self-Learning Insights v2\n"]

            lines.append("🏆 Best converting funnel stages:")
            if stage_rows:
                for row in stage_rows:
                    lines.append(f"  • {row[0]}: {row[2]}/{row[1]} ({row[3]}%)")
            else:
                lines.append("  No data yet")

            lines.append("\n🔬 Best converting A/B variants:")
            if variant_rows:
                for row in variant_rows:
                    lines.append(f"  • Variant {row[0]}: {row[2]}/{row[1]} ({row[3]}%)")
            else:
                lines.append("  No data yet")

            lines.append("\n🎯 Closing technique performance:")
            if technique_rows:
                for row in technique_rows:
                    tech_info = CLOSING_TECHNIQUES.get(row[0], {})
                    label = tech_info.get("label", row[0])
                    wilson = round(_wilson_score(row[2], row[1]) * 100, 1)
                    lines.append(f"  • {label}: {row[2]}/{row[1]} ({row[3]}%) [Wilson: {wilson}%]")
            else:
                lines.append("  Not enough data (need ≥5 samples per technique)")

            lines.append("\n🏪 Niche performance:")
            if niche_rows:
                for row in niche_rows:
                    niche_info = NICHE_PATTERNS.get(row[0], {})
                    label = niche_info.get("label", row[0])
                    lines.append(f"  • {label}: {row[2]}/{row[1]} ({row[3]}%)")
            else:
                lines.append("  Not enough data (need ≥5 samples per niche)")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to get learning insights: {e}")
            return "Error generating insights"

    def cleanup_old(self, days: int = 90) -> int:
        if not DATABASE_URL:
            return 0

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM response_outcomes
                        WHERE created_at < NOW() - %s * INTERVAL '1 day'
                    """, (days,))
                    deleted = cur.rowcount
                    logger.info(f"Cleaned up {deleted} old response outcomes (older than {days} days)")
                    return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old response outcomes: {e}")
            return 0


feedback_loop = FeedbackLoop()
