import asyncio
import logging
import re
import hashlib
import time
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
_elevenlabs_async_client = None
_voice_cache = {}

STREAMING_LATENCY_OPTIMIZATION = 3
SHORT_TEXT_THRESHOLD = 200
SHORT_TEXT_FORMAT = "mp3_22050_32"
LONG_TEXT_FORMAT = "mp3_44100_128"


def _get_elevenlabs_client():
    global _elevenlabs_client
    if _elevenlabs_client is None and config.elevenlabs_api_key:
        from elevenlabs import ElevenLabs
        _elevenlabs_client = ElevenLabs(api_key=config.elevenlabs_api_key)
    return _elevenlabs_client


def _get_async_elevenlabs_client():
    global _elevenlabs_async_client
    if _elevenlabs_async_client is None and config.elevenlabs_api_key:
        try:
            from elevenlabs import AsyncElevenLabs
            _elevenlabs_async_client = AsyncElevenLabs(api_key=config.elevenlabs_api_key)
        except ImportError:
            logger.warning("AsyncElevenLabs not available, will use sync client with threading")
            return None
    return _elevenlabs_async_client


VOICE_ENHANCE_PROMPT = """Ты — Enhance-движок для ElevenLabs v3. Твоя задача: получить чистый текст и ТОЧЕЧНО расставить эмоциональные теги там, где они усилят речь.

ПРИНЦИП: Как кнопка Enhance в ElevenLabs — анализируешь смысл каждой фразы и добавляешь ТОЛЬКО подходящий тег. Не все теги нужны в каждом тексте. Используй только то, что реально улучшит звучание.

ШАГ 1 — АНАЛИЗ: Прочитай текст. Определи эмоциональные точки:
- Где радость? Где грусть? Где уверенность? Где интрига?
- Какой общий тон: деловой, дружеский, тёплый, серьёзный?
- Есть ли смена настроения в тексте?

ШАГ 2 — РАССТАНОВКА ТЕГОВ (только нужные, не все подряд):
Теги в [квадратных скобках] перед фразой. НЕ произносятся. Управляют тоном голоса.

ДОСТУПНЫЕ ТЕГИ:
Эмоции: [happy] [excited] [sad] [nervous] [frustrated] [sorrowful] [curious] [mischievous]
Реакции: [laughs] [giggles] [sighs] [gasps] [clears throat]
Стили: [whispers] [cheerfully] [flatly] [deadpan] [playfully] [hesitant] [resigned tone]
Настроение: [warm] [friendly] [calm] [confident]

КОГДА КАКОЙ ТЕГ (выбирай по смыслу, а не по списку):
- Приветствие, тёплые слова → [warm] или [friendly]
- Экспертное мнение, факты → [confident]
- Хорошая новость, результат → [excited] или [happy]
- Впечатляющая цифра → [gasps] перед ней
- Вопрос с интересом → [curious]
- Сочувствие, проблема → [calm] или [sighs]
- Секрет, скидка, бонус → [whispers] или [mischievous]
- Лёгкий юмор → [giggles] или [playfully]
- Призыв к действию → [cheerfully]
- Размышление, сомнение → [hesitant]
- Контраст (было плохо → стало хорошо) → [flatly] потом [excited]
- Серьёзные цифры без эмоций → [deadpan]

ПРАВИЛА:
1. Максимум 2-4 тега на ответ до 300 символов, 3-5 на длинный
2. НЕ ставь тег на каждое предложение — только на эмоциональные точки
3. Первый тег — задаёт общий тон (обычно [warm], [friendly] или [confident])
4. Между тегами должно быть 1-3 предложения без тегов — это нормально
5. Если текст нейтральный/фактический — хватит 1-2 тегов
6. НЕ МЕНЯЙ сам текст — только добавляй теги перед фразами
7. Сохраняй "..." паузы и " — " тире — они важны для ритма
8. Убери markdown (**, *, #, •, `) и emoji, замени переносы на ". "
9. Числа оставь как есть

Верни ТОЛЬКО текст с расставленными тегами. Без комментариев.

Текст:
"""

