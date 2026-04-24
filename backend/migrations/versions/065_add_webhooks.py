"""Add webhook tables for subscription management and delivery tracking.

Revision ID: 065_add_webhooks
Revises: 064_add_credential_bindings
Create Date: 2025-04-23

This migration:
1. Creates webhook_subscriptions table for webhook endpoint configuration
2. Creates webhook_deliveries table for delivery tracking and retry scheduling
3. Creates webhook_delivery_attempts table for audit logging
4. Adds indexes for efficient querying by org, status, and event type
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "065_add_webhooks"
down_revision: Union[str, None] = "064_add_credential_bindings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create webhook subscription, delivery, and attempt tables."""
    # Create webhook_subscriptions table
    op.create_table(
        "webhook_subscriptions",
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
            "url",
            sa.String(2048),
            nullable=False,
        ),
        sa.Column(
            "events",
            postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "secret",
            sa.String(256),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean,
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
        sa.Index("idx_webhook_subs_org_active", "org_id", "active"),
        sa.Index(
            "idx_webhook_subs_events",
            "events",
            postgresql_using="gin",
        ),
    )

    # Create webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "event",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "response_status",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "response_body",
            sa.String(4096),
            nullable=True,
        ),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.Index("idx_webhook_deliveries_status_retry", "status", "next_retry_at"),
        sa.Index("idx_webhook_deliveries_sub_event", "subscription_id", "event"),
    )

    # Create webhook_delivery_attempts table
    op.create_table(
        "webhook_delivery_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "delivery_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "attempt_number",
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            "response_status",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "response_body",
            sa.String(4096),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.String(1024),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_webhook_attempts_delivery", "delivery_id", "attempt_number"),
    )


def downgrade() -> None:
    """Drop webhook tables."""
    op.drop_table("webhook_delivery_attempts")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
