"""resource import staging

Revision ID: 003_resource_import_staging
Revises: 002_users
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from fastapi_users_db_sqlalchemy.generics import GUID

revision: str = "003_resource_import_staging"
down_revision: Union[str, Sequence[str], None] = "002_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resource_import_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="previewed"),
        sa.Column("total_rows", sa.Integer, nullable=False),
        sa.Column("valid_rows", sa.Integer, nullable=False),
        sa.Column("invalid_rows", sa.Integer, nullable=False),
        sa.Column("errors", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("uploaded_by", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "resource_import_rows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("resource_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column("errors", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.create_index("ix_resource_import_rows_batch_id", "resource_import_rows", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_resource_import_rows_batch_id", table_name="resource_import_rows")
    op.drop_table("resource_import_rows")
    op.drop_table("resource_import_batches")