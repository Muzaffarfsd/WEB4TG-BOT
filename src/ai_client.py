import asyncio
import logging
import re
from typing import Any, List, Dict, Optional, Tuple
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.config import config
from src.knowledge_base import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def is_rate_limit_error(exc: BaseException) -> bool:
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__
    if "429" in exc_str or "rate" in exc_str or "quota" in exc_str:
        return True
    if "resourceexhausted" in exc_type.lower():
        return True
    if "too many requests" in exc_str:
        return True
    return False

VALID_TEMPLATE_PRICES = {150000, 170000, 180000, 200000}
VALID_SUBSCRIPTION_PRICES = {9900, 14900, 24900}
VALID_FEATURE_PRICE_MIN = 12000
VALID_FEATURE_PRICE_MAX = 120000
VALID_PREPAYMENT_PERCENT = 35
VALID_FREE_FIXES_DAYS = 14
VALID_TIMELINE_MIN = 7
VALID_TIMELINE_MAX = 30

KNOWN_FEATURES = {
    "каталог", "корзина", "авторизация", "поиск", "избранное", "отзывы",
    "оплата", "подписки", "рассрочка", "доставка", "пвз", "экспресс",
    "push", "чат", "видеозвонки", "лояльность", "промокоды", "реферальная",
    "аналитика", "админ-панель", "crm", "трекинг", "бронирование", "очередь",
    "календарь", "ai", "чат-бот", "рекомендации", "авто-ответы", "умный поиск",
    "голосовой", "telegram бот", "whatsapp", "google maps", "sms", "email", "1c", "api",
}

PRICE_CORRECTION_MAP = {
    "магазин": 150000, "интернет-магазин": 150000,
    "ресторан": 180000, "доставка": 180000,
    "фитнес": 200000, "фитнес-клуб": 200000,
    "услуги": 170000, "сервис": 170000,
}


