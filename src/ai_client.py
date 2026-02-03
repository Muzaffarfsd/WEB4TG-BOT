import asyncio
import logging
from typing import List, Dict, Optional
from google import genai

from src.config import config
from src.knowledge_base import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self):
        self._client = genai.Client(
            api_key=config.gemini_api_key,
            http_options=genai.types.HttpOptions(
                base_url=config.gemini_base_url
            )
        )
    
    async def generate_response(
        self,
        messages: List[Dict],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> str:
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=config.model_name,
                    contents=messages,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=config.max_tokens,
                        temperature=config.temperature
                    )
                )
                
                if response.text:
                    return response.text
                else:
                    logger.warning("Empty response from AI")
                    return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
                    
            except Exception as e:
                logger.error(f"AI request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise
        
        return "Извините, произошла ошибка. Попробуйте позже."


ai_client = AIClient()
