import asyncio
import logging
import re
import hashlib
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.config import config
from src.leads import lead_manager
from src.keyboards import get_loyalty_menu_keyboard

from src.handlers.utils import (
    send_typing_action, apply_stress_marks, expand_abbreviations,
    numbers_to_words, naturalize_speech,
    loyalty_system, MANAGER_CHAT_ID
)

logger = logging.getLogger(__name__)

_elevenlabs_client = None
_voice_cache = {}


def _get_elevenlabs_client():
    global _elevenlabs_client
    if _elevenlabs_client is None and config.elevenlabs_api_key:
        from elevenlabs import ElevenLabs
        _elevenlabs_client = ElevenLabs(api_key=config.elevenlabs_api_key)
    return _elevenlabs_client


VOICE_EMOTION_PROMPT = """Ты эксперт по подготовке текста для озвучки через ElevenLabs v3. Твоя главная цель — сделать речь НЕОТЛИЧИМОЙ от живого человека-консультанта.

ДОСТУПНЫЕ ТЕГИ v3 (в квадратных скобках перед фразой):
Эмоции: [happy] [sad] [angry] [excited] [nervous]
Акустика: [whispers] [shouts] [laughs] [giggles] [sighs]
Стиль: [friendly] [calm] [confident] [warm] [curious]

ПРАВИЛА ЖИВОЙ РЕЧИ (приоритет — естественность):

1. ДЫХАНИЕ И РИТМ:
   - Разбивай длинные предложения на 8-12 слов — человек дышит между фразами
   - Ставь "..." для микро-пауз (раздумье, переход мысли): "Ну вот... получается так"
   - Ставь " — " для смены темы или акцента: "Магазин — это наш конёк"
   - Чередуй длинные и короткие фразы для живого ритма

2. РЕЧЕВЫЕ МАРКЕРЫ ЖИВОГО ЧЕЛОВЕКА (добавляй 2-3 на ответ):
   - Начало мысли: "Смотрите,", "Знаете что,", "Вот что скажу —", "Ну смотрите,"
   - Переходы: "Кстати,", "И ещё момент —", "А вот тут интересно —"
   - Размышление: "Хм...", "Ну...", "Как бы это сказать..."
   - Подтверждение: "Да-да,", "Точно,", "Именно,"
   - Не переусердствуй — 2-3 маркера на весь ответ, естественно распределённых

3. ЭМОЦИОНАЛЬНАЯ ПАЛИТРА ПРОДАВЦА:
   - Приветствие: [warm] или [friendly] — тёплый старт
   - Цены и факты: [confident] — уверенность, компетентность
   - Выгоды и кейсы: [excited] — энтузиазм заразителен
   - Вопросы: [curious] — искренний интерес
   - Возражения: [calm] → [warm] — спокойствие и забота
   - Секреты: [whispers] "между нами..." — эффект доверия
   - Юмор: [giggles] — лёгкость в общении
   - Максимум 3-4 тега на ответ, НЕ на каждое предложение

4. ИНТОНАЦИОННЫЕ ПРИЁМЫ:
   - Восходящая интонация вопроса: "А вы пробовали считать, сколько клиентов теряете?"
   - Пауза перед ключевым числом: "И вот результат... плюс сорок процентов к заказам"
   - Перечисление с ускорением: "Каталог, корзина, оплата — всё в одном"
   - Финальный акцент: последнюю фразу делай с уверенной точкой

5. ЧИСТКА ТЕКСТА:
   - Убери ВСЮ markdown разметку: **, *, #, •, `, _
   - Замени переносы строк на паузы (". " или ", ")
   - Убери emoji
   - НЕ меняй смысл, только оформи для естественной речи
   - Числа пиши с пробелами (150 000)

Верни ТОЛЬКО обработанный текст.

Текст:
"""

