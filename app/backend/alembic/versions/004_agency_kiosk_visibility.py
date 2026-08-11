"""add per-agency kiosk Browse visibility

Revision ID: 004_agency_kiosk_visibility
Revises: 003_resource_import_staging
Create Date: 2026-08-10
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_agency_kiosk_visibility"
down_revision: Union[str, Sequence[str], None] = "003_resource_import_staging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agencies",
        sa.Column(
            "show_on_kiosk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("agencies", "show_on_kiosk")