VOICE_CONTEXT_INSTRUCTION = """
[ГОЛОСОВОЙ ФОРМАТ] Клиент общается голосовыми. Твой ответ ОЗВУЧАТ — пиши КАК ГОВОРИШЬ вслух.
Эмоции и интонации будут добавлены автоматически — тебе НЕ нужно ставить теги вроде [warm] или [excited]. Просто пиши живой текст, остальное сделает система.

ГЛАВНОЕ — ты живой консультант Алекс, а не текстовый бот.

ДЛИНА ОТВЕТА (КРИТИЧЕСКИ ВАЖНО):
- СТРОГО 300-500 символов (20-30 секунд). Это МАКСИМУМ.
- Одна ключевая мысль на ответ. Не пытайся уместить всё.
- Если тема сложная — скажи "Могу подробнее рассказать, если интересно".

СТИЛЬ РЕЧИ:
- Никакого markdown, emoji, списков с тире или звёздочками
- Говори как в жизни: "Ну смотрите, тут вот какая история..."
- Числа — словами: "сто пятьдесят тысяч"
- Аббревиатуры раскрывай: "возврат инвестиций" вместо "ROI"

ПРИЁМЫ ЖИВОГО ЧЕЛОВЕКА (1-2 за ответ):
- Думай вслух: "Хм, давайте прикинем..."
- Переходы: "Кстати,", "И знаете что —"
- Эмпатия: "Да, понимаю,", "Логичный вопрос,"
- Паузы через "..." и " — " для естественного дыхания
- Чередуй длинные и короткие фразы: "Магазин за сто пятьдесят. Семь-десять дней. Готово."

ЧЕГО ИЗБЕГАТЬ:
- Шаблонных фраз: "Рад помочь!", "Отличный выбор!"
- Списков (1. 2. 3.) — это текстовый формат
- Формальных оборотов: "В рамках нашего сотрудничества..."
"""


async def enhance_voice_text(text: str) -> str:
    existing_tags = re.findall(r'\[\w[\w\s]*?\]', text)
    if len(existing_tags) >= 2:
        logger.debug(f"Text already has {len(existing_tags)} tags, skipping enhance")
        return text

    if len(text) < 50:
        return _auto_enhance_short(text)

    from google.genai import types
    from src.config import get_gemini_client

    client = get_gemini_client()

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.model_name,
            contents=[VOICE_ENHANCE_PROMPT + text],
            config=types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.2
            )
        )

        if response.text:
            enhanced = response.text.strip()
            enhanced = enhanced.strip('"').strip("'")
            enhanced = re.sub(r'\*+', '', enhanced)
            enhanced = re.sub(r'#+\s*', '', enhanced)

            enhanced_tags = re.findall(r'\[\w[\w\s]*?\]', enhanced)
            valid_tags = {
                '[happy]', '[excited]', '[sad]', '[angry]', '[nervous]',
                '[frustrated]', '[sorrowful]', '[curious]', '[mischievous]',
                '[laughs]', '[giggles]', '[sighs]', '[gasps]', '[gulps]',
                '[clears throat]', '[whispers]', '[shouts]', '[cheerfully]',
                '[flatly]', '[deadpan]', '[playfully]', '[sarcastically]',
                '[hesitant]', '[resigned tone]', '[warm]', '[friendly]',
                '[calm]', '[confident]'
            }
            bad_tags = [t for t in enhanced_tags if t not in valid_tags]
            for bt in bad_tags:
                enhanced = enhanced.replace(bt, '')

            tag_count = len(re.findall(r'\[\w[\w\s]*?\]', enhanced))
            text_len = len(re.sub(r'\[\w[\w\s]*?\]\s*', '', enhanced))
            max_tags = 3 if text_len < 300 else 5
            if tag_count > max_tags:
                logger.debug(f"Enhance produced {tag_count} tags, capping at {max_tags}")
                found = 0
                result = []
                i = 0
                while i < len(enhanced):
                    match = re.match(r'\[(\w[\w\s]*?)\]', enhanced[i:])
                    if match:
                        found += 1
                        if found <= max_tags:
                            result.append(match.group(0))
                        i += len(match.group(0))
                    else:
                        result.append(enhanced[i])
                        i += 1
                enhanced = ''.join(result)

            enhanced = re.sub(r'\s{2,}', ' ', enhanced).strip()
            final_tag_count = len(re.findall(r'\[\w[\w\s]*?\]', enhanced))
            logger.info(f"Enhance: {len(existing_tags)} -> {final_tag_count} tags")
            return enhanced
    except Exception as e:
        logger.error(f"Voice enhance error: {e}")

    return _auto_enhance_short(text)