VOICE_CONTEXT_INSTRUCTION = """
[ГОЛОСОВОЙ ФОРМАТ] Клиент общается голосовыми. Твой ответ ОЗВУЧАТ — пиши КАК ГОВОРИШЬ вслух.

ГЛАВНОЕ — ты живой консультант Алекс, а не текстовый бот. Вот как ты говоришь:

ДЛИНА ОТВЕТА (КРИТИЧЕСКИ ВАЖНО):
- СТРОГО 300-500 символов (20-30 секунд). Это МАКСИМУМ.
- Одна ключевая мысль на ответ. Не пытайся уместить всё.
- Если тема сложная — ответь на главное и скажи "Могу подробнее рассказать, если интересно".
- Лучше короткий живой ответ, чем длинная лекция.

СТИЛЬ РЕЧИ:
- Никакого markdown, emoji, списков с тире или звёздочками.
- Говори как в жизни: "Ну смотрите, тут вот какая история..." а не "Вот перечень преимуществ:"
- Перечисляй через речь: "во-первых... во-вторых..." или "и каталог, и корзина, и оплата"
- Числа — словами: "сто пятьдесят тысяч", "около двухсот тысяч"
- Аббревиатуры раскрывай: "возврат инвестиций" вместо "ROI"

ПРИЁМЫ ЖИВОГО ЧЕЛОВЕКА (используй 1-2 за ответ):
- Думай вслух: "Хм, давайте прикинем...", "Вот что я бы предложил..."
- Переходы: "Кстати,", "И знаете что —"
- Эмпатия: "Да, понимаю,", "Логичный вопрос,"
- Паузы через "..." и " — " для естественного дыхания
- Чередуй длинные и короткие фразы: "Магазин за сто пятьдесят. Семь-десять дней. Готово."

ЧЕГО ИЗБЕГАТЬ:
- Шаблонных фраз типа "Рад помочь!", "Отличный выбор!"
- Списков (1. 2. 3.) — это текстовый формат, не устный
- Формальных оборотов: "В рамках нашего сотрудничества..."
- Повторения одних и тех же слов-филлеров
- Длинных монологов больше 500 символов
"""


async def analyze_emotions_and_prepare_text(text: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.gemini_api_key)

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.model_name,
            contents=[VOICE_EMOTION_PROMPT + text],
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3
            )
        )

        if response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Emotion analysis error: {e}")

    return text


def _clean_text_for_voice(text: str) -> str:
    clean = text.replace("**", "").replace("*", "").replace("#", "")
    clean = clean.replace("`", "").replace("_", " ")
    clean = clean.replace("•", ",").replace("—", " — ")
    clean = clean.replace("\n\n", ". ").replace("\n", ", ")
    clean = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001f926-\U0001f937\U00010000-\U0010ffff\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030\u2066\u2069]+', '', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)
    clean = re.sub(r'[,\.]{2,}', '.', clean)
    return clean.strip()


VOICE_PROFILES = {
    "greeting": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.7},
    "empathy": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.65},
    "factual": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.5},
    "excited": {"stability": 0.3, "similarity_boost": 0.75, "style": 0.8},
    "default": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.6},
}


def _detect_voice_profile(text: str) -> dict:
    lower = text.lower()
    if any(w in lower for w in ['привет', 'здравствуй', 'добро пожалов', 'рад вас', 'знакомств']):
        return VOICE_PROFILES["greeting"]
    if any(w in lower for w in ['понимаю', 'сочувств', 'непросто', 'к сожалению', 'извин', 'жаль', 'бывает']):
        return VOICE_PROFILES["empathy"]
    if any(w in lower for w in ['стоимость', 'цена', 'рублей', 'тысяч', 'процент', 'срок', 'гарантия', 'договор']):
        return VOICE_PROFILES["factual"]
    if any(w in lower for w in ['отлично', 'замечательно', 'круто', 'результат', 'рост', 'увеличил', 'сэкономил']):
        return VOICE_PROFILES["excited"]
    return VOICE_PROFILES["default"]


async def generate_voice_response(text: str, use_cache: bool = False, voice_profile: str = None) -> bytes:
    global _voice_cache
    
    el_client = _get_elevenlabs_client()
    if not el_client:
        raise RuntimeError("ElevenLabs client not configured")

    clean_text = _clean_text_for_voice(text)
    
    if use_cache:
        cache_key = hashlib.md5(clean_text.encode()).hexdigest()
        if cache_key in _voice_cache:
            logger.debug("Using cached voice response")
            return _voice_cache[cache_key]

    voice_text = await analyze_emotions_and_prepare_text(clean_text)

    voice_text = naturalize_speech(voice_text)
    voice_text = expand_abbreviations(voice_text)
    voice_text = numbers_to_words(voice_text)
    voice_text = apply_stress_marks(voice_text)

    if len(voice_text) > 4500:
        cut_pos = voice_text[:4500].rfind('.')
        if cut_pos > 3000:
            voice_text = voice_text[:cut_pos + 1]
        else:
            voice_text = voice_text[:4500].rsplit(' ', 1)[0] + '.'

    if voice_profile and voice_profile in VOICE_PROFILES:
        profile = VOICE_PROFILES[voice_profile]
    else:
        profile = _detect_voice_profile(voice_text)

    try:
        from elevenlabs import VoiceSettings
        
        audio_generator = await asyncio.to_thread(
            el_client.text_to_speech.convert,
            voice_id=config.elevenlabs_voice_id,
            text=voice_text,
            model_id="eleven_v3",
            output_format="mp3_44100_192",
            voice_settings=VoiceSettings(
                stability=profile["stability"],
                similarity_boost=profile["similarity_boost"],
                style=profile["style"],
            )
        )

        audio_bytes = b"".join(audio_generator)
        
        if use_cache:
            cache_key = hashlib.md5(clean_text.encode()).hexdigest()
            _voice_cache[cache_key] = audio_bytes
            if len(_voice_cache) > 10:
                oldest = next(iter(_voice_cache))
                del _voice_cache[oldest]
        
        return audio_bytes
    except Exception as e:
        logger.error(f"ElevenLabs voice generation failed ({type(e).__name__}): {e}")
        raise


