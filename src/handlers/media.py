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


async def analyze_emotions_and_prepare_text(text: str) -> str:
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=config.gemini_api_key)
    
    prompt = """Ты эксперт по подготовке текста для естественного озвучивания.

Твоя задача: добавить эмоциональные теги ElevenLabs v3 в текст для естественного звучания.

Доступные теги (вставляй в квадратных скобках перед фразой):
- [friendly] - дружелюбно
- [excited] - с энтузиазмом  
- [calm] - спокойно
- [professional] - деловой тон
- [warm] - тепло
- [curious] - с интересом
- [confident] - уверенно
- [helpful] - услужливо

Правила:
1. Добавляй теги перед предложениями/фразами где меняется эмоция
2. Не переусердствуй - 2-4 тега на абзац максимум
3. Приветствия: [friendly, warm]
4. Цены/факты: [confident, professional]  
5. Предложения помощи: [helpful, warm]
6. Интересные факты: [excited]
7. Вопросы: [curious]
8. Убери markdown разметку (**, *, #, •)
9. Замени переносы строк на точки или запятые для пауз
10. НЕ меняй смысл текста, только добавь теги

Верни ТОЛЬКО обработанный текст, без объяснений.

Текст для обработки:
"""
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[prompt + text],
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
    clean_text = clean_text.replace("\n\n", ". ").replace("\n", ", ")
    
    voice_text = await analyze_emotions_and_prepare_text(clean_text)
    
    voice_text = apply_stress_marks(voice_text)
    
    try:
        audio_generator = await asyncio.to_thread(
            client.text_to_speech.convert,
            voice_id=config.elevenlabs_voice_id,
            text=voice_text,
            model_id="eleven_v3",
            output_format="mp3_44100_192"
        )
        
        audio_bytes = b"".join(audio_generator)
        return audio_bytes
    except Exception as e:
        logger.error(f"ElevenLabs voice generation failed ({type(e).__name__}): {e}")
        raise


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    typing_task = asyncio.create_task(
        send_typing_action(update, duration=30.0)
    )
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        voice_bytes = await file.download_as_bytearray()
        
        session = session_manager.get_session(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        from google import genai
        from google.genai import types
        from src.knowledge_base import SYSTEM_PROMPT
        
        client = genai.Client(api_key=config.gemini_api_key)
        
        audio_part = types.Part.from_bytes(data=bytes(voice_bytes), mime_type="audio/ogg")
        text_part = types.Part(text="Это голосовое сообщение от клиента. Пойми что он сказал и сразу ответь на его вопрос как консультант Алекс из WEB4TG Studio. НЕ пиши расшифровку, НЕ пиши 'вы сказали', просто отвечай на вопрос.")
        
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=config.model_name,
            contents=[audio_part, text_part],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        
        typing_task.cancel()
        
        if response.text:
            session.add_message("user", "[Голосовое сообщение]", config.max_history_length)
            session.add_message("assistant", response.text, config.max_history_length)
            
            lead_manager.save_message(user.id, "user", "[Голосовое сообщение]")
            lead_manager.save_message(user.id, "assistant", response.text)
            lead_manager.log_event("voice_message", user.id)
            lead_manager.update_activity(user.id)
            
            if config.elevenlabs_api_key:
                try:
                    await update.effective_chat.send_action(ChatAction.RECORD_VOICE)
                    voice_response = await generate_voice_response(response.text)
                    await update.message.reply_voice(voice=voice_response)
                except Exception as e:
                    logger.error(f"ElevenLabs TTS error ({type(e).__name__}): {e}")
                    await update.message.reply_text(response.text)
            else:
                await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("Не удалось распознать сообщение. Попробуйте ещё раз или напишите текстом.")
            
    except Exception as e:
        typing_task.cancel()
        logger.error(f"Voice processing error: {e}")
        await update.message.reply_text(
            "Не удалось обработать голосовое сообщение. Напишите текстом, пожалуйста."
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
