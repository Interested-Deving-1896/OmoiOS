"""Add artifacts table for unified artifact storage.

Revision ID: 063_add_artifacts
Revises: 062_add_environments
Create Date: 2025-04-23

This migration:
1. Creates the artifacts table with metadata and storage backend info
2. Adds indexes for workspace queries and checksum lookups
3. Uses artifact_metadata (not metadata - reserved SQLAlchemy word)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "063_add_artifacts"
down_revision: Union[str, None] = "062_add_environments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create artifacts table."""
    # Create artifacts table
    op.create_table(
        "artifacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(512),
            nullable=False,
        ),
        sa.Column(
            "storage_backend",
            sa.String(32),
            nullable=False,
            server_default="local",
        ),
        sa.Column(
            "storage_path",
            sa.String(1024),
            nullable=False,
        ),
        sa.Column(
            "checksum",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "content_type",
            sa.String(128),
            nullable=True,
        ),
        sa.Column(
            "artifact_metadata",
            postgresql.JSONB(),
            nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Artifact metadata for uploaded files",
    )

    # Create indexes
    op.create_index(
        "idx_artifacts_workspace",
        "artifacts",
        ["workspace_id", "created_at"],
    )

    op.create_index(
        "idx_artifacts_checksum",
        "artifacts",
        ["checksum"],
    )

    op.create_index(
        "idx_artifacts_backend",
        "artifacts",
        ["storage_backend", "workspace_id"],
    )


def downgrade() -> None:
    """Drop artifacts table."""
    op.drop_index("idx_artifacts_backend", table_name="artifacts")
    op.drop_index("idx_artifacts_checksum", table_name="artifacts")
    op.drop_index("idx_artifacts_workspace", table_name="artifacts")
    op.drop_table("artifacts")
