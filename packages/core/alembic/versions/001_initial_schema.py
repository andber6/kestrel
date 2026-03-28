"""Initial schema: api_keys and request_logs tables.

Revision ID: 001
Revises:
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(128), unique=True, index=True, nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
        sa.Column("api_key_id", sa.String(64), nullable=False, index=True),
        sa.Column("model_requested", sa.String(128), nullable=False),
        sa.Column("model_used", sa.String(128), nullable=False),
        sa.Column("messages_json", postgresql.JSONB(), nullable=False),
        sa.Column("request_params_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_streaming", sa.Boolean(), default=False, nullable=False),
        sa.Column("has_tools", sa.Boolean(), default=False, nullable=False),
        sa.Column("has_json_mode", sa.Boolean(), default=False, nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=True),
        sa.Column("finish_reason", sa.String(32), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("time_to_first_token_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("status_code", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("request_logs")
    op.drop_table("api_keys")
