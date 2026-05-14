"""Initial schema — sync_records + audit_log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("sop_instance_uid", sa.String(128), nullable=True),
        sa.Column("study_instance_uid", sa.String(128), nullable=True),
        sa.Column("series_instance_uid", sa.String(128), nullable=True),
        sa.Column("storage_uri", sa.String(1024), nullable=True),
        sa.Column("error", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sync_records_device_id", "sync_records", ["device_id"])
    op.create_index("ix_sync_records_user_id", "sync_records", ["user_id"])
    op.create_index("ix_sync_records_sha256", "sync_records", ["sha256"], unique=True)
    op.create_index("ix_sync_records_sop_instance_uid", "sync_records", ["sop_instance_uid"])
    op.create_index("ix_sync_records_study_instance_uid", "sync_records", ["study_instance_uid"])
    op.create_index("ix_sync_records_series_instance_uid", "sync_records", ["series_instance_uid"])

    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_request_id", "audit_log", ["request_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    for ix in (
        "ix_audit_log_created_at",
        "ix_audit_log_request_id",
        "ix_audit_log_action",
        "ix_audit_log_actor",
    ):
        op.drop_index(ix, table_name="audit_log")
    op.drop_table("audit_log")
    for ix in (
        "ix_sync_records_series_instance_uid",
        "ix_sync_records_study_instance_uid",
        "ix_sync_records_sop_instance_uid",
        "ix_sync_records_sha256",
        "ix_sync_records_user_id",
        "ix_sync_records_device_id",
    ):
        op.drop_index(ix, table_name="sync_records")
    op.drop_table("sync_records")
