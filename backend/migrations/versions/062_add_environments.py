"""Add environments and environment_versions tables.

Revision ID: 062_add_environments
Revises: 061_add_encrypted_api_key
Create Date: 2025-04-23

This migration:
1. Creates the environments table with org_id, name, description
2. Creates the environment_versions table with version_number and variables (JSONB)
3. Adds indexes for org-scoped queries and version lookups
4. Adds unique constraints for org+name and environment+version_number
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "062_add_environments"
down_revision: Union[str, None] = "061_add_encrypted_api_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create environments and environment_versions tables."""
    # Create environments table
    op.create_table(
        "environments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
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
        sa.UniqueConstraint("org_id", "name", name="uq_environment_org_name"),
        comment="Environment metadata for configuration management",
    )

    # Create indexes for environments table
    op.create_index(
        "idx_environments_org",
        "environments",
        ["org_id", "created_at"],
    )
    op.create_index(
        "idx_environments_org_id",
        "environments",
        ["org_id"],
    )

    # Create environment_versions table
    op.create_table(
        "environment_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "variables",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environments.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "environment_id",
            "version_number",
            name="uq_environment_version_number",
        ),
        comment="Immutable versioned environment variable configurations",
    )

    # Create indexes for environment_versions table
    op.create_index(
        "idx_environment_versions_env",
        "environment_versions",
        ["environment_id", "version_number"],
    )
    op.create_index(
        "idx_environment_versions_env_id",
        "environment_versions",
        ["environment_id"],
    )


def downgrade() -> None:
    """Drop environments and environment_versions tables."""
    # Drop indexes for environment_versions
    op.drop_index("idx_environment_versions_env_id", table_name="environment_versions")
    op.drop_index("idx_environment_versions_env", table_name="environment_versions")

    # Drop environment_versions table
    op.drop_table("environment_versions")

    # Drop indexes for environments
    op.drop_index("idx_environments_org_id", table_name="environments")
    op.drop_index("idx_environments_org", table_name="environments")

    # Drop environments table
    op.drop_table("environments")
