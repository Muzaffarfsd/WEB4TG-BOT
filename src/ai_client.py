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
    
    async def generate_response(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> str:
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_delay, min=1, max=30),
            retry=retry_if_exception(is_rate_limit_error),
            reraise=True
        )
        async def _generate():
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=config.model_name,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=config.max_tokens,
                    temperature=config.temperature,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=8192 if thinking_level == "high" else 4096
                    )
                )
            )
            return response
        
        try:
            response = await _generate()
            
            if response.text:
                return response.text
            else:
                logger.warning("Empty response from AI")
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
                
        except Exception as e:
            logger.error(f"AI request failed: {e}")
            raise
    
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
