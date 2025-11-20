"""
Application settings and configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Zoom Configuration
    zoom_client_id: Optional[str] = None
    zoom_client_secret: Optional[str] = None
    zoom_bot_jid: Optional[str] = None

    # Deepgram Configuration
    deepgram_api_key: Optional[str] = None

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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