async def _transcribe_voice(voice_bytes: bytes) -> str:
    result = await _transcribe_voice_with_emotion(voice_bytes)
    return result.get("text", "")


async def _convert_ogg_to_wav(ogg_bytes: bytes) -> bytes:
    import tempfile
    import os
    from io import BytesIO

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_ogg(BytesIO(ogg_bytes))
        audio = audio.set_frame_rate(16000).set_channels(1)
        wav_buffer = BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_data = wav_buffer.getvalue()
        logger.info(f"Converted OGG ({len(ogg_bytes)} bytes) to WAV ({len(wav_data)} bytes) via pydub")
        return wav_data
    except Exception as e:
        logger.warning(f"pydub conversion failed: {e}")

    ogg_path = None
    wav_path = None
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as ogg_file:
            ogg_file.write(ogg_bytes)
            ogg_path = ogg_file.name
        wav_path = ogg_path.replace('.ogg', '.wav')
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', ogg_path, '-ar', '16000', '-ac', '1', '-f', 'wav', wav_path],
            capture_output=True, timeout=15
        )
        if result.returncode == 0:
            with open(wav_path, 'rb') as f:
                wav_data = f.read()
            logger.info(f"Converted OGG ({len(ogg_bytes)} bytes) to WAV ({len(wav_data)} bytes) via ffmpeg")
            return wav_data
        else:
            logger.warning(f"ffmpeg conversion failed: {result.stderr[:200]}")
    except FileNotFoundError:
        logger.warning("ffmpeg not found")
    except Exception as e:
        logger.warning(f"ffmpeg conversion error: {e}")
    finally:
        for p in [ogg_path, wav_path]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass
    return b""


def _parse_emotion_json(raw: str) -> dict:
    import json as _json

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        parsed = _json.loads(raw)
        return {
            "text": parsed.get("text", "").strip(),
            "emotion": parsed.get("emotion", "neutral"),
            "energy": parsed.get("energy", "medium")
        }
    except _json.JSONDecodeError:
        pass

    json_match = re.search(r'\{[^}]*"text"\s*:\s*"[^"]*"[^}]*\}', raw)
    if not json_match:
        json_match = re.search(r'\{[^}]+\}', raw)
    if json_match:
        try:
            parsed = _json.loads(json_match.group())
            return {
                "text": parsed.get("text", "").strip(),
                "emotion": parsed.get("emotion", "neutral"),
                "energy": parsed.get("energy", "medium")
            }
        except _json.JSONDecodeError:
            pass

    clean_text = raw.strip().strip('"').strip("'")
    if len(clean_text) > 5 and not clean_text.startswith("{"):
        return {"text": clean_text, "emotion": "neutral", "energy": "medium"}
    return {"text": "", "emotion": "neutral", "energy": "medium"}


