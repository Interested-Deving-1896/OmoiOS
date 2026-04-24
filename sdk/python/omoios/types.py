"""Pydantic models for OmoiOS API types."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, field_validator


class BindingKind(str, Enum):
    """Credential binding kinds."""

    BEARER_SECRET = "bearer_secret"
    USER_OAUTH = "user_oauth"
    GITHUB_APP = "github_app"


class VariableType(str, Enum):
    """Environment variable types."""

    STRING = "string"
    SECRET = "secret"
    JSON = "json"


class WebhookEvent(str, Enum):
    """Webhook event types."""

    SPEC_CREATED = "spec.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    SESSION_CREATED = "session.created"
    ARTIFACT_UPLOADED = "artifact.uploaded"


class Credential(BaseModel):
    """Credential resource."""

    id: str = Field(..., description="Unique identifier")
    workspace_id: str = Field(..., description="Workspace ID")
    kind: BindingKind = Field(..., description="Credential binding kind")
    name: str = Field(..., description="User-friendly name")
    created_at: datetime = Field(..., description="Creation timestamp")
    rotated_at: Optional[datetime] = Field(
        None, description="Last rotation timestamp"
    )


class CreateCredentialRequest(BaseModel):
    """Request to create a credential."""

    kind: BindingKind = Field(..., description="Credential binding kind")
    name: str = Field(..., description="User-friendly name")
    value: str = Field(..., description="Credential value (encrypted at rest)")
    workspace_id: Optional[str] = Field(
        None, description="Workspace ID (optional)"
    )


class EnvironmentVariable(BaseModel):
    """Environment variable definition."""

    type: VariableType = Field(..., description="Variable type")
    value: Union[str, Dict[str, Any]] = Field(..., description="Variable value")


class Environment(BaseModel):
    """Environment resource."""

    id: str = Field(..., description="Unique identifier")
    org_id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Environment name")
    description: Optional[str] = Field(None, description="Optional description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EnvironmentVersion(BaseModel):
    """Environment version (immutable snapshot)."""

    id: str = Field(..., description="Unique identifier")
    environment_id: str = Field(..., description="Parent environment ID")
    version_number: int = Field(..., description="Version number (1, 2, 3...)")
    variables: Dict[str, EnvironmentVariable] = Field(
        ..., description="Environment variables"
    )
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateEnvironmentRequest(BaseModel):
    """Request to create an environment."""

    name: str = Field(..., description="Environment name")
    description: Optional[str] = Field(None, description="Optional description")


class CreateEnvironmentVersionRequest(BaseModel):
    """Request to create an environment version."""

    variables: Dict[str, EnvironmentVariable] = Field(
        ..., description="Environment variables"
    )


class Artifact(BaseModel):
    """Artifact resource."""

    id: str = Field(..., description="Unique identifier")
    workspace_id: str = Field(..., description="Workspace ID")
    name: str = Field(..., description="Artifact name")
    storage_backend: str = Field(..., description="Storage backend (local, s3)")
    storage_path: str = Field(..., description="Storage path")
    checksum: str = Field(..., description="SHA-256 checksum")
    size_bytes: int = Field(..., description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME content type")
    artifact_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class WebhookSubscription(BaseModel):
    """Webhook subscription resource."""

    id: str = Field(..., description="Unique identifier")
    org_id: str = Field(..., description="Organization ID")
    url: str = Field(..., description="Webhook URL")
    events: list[WebhookEvent] = Field(..., description="Subscribed events")
    active: bool = Field(..., description="Whether subscription is active")
    created_at: datetime = Field(..., description="Creation timestamp")


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    id: str = Field(..., description="Unique identifier")
    subscription_id: str = Field(..., description="Parent subscription ID")
    event: WebhookEvent = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    status: str = Field(..., description="Delivery status")
    attempts: int = Field(..., description="Number of delivery attempts")
    next_retry_at: Optional[datetime] = Field(
        None, description="Next retry timestamp"
    )
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateWebhookRequest(BaseModel):
    """Request to create a webhook subscription."""

    url: str = Field(..., description="Webhook URL")
    events: list[WebhookEvent] = Field(..., description="Events to subscribe to")
    secret: str = Field(..., description="Secret for signature verification")


class WorkspaceSettings(BaseModel):
    """Workspace settings resource."""

    id: str = Field(..., description="Unique identifier")
    workspace_id: str = Field(..., description="Workspace ID")
    egress_allowlist: list[str] = Field(
        ..., description="Allowed egress hostnames"
    )
    max_artifact_size_mb: int = Field(
        ..., description="Maximum artifact size in MB"
    )
    allowed_binding_kinds: list[BindingKind] = Field(
        ..., description="Allowed credential binding kinds"
    )
