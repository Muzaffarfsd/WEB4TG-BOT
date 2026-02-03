import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "rQOBu7YxCDxGiFdTm28w"
    
    model_name: str = "gemini-2.0-flash"
    fast_model_name: str = "gemini-2.0-flash"
    thinking_model_name: str = "gemini-2.5-pro-preview-05-06"
    max_tokens: int = 1500
    temperature: float = 0.7
    
    max_history_length: int = 20
    typing_interval: float = 4.0
    max_retries: int = 2
    retry_delay: float = 0.5
    
    @classmethod
    def from_env(cls) -> "Config":
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        
        if not telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        
        return cls(
            telegram_token=telegram_token,
            gemini_api_key=gemini_api_key,
            elevenlabs_api_key=elevenlabs_api_key
        )


config = Config.from_env()