async def _transcribe_voice_with_emotion(voice_bytes: bytes) -> dict:
    from google import genai
    from google.genai import types
    import tempfile
    import os

    client = genai.Client(api_key=config.gemini_api_key)
    audio_model = config.audio_model_name

    prompt_text = (
        "Проанализируй это голосовое сообщение. Верни JSON:\n"
        '{"text": "дословная расшифровка на языке оригинала", '
        '"emotion": "одно слово: confident/hesitant/frustrated/excited/neutral/friendly/rushed/calm", '
        '"energy": "low/medium/high"}\n'
        "Если не можешь разобрать текст — верни пустой text.\n"
        "Верни ТОЛЬКО JSON, без комментариев и markdown."
    )

    wav_bytes = await _convert_ogg_to_wav(voice_bytes)

    strategies = []

    if wav_bytes:
        strategies.append(("files_api_wav", wav_bytes, "audio/wav", ".wav"))
        strategies.append(("inline_wav", wav_bytes, "audio/wav", None))
    strategies.append(("files_api_ogg", bytes(voice_bytes), "audio/ogg", ".ogg"))
    strategies.append(("inline_ogg", bytes(voice_bytes), "audio/ogg", None))

    for strategy_name, audio_data, mime, suffix in strategies:
        uploaded_file = None
        tmp_path = None
        try:
            if strategy_name.startswith("files_api"):
                try:
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                        tmp.write(audio_data)
                        tmp_path = tmp.name

                    upload_config = types.UploadFileConfig(mime_type=mime)
                    uploaded_file = await asyncio.to_thread(
                        client.files.upload,
                        file=tmp_path,
                        config=upload_config
                    )
                    logger.info(f"[{strategy_name}] Uploaded {len(audio_data)} bytes, uri={uploaded_file.uri}, mime={uploaded_file.mime_type}")

                    audio_part = types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=mime
                    )
                except Exception as upload_err:
                    logger.warning(f"[{strategy_name}] Upload failed: {upload_err}")
                    continue
                finally:
                    if tmp_path:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
            else:
                audio_part = types.Part.from_bytes(data=audio_data, mime_type=mime)
                logger.info(f"[{strategy_name}] Using inline {len(audio_data)} bytes, mime={mime}")

            text_part = types.Part(text=prompt_text)

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=audio_model,
                contents=[audio_part, text_part],
                config=types.GenerateContentConfig(
                    max_output_tokens=600,
                    temperature=0.1
                )
            )

            resp_text = None
            try:
                resp_text = response.text
            except (ValueError, AttributeError):
                candidates = getattr(response, 'candidates', None)
                if candidates and len(candidates) > 0:
                    parts = getattr(candidates[0].content, 'parts', [])
                    if parts:
                        resp_text = getattr(parts[0], 'text', None)

            logger.info(f"[{strategy_name}] model={audio_model}, response={resp_text[:300] if resp_text else 'None'}")

            if resp_text:
                result = _parse_emotion_json(resp_text.strip())
                if result["text"]:
                    if uploaded_file:
                        try:
                            await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
                        except Exception:
                            pass
                    return result
                logger.warning(f"[{strategy_name}] Parsed text is empty from raw: {resp_text[:300]}")
            else:
                logger.warning(f"[{strategy_name}] No text in response, candidates={getattr(response, 'candidates', 'N/A')}")

        except Exception as e:
            logger.error(f"[{strategy_name}] Transcription error: {e}", exc_info=True)
        finally:
            if uploaded_file:
                try:
                    await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
                except Exception:
                    pass

    logger.error(f"All transcription strategies failed for {len(voice_bytes)} bytes audio")
    return {"text": "", "emotion": "neutral", "energy": "medium"}


EMOTION_TO_VOICE_STYLE = {
    "confident": "Клиент звучит уверенно — говори на его уровне, факты и конкретика.",
    "hesitant": "Клиент звучит нерешительно — будь мягче, убирай давление, предлагай маленькие шаги.",
    "frustrated": "Клиент звучит раздражённо — прояви эмпатию, признай проблему, предложи решение.",
    "excited": "Клиент звучит воодушевлённо — поддержи энтузиазм, усиль эмоцию, двигай к действию.",
    "neutral": "",
    "friendly": "Клиент звучит дружелюбно — зеркаль тёплый тон, будь открытым.",
    "rushed": "Клиент торопится — будь максимально кратким, только суть.",
    "calm": "Клиент спокоен — отвечай размеренно, без суеты."
}


VOICE_SALES_TRIGGERS = {
    "price_discussion": ["цена", "стоимость", "сколько стоит", "бюджет", "дорого", "дешевле", "скидк"],
    "objection": ["не уверен", "подумаю", "дорого", "потом", "не знаю", "сомневаюсь", "может быть"],
    "decision": ["готов", "хочу заказать", "давайте", "начинаем", "оплата", "договор", "когда начнём"],
    "closing": ["оплатить", "реквизит", "счёт", "предоплат", "договор подпис"],
}


PROACTIVE_VOICE_COOLDOWN = 600
PROACTIVE_VOICE_MAX_PER_SESSION = 3