def _auto_enhance_short(text: str) -> str:
    lower = text.lower()

    if any(w in lower for w in ['привет', 'здравствуй', 'добрый', 'доброе', 'доброй']):
        if not text.startswith('['):
            return f'[warm] {text}'

    if any(w in lower for w in ['отлично', 'замечательно', 'круто', 'супер', 'ура', 'класс']):
        if not text.startswith('['):
            return f'[excited] {text}'

    if any(w in lower for w in ['понимаю', 'сочувств', 'к сожалению', 'жаль']):
        if not text.startswith('['):
            return f'[calm] {text}'

    if any(w in lower for w in ['стоимость', 'цена', 'рублей', 'тысяч', 'гарантия']):
        if not text.startswith('['):
            return f'[confident] {text}'

    if not text.startswith('['):
        return f'[friendly] {text}'

    return text


def _clean_text_for_voice(text: str) -> str:
    clean = re.sub(r'\.{3,}', '...', text)
    _ellipsis_placeholder = '\x00ELLIPSIS\x00'
    clean = clean.replace('...', _ellipsis_placeholder)
    clean = clean.replace("**", "").replace("*", "").replace("#", "")
    clean = clean.replace("`", "").replace("_", " ")
    clean = clean.replace("•", ",").replace("—", " — ")
    clean = clean.replace("\n\n", ". ").replace("\n", ", ")
    clean = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001f926-\U0001f937\U00010000-\U0010ffff\u2600-\u2B55\u200d\u23cf\u23e9\u231a\ufe0f\u3030\u2066\u2069]+', '', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)
    clean = re.sub(r'[,\.]{2,}', '.', clean)
    clean = clean.replace(_ellipsis_placeholder, '...')
    return clean.strip()


VOICE_PROFILES = {
    "greeting": {"stability": 0.35, "similarity_boost": 0.8, "style": 1.0},
    "empathy": {"stability": 0.5, "similarity_boost": 0.85, "style": 1.0},
    "factual": {"stability": 1.0, "similarity_boost": 0.8, "style": 0.5},
    "excited": {"stability": 0.15, "similarity_boost": 0.75, "style": 1.0},
    "whisper": {"stability": 0.6, "similarity_boost": 0.9, "style": 0.8},
    "playful": {"stability": 0.25, "similarity_boost": 0.75, "style": 1.0},
    "default": {"stability": 0.5, "similarity_boost": 0.8, "style": 1.0},
}


def _detect_voice_profile(text: str) -> dict:
    lower = text.lower()
    tags = re.findall(r'\[(\w[\w\s]*?)\]', text)
    tag_set = {t.lower() for t in tags}

    if tag_set & {'whispers', 'mischievous'}:
        return VOICE_PROFILES["whisper"]
    if tag_set & {'excited', 'happy', 'gasps', 'cheerfully'}:
        return VOICE_PROFILES["excited"]
    if tag_set & {'warm', 'friendly'} and any(w in lower for w in ['привет', 'здравствуй', 'добро пожалов', 'рад вас', 'знакомств']):
        return VOICE_PROFILES["greeting"]
    if tag_set & {'playfully', 'giggles', 'laughs'}:
        return VOICE_PROFILES["playful"]
    if tag_set & {'calm', 'sorrowful', 'sighs', 'sad'}:
        return VOICE_PROFILES["empathy"]
    if tag_set & {'confident', 'deadpan', 'flatly'}:
        return VOICE_PROFILES["factual"]

    if any(w in lower for w in ['привет', 'здравствуй', 'добро пожалов', 'рад вас', 'знакомств']):
        return VOICE_PROFILES["greeting"]
    if any(w in lower for w in ['понимаю', 'сочувств', 'непросто', 'к сожалению', 'извин', 'жаль', 'бывает']):
        return VOICE_PROFILES["empathy"]
    if any(w in lower for w in ['стоимость', 'цена', 'рублей', 'тысяч', 'процент', 'срок', 'гарантия', 'договор']):
        return VOICE_PROFILES["factual"]
    if any(w in lower for w in ['отлично', 'замечательно', 'круто', 'результат', 'рост', 'увеличил', 'сэкономил']):
        return VOICE_PROFILES["excited"]
    return VOICE_PROFILES["default"]


