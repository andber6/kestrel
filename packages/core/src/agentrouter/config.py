"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AR_")

    database_url: str = "postgresql+asyncpg://agentrouter:agentrouter@localhost:5432/agentrouter"
    openai_base_url: str = "https://api.openai.com/v1"
    log_level: str = "INFO"

    # Bypass auth for local development
    dev_mode: bool = False
    # Default OpenAI key for dev mode (when operator doesn't pass one)
    dev_openai_api_key: str = ""
