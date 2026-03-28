"""Add multi-provider support columns.

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New provider key columns on api_keys
    op.add_column(
        "api_keys",
        sa.Column("anthropic_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("gemini_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("groq_api_key_encrypted", sa.Text(), nullable=True),
    )

    # New columns on request_logs for multi-provider tracking
    op.add_column(
        "request_logs",
        sa.Column("provider_used", sa.String(32), nullable=True),
    )
    op.add_column(
        "request_logs",
        sa.Column("failover_attempts", sa.SmallInteger(), nullable=True, default=0),
    )


def downgrade() -> None:
    op.drop_column("request_logs", "failover_attempts")
    op.drop_column("request_logs", "provider_used")
    op.drop_column("api_keys", "groq_api_key_encrypted")
    op.drop_column("api_keys", "gemini_api_key_encrypted")
    op.drop_column("api_keys", "anthropic_api_key_encrypted")
