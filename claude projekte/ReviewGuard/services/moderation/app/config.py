from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    database_url: str = "postgresql://reviewguard:reviewguard_secret@localhost:5432/reviewguard"
    ai_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    notification_service_url: str = "http://notification:8000"
    default_risk_threshold: float = 0.65

    class Config:
        env_file = ".env"


settings = Settings()
