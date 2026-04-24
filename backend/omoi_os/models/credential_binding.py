"""Credential binding model for secure credential storage.

This model stores encrypted credentials bound to workspaces with support
for different binding kinds (bearer_secret, user_oauth, github_app).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from omoi_os.models.base import Base
from omoi_os.utils.datetime import utc_now

if TYPE_CHECKING:
    pass


class CredentialBinding(Base):
    """Stores encrypted credentials bound to workspaces.

    Credentials are encrypted using Fernet AES-256-GCM via the
    CredentialEncryptionService. The actual plaintext values are never
    stored in the database.

    Binding kinds:
    - bearer_secret: Simple bearer token or API key
    - user_oauth: OAuth token with optional refresh token
    - github_app: GitHub App installation token
    """

    __tablename__ = "credential_bindings"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Workspace relationship (for isolation) - no FK constraint for safety
    workspace_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Workspace that owns this credential",
    )

    # Binding kind (constrained to valid values)
    kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Binding kind: bearer_secret, user_oauth, or github_app",
    )

    # Human-readable name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable name for this credential",
    )

    # Encrypted value (never store plaintext)
    encrypted_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted credential value (Fernet ciphertext)",
    )

    # Additional configuration (OAuth scopes, GitHub App ID, etc.)
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        server_default="{}",
        comment="Additional configuration as JSON (e.g., OAuth scopes)",
    )

    # Version for rotation tracking
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Version number for rotation tracking",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    rotated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the credential was last rotated",
    )

    __table_args__ = (
        # Unique constraint: prevent duplicate names per workspace per kind
        UniqueConstraint(
            "workspace_id",
            "kind",
            "name",
            name="uq_credential_binding_workspace_kind_name",
        ),
        # Index for workspace-scoped queries
        Index(
            "idx_credential_bindings_workspace",
            "workspace_id",
            "created_at",
        ),
        # Index for kind-based queries
        Index(
            "idx_credential_bindings_kind",
            "kind",
            "workspace_id",
        ),
        {"comment": "Encrypted credentials bound to workspaces"},
    )

    def __repr__(self) -> str:
        return (
            f"<CredentialBinding(id={self.id}, workspace_id={self.workspace_id}, "
            f"kind={self.kind}, name={self.name}, version={self.version})>"
        )
