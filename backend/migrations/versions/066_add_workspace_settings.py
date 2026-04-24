"""Add workspace settings table for session isolation.

Revision ID: 066_add_workspace_settings
Revises: 065_add_webhooks
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "066_add_workspace_settings"
down_revision: Union[str, None] = "065_add_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workspace_settings table."""
    inspector = sa.inspect(op.get_bind())
    if "workspace_settings" in inspector.get_table_names():
        return

    op.create_table(
        "workspace_settings",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "egress_proxy_config",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
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
        sa.PrimaryKeyConstraint("workspace_id"),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environments.id"],
            ondelete="SET NULL",
        ),
        comment="Workspace-level isolation settings for agent sessions",
    )
    op.create_index(
        "idx_workspace_settings_environment",
        "workspace_settings",
        ["environment_id"],
    )


def downgrade() -> None:
    """Drop workspace_settings table."""
    inspector = sa.inspect(op.get_bind())
    if "workspace_settings" not in inspector.get_table_names():
        return

    op.drop_index(
        "idx_workspace_settings_environment",
        table_name="workspace_settings",
    )
    op.drop_table("workspace_settings")
