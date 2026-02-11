import logging
import asyncio
from typing import Optional, Union
from telegram import Bot, InputFile

logger = logging.getLogger(__name__)

BOT_API_VERSION = "9.4"


async def send_message_draft(
    bot: Bot,
    chat_id: int,
    text: str,
    business_connection_id: Optional[str] = None
) -> dict:
    api_kwargs = {
        "chat_id": chat_id,
        "text": text,
    }
    if business_connection_id:
        api_kwargs["business_connection_id"] = business_connection_id

    try:
        result = await bot.do_api_request(
            endpoint="sendMessageDraft",
            api_kwargs=api_kwargs
        )
        return result
    except Exception as e:
        logger.debug(f"sendMessageDraft not available: {e}")
        return {}


async def stream_ai_response(
    bot: Bot,
    chat_id: int,
    generate_func,
    interval: float = 0.8
) -> Optional[str]:
    full_text = ""
    buffer = ""
    task = asyncio.ensure_future(generate_func())

    async def _collect():
        nonlocal full_text
        result = await task
        full_text = result
        return result

    collector = asyncio.ensure_future(_collect())

    chunks_sent = 0
    while not collector.done():
        await asyncio.sleep(interval)
        if full_text and len(full_text) > len(buffer) + 20:
            draft_text = full_text[:len(buffer) + 80]
            buffer = draft_text
            try:
                await send_message_draft(bot, chat_id, draft_text + " ▌")
                chunks_sent += 1
            except Exception:
                pass

    await collector
    if chunks_sent > 0:
        try:
            await send_message_draft(bot, chat_id, "")
        except Exception:
            pass

    return full_text


def styled_button_api_kwargs(
    style: Optional[str] = None,
    icon_custom_emoji_id: Optional[str] = None
) -> dict:
    api_kwargs = {}
    if style:
        api_kwargs["style"] = style
    if icon_custom_emoji_id:
        api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
    if api_kwargs:
        return {"api_kwargs": api_kwargs}
    return {}


async def set_bot_profile_photo(
    bot: Bot,
    photo: Union[str, bytes, InputFile]
) -> bool:
    try:
        api_kwargs = {"photo": photo}
        await bot.do_api_request(
            endpoint="setMyProfilePhoto",
            api_kwargs=api_kwargs
        )
        logger.info("Bot profile photo updated successfully")
        return True
    except Exception as e:
        logger.debug(f"setMyProfilePhoto not available: {e}")
        return False


async def remove_bot_profile_photo(bot: Bot) -> bool:
    try:
        await bot.do_api_request(
            endpoint="removeMyProfilePhoto",
            api_kwargs={}
        )
        logger.info("Bot profile photo removed")
        return True
    except Exception as e:
        logger.debug(f"removeMyProfilePhoto not available: {e}")
        return False


async def create_invoice_link(
    bot: Bot,
    title: str,
    description: str,
    payload: str,
    currency: str = "RUB",
    prices: list = None,
    provider_token: Optional[str] = None
) -> Optional[str]:
    api_kwargs = {
        "title": title,
        "description": description,
        "payload": payload,
        "currency": currency,
        "prices": prices or [],
    }
    if provider_token:
        api_kwargs["provider_token"] = provider_token

    try:
        result = await bot.do_api_request(
            endpoint="createInvoiceLink",
            api_kwargs=api_kwargs
        )
        return result if isinstance(result, str) else None
    except Exception as e:
        logger.error(f"createInvoiceLink failed: {e}")
        return None


async def get_user_profile_audios(
    bot: Bot,
    user_id: int,
    offset: int = 0,
    limit: int = 100
) -> dict:
    try:
        result = await bot.do_api_request(
            endpoint="getUserProfileAudios",
            api_kwargs={
                "user_id": user_id,
                "offset": offset,
                "limit": limit,
            }
        )
        return result
    except Exception as e:
        logger.debug(f"getUserProfileAudios not available: {e}")
        return {}


def copy_text_button(text: str, copy_text: str) -> dict:
    return {
        "api_kwargs": {
            "copy_text": {"text": copy_text}
        }
    }


async def create_private_topic(
    bot: Bot,
    chat_id: int,
    name: str,
    icon_custom_emoji_id: Optional[str] = None
) -> Optional[int]:
    api_kwargs = {
        "chat_id": chat_id,
        "name": name,
    }
    if icon_custom_emoji_id:
        api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
    
    try:
        result = await bot.do_api_request(
            endpoint="createForumTopic",
            api_kwargs=api_kwargs
        )
        if isinstance(result, dict):
            return result.get("message_thread_id")
        return None
    except Exception as e:
        logger.debug(f"createForumTopic not available: {e}")
        return None


async def send_to_topic(
    bot: Bot,
    chat_id: int,
    message_thread_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup=None
) -> bool:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=message_thread_id,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
    except Exception as e:
        logger.debug(f"send_to_topic failed: {e}")
        return False


def get_api_version() -> str:
    return BOT_API_VERSION
