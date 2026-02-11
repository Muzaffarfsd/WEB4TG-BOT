import asyncio
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from src.session import session_manager
from src.config import config
from src.leads import lead_manager
from src.keyboards import get_loyalty_menu_keyboard

from src.handlers.utils import (
    send_typing_action, STRESS_DICTIONARY, apply_stress_marks,
    loyalty_system, MANAGER_CHAT_ID
)

logger = logging.getLogger(__name__)


VOICE_EMOTION_PROMPT = """Ты эксперт по подготовке текста для озвучки через ElevenLabs v3.

Твоя задача: добавить нативные audio-теги ElevenLabs v3 для максимально естественного и выразительного звучания.

ДОСТУПНЫЕ ТЕГИ v3 (вставляй в квадратных скобках перед фразой):

Эмоциональные:
- [happy] — радостно, позитивно
- [sad] — грустно, сочувственно
- [angry] — с напором, решительно
- [excited] — с энтузиазмом, воодушевлённо
- [nervous] — с волнением, неуверенно

Акустические:
- [whispers] — шёпот, интимно, секрет
- [shouts] — громко, призыв
- [laughs] — смех перед фразой
- [giggles] — лёгкий смешок
- [sighs] — вздох (усталость, облегчение, задумчивость)

Стилевые:
- [friendly] — дружелюбно
- [calm] — спокойно, размеренно
- [confident] — уверенно, авторитетно
- [warm] — тепло, заботливо
- [curious] — с интересом, вопросительно

ПРАВИЛА:
1. Приветствия и знакомство: [friendly] или [warm]
2. Цены, факты, гарантии: [confident]
3. Выгоды и результаты кейсов: [excited]
4. Вопросы к клиенту: [curious]
5. Эмпатия при возражениях: [calm] или [warm]
6. Инсайты и секреты: [whispers] — для эффекта "между нами"
7. Впечатляющие цифры: [excited] перед числом
8. Максимум 3-4 тега на абзац, не переусердствуй
9. Убери ВСЮ markdown разметку: **, *, #, •, `, _
10. Замени \\n\\n на точку и пробел для пауз
11. Замени \\n на запятую для лёгких пауз
12. Убери emoji (они не озвучиваются)
13. НЕ меняй смысл и слова, только добавь теги и очисти разметку
14. Числа пиши словами или с пробелами (150 000, не 150000)

Верни ТОЛЬКО обработанный текст, без объяснений и комментариев.

Текст для обработки:
"""


async def analyze_emotions_and_prepare_text(text: str) -> str:
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=config.gemini_api_key)
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
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


async def generate_voice_response(text: str) -> bytes:
    from elevenlabs import ElevenLabs
    
    client = ElevenLabs(api_key=config.elevenlabs_api_key)
    
    clean_text = text.replace("**", "").replace("*", "").replace("#", "").replace("•", ",")
    clean_text = clean_text.replace("`", "").replace("_", "")
    clean_text = clean_text.replace("\n\n", ". ").replace("\n", ", ")
    
    import re
    clean_text = re.sub(r'[^\w\s\[\].,!?;:\'\"—–\-()₽%+=/\\]', '', clean_text)
    
    voice_text = await analyze_emotions_and_prepare_text(clean_text)
    
    voice_text = apply_stress_marks(voice_text)
    
    if len(voice_text) > 4500:
        voice_text = voice_text[:4500].rsplit('.', 1)[0] + '.'
    
    try:
        audio_generator = await asyncio.to_thread(
            client.text_to_speech.convert,
            voice_id=config.elevenlabs_voice_id,
            text=voice_text,
            model_id="eleven_v3",
            output_format="mp3_44100_192",
            voice_settings={
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.6,
                "use_speaker_boost": True,
            }
        )
        
        audio_bytes = b"".join(audio_generator)
        return audio_bytes
    except Exception as e:
        logger.error(f"ElevenLabs voice generation failed ({type(e).__name__}): {e}")
        raise


