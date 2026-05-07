from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://reviewguard:reviewguard_secret@localhost:5432/reviewguard"
    moderation_service_url: str = "http://moderation:8000"

    class Config:
        env_file = ".env"


settings = Settings()
