import asyncio
import logging
from typing import List, Dict, Optional
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.config import config
from src.knowledge_base import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def is_rate_limit_error(exception: BaseException) -> bool:
    error_msg = str(exception)
    return (
        "429" in error_msg 
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower() 
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, 'status') and exception.status == 429)
    )


class AIClient:
    def __init__(self):
        self._client = genai.Client(api_key=config.gemini_api_key)

    async def generate_response_stream(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        on_chunk=None
    ) -> str:
        if thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=4096)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

        try:
            import queue
            chunk_queue = queue.Queue()

            def _stream_in_thread():
                full = ""
                try:
                    stream = self._client.models.generate_content_stream(
                        model=model,
                        contents=messages,
                        config=gen_config
                    )
                    for chunk in stream:
                        if chunk.text:
                            full += chunk.text
                            chunk_queue.put(full)
                except Exception:
                    pass
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

            if full_text:
                return full_text
            return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if is_rate_limit_error(e):
                logger.warning(f"Gemini stream rate limit: {error_type}: {error_msg}")
                return "Сейчас высокая нагрузка, попробуйте через минуту 🙏"
            logger.error(f"Gemini stream failed: {error_type}: {error_msg}")
            return await self.generate_response(messages, thinking_level)

    async def generate_response(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        max_retries: int = 2,
        retry_delay: float = 0.5
    ) -> str:
        if thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=4096)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )
        
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_delay, min=0.5, max=10),
            retry=retry_if_exception(is_rate_limit_error),
            reraise=True
        )
        async def _generate():
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=messages,
                config=gen_config
            )
            return response
        
        try:
            response = await _generate()
            
            if response.text:
                return response.text
            else:
                logger.warning("Empty response from Gemini")
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            if is_rate_limit_error(e):
                logger.warning(f"Gemini rate limit hit: {error_type}: {error_msg}")
                return "Сейчас высокая нагрузка, попробуйте через минуту 🙏"
            elif "timeout" in error_msg.lower() or "connect" in error_msg.lower():
                logger.error(f"Gemini connection error: {error_type}: {error_msg}")
                return "Не удалось подключиться к серверу. Попробуйте позже."
            else:
                logger.error(f"Gemini request failed: {error_type}: {error_msg}")
                return "Произошла техническая ошибка. Попробуйте ещё раз или напишите позже."
    
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


ai_client = AIClient()
