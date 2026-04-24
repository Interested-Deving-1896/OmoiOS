"""Environment model for immutable versioned configuration storage.

This model stores environment configurations with support for versioned
immutable variables. Each environment can have multiple versions, and
variables can be of type string, secret (encrypted), or json.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from omoi_os.models.base import Base
from omoi_os.utils.datetime import utc_now

if TYPE_CHECKING:
    pass


class Environment(Base):
    """Stores environment metadata for configuration management.

    Environments are scoped to organizations and have unique names within
    each organization. Each environment can have multiple immutable versions
    of variable configurations.
    """

    __tablename__ = "environments"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Organization relationship (for isolation) - no FK constraint for safety
    org_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
        comment="Organization that owns this environment",
    )

    # Environment identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Environment name (unique within org)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional environment description",
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

    # Relationship to versions
    versions: Mapped[list["EnvironmentVersion"]] = relationship(
        "EnvironmentVersion",
        back_populates="environment",
        cascade="all, delete-orphan",
        order_by="EnvironmentVersion.version_number.desc()",
    )

    __table_args__ = (
        # Unique constraint: environment names are unique within an org
        UniqueConstraint("org_id", "name", name="uq_environment_org_name"),
        # Index for org-scoped queries
        Index(
            "idx_environments_org",
            "org_id",
            "created_at",
        ),
        {"comment": "Environment metadata for configuration management"},
    )

    def __repr__(self) -> str:
        return (
            f"<Environment(id={self.id}, org_id={self.org_id}, "
            f"name={self.name}, versions={len(self.versions) if self.versions else 0})>"
        )


class EnvironmentVersion(Base):
    """Stores immutable versioned environment variable configurations.

    Each version is immutable once created. Variables are stored as JSONB
    with structure: {"VAR_NAME": {"type": "string|secret|json", "value": "..."}}

    Secret values are encrypted before storage using CredentialEncryptionService.
    """

    __tablename__ = "environment_versions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Environment relationship
    environment_id: Mapped[UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Environment this version belongs to",
    )

    # Version identification
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential version number (1, 2, 3, ...)",
    )

    # Variable storage
    # Structure: {"VAR_NAME": {"type": "string|secret|json", "value": "..."}}
    # For secrets, value is encrypted
    variables: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Environment variables with type and value",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationship to environment
    environment: Mapped["Environment"] = relationship(
        "Environment",
        back_populates="versions",
    )

    __table_args__ = (
        # Unique constraint: version numbers are unique within an environment
        UniqueConstraint(
            "environment_id",
            "version_number",
            name="uq_environment_version_number",
        ),
        # Index for version lookups
        Index(
            "idx_environment_versions_env",
            "environment_id",
            "version_number",
        ),
        {"comment": "Immutable versioned environment variable configurations"},
    )

    def __repr__(self) -> str:
        return (
            f"<EnvironmentVersion(id={self.id}, environment_id={self.environment_id}, "
            f"version_number={self.version_number}, variables_count={len(self.variables) if self.variables else 0})>"
        )
