"""add multi-category agency assignments

Revision ID: 005_agency_categories
Revises: 004_agency_kiosk_visibility
Create Date: 2026-08-10
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_agency_categories"
down_revision: Union[str, Sequence[str], None] = "004_agency_kiosk_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agency_categories",
        sa.Column(
            "agency_id",
            sa.Integer,
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("agency_id", "category_id"),
    )
    op.create_index(
        "ix_agency_categories_category_id", "agency_categories", ["category_id"]
    )
    op.execute(
        """
        INSERT INTO agency_categories (agency_id, category_id)
        SELECT id, category_id
        FROM agencies
        WHERE category_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_agency_categories_category_id", table_name="agency_categories")
    op.drop_table("agency_categories")
