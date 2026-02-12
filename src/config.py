import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "rQOBu7YxCDxGiFdTm28w"
    
    model_name: str = "gemini-3-pro-preview"
    fast_model_name: str = "gemini-3-pro-preview"
    thinking_model_name: str = "gemini-3-pro-preview"
    audio_model_name: str = "gemini-2.0-flash"
    max_tokens: int = 2000
    temperature: float = 0.7
    
    max_history_length: int = 30
    typing_interval: float = 4.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    webapp_url: str = "https://web4tg.com"
    telegram_channel: str = "https://t.me/web4_tg"
    youtube_channel: str = "https://www.youtube.com/@WEB4TG"
    instagram_url: str = "https://instagram.com/web4tg"
    tiktok_url: str = "https://tiktok.com/@web4tg"
    
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
