"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KS_")

    database_url: str = "postgresql+asyncpg://kestrel:kestrel@localhost:5432/kestrel"
    log_level: str = "INFO"

    # Provider base URLs
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    mistral_base_url: str = "https://api.mistral.ai/v1"
    cohere_base_url: str = "https://api.cohere.com/v2"
    together_base_url: str = "https://api.together.xyz/v1"

    # Bypass auth for local development
    dev_mode: bool = False

    # Default provider keys for dev mode
    dev_openai_api_key: str = ""
    dev_anthropic_api_key: str = ""
    dev_gemini_api_key: str = ""
    dev_groq_api_key: str = ""
    dev_mistral_api_key: str = ""
    dev_cohere_api_key: str = ""
    dev_together_api_key: str = ""

    # Health check interval in seconds
    health_check_interval: int = 30

    # Routing
    routing_enabled: bool = True
    routing_allowed_providers: str = ""  # Comma-separated, empty = all allowed
    routing_denied_providers: str = ""  # Comma-separated
    routing_tier_floor: str = ""  # Minimum tier: "economy", "standard", "premium"
    routing_tier_ceiling: str = ""  # Maximum tier (overrides model ceiling if lower)