def _select_output_format(text_length: int) -> str:
    if text_length <= SHORT_TEXT_THRESHOLD:
        return SHORT_TEXT_FORMAT
    return LONG_TEXT_FORMAT


async def _generate_voice_streaming_async(voice_text: str, profile: dict, output_format: str) -> bytes:
    async_client = _get_async_elevenlabs_client()
    if not async_client:
        return await _generate_voice_sync_fallback(voice_text, profile, output_format)

    from elevenlabs import VoiceSettings

    start_time = time.monotonic()

    try:
        stream_kwargs = {
            "voice_id": config.elevenlabs_voice_id,
            "text": voice_text,
            "model_id": "eleven_v3",
            "output_format": output_format,
            "voice_settings": VoiceSettings(
                stability=profile["stability"],
                similarity_boost=profile["similarity_boost"],
                style=profile["style"],
            ),
        }

        stream_call = async_client.text_to_speech.stream(**stream_kwargs)
        if asyncio.iscoroutine(stream_call):
            audio_stream = await stream_call
        else:
            audio_stream = stream_call

        chunks = []
        first_chunk_time = None
        async for chunk in audio_stream:
            if chunk:
                if first_chunk_time is None:
                    first_chunk_time = time.monotonic()
                chunks.append(chunk)

        audio_bytes = b"".join(chunks)
        total_time = time.monotonic() - start_time
        ttfb = (first_chunk_time - start_time) if first_chunk_time else total_time

        logger.info(
            f"Streaming TTS: {len(voice_text)} chars → {len(audio_bytes)} bytes, "
            f"TTFB={ttfb:.2f}s, total={total_time:.2f}s, "
            f"format={output_format}, chunks={len(chunks)}"
        )
        return audio_bytes

    except Exception as e:
        logger.warning(f"Async streaming TTS failed ({type(e).__name__}): {e}, falling back to sync")
        return await _generate_voice_sync_fallback(voice_text, profile, output_format)


async def _generate_voice_sync_fallback(voice_text: str, profile: dict, output_format: str) -> bytes:
    el_client = _get_elevenlabs_client()
    if not el_client:
        raise RuntimeError("ElevenLabs client not configured")

    from elevenlabs import VoiceSettings

    start_time = time.monotonic()

    audio_generator = await asyncio.to_thread(
        el_client.text_to_speech.convert,
        voice_id=config.elevenlabs_voice_id,
        text=voice_text,
        model_id="eleven_v3",
        output_format=output_format,
        voice_settings=VoiceSettings(
            stability=profile["stability"],
            similarity_boost=profile["similarity_boost"],
            style=profile["style"],
        )
    )

    audio_bytes = b"".join(audio_generator)
    total_time = time.monotonic() - start_time
    logger.info(
        f"Sync TTS fallback: {len(voice_text)} chars → {len(audio_bytes)} bytes, "
        f"total={total_time:.2f}s, format={output_format}"
    )
    return audio_bytes