def validate_response(response_text: str) -> Tuple[bool, str]:
    is_valid = True
    cleaned = response_text

    price_pattern = re.compile(r'(\d[\d\s]*\d)\s*(?:₽|руб|рублей)')
    for match in price_pattern.finditer(cleaned):
        raw_price = match.group(1).replace(" ", "").replace("\u00a0", "")
        try:
            price_val = int(raw_price)
        except ValueError:
            continue

        if price_val < 1000:
            continue

        if price_val in VALID_TEMPLATE_PRICES:
            continue
        if price_val in VALID_SUBSCRIPTION_PRICES:
            continue
        if VALID_FEATURE_PRICE_MIN <= price_val <= VALID_FEATURE_PRICE_MAX:
            if price_val % 1000 == 0:
                continue

        is_combined = False
        if price_val % 1000 == 0:
            for tp in VALID_TEMPLATE_PRICES:
                remainder = price_val - tp
                if remainder > 0 and remainder % 1000 == 0 and remainder <= 400000:
                    is_combined = True
                    break
        if is_combined:
            continue

        if 100000 <= price_val <= 500000:
            is_valid = False
            closest = min(VALID_TEMPLATE_PRICES, key=lambda p: abs(p - price_val))
            old_price_str = match.group(0)
            new_price_str = f"{closest:,}".replace(",", " ") + " ₽"
            cleaned = cleaned.replace(old_price_str, new_price_str)
            logger.warning(f"Replaced suspicious price {price_val} with {closest}")

    prepay_pattern = re.compile(r'(\d+)\s*%\s*(?:предоплат|аванс)')
    for match in prepay_pattern.finditer(cleaned.lower()):
        pct = int(match.group(1))
        if pct != VALID_PREPAYMENT_PERCENT:
            is_valid = False
            cleaned = cleaned.replace(match.group(0), f"{VALID_PREPAYMENT_PERCENT}% предоплат")
            logger.warning(f"Corrected prepayment from {pct}% to {VALID_PREPAYMENT_PERCENT}%")

    fixes_pattern = re.compile(r'(\d+)\s*(?:дн|день|дней)\s*(?:бесплатн|правок|исправлен)')
    for match in fixes_pattern.finditer(cleaned.lower()):
        days = int(match.group(1))
        if days != VALID_FREE_FIXES_DAYS:
            is_valid = False
            old_text = match.group(0)
            new_text = old_text.replace(str(days), str(VALID_FREE_FIXES_DAYS))
            cleaned = cleaned.replace(match.group(0), new_text)
            logger.warning(f"Corrected free fixes from {days} to {VALID_FREE_FIXES_DAYS} days")

    timeline_pattern = re.compile(r'за\s*(\d+)\s*(?:дн|день|дней)')
    for match in timeline_pattern.finditer(cleaned.lower()):
        days = int(match.group(1))
        if days < VALID_TIMELINE_MIN or days > VALID_TIMELINE_MAX:
            is_valid = False
            corrected = max(VALID_TIMELINE_MIN, min(days, VALID_TIMELINE_MAX))
            old_text = match.group(0)
            new_text = old_text.replace(str(days), str(corrected))
            cleaned = cleaned.replace(old_text, new_text)
            logger.warning(f"Corrected timeline from {days} to {corrected} days")

    guarantee_patterns = [
        r'гарантируем\s+(?:100|полн)',
        r'гарантия\s+(?:возврата|денег)',
        r'100%\s*(?:гарантия|uptime|аптайм)',
        r'бесплатн(?:о|ый|ая|ые)\s+(?:доработк|модул|функци)',
    ]
    for pat in guarantee_patterns:
        if re.search(pat, cleaned.lower()):
            is_valid = False
            logger.warning(f"Unauthorized guarantee detected: {pat}")

    discount_patterns = [
        r'скидк[аеу]\s+\d+\s*%(?!\s*(?:за\s+монет|при\s+накоплен|за\s+coin))',
        r'(?:дарим|даём|предоставляем)\s+скидк',
        r'персональн\w*\s+скидк',
        r'специальн\w*\s+скидк',
    ]
    for pat in discount_patterns:
        if re.search(pat, cleaned.lower()):
            context_around = cleaned.lower()
            if "монет" not in context_around and "coin" not in context_around and "bonus" not in context_around:
                is_valid = False
                logger.warning(f"Unauthorized discount detected: {pat}")

    ALLOWED_DOMAINS = {
        "web4tg.com", "t.me", "youtube.com", "www.youtube.com",
        "instagram.com", "www.instagram.com", "tiktok.com", "www.tiktok.com",
        "telegram.me",
    }
    url_pattern = re.compile(r'(?:\[([^\]]*)\]\()?(?:https?://)([\w.-]+)(/[^\s\)\]]*)?(?:\))?')
    for match in url_pattern.finditer(cleaned):
        domain = match.group(2).lower()
        if domain not in ALLOWED_DOMAINS:
            is_valid = False
            full_match = match.group(0)
            logger.warning(f"Removed hallucinated URL with domain '{domain}': {full_match}")
            cleaned = cleaned.replace(full_match, "")

    cleaned = re.sub(r'\[Скачать[^\]]*\]\s*', '', cleaned)
    cleaned = re.sub(r'📄\s*\*?\*?\s*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return (is_valid, cleaned)


def _compute_adaptive_word_limit(user_message: str, query_context: str = "") -> int:
    user_words = len(user_message.split())
    user_chars = len(user_message)

    if user_words <= 3 or user_chars <= 15:
        return 50
    if user_words <= 8 or user_chars <= 40:
        return 80
    if query_context in ("faq", "greeting", "simple"):
        return 80
    if query_context in ("creative", "upsell"):
        return 180
    if query_context in ("objection", "complex", "sales", "closing", "decision"):
        return 180

    question_marks = user_message.count("?")
    if question_marks >= 2 or user_words > 30:
        return 180

    return 120


def check_response_quality(response_text: str, user_message: str, query_context: str = "") -> str:
    if not response_text or not response_text.strip():
        return response_text

    cleaned = response_text.strip()

    fluff_openers = [
        "Конечно!", "Конечно,", "Безусловно!", "Безусловно,",
        "Разумеется!", "Разумеется,", "Несомненно!", "Несомненно,",
        "С удовольствием!", "С удовольствием,",
        "Отличный вопрос!", "Отличный вопрос,",
        "Хороший вопрос!", "Хороший вопрос,",
        "Спасибо за вопрос!", "Спасибо за вопрос,",
        "Рад, что вы спросили!", "Рад, что спросили!",
        "Здравствуйте!", "Добрый день!",
        "Благодарю за обращение!", "Благодарю!",
    ]
    for opener in fluff_openers:
        if cleaned.startswith(opener):
            rest = cleaned[len(opener):].strip()
            if rest:
                cleaned = rest
                logger.debug(f"Removed fluff opener: '{opener}'")
            break

    bot_phrases = [
        "Чем я могу вам помочь?", "Чем могу помочь?",
        "Обращайтесь, если будут вопросы!",
        "Я всегда готов помочь!", "Всегда рад помочь!",
        "Не стесняйтесь обращаться!",
        "Если у вас есть ещё вопросы, не стесняйтесь задавать!",
    ]
    for phrase in bot_phrases:
        if cleaned.endswith(phrase):
            rest = cleaned[:-len(phrase)].strip()
            if rest:
                cleaned = rest
                logger.debug(f"Removed bot phrase: '{phrase}'")

    response_words = len(cleaned.split())

    max_words = _compute_adaptive_word_limit(user_message, query_context)
    if response_words > max_words:
        sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        trimmed = []
        word_count = 0
        for sent in sentences:
            sent_words = len(sent.split())
            if word_count + sent_words > max_words and trimmed:
                break
            trimmed.append(sent)
            word_count += sent_words
        if trimmed:
            cleaned = " ".join(trimmed)
            logger.debug(f"Adaptive trim: {response_words} → {word_count} words (limit={max_words})")

    if len(cleaned.split()) > 40:
        cta_patterns = [
            r'давайте', r'напишите', r'попробуйте', r'посмотрите',
            r'расскажите', r'выбирайте', r'закажите', r'записывайтесь',
            r'свяжитесь', r'обращайтесь', r'звоните', r'пишите',
            r'/\w+', r'хотите\s', r'готовы\s', r'начнём',
            r'\?$', r'могу\s', r'предлагаю', r'начать',
            r'удобно\s', r'интересно\?',
        ]
        has_cta = any(re.search(pat, cleaned.lower()) for pat in cta_patterns)
        if not has_cta:
            if "?" not in cleaned[-100:]:
                cleaned += "\n\nРасскажите подробнее о вашем проекте — подберу оптимальное решение)"
                logger.debug("Added CTA to response without call-to-action")

    return cleaned


class AIClient:
    def __init__(self):
        from src.config import get_gemini_client
        self._client = get_gemini_client()

    def select_model_and_config(self, query_context: Optional[str] = None, dynamic_system_prompt: Optional[str] = None) -> Tuple[str, types.GenerateContentConfig]:
        sys_prompt = dynamic_system_prompt or SYSTEM_PROMPT

        if not query_context:
            return config.fast_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

        ctx = query_context.lower()

        if ctx in ("faq", "greeting", "simple"):
            return config.fast_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=1000,
                temperature=config.temperature_precise
            )
        elif ctx in ("objection", "complex", "sales"):
            return config.thinking_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
            )
        elif ctx in ("closing", "decision"):
            return config.thinking_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
            )
        elif ctx in ("creative", "upsell"):
            return config.fast_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature_creative
            )
        else:
            return config.fast_model_name, types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

    def _get_contextual_fallback(self, user_message: str) -> str:
        msg = user_message.lower() if user_message else ""

        if any(w in msg for w in ["цен", "стоимость", "сколько стоит", "прайс", "бюджет", "дорого", "price"]):
            return (
                "Шаблоны Mini App от 150 000 ₽ (магазин) до 200 000 ₽ (фитнес-клуб). "
                "Доп. функции от 12 000 ₽. Предоплата 35%, 14 дней правок бесплатно. "
                "Напишите /price для полного прайса или расскажите о проекте — посчитаю точнее)"
            )
        elif any(w in msg for w in ["портфолио", "примеры", "кейс", "работ", "portfolio"]):
            return (
                "У нас есть кейсы в e-commerce, ресторанах, фитнесе, услугах и образовании. "
                "Напишите /portfolio чтобы посмотреть примеры работ)"
            )
        elif any(w in msg for w in ["срок", "когда", "быстро", "сколько дней", "время", "deadline"]):
            return (
                "Сроки разработки: простой проект 7-10 дней, средний 10-15, сложный 15-20 дней. "
                "Расскажите о проекте — назову точные сроки)"
            )
        elif any(w in msg for w in ["оплат", "заплатить", "реквизит", "счёт", "payment"]):
            return (
                "Оплата в 2 этапа: 35% предоплата до начала работ, 65% после сдачи. "
                "Напишите /payment для реквизитов)"
            )
        elif any(w in msg for w in ["подписк", "обслужив", "поддержк", "subscription"]):
            return (
                "Подписки на обслуживание: Мини 9 900₽/мес, Стандарт 14 900₽/мес, Премиум 24 900₽/мес. "
                "Напишите /price → Подписки для деталей)"
            )
        elif any(w in msg for w in ["скидк", "акци", "промокод", "discount", "монет", "bonus"]):
            return (
                "Скидки за накопленные монеты: от 5% (500 монет) до 25% (2500+ монет). "
                "Зарабатывайте через /referral и задания в /bonus)"
            )
        elif any(w in msg for w in ["привет", "здравств", "добрый", "hello", "hi"]):
            return (
                "Привет) Я Алекс из WEB4TG Studio — делаем Telegram Mini Apps для бизнеса. "
                "Расскажите о вашем проекте или задайте вопрос — помогу разобраться)"
            )
        elif any(w in msg for w in ["консультац", "созвон", "звонок", "встреч"]):
            return (
                "Бесплатная консультация — отличная идея) "
                "Напишите /consult чтобы выбрать удобное время для созвона)"
            )
        else:
            return (
                "Сейчас небольшая задержка с ответом. "
                "Напишите ваш вопрос ещё раз через минуту, или используйте /help для навигации по командам)"
            )

    async def generate_response_stream(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        on_chunk=None,
        max_retries: int = 2,
        query_context: Optional[str] = None,
        dynamic_system_prompt: Optional[str] = None
    ) -> str:
        if query_context:
            model, gen_config = self.select_model_and_config(query_context, dynamic_system_prompt)
        elif thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=dynamic_system_prompt or SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=dynamic_system_prompt or SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                parts = msg.get("parts", [])
                if parts and isinstance(parts[0], dict):
                    user_message = parts[0].get("text", "")
                elif parts and isinstance(parts[0], str):
                    user_message = parts[0]
                break

        for attempt in range(max_retries + 1):
            try:
                import queue
                chunk_queue = queue.Queue()
                stream_error: list[Optional[Exception]] = [None]

                def _stream_in_thread():
                    full = ""
                    try:
                        stream = self._client.models.generate_content_stream(
                            model=model,
                            contents=messages,  # type: ignore[arg-type]
                            config=gen_config
                        )
                        for chunk in stream:
                            if chunk.text:
                                full += chunk.text
                                chunk_queue.put(full)
                    except Exception as e:
                        stream_error[0] = e
                        logger.warning(f"Stream error (attempt {attempt+1}/{max_retries+1}): {type(e).__name__}: {e}")
                    finally:
                        chunk_queue.put(None)
                    return full

                stream_task = asyncio.get_event_loop().run_in_executor(None, _stream_in_thread)

                full_text = ""
                while True:
                    try:
                        partial = await asyncio.to_thread(chunk_queue.get, timeout=0.3)
                        if partial is None:
                            break
                        full_text = partial
                        if on_chunk:
                            try:
                                await on_chunk(full_text)
                            except Exception:
                                pass
                    except Exception:
                        if stream_task.done():
                            while not chunk_queue.empty():
                                item = chunk_queue.get_nowait()
                                if item is None:
                                    break
                                full_text = item
                                if on_chunk:
                                    try:
                                        await on_chunk(full_text)
                                    except Exception:
                                        pass
                            break

                result = await stream_task
                if result:
                    full_text = result

                if stream_error[0] and not full_text:
                    if model != config.fast_model_name and attempt == max_retries:
                        logger.warning(f"Pro model failed after {max_retries+1} attempts, cascading to Flash: {stream_error[0]}")
                        model = config.fast_model_name
                        if gen_config.thinking_config:
                            gen_config = types.GenerateContentConfig(
                                system_instruction=gen_config.system_instruction,
                                max_output_tokens=gen_config.max_output_tokens,
                                temperature=gen_config.temperature,
                            )
                        attempt = -1
                        max_retries = 1
                        continue
                    if is_rate_limit_error(stream_error[0]) and attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)
                        logger.info(f"Stream rate limited, retrying in {delay}s (attempt {attempt+1}/{max_retries+1})")
                        await asyncio.sleep(delay)
                        continue
                    elif "timeout" in str(stream_error[0]).lower() and attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)
                        logger.info(f"Stream timeout, auto-retrying in {delay}s (attempt {attempt+1}/{max_retries+1})")
                        await asyncio.sleep(delay)
                        continue
                    elif attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)
                        logger.info(f"Stream failed, retrying in {delay}s (attempt {attempt+1}/{max_retries+1})")
                        await asyncio.sleep(delay)
                        continue

                if full_text:
                    is_valid, cleaned = validate_response(full_text)
                    if not is_valid:
                        logger.warning("Response validation found issues, using cleaned version")
                    return check_response_quality(cleaned, user_message, query_context=query_context or "")

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                if is_rate_limit_error(e):
                    if attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)
                        logger.warning(f"Gemini stream rate limit (attempt {attempt+1}), retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(f"Gemini stream rate limit exhausted: {error_type}: {error_msg}")
                    return self._get_contextual_fallback(user_message)
                if "timeout" in error_msg.lower():
                    if attempt < max_retries:
                        delay = 0.5 * (2 ** attempt)
                        logger.warning(f"Gemini stream timeout (attempt {attempt+1}), auto-retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(f"Gemini stream timeout exhausted: {error_type}: {error_msg}")
                    return self._get_contextual_fallback(user_message)
                logger.error(f"Gemini stream failed: {error_type}: {error_msg}")
                return self._get_contextual_fallback(user_message)

        logger.warning("Stream retries exhausted, providing contextual fallback")
        return self._get_contextual_fallback(user_message)

    async def generate_response(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        max_retries: int = 2,
        retry_delay: float = 0.5,
        query_context: Optional[str] = None,
        dynamic_system_prompt: Optional[str] = None
    ) -> str:
        if query_context:
            model, gen_config = self.select_model_and_config(query_context, dynamic_system_prompt)
        elif thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=dynamic_system_prompt or SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=dynamic_system_prompt or SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                parts = msg.get("parts", [])
                if parts and isinstance(parts[0], dict):
                    user_message = parts[0].get("text", "")
                elif parts and isinstance(parts[0], str):
                    user_message = parts[0]
                break
        
        current_model = model
        current_config = gen_config

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_delay, min=0.5, max=10),
            retry=retry_if_exception(is_rate_limit_error),
            reraise=True
        )
        async def _generate():
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=current_model,
                contents=messages,  # type: ignore[arg-type]
                config=current_config
            )
            return response
        
        try:
            response = await _generate()
            
            if response.text:
                is_valid, cleaned = validate_response(response.text)
                if not is_valid:
                    logger.warning("Response validation found issues, using cleaned version")
                return check_response_quality(cleaned, user_message, query_context=query_context or "")
            else:
                logger.warning("Empty response from Gemini")
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            if current_model != config.fast_model_name:
                logger.warning(f"Pro model failed ({error_type}), cascading to Flash")
                current_model = config.fast_model_name
                current_config = types.GenerateContentConfig(
                    system_instruction=current_config.system_instruction,
                    max_output_tokens=current_config.max_output_tokens,
                    temperature=current_config.temperature,
                )
                try:
                    response = await _generate()
                    if response.text:
                        is_valid, cleaned = validate_response(response.text)
                        return check_response_quality(cleaned, user_message, query_context=query_context or "")
                except Exception as fallback_e:
                    logger.error(f"Flash fallback also failed: {fallback_e}")

            if is_rate_limit_error(e):
                logger.warning(f"Gemini rate limit hit: {error_type}: {error_msg}")
            elif "timeout" in error_msg.lower() or "connect" in error_msg.lower():
                logger.error(f"Gemini connection error: {error_type}: {error_msg}")
            else:
                logger.error(f"Gemini request failed: {error_type}: {error_msg}")
            return self._get_contextual_fallback(user_message)
    
    async def generate_response_with_tools(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        on_chunk=None,
        query_context: Optional[str] = None,
        dynamic_system_prompt: Optional[str] = None
    ) -> dict:
        """Returns {"text": str, "tool_calls": list[dict], "all_tool_calls": list}"""
        try:
            sys_prompt = dynamic_system_prompt or SYSTEM_PROMPT
            if query_context and query_context in ("objection", "complex", "sales", "closing", "decision"):
                model = config.thinking_model_name
            elif thinking_level == "high":
                model = config.thinking_model_name
            else:
                model = config.fast_model_name

            tools = types.Tool(function_declarations=TOOL_DECLARATIONS)  # type: ignore[arg-type]
            gen_config = types.GenerateContentConfig(
                system_instruction=sys_prompt,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                tools=[tools],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode=types.FunctionCallingConfigMode.AUTO)
                )
            )

            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=messages,  # type: ignore[arg-type]
                config=gen_config
            )

            tool_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        fc = part.function_call
                        tool_calls.append({
                            "name": fc.name,
                            "args": dict(fc.args) if fc.args else {}
                        })

            if tool_calls:
                return {"text": None, "tool_calls": tool_calls, "all_tool_calls": tool_calls}

            text = response.text if response.text else None
            return {"text": text, "tool_calls": [], "all_tool_calls": []}

        except Exception as e:
            logger.warning(f"Tool calling failed, falling back to regular response: {e}")
            fallback = await self.generate_response(messages, thinking_level)
            return {"text": fallback, "tool_calls": [], "all_tool_calls": []}

    async def agentic_loop(
        self,
        messages: List[Dict],
        tool_executor,
        thinking_level: str = "medium",
        max_steps: int = 4,
        query_context: Optional[str] = None,
        dynamic_system_prompt: Optional[str] = None
    ) -> dict:
        """Multi-step agentic loop: AI calls tools, gets results, decides next action.
        
        Returns {"text": str, "special_actions": list, "all_tool_results": list}
        """
        all_tool_results = []
        special_actions = []
        current_messages = list(messages)
        
        effective_thinking = thinking_level
        if query_context in ("objection", "complex", "sales"):
            effective_thinking = "high"
        elif query_context in ("faq", "greeting", "simple"):
            effective_thinking = "low"

        for step in range(max_steps):
            result = await self.generate_response_with_tools(
                messages=current_messages,
                thinking_level=effective_thinking,
                query_context=query_context,
                dynamic_system_prompt=dynamic_system_prompt
            )
            
            if not result["tool_calls"]:
                return {
                    "text": result["text"],
                    "special_actions": special_actions,
                    "all_tool_results": all_tool_results
                }
            
            step_tool_results = []
            for tc in result["tool_calls"]:
                try:
                    tool_result = await tool_executor(tc["name"], tc["args"])
                except Exception as e:
                    tool_result = f"Ошибка вызова инструмента {tc['name']}: {e}"
                    logger.error(f"Tool executor error for {tc['name']}: {e}")
                
                if not isinstance(tool_result, str):
                    tool_result = str(tool_result) if tool_result is not None else "Нет результата"
                
                if tool_result.startswith("[PORTFOLIO:"):
                    special_actions.append(("portfolio", tool_result))
                    step_tool_results.append(f"{tc['name']}: показано портфолио")
                elif tool_result == "[PRICING]":
                    special_actions.append(("pricing", None))
                    step_tool_results.append(f"{tc['name']}: показан прайс")
                elif tool_result == "[PAYMENT]":
                    special_actions.append(("payment", None))
                    step_tool_results.append(f"{tc['name']}: показана оплата")
                elif tool_result == "[AI_BRIEF_GENERATED]":
                    special_actions.append(("ai_brief", None))
                    step_tool_results.append(f"{tc['name']}: AI сформировал бриф проекта")
                else:
                    step_tool_results.append(f"{tc['name']}: {tool_result}")
                    all_tool_results.append({"tool": tc["name"], "result": tool_result})
            
            tool_results_text = "\n\n".join(step_tool_results)
            current_messages.append({
                "role": "model",
                "parts": [{"text": f"Я вызвал инструменты. Результаты:\n{tool_results_text}"}]
            })
            current_messages.append({
                "role": "user",
                "parts": [{"text": "Проанализируй результаты. Если нужно — вызови ещё инструменты для полного ответа. Если данных достаточно — сформулируй финальный ответ клиенту."}]
            })
            
            logger.info(f"Agentic loop step {step+1}: {len(result['tool_calls'])} tool calls")
        
        final_response = await self.generate_response(
            messages=current_messages,
            thinking_level=effective_thinking,
            query_context=query_context,
            dynamic_system_prompt=dynamic_system_prompt
        )
        
        return {
            "text": final_response,
            "special_actions": special_actions,
            "all_tool_results": all_tool_results
        }

    async def analyze_complex_query(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        prompt = query
        if context:
            prompt = f"Контекст: {context}\n\nВопрос: {query}"
        
        messages = [{"role": "user", "parts": [{"text": prompt}]}]
        return await self.generate_response(messages, thinking_level="high")
    
    async def quick_response(self, query: str) -> str:
        messages = [{"role": "user", "parts": [{"text": query}]}]
        return await self.generate_response(messages, thinking_level="low")


TOOL_DECLARATIONS = [
    {
        "name": "calculate_price",
        "description": "Рассчитать стоимость разработки Telegram Mini App по набору функций. Вызывай когда клиент спрашивает цену конкретного набора функций или хочет посчитать стоимость.",
        "parameters": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список функций: catalog, cart, auth, search, favorites, reviews, payments, subscriptions, installments, delivery, pickup, express, push, chat, video, loyalty, promo, referral, analytics, admin, crm, booking, queue, calendar, ai, ai_rec, auto_reply, smart_search, voice, tg_bot, whatsapp, maps, sms, email, 1c, api, progress"
                }
            },
            "required": ["features"]
        }
    },
    {
        "name": "show_portfolio",
        "description": "Показать примеры работ из портфолио. Вызывай когда клиент хочет увидеть примеры, кейсы или портфолио.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["ecommerce", "services", "fintech", "education", "all"],
                    "description": "Категория портфолио"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "show_pricing",
        "description": "Показать общий прайс-лист услуг. Вызывай когда клиент спрашивает о ценах в общем.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_lead",
        "description": "Создать заявку от клиента. Вызывай когда клиент говорит что хочет заказать, готов начать, просит связаться с ним.",
        "parameters": {
            "type": "object",
            "properties": {
                "interest": {
                    "type": "string",
                    "description": "Что интересует клиента"
                },
                "budget": {
                    "type": "string",
                    "description": "Примерный бюджет, если озвучен"
                }
            },
            "required": ["interest"]
        }
    },
    {
        "name": "show_payment_info",
        "description": "Показать реквизиты для оплаты. Вызывай когда клиент готов оплатить или спрашивает как оплатить.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "calculate_roi",
        "description": "Рассчитать окупаемость (ROI) Telegram Mini App для бизнеса клиента. Вызывай когда клиент сомневается в выгоде, спрашивает 'зачем мне это' или 'окупится ли'.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_type": {
                    "type": "string",
                    "description": "Тип бизнеса: restaurant, shop, beauty, education, services, fitness, delivery, other"
                },
                "monthly_clients": {
                    "type": "integer",
                    "description": "Примерное количество клиентов в месяц"
                },
                "avg_check": {
                    "type": "integer",
                    "description": "Средний чек в рублях"
                },
                "app_cost": {
                    "type": "integer",
                    "description": "Стоимость приложения в рублях (по умолчанию 150000). Используй если клиент уже обсудил конкретный бюджет."
                }
            },
            "required": ["business_type"]
        }
    },
    {
        "name": "compare_plans",
        "description": "Сравнить тарифные планы и пакеты услуг. Вызывай когда клиент не может выбрать между вариантами или просит сравнение.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "enum": ["packages", "subscriptions", "custom_vs_template"],
                    "description": "Что сравнить: packages (MVP/Standard/Premium), subscriptions (подписки), custom_vs_template (заказная vs шаблон)"
                }
            },
            "required": ["plan_type"]
        }
    },
    {
        "name": "schedule_consultation",
        "description": "Записать клиента на бесплатную консультацию с менеджером. Вызывай когда клиент хочет обсудить проект подробнее, задаёт сложные вопросы или готов к созвону.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_time": {
                    "type": "string",
                    "description": "Предпочитаемое время (если указано)"
                },
                "topic": {
                    "type": "string",
                    "description": "Тема консультации"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "generate_brief",
        "description": "Автоматически сформировать бриф проекта и предложить PDF коммерческое предложение. Вызывай когда из разговора ты собрал достаточно информации о проекте клиента (минимум: тип проекта + бюджет/приоритет). Заполни максимум полей на основе контекста диалога. AI должен ПРОАКТИВНО предлагать сформировать бриф, когда понимает потребности клиента.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_type": {
                    "type": "string",
                    "enum": ["shop", "restaurant", "beauty", "fitness", "medical", "education", "services", "custom"],
                    "description": "Тип проекта: shop=магазин, restaurant=ресторан/доставка, beauty=салон красоты, fitness=фитнес, medical=медицина, education=образование, services=услуги, custom=кастомный"
                },
                "audience": {
                    "type": "string",
                    "enum": ["b2c_young", "b2c_adult", "b2c_premium", "b2c_mass", "b2b", "mixed"],
                    "description": "Аудитория: b2c_young=молодёжь 18-35, b2c_adult=семейные 25-45, b2c_premium=премиум, b2c_mass=массовый, b2b=бизнес, mixed=смешанная"
                },
                "key_features": {
                    "type": "string",
                    "enum": ["catalog_cart", "booking", "payments", "loyalty", "ai_bot", "delivery", "analytics", "crm"],
                    "description": "Главная функция: catalog_cart=каталог+корзина, booking=бронирование, payments=оплата, loyalty=лояльность, ai_bot=AI бот, delivery=доставка, analytics=аналитика, crm=CRM"
                },
                "design_pref": {
                    "type": "string",
                    "enum": ["minimal", "modern", "premium", "bright", "corporate", "custom_design"],
                    "description": "Стиль дизайна: minimal, modern, premium, bright=яркий, corporate, custom_design=свой макет"
                },
                "integrations": {
                    "type": "string",
                    "enum": ["tg_payments", "bank_cards", "1c", "crm_ext", "maps", "sms_email", "none"],
                    "description": "Интеграции: tg_payments=Telegram Stars, bank_cards=карты, 1c, crm_ext=Bitrix/AmoCRM, maps, sms_email, none"
                },
                "budget_timeline": {
                    "type": "string",
                    "enum": ["fast_cheap", "balanced", "quality", "mvp_first"],
                    "description": "Приоритет: fast_cheap=быстро и бюджетно, balanced=баланс, quality=максимальное качество, mvp_first=сначала MVP"
                },
                "project_description": {
                    "type": "string",
                    "description": "Краткое описание проекта клиента своими словами"
                }
            },
            "required": ["project_type", "budget_timeline"]
        }
    },
    {
        "name": "check_discount",
        "description": "Проверить доступные скидки для клиента. Вызывай когда клиент спрашивает про скидки, акции, промокоды.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "show_available_slots",
        "description": "Показать доступные слоты для записи на консультацию. Вызывай когда клиент хочет записаться на конкретное время или спрашивает когда можно созвониться.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "book_consultation_slot",
        "description": "Забронировать конкретный слот для консультации. Вызывай когда клиент выбрал дату и время для созвона.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Дата в формате YYYY-MM-DD"
                },
                "time": {
                    "type": "string",
                    "description": "Время в формате HH:MM"
                },
                "topic": {
                    "type": "string",
                    "description": "Тема консультации"
                }
            },
            "required": ["date", "time"]
        }
    },
    {
        "name": "show_social_links",
        "description": "Показать ссылки на соцсети WEB4TG Studio. Вызывай когда клиент спрашивает о соцсетях, YouTube, Instagram, TikTok, или хочет подписаться.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_tasks": {
                    "type": "boolean",
                    "description": "Показать задания за монеты (подписка = монеты)"
                }
            }
        }
    },
    {
        "name": "search_knowledge_base",
        "description": "Поиск в базе знаний WEB4TG Studio. Вызывай когда нужно найти точную информацию о технологиях, процессах, гарантиях, условиях работы или деталях, которых нет в прайсе. Полезно для ответов на нестандартные вопросы.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос — что именно нужно найти в базе знаний"
                },
                "limit": {
                    "type": "integer",
                    "description": "Количество результатов (по умолчанию 3)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "remember_client_info",
        "description": "Сохранить важную информацию о клиенте для персонализации будущих ответов. Вызывай когда клиент рассказывает о своём бизнесе, бюджете, сроках, потребностях или возражениях. Это позволяет помнить контекст между сессиями.",
        "parameters": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Отрасль бизнеса: shop, restaurant, beauty, fitness, medical, education, delivery, services, other"
                },
                "budget_range": {
                    "type": "string",
                    "description": "Примерный бюджет клиента, например '150-200к' или 'до 300к'"
                },
                "timeline": {
                    "type": "string",
                    "description": "Желаемые сроки, например 'срочно', '2 недели', 'к лету'"
                },
                "needs": {
                    "type": "string",
                    "description": "Ключевые потребности клиента (что хочет реализовать)"
                },
                "objections": {
                    "type": "string",
                    "description": "Основные возражения или сомнения клиента"
                },
                "business_name": {
                    "type": "string",
                    "description": "Название бизнеса клиента, если озвучено"
                },
                "city": {
                    "type": "string",
                    "description": "Город клиента, если озвучен"
                }
            }
        }
    },
    {
        "name": "compare_with_competitors",
        "description": "Сравнить разработку в WEB4TG Studio с альтернативами. Вызывай когда клиент упоминает конкурентов, фрилансеров, конструкторы или собственную разработку.",
        "parameters": {
            "type": "object",
            "properties": {
                "competitor_type": {
                    "type": "string",
                    "enum": ["freelancer", "agency", "constructor", "nocode", "inhouse", "general"],
                    "description": "Тип альтернативы для сравнения"
                }
            },
            "required": ["competitor_type"]
        }
    },
    {
        "name": "request_screenshot",
        "description": "Попросить клиента прислать скриншот или фото для профессионального анализа. Вызывай когда клиент описывает свой сайт/приложение/бизнес словами, но визуальный анализ даст лучший результат. Также вызывай когда клиент упоминает конкурента — предложи прислать скриншот для детального сравнения.",
        "parameters": {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["app_audit", "website_audit", "competitor_analysis", "design_review", "business_photo", "document_review"],
                    "description": "Тип запрашиваемого анализа: app_audit=аудит приложения, website_audit=аудит сайта, competitor_analysis=анализ конкурента, design_review=ревью дизайна, business_photo=фото бизнеса, document_review=анализ ТЗ/документа"
                },
                "reason": {
                    "type": "string",
                    "description": "Почему визуальный анализ будет полезен клиенту"
                }
            },
            "required": ["analysis_type", "reason"]
        }
    }
]


ai_client = AIClient()
