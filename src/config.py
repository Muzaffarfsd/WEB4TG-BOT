import os
import json
import logging
from dataclasses import dataclass
from typing import Optional

_config_logger = logging.getLogger(__name__)


def _fetch_elevenlabs_key_from_connector() -> Optional[str]:
    try:
        import urllib.request
        hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME", "")
        if not hostname:
            return None

        repl_identity = os.environ.get("REPL_IDENTITY", "")
        web_repl_renewal = os.environ.get("WEB_REPL_RENEWAL", "")
        if repl_identity:
            token = f"repl {repl_identity}"
        elif web_repl_renewal:
            token = f"depl {web_repl_renewal}"
        else:
            return None

        url = f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=elevenlabs"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X_REPLIT_TOKEN": token
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            if items:
                api_key = items[0].get("settings", {}).get("api_key", "")
                if api_key:
                    _config_logger.info("ElevenLabs API key loaded from Replit connector")
                    return api_key
    except Exception as e:
        _config_logger.warning(f"Failed to fetch ElevenLabs key from connector: {e}")
    return None


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "rQOBu7YxCDxGiFdTm28w"
    
    model_name: str = "gemini-3-flash-preview"
    fast_model_name: str = "gemini-3-flash-preview"
    thinking_model_name: str = "gemini-3-pro-preview"
    audio_model_name: str = "gemini-3-pro-preview"
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
        
        if not elevenlabs_api_key:
            elevenlabs_api_key = _fetch_elevenlabs_key_from_connector()
        
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
