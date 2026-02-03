import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    gemini_base_url: str
    
    model_name: str = "gemini-2.5-pro"
    max_tokens: int = 2000
    temperature: float = 0.7
    
    max_history_length: int = 30
    typing_interval: float = 4.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    @classmethod
    def from_env(cls) -> "Config":
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        gemini_api_key = os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY")
        gemini_base_url = os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL")
        
        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not gemini_api_key:
            raise ValueError("AI_INTEGRATIONS_GEMINI_API_KEY is not set")
        if not gemini_base_url:
            raise ValueError("AI_INTEGRATIONS_GEMINI_BASE_URL is not set")
        
        return cls(
            telegram_token=telegram_token,
            gemini_api_key=gemini_api_key,
            gemini_base_url=gemini_base_url
        )


config = Config.from_env()
