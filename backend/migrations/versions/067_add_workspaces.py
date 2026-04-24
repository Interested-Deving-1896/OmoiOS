"""Add tenant-level workspaces table.

Introduces a first-class Workspace resource per spec §02 (agent-platform-spec):
an org-scoped grouping that owns environments, credentials, artifacts, and
webhook subscriptions. Prior to this, `workspace_id` was a free-floating UUID
across credential_bindings / environments / artifacts / webhook_subscriptions /
workspace_settings with no referential integrity.

This migration is strictly additive — we do NOT add FKs from the existing
`workspace_id` columns yet, so legacy rows with opaque UUIDs keep working.
A follow-up migration can lift them once we're sure every new write goes
through this table.

Revision ID: 067_add_workspaces
Revises: 066_add_workspace_settings
Create Date: 2026-04-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "067_add_workspaces"
down_revision: Union[str, None] = "066_add_workspace_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "workspaces" in inspector.get_table_names():
        return

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "default_environment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["default_environment_id"],
            ["environments.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
        comment="Tenant-level workspace grouping for environments, credentials, sessions, and artifacts",
    )
    op.create_index("idx_workspaces_org", "workspaces", ["organization_id"])
    op.create_index(
        "idx_workspaces_org_active",
        "workspaces",
        ["organization_id", "is_active"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "workspaces" not in inspector.get_table_names():
        return

    op.drop_index("idx_workspaces_org_active", table_name="workspaces")
    op.drop_index("idx_workspaces_org", table_name="workspaces")
    op.drop_table("workspaces")
