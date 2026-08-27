"""catalog push version (singleton)

Revision ID: 006_catalog_meta
Revises: 005_agency_categories
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_catalog_meta"
down_revision: Union[str, Sequence[str], None] = "005_agency_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_meta",
        sa.Column("singleton_id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("refresh_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("singleton_id = 1", name="catalog_meta_singleton"),
    )
    op.execute(
        "INSERT INTO catalog_meta (singleton_id, version) VALUES (1, 1) "
        "ON CONFLICT (singleton_id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("catalog_meta")
