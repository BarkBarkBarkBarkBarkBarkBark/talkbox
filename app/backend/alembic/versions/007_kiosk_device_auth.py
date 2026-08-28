"""add kiosk device authentication tables

Revision ID: 007_kiosk_device_auth
Revises: 006_catalog_meta
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_kiosk_device_auth"
down_revision: Union[str, Sequence[str], None] = "006_catalog_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kiosk_devices",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("device_code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("credential_hash", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("device_code", name="uq_kiosk_devices_device_code"),
    )
    op.create_index("ix_kiosk_devices_enabled", "kiosk_devices", ["enabled"])

    op.create_table(
        "kiosk_enrollment_codes",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("device_code", sa.String(length=32), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_device_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_kiosk_enrollment_codes_active",
        "kiosk_enrollment_codes",
        ["expires_at", "used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_kiosk_enrollment_codes_active", table_name="kiosk_enrollment_codes")
    op.drop_table("kiosk_enrollment_codes")
    op.drop_index("ix_kiosk_devices_enabled", table_name="kiosk_devices")
    op.drop_table("kiosk_devices")
