import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "rQOBu7YxCDxGiFdTm28w"
    
    model_name: str = "gemini-2.5-flash"
    fast_model_name: str = "gemini-2.5-flash"
    thinking_model_name: str = "gemini-2.5-pro"
    audio_model_name: str = "gemini-2.5-flash"
    max_tokens: int = 2000
    temperature: float = 0.45
    temperature_creative: float = 0.65
    temperature_precise: float = 0.3
    
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

_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=config.gemini_api_key)
    return _gemini_client
