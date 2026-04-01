"""SQLAlchemy ORM models for database tables."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12))  # "ks-xxxx" for display
    name: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Operator's upstream provider credentials (encrypted at rest in production)
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    gemini_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    groq_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mistral_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    cohere_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    together_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    xai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Who
    api_key_id: Mapped[str] = mapped_column(String(64), index=True)

    # Request
    model_requested: Mapped[str] = mapped_column(String(128))
    model_used: Mapped[str] = mapped_column(String(128))
    messages_json: Mapped[dict] = mapped_column(JSONB)  # type: ignore[type-arg]
    request_params_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    is_streaming: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    has_json_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # Response
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # type: ignore[type-arg]
    finish_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Tokens & cost
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Errors
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