def should_send_proactive_voice(user_id: int, message_text: str, context_user_data: dict) -> bool:
    import time as _time

    if not config.elevenlabs_api_key:
        return False
    if not context_user_data.get('prefers_voice'):
        return False
    if context_user_data.get('voice_message_count', 0) < 1:
        return False

    proactive_count = context_user_data.get('proactive_voice_count', 0)
    if proactive_count >= PROACTIVE_VOICE_MAX_PER_SESSION:
        return False

    last_voice_ts = context_user_data.get('last_proactive_voice_ts', 0)
    if _time.time() - last_voice_ts < PROACTIVE_VOICE_COOLDOWN:
        return False

    triggered = False
    lower = message_text.lower()
    for trigger_words in VOICE_SALES_TRIGGERS.values():
        if any(w in lower for w in trigger_words):
            triggered = True
            break

    if not triggered:
        try:
            from src.context_builder import detect_funnel_stage
            stage = detect_funnel_stage(user_id, message_text, 0)
            if stage in ("decision", "action"):
                triggered = True
        except Exception:
            pass

    if not triggered:
        try:
            from src.propensity import propensity_scorer
            score = propensity_scorer.get_score(user_id)
            if score and score >= 60:
                triggered = True
        except Exception:
            pass

    if triggered:
        context_user_data['last_proactive_voice_ts'] = _time.time()
        context_user_data['proactive_voice_count'] = proactive_count + 1

    return triggered


