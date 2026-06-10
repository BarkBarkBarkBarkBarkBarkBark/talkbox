"""initial schema: pgvector extension + categories + agencies

Revision ID: 001_initial
Revises:
Create Date: 2026-04-17

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "agencies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agency_name", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(50)),
        sa.Column("address", sa.Text),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
        ),
        sa.Column("description", sa.Text),
        sa.Column("insurance", sa.String(255)),
        sa.Column("knowledge_tags", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("agencies")
    op.drop_table("categories")
    # pgvector may be used by other migrations; leave the extension in place.