async def _transcribe_voice(voice_bytes: bytes) -> str:
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=config.gemini_api_key)
    
    audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
    text_part = types.Part(text=(
        "Расшифруй это голосовое сообщение дословно. "
        "Верни ТОЛЬКО текст того, что сказал человек. "
        "Без комментариев, без пояснений, без кавычек."
    ))
    
    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.0-flash",
        contents=[audio_part, text_part],
        config=types.GenerateContentConfig(
            max_output_tokens=500,
            temperature=0.1
        )
    )
    
    if response.text:
        return response.text.strip()
    return ""


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=60.0)
    )
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        voice_bytes = await file.download_as_bytearray()
        
        transcription = await _transcribe_voice(voice_bytes)
        
        if not transcription:
            typing_task.cancel()
            await update.message.reply_text(
                "Не удалось распознать сообщение. Попробуйте ещё раз или напишите текстом."
            )
            return
        
        logger.info(f"User {user.id} voice transcribed: {transcription[:100]}...")
        
        session = session_manager.get_session(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        session.add_message("user", transcription, config.max_history_length)
        lead_manager.save_message(user.id, "user", f"[Голосовое] {transcription}")
        lead_manager.log_event("voice_message", user.id)
        lead_manager.update_activity(user.id)
        
        from src.followup import follow_up_manager
        follow_up_manager.cancel_follow_ups(user.id)
        follow_up_manager.schedule_follow_up(user.id)
        
        from src.context_builder import build_full_context, get_dynamic_buttons
        client_context = build_full_context(user.id, transcription, user.username, user.first_name)
        
        from src.ai_client import ai_client
        
        messages_for_ai = session.get_history()
        if client_context:
            context_msg = {
                "role": "user",
                "parts": [{"text": f"[СИСТЕМНЫЙ КОНТЕКСТ — не показывай клиенту, используй для персонализации]\n{client_context}"}]
            }
            response_ack = {
                "role": "model",
                "parts": [{"text": "Понял контекст, учту в ответе."}]
            }
            messages_for_ai = [context_msg, response_ack] + messages_for_ai
        
        from src.handlers.messages import execute_tool_call
        
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
                            "💳 Выберите способ оплаты:",
                            reply_markup=get_payment_keyboard()
                        )
            
            if agentic_result.get("text"):
                response_text = agentic_result["text"]
            elif special_actions and not agentic_result.get("text"):
                typing_task.cancel()
                session.add_message("assistant", "Показал запрошенную информацию", config.max_history_length)
                lead_manager.save_message(user.id, "assistant", "Показал запрошенную информацию")
                _run_voice_post_processing(user.id, transcription, session)
                return
        except Exception as e:
            logger.warning(f"Voice agentic loop failed, falling back to direct: {e}")
            
            from src.knowledge_base import SYSTEM_PROMPT
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=config.gemini_api_key)
            
            history_text = ""
            for msg in session.get_history()[-6:]:
                role = "Клиент" if msg.get("role") == "user" else "Алекс"
                parts = msg.get("parts", [])
                txt = parts[0].get("text", "") if parts else ""
                if txt and not txt.startswith("[СИСТЕМНЫЙ"):
                    history_text += f"{role}: {txt}\n"
            
            context_addition = ""
            if client_context:
                context_addition = f"\n[КОНТЕКСТ]\n{client_context}\n"
            
            full_prompt = (
                f"{context_addition}"
                f"История диалога:\n{history_text}\n"
                f"Клиент сказал голосовым: {transcription}\n\n"
                f"Ответь как консультант Алекс."
            )
            
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=config.model_name,
                contents=[full_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1500,
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
            except Exception as e:
                logger.error(f"ElevenLabs TTS error ({type(e).__name__}): {e}")
        
        if not voice_sent:
            dynamic_btns = get_dynamic_buttons(user.id, transcription, session.message_count)
            reply_markup = None
            if dynamic_btns:
                keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in dynamic_btns[:3]]
                reply_markup = InlineKeyboardMarkup(keyboard_rows)
            
            if len(response_text) > 4096:
                chunks = [response_text[i:i+4096] for i in range(0, len(response_text), 4096)]
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        await update.message.reply_text(chunk, reply_markup=reply_markup)
                    else:
                        await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response_text, reply_markup=reply_markup)
        else:
            dynamic_btns = get_dynamic_buttons(user.id, transcription, session.message_count)
            if dynamic_btns:
                keyboard_rows = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in dynamic_btns[:3]]
                reply_markup = InlineKeyboardMarkup(keyboard_rows)
                await update.message.reply_text(
                    "☝️ Ответил голосовым. Если нужны детали:",
                    reply_markup=reply_markup
                )
        
        logger.info(f"User {user.id}: voice message processed (agentic, voice_reply={'yes' if voice_sent else 'no'})")
        
        _run_voice_post_processing(user.id, transcription, session)
        
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Voice processing error: {e}")
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
                return
            
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()
            
            from google import genai
            from google.genai import types
            from src.knowledge_base import SYSTEM_PROMPT
            
            client = genai.Client(api_key=config.gemini_api_key)
            
            caption = update.message.caption or ""
            
            image_part = types.Part.from_bytes(data=bytes(photo_bytes), mime_type="image/jpeg")
            
            user_instruction = caption if caption else "Клиент отправил изображение. Проанализируй что на нём и ответь как консультант Алекс из WEB4TG Studio. Если это скриншот приложения или дизайн — оцени и предложи улучшения. Если это ТЗ или схема — проанализируй и дай рекомендации. Если это что-то другое — вежливо спроси как это связано с разработкой Mini App."
            
            text_part = types.Part(text=user_instruction)
            
            session = session_manager.get_session(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name
            )
            
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=config.model_name,
                contents=[image_part, text_part],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1000,
                    temperature=0.7
                )
            )
            
            typing_task.cancel()
            
            if response.text:
                session.add_message("user", f"[Фото]{f': {caption}' if caption else ''}", config.max_history_length)
                session.add_message("assistant", response.text, config.max_history_length)
                
                lead_manager.save_message(user.id, "user", f"[Фото]{f': {caption}' if caption else ''}")
                lead_manager.save_message(user.id, "assistant", response.text)
                lead_manager.log_event("photo_analysis", user.id)
                lead_manager.update_activity(user.id)
                
                await update.message.reply_text(response.text, parse_mode="Markdown")
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
                "❌ Вы уже отправляли отзыв этого типа или произошла ошибка.",
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