def _make_text_summary(full_text: str, max_len: int = 300) -> str:
    clean = full_text.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
    clean = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001f926-\U0001f937\U00010000-\U0010ffff\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030\u2066\u2069]+', '', clean)
    if len(clean) <= max_len:
        return clean.strip()
    cut = clean[:max_len].rfind('.')
    if cut > max_len * 0.5:
        return clean[:cut + 1].strip()
    cut = clean[:max_len].rfind(' ')
    if cut > 0:
        return clean[:cut].strip() + "..."
    return clean[:max_len].strip() + "..."


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        voice_bytes = await file.download_as_bytearray()

        voice_analysis = await _transcribe_voice_with_emotion(voice_bytes)
        transcription = voice_analysis.get("text", "")
        client_emotion = voice_analysis.get("emotion", "neutral")
        client_energy = voice_analysis.get("energy", "medium")

        if not transcription:
            typing_task.cancel()
            await update.message.reply_text(
                "Не удалось распознать сообщение. Попробуйте ещё раз или напишите текстом."
            )
            return

        logger.info(f"User {user.id} voice transcribed ({len(transcription)} chars, emotion={client_emotion}, energy={client_energy}): {transcription[:100]}...")

        session = session_manager.get_session(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

        session.add_message("user", transcription, config.max_history_length)
        lead_manager.save_message(user.id, "user", f"[Голосовое] {transcription}")
        lead_manager.log_event("voice_message", user.id, {
            "duration": voice.duration if voice.duration else 0,
            "length": len(transcription),
            "emotion": client_emotion,
            "energy": client_energy
        })
        lead_manager.update_activity(user.id)
        
        context.user_data['prefers_voice'] = True
        context.user_data['voice_message_count'] = context.user_data.get('voice_message_count', 0) + 1

        try:
            from src.session import save_client_profile
            save_client_profile(user.id, prefers_voice="true")
        except Exception:
            pass

        from src.followup import follow_up_manager
        follow_up_manager.cancel_follow_ups(user.id)
        follow_up_manager.schedule_follow_up(user.id)

        from src.context_builder import build_full_context, get_dynamic_buttons
        client_context = build_full_context(user.id, transcription, user.username, user.first_name)

        emotion_hint = EMOTION_TO_VOICE_STYLE.get(client_emotion, "")
        if emotion_hint:
            emotion_context = f"\n[ЭМОЦИЯ КЛИЕНТА] {emotion_hint} Энергия: {client_energy}."
            if client_context:
                client_context += emotion_context
            else:
                client_context = emotion_context

        from src.ai_client import ai_client

        messages_for_ai = session.get_history()
        
        voice_instruction = {
            "role": "user",
            "parts": [{"text": VOICE_CONTEXT_INSTRUCTION}]
        }
        voice_ack = {
            "role": "model",
            "parts": [{"text": "Понял, говорю как живой человек — коротко, по делу, разговорным языком без разметки."}]
        }
        
        if client_context:
            context_msg = {
                "role": "user",
                "parts": [{"text": f"[СИСТЕМНЫЙ КОНТЕКСТ — не показывай клиенту, используй для персонализации]\n{client_context}"}]
            }
            response_ack = {
                "role": "model",
                "parts": [{"text": "Понял контекст, учту в ответе."}]
            }
            messages_for_ai = [voice_instruction, voice_ack, context_msg, response_ack] + messages_for_ai
        else:
            messages_for_ai = [voice_instruction, voice_ack] + messages_for_ai

        from src.tool_handlers import execute_tool_call

        async def _tool_executor(tool_name, tool_args):
            return await execute_tool_call(
                tool_name, tool_args,
                user.id, user.username, user.first_name
            )

        thinking_level = "high" if len(transcription) > 100 else "medium"

        response_text = None
        special_actions = []

        try:
            agentic_result = await ai_client.agentic_loop(
                messages=messages_for_ai,
                tool_executor=_tool_executor,
                thinking_level=thinking_level,
                max_steps=4
            )

            special_actions = agentic_result.get("special_actions", [])

            if special_actions:
                for action_type, action_data in special_actions:
                    if action_type == "portfolio":
                        from src.keyboards import get_portfolio_keyboard
                        from src.knowledge_base import PORTFOLIO_MESSAGE
                        await update.message.reply_text(
                            PORTFOLIO_MESSAGE, parse_mode="Markdown",
                            reply_markup=get_portfolio_keyboard()
                        )
                    elif action_type == "pricing":
                        from src.pricing import get_price_main_text, get_price_main_keyboard
                        await update.message.reply_text(
                            get_price_main_text(), parse_mode="Markdown",
                            reply_markup=get_price_main_keyboard()
                        )
                    elif action_type == "payment":
                        from src.payments import get_payment_keyboard
                        await update.message.reply_text(
                            "Выберите способ оплаты:",
                            reply_markup=get_payment_keyboard()
                        )

            if agentic_result.get("text"):
                response_text = agentic_result["text"]
            elif special_actions and not agentic_result.get("text"):
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
                session.add_message("assistant", "Показал запрошенную информацию", config.max_history_length)
                lead_manager.save_message(user.id, "assistant", "Показал запрошенную информацию")
                _run_voice_post_processing(user.id, transcription, session)
                return
        except Exception as e:
            logger.warning(f"Voice agentic loop failed, falling back to direct: {e}")

            from src.knowledge_base import SYSTEM_PROMPT
            from google import genai
            from google.genai import types

            gemini_client = genai.Client(api_key=config.gemini_api_key)

            history_text = ""
            for msg in session.get_history()[-6:]:
                role = "Клиент" if msg.get("role") == "user" else "Алекс"
                parts = msg.get("parts", [])
                txt = parts[0].get("text", "") if parts else ""
                if txt and not txt.startswith("[СИСТЕМНЫЙ") and not txt.startswith("[ГОЛОСОВОЙ"):
                    history_text += f"{role}: {txt}\n"

            context_addition = ""
            if client_context:
                context_addition = f"\n[КОНТЕКСТ]\n{client_context}\n"

            full_prompt = (
                f"{VOICE_CONTEXT_INSTRUCTION}\n"
                f"{context_addition}"
                f"История диалога:\n{history_text}\n"
                f"Клиент сказал голосовым: {transcription}\n\n"
                f"Ответь как консультант Алекс. Коротко, разговорно, для озвучки."
            )

            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=config.model_name,
                contents=[full_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1000,
                    temperature=0.7
                )
            )

            if response.text:
                response_text = response.text

        if not response_text:
            response_text = "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."

        session.add_message("assistant", response_text, config.max_history_length)
        lead_manager.save_message(user.id, "assistant", response_text)

        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

        voice_sent = False
        if config.elevenlabs_api_key:
            try:
                await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
                voice_response = await generate_voice_response(response_text)
                await update.message.reply_voice(voice=voice_response)
                voice_sent = True
                lead_manager.log_event("voice_reply_sent", user.id)
            except Exception as e:
                logger.error(f"ElevenLabs TTS error ({type(e).__name__}): {e}")

        dynamic_btns = get_dynamic_buttons(user.id, transcription, session.message_count)
        reply_markup = None
        if dynamic_btns:
            keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in dynamic_btns[:3]]
            reply_markup = InlineKeyboardMarkup(keyboard_rows)

        text_summary = _make_text_summary(response_text)
        if voice_sent:
            summary_with_note = f"👆 Голосовое сообщение\n\n{text_summary}"
            if reply_markup:
                await update.message.reply_text(summary_with_note, reply_markup=reply_markup)
            else:
                await update.message.reply_text(summary_with_note)
        else:
            if len(response_text) > 4096:
                chunks = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        await update.message.reply_text(chunk, reply_markup=reply_markup)
                    else:
                        await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response_text, reply_markup=reply_markup)

        logger.info(f"User {user.id}: voice processed (emotion={client_emotion}, voice_reply={'yes' if voice_sent else 'no'}, voice_msg#{context.user_data.get('voice_message_count', 0)})")

        _run_voice_post_processing(user.id, transcription, session)

    except Exception as e:
        typing_task.cancel()
        logger.error(f"Voice processing error ({type(e).__name__}): {e}")
        await update.message.reply_text(
            "Не удалось обработать голосовое сообщение. Напишите текстом, пожалуйста."
        )