async def generate_voice_response(text: str, use_cache: bool = False, voice_profile: str = None) -> bytes:
    global _voice_cache
    
    if not config.elevenlabs_api_key:
        raise RuntimeError("ElevenLabs client not configured")

    clean_text = _clean_text_for_voice(text)
    
    if use_cache:
        cache_key = hashlib.md5(clean_text.encode()).hexdigest()
        if cache_key in _voice_cache:
            logger.debug("Using cached voice response")
            return _voice_cache[cache_key]

    voice_text = await enhance_voice_text(clean_text)

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

    output_format = _select_output_format(len(voice_text))

    try:
        audio_bytes = await _generate_voice_streaming_async(voice_text, profile, output_format)

        if not audio_bytes:
            raise RuntimeError("Empty audio response from TTS")

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

    json_match = re.search(r'\{.*?"text"\s*:\s*".*?".*?\}', raw, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{.+?\}', raw, re.DOTALL)
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

    text_match = re.search(r'"text"\s*:\s*"([^"]*)"', raw)
    if text_match and text_match.group(1).strip():
        emotion_match = re.search(r'"emotion"\s*:\s*"([^"]*)"', raw)
        energy_match = re.search(r'"energy"\s*:\s*"([^"]*)"', raw)
        return {
            "text": text_match.group(1).strip(),
            "emotion": emotion_match.group(1) if emotion_match else "neutral",
            "energy": energy_match.group(1) if energy_match else "medium"
        }

    clean_text = raw.strip().strip('"').strip("'")
    if len(clean_text) > 5 and not clean_text.startswith("{"):
        return {"text": clean_text, "emotion": "neutral", "energy": "medium"}
    return {"text": "", "emotion": "neutral", "energy": "medium"}


async def _transcribe_voice_with_emotion(voice_bytes: bytes) -> dict:
    from google import genai
    from google.genai import types
    import tempfile
    import os

    from src.config import get_gemini_client
    client = get_gemini_client()
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

        from src.context_builder import build_full_context, parse_ai_buttons
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

            from src.config import get_gemini_client
            gemini_client = get_gemini_client()

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

        response_text, ai_buttons = parse_ai_buttons(response_text)

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
        reply_markup = None
        if ai_buttons:
            keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in ai_buttons]
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
    if not user or not update.message:
        return
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
            send_typing_action(update, duration=45.0)
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

            from src.vision_sales import (
                VISION_CLASSIFICATION_PROMPT,
                get_image_type_from_caption,
                build_vision_system_prompt,
                get_smart_buttons_for_image,
                get_lead_score_boost,
                get_intents_for_image,
                is_hot_image,
                is_warm_image,
                build_manager_notification,
                get_vision_analysis_context,
                ImageType,
            )

            from google.genai import types as genai_types
            from src.config import get_gemini_client
            gemini_client = get_gemini_client()

            image_part = genai_types.Part.from_bytes(data=bytes(photo_bytes), mime_type="image/jpeg")

            caption_hint = get_image_type_from_caption(caption)

            if caption_hint:
                image_type = caption_hint
            else:
                try:
                    classify_response = await asyncio.to_thread(
                        gemini_client.models.generate_content,
                        model=config.model_name,
                        contents=[image_part, genai_types.Part(text=VISION_CLASSIFICATION_PROMPT)],
                        config=genai_types.GenerateContentConfig(
                            max_output_tokens=30,
                            temperature=0.1
                        )
                    )
                    raw_type = (classify_response.text or "general").strip().lower().replace(" ", "_")
                    valid_types = {e.value for e in ImageType}
                    image_type = raw_type if raw_type in valid_types else ImageType.GENERAL.value
                except Exception as classify_err:
                    logger.warning(f"Image classification failed: {classify_err}")
                    image_type = ImageType.GENERAL.value

            logger.info(f"Vision analysis for user {user_id}: type={image_type}, caption={caption[:100] if caption else 'none'}")

            user_text = caption if caption else f"Проанализируй это изображение (тип: {image_type})"

            session.add_message("user", f"[Фото: {image_type}]{f': {caption}' if caption else ''}", config.max_history_length)
            lead_manager.save_message(user.id, "user", f"[Фото: {image_type}]{f': {caption}' if caption else ''}")
            lead_manager.log_event(f"photo_{image_type}", user.id)
            lead_manager.update_activity(user.id)

            from src.context_builder import build_full_context, parse_ai_buttons
            client_context = build_full_context(user.id, user_text, user.username, user.first_name)

            vision_context = get_vision_analysis_context(image_type)
            full_client_ctx = f"{vision_context}\n{client_context}" if client_context else vision_context

            system_prompt = build_vision_system_prompt(image_type, full_client_ctx)

            analysis_text = genai_types.Part(text=user_text if caption else "Проанализируй это изображение.")
            all_parts = [image_part, analysis_text]

            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=config.model_name,
                contents=all_parts,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=2000,
                    temperature=0.7
                )
            )

            typing_task.cancel()

            if response.text:
                clean_text, ai_buttons = parse_ai_buttons(response.text)
                session.add_message("assistant", clean_text, config.max_history_length)
                lead_manager.save_message(user.id, "assistant", clean_text)

                try:
                    from src.session import save_vision_context
                    save_vision_context(user.id, image_type, clean_text[:300])
                except Exception as e:
                    logger.debug(f"Vision context save error: {e}")

                if not ai_buttons:
                    smart_btns = get_smart_buttons_for_image(image_type)
                    ai_buttons = smart_btns[:3]

                keyboard_rows = []
                for i in range(0, len(ai_buttons), 2):
                    row = []
                    for label, cb in ai_buttons[i:i+2]:
                        row.append(InlineKeyboardButton(label, callback_data=cb))
                    keyboard_rows.append(row)
                reply_markup = InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None

                await update.message.reply_text(clean_text, parse_mode="Markdown", reply_markup=reply_markup)

                from src.handlers.messages import auto_tag_lead, auto_score_lead
                auto_tag_lead(user.id, user_text + f" [photo:{image_type}]")
                auto_score_lead(user.id, user_text)

                score_boost = get_lead_score_boost(image_type)
                if score_boost > 5:
                    try:
                        from src.propensity import propensity_scorer
                        propensity_scorer.boost_score(user.id, score_boost, f"photo_{image_type}")
                    except Exception:
                        pass

                if is_hot_image(image_type) or is_warm_image(image_type):
                    manager_text = build_manager_notification(
                        user.id, user.username, user.first_name, image_type, caption
                    )
                    if manager_text and MANAGER_CHAT_ID:
                        try:
                            await context.bot.send_message(
                                chat_id=MANAGER_CHAT_ID,
                                text=manager_text,
                                parse_mode="HTML"
                            )
                            await context.bot.forward_message(
                                chat_id=MANAGER_CHAT_ID,
                                from_chat_id=update.effective_chat.id if update.effective_chat else user_id,
                                message_id=update.message.message_id
                            )
                            if is_hot_image(image_type):
                                try:
                                    from src.manager_coaching import generate_coaching_briefing
                                    briefing = generate_coaching_briefing(
                                        user_id=user.id,
                                        trigger_type="high_value",
                                        last_user_message=caption,
                                    )
                                    if briefing:
                                        await context.bot.send_message(
                                            chat_id=MANAGER_CHAT_ID,
                                            text=briefing,
                                            parse_mode="HTML"
                                        )
                                except Exception:
                                    pass
                        except Exception as notify_err:
                            logger.warning(f"Manager notification failed: {notify_err}")

                try:
                    from src.feedback_loop import feedback_loop
                    from src.context_builder import detect_funnel_stage
                    stage = detect_funnel_stage(user.id, user_text, 0)
                    feedback_loop.log_response(
                        user_id=user.id,
                        message_text=f"[photo:{image_type}] {caption[:200] if caption else ''}",
                        response_text=clean_text[:500],
                        variant=f"vision_{image_type}",
                        funnel_stage=stage,
                    )
                except Exception:
                    pass
            else:
                await update.message.reply_text("Не удалось проанализировать изображение. Попробуйте описать словами что вам нужно.")
        except Exception as e:
            typing_task.cancel()
            logger.error(f"Photo analysis error: {e}", exc_info=True)
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
