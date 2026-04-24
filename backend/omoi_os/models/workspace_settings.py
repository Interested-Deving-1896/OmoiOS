"""Workspace settings model for session isolation boundaries."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from omoi_os.models.base import Base
from omoi_os.utils.datetime import utc_now


class WorkspaceSettings(Base):
    """Stores isolation settings for an agent workspace.

    Each workspace has an isolated filesystem root, optional environment binding,
    and optional network egress proxy configuration. Credential access is enforced
    against the credential_bindings.workspace_id boundary rather than stored here.
    """

    __tablename__ = "workspace_settings"

    workspace_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Workspace UUID that owns these isolation settings",
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Isolated filesystem path for the workspace",
    )
    environment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional environment whose latest version is injected into sessions",
    )
    egress_proxy_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Workspace-scoped network egress proxy configuration",
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
        Index("idx_workspace_settings_environment", "environment_id"),
        {"comment": "Workspace-level isolation settings for agent sessions"},
    )