def _run_voice_post_processing(user_id: int, transcription: str, session):
    from src.handlers.messages import auto_tag_lead, auto_score_lead, extract_insights_if_needed, summarize_if_needed

    auto_tag_lead(user_id, transcription)
    auto_score_lead(user_id, transcription)

    asyncio.create_task(
        extract_insights_if_needed(user_id, session)
    )
    asyncio.create_task(
        summarize_if_needed(user_id, session)
    )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    if context.user_data.get('broadcast_compose'):
        from src.security import is_admin
        if is_admin(user_id):
            context.user_data.pop('broadcast_compose', None)
            photo = update.message.photo[-1]
            context.user_data['broadcast_draft'] = {
                'type': 'photo',
                'file_id': photo.file_id,
                'caption': update.message.caption or '',
            }
            from src.broadcast import broadcast_manager
            counts = broadcast_manager.get_audience_counts()
            from src.handlers.utils import get_broadcast_audience_keyboard
            keyboard = get_broadcast_audience_keyboard(counts)
            caption_preview = f"\n📝 {update.message.caption}" if update.message.caption else ""
            await update.message.reply_text(
                f"📋 <b>Предпросмотр рассылки:</b>\n\n📸 Фото{caption_preview}\n\n<b>Выберите аудиторию:</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return

    pending_review_type = context.user_data.get("pending_review_type")

    if pending_review_type != "text_photo":
        typing_task = asyncio.create_task(
            send_typing_action(update, duration=30.0)
        )
        try:
            photo = update.message.photo[-1] if update.message.photo else None
            if not photo:
                typing_task.cancel()
                return

            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()

            caption = update.message.caption or ""

            session = session_manager.get_session(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name
            )

            user_text = caption if caption else "Клиент отправил изображение. Проанализируй что на нём и ответь как консультант Алекс из WEB4TG Studio. Если это скриншот приложения или дизайн — оцени и предложи улучшения. Если это ТЗ или схема — проанализируй и дай рекомендации."

            session.add_message("user", f"[Фото]{f': {caption}' if caption else ''}", config.max_history_length)
            lead_manager.save_message(user.id, "user", f"[Фото]{f': {caption}' if caption else ''}")
            lead_manager.log_event("photo_analysis", user.id)
            lead_manager.update_activity(user.id)

            from src.context_builder import build_full_context, get_dynamic_buttons
            client_context = build_full_context(user.id, user_text, user.username, user.first_name)

            from google import genai
            from google.genai import types
            from src.knowledge_base import SYSTEM_PROMPT

            gemini_client = genai.Client(api_key=config.gemini_api_key)

            image_part = types.Part.from_bytes(data=bytes(photo_bytes), mime_type="image/jpeg")
            text_part = types.Part(text=user_text)

            context_parts = []
            if client_context:
                context_parts.append(types.Part(text=f"[СИСТЕМНЫЙ КОНТЕКСТ — не показывай клиенту]\n{client_context}"))

            all_parts = context_parts + [image_part, text_part]

            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=config.model_name,
                contents=all_parts,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1500,
                    temperature=0.7
                )
            )

            typing_task.cancel()

            if response.text:
                session.add_message("assistant", response.text, config.max_history_length)
                lead_manager.save_message(user.id, "assistant", response.text)

                dynamic_btns = get_dynamic_buttons(user.id, user_text, session.message_count)
                reply_markup = None
                if dynamic_btns:
                    keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in dynamic_btns[:3]]
                    reply_markup = InlineKeyboardMarkup(keyboard_rows)

                await update.message.reply_text(response.text, parse_mode="Markdown", reply_markup=reply_markup)

                from src.handlers.messages import auto_tag_lead, auto_score_lead
                auto_tag_lead(user.id, user_text)
                auto_score_lead(user.id, user_text)
            else:
                await update.message.reply_text("Не удалось проанализировать изображение. Попробуйте описать словами что вам нужно.")
        except Exception as e:
            typing_task.cancel()
            logger.error(f"Photo analysis error: {e}")
            await update.message.reply_text(
                "Не удалось обработать фото. Опишите словами что вам нужно, я помогу!"
            )
        return

    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        return

    file_id = photo.file_id
    caption = update.message.caption or ""

    try:
        review_id = loyalty_system.submit_review(
            user_id=user_id,
            review_type="text_photo",
            content_url=f"[PHOTO] file_id: {file_id}",
            comment=caption if caption else None
        )

        if review_id:
            context.user_data.pop("pending_review_type", None)

            from src.loyalty import REVIEW_REWARDS
            coins = REVIEW_REWARDS.get("text_photo", 200)

            await update.message.reply_text(
                f"""✅ <b>Отзыв с фото принят!</b>

Спасибо за ваш отзыв! После модерации вы получите <b>{coins} монет</b>.

Обычно модерация занимает до 24 часов.""",
                parse_mode="HTML",
                reply_markup=get_loyalty_menu_keyboard()
            )

            if MANAGER_CHAT_ID:
                try:
                    manager_text = f"""📸 <b>Новый текстовый отзыв с фото!</b>

👤 {user.first_name or 'Пользователь'} (@{user.username or 'no_username'})
🆔 ID: {user_id}
💬 Текст: {caption or '(без подписи)'}"""

                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID,
                        text=manager_text,
                        parse_mode="HTML"
                    )
                    await context.bot.forward_message(
                        chat_id=MANAGER_CHAT_ID,
                        from_chat_id=update.effective_chat.id,
                        message_id=update.message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify manager about photo review: {e}")
        else:
            await update.message.reply_text(
                "Вы уже отправляли отзыв этого типа или произошла ошибка.",
                reply_markup=get_loyalty_menu_keyboard()
            )
            context.user_data.pop("pending_review_type", None)

    except Exception as e:
        logger.error(f"Error processing photo review: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_loyalty_menu_keyboard()
        )
        context.user_data.pop("pending_review_type", None)


async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    if context.user_data.get('broadcast_compose'):
        from src.security import is_admin
        if is_admin(user.id):
            context.user_data.pop('broadcast_compose', None)
            video = update.message.video or update.message.video_note
            context.user_data['broadcast_draft'] = {
                'type': 'video',
                'file_id': video.file_id,
                'caption': update.message.caption or '',
            }
            from src.broadcast import broadcast_manager
            counts = broadcast_manager.get_audience_counts()
            from src.handlers.utils import get_broadcast_audience_keyboard
            keyboard = get_broadcast_audience_keyboard(counts)
            caption_preview = f"\n📝 {update.message.caption}" if update.message.caption else ""
            await update.message.reply_text(
                f"📋 <b>Предпросмотр рассылки:</b>\n\n🎬 Видео{caption_preview}\n\n<b>Выберите аудиторию:</b>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return

    pending_review_type = context.user_data.get("pending_review_type")

    if pending_review_type != "video":
        await update.message.reply_text(
            "Если хотите оставить видео-отзыв, нажмите /bonus → Отзывы и бонусы → Видео-отзыв"
        )
        return

    video = update.message.video or update.message.video_note
    if not video:
        return

    file_id = video.file_id

    try:
        review = loyalty_system.submit_review(
            user_id=user_id,
            review_type="video",
            content=f"[VIDEO] file_id: {file_id}"
        )

        if review:
            context.user_data.pop("pending_review_type", None)

            from src.loyalty import REVIEW_REWARDS
            coins = REVIEW_REWARDS.get("video", 500)

            await update.message.reply_text(
                f"""✅ <b>Видео-отзыв принят!</b>

Спасибо за ваш отзыв! После модерации вы получите <b>{coins} монет</b>.

Обычно модерация занимает до 24 часов.""",
                parse_mode="HTML",
                reply_markup=get_loyalty_menu_keyboard()
            )

            if MANAGER_CHAT_ID:
                try:
                    manager_text = f"""🎬 <b>Новый видео-отзыв!</b>

👤 {user.first_name or 'Пользователь'} (@{user.username or 'no_username'})
🆔 ID: {user_id}"""

                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID,
                        text=manager_text,
                        parse_mode="HTML"
                    )
                    await context.bot.forward_message(
                        chat_id=MANAGER_CHAT_ID,
                        from_chat_id=update.effective_chat.id,
                        message_id=update.message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify manager about video review: {e}")
        else:
            await update.message.reply_text(
                "Не удалось сохранить отзыв. Попробуйте позже.",
                reply_markup=get_loyalty_menu_keyboard()
            )
            context.user_data.pop("pending_review_type", None)

    except Exception as e:
        logger.error(f"Error processing video review: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_loyalty_menu_keyboard()
        )
        context.user_data.pop("pending_review_type", None)
