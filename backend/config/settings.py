"""
Application settings and configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
from dotenv import dotenv_values
from pathlib import Path


# Load .env file values directly using absolute path
_env_file = Path(__file__).parent.parent / ".env"
_env_values = dotenv_values(_env_file) if _env_file.exists() else {}


def _get_env_value(key: str, default=None):
    """Get value from .env file, ignoring empty system env vars"""
    import os
    sys_val = os.environ.get(key, '')
    # If system env var is empty, use .env file value
    if sys_val == '':
        return _env_values.get(key, default)
    return sys_val


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Zoom Configuration
    zoom_client_id: Optional[str] = None
    zoom_client_secret: Optional[str] = None
    zoom_bot_jid: Optional[str] = None

    # Deepgram Configuration (for real-time live transcription)
    deepgram_api_key: Optional[str] = _get_env_value('DEEPGRAM_API_KEY')
    deepgram_model: str = "nova-2"  # Best accuracy model
    deepgram_language: str = "de"  # German default

    # Fireflies Configuration
    fireflies_api_key: Optional[str] = _get_env_value('FIREFLIES_API_KEY')
    fireflies_enabled: bool = False  # Set to True to use Fireflies instead of Deepgram
    fireflies_poll_interval: int = 10  # Seconds between active meeting checks
    fireflies_webhook_secret: Optional[str] = _get_env_value('FIREFLIES_WEBHOOK_SECRET')

    # n8n Webhooks
    n8n_transcript_webhook: str = "https://n8n.suigeneris.de/webhook/zoom-transcript-stream"
    n8n_command_webhook: str = "https://n8n.suigeneris.de/webhook/zoom-user-command"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379"

    # Database (optional)
    database_url: Optional[str] = None

    # Application Settings
    app_environment: str = "development"
    debug_mode: bool = True

    @field_validator('deepgram_api_key', 'fireflies_api_key', 'zoom_client_id', 'zoom_client_secret', 'zoom_bot_jid', 'fireflies_webhook_secret', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None"""
        if v == '':
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()

# Post-init fix: Override API keys with .env values if system env vars are empty
import os as _os
if not settings.deepgram_api_key or settings.deepgram_api_key == '':
    if 'DEEPGRAM_API_KEY' in _env_values:
        object.__setattr__(settings, 'deepgram_api_key', _env_values['DEEPGRAM_API_KEY'])
if not settings.fireflies_api_key or settings.fireflies_api_key == '':
    if 'FIREFLIES_API_KEY' in _env_values:
        object.__setattr__(settings, 'fireflies_api_key', _env_values['FIREFLIES_API_KEY'])
