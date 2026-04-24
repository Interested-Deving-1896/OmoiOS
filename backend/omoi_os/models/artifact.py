"""Artifact model for unified artifact storage.

This model stores metadata about uploaded artifacts with support for
multiple storage backends (local filesystem, S3, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from omoi_os.models.base import Base
from omoi_os.utils.datetime import utc_now

if TYPE_CHECKING:
    pass


class Artifact(Base):
    """Stores artifact metadata for uploaded files.

    Artifacts can be stored in different backends:
    - "local": Local filesystem storage
    - "s3": Amazon S3 storage (v1 interface only)

    The actual file content is stored in the configured backend,
    while this model tracks metadata, checksums, and storage paths.
    """

    __tablename__ = "artifacts"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Workspace relationship (for isolation)
    workspace_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Workspace that owns this artifact",
    )

    # Artifact identification
    name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Original filename of the artifact",
    )

    # Storage backend configuration
    storage_backend: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="local",
        comment="Storage backend: 'local' or 's3'",
    )

    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Relative path or URI to the stored file",
    )

    # Content metadata
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hex digest of the file content",
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )

    content_type: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="MIME type of the content (e.g., 'text/plain', 'image/png')",
    )

    # Custom metadata (NOT 'metadata' - reserved SQLAlchemy word)
    artifact_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional user-defined metadata as JSON",
    )

    # Timestamps
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
        # Index for workspace-scoped queries
        Index(
            "idx_artifacts_workspace",
            "workspace_id",
            "created_at",
        ),
        # Index for checksum lookups (deduplication)
        Index(
            "idx_artifacts_checksum",
            "checksum",
        ),
        # Index for storage backend queries
        Index(
            "idx_artifacts_backend",
            "storage_backend",
            "workspace_id",
        ),
        {"comment": "Artifact metadata for uploaded files"},
    )

    def __repr__(self) -> str:
        return (
            f"<Artifact(id={self.id}, workspace_id={self.workspace_id}, "
            f"name={self.name}, size={self.size_bytes} bytes, "
            f"backend={self.storage_backend})>"
        )
