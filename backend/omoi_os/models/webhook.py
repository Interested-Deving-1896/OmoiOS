"""Webhook models for subscription management and delivery tracking.

Provides SQLAlchemy models for:
- Webhook subscriptions (URL, events, secret, active status)
- Webhook deliveries (status, attempts, retry scheduling)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from omoi_os.models.base import Base
from omoi_os.utils.datetime import utc_now

if TYPE_CHECKING:
    pass


class WebhookSubscription(Base):
    """Stores webhook subscription configuration.

    Each subscription defines:
    - Target URL for webhook delivery
    - Event types to subscribe to
    - HMAC-SHA256 signing secret
    - Active/inactive status
    """

    __tablename__ = "webhook_subscriptions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    org_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Organization that owns this subscription",
    )

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Webhook delivery URL",
    )

    events: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        comment="Subscribed event types",
    )

    secret: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="HMAC-SHA256 signing secret",
    )

    active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether this subscription is active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        Index(
            "idx_webhook_subs_org_active",
            "org_id",
            "active",
        ),
        Index(
            "idx_webhook_subs_events",
            "events",
            postgresql_using="gin",
        ),
        {"comment": "Webhook subscription configuration"},
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookSubscription(id={self.id}, org_id={self.org_id}, "
            f"url={self.url}, events={self.events}, active={self.active})>"
        )


class WebhookDeliveryStatus:
    """Webhook delivery status constants."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookDelivery(Base):
    """Tracks webhook delivery attempts and status.

    Each delivery record represents one webhook payload sent to
    one subscription, with retry tracking.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    subscription_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Webhook subscription this delivery belongs to",
    )

    event: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Event type that triggered this delivery",
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Webhook payload data",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=WebhookDeliveryStatus.PENDING,
        comment="Delivery status: pending, delivered, failed, retrying",
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of delivery attempts made",
    )

    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When to attempt next delivery (for retries)",
    )

    response_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP response status from last attempt",
    )

    response_body: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
        comment="HTTP response body from last attempt (truncated)",
    )

    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When delivery was successfully completed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        Index(
            "idx_webhook_deliveries_status_retry",
            "status",
            "next_retry_at",
        ),
        Index(
            "idx_webhook_deliveries_sub_event",
            "subscription_id",
            "event",
        ),
        {"comment": "Webhook delivery tracking"},
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery(id={self.id}, subscription_id={self.subscription_id}, "
            f"event={self.event}, status={self.status}, attempts={self.attempts})>"
        )


class WebhookDeliveryAttempt(Base):
    """Audit log for individual delivery attempts.

    Each row represents one attempt to deliver a webhook,
    including response details for debugging.
    """

    __tablename__ = "webhook_delivery_attempts"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    delivery_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Webhook delivery this attempt belongs to",
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Attempt number (1-indexed)",
    )

    response_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP response status code",
    )

    response_body: Mapped[Optional[str]] = mapped_column(
        String(4096),
        nullable=True,
        comment="HTTP response body (truncated)",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="Error message if delivery failed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    __table_args__ = (
        Index(
            "idx_webhook_attempts_delivery",
            "delivery_id",
            "attempt_number",
        ),
        {"comment": "Webhook delivery attempt audit log"},
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookDeliveryAttempt(id={self.id}, delivery_id={self.delivery_id}, "
            f"attempt={self.attempt_number}, status={self.response_status})>"
        )
