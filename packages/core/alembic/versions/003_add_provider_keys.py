"""Add Mistral, Cohere, and Together AI provider key columns.

Revision ID: 003
Revises: 002
Create Date: 2026-03-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("mistral_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("cohere_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("together_api_key_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "together_api_key_encrypted")
    op.drop_column("api_keys", "cohere_api_key_encrypted")
    op.drop_column("api_keys", "mistral_api_key_encrypted")
