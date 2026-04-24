"""Pydantic schemas for the tenant-level Workspace resource (spec §02)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    """Create a workspace under the caller's organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$", max_length=255)
    organization_id: Optional[UUID] = Field(
        None,
        description="Organization to create under. If omitted, uses the organization "
        "bound to the caller's API key, or their first-owned organization.",
    )
    default_environment_id: Optional[UUID] = None
    settings: Optional[dict] = None


class WorkspaceUpdate(BaseModel):
    """Mutate a workspace. Organization cannot be changed."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    default_environment_id: Optional[UUID] = None
    settings: Optional[dict] = None
    is_active: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    """Workspace as returned by the API."""

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    default_environment_id: Optional[UUID] = None
    settings: dict = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
