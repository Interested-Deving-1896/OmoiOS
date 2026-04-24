"""Workspace isolation API routes."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, Field

from omoi_os.config import is_feature_enabled
from omoi_os.logging import get_logger
from omoi_os.models.workspace_settings import WorkspaceSettings
from omoi_os.services.workspace_isolation_service import (
    CrossWorkspaceCredentialError,
    WorkspaceIsolationError,
    WorkspaceIsolationFeatureDisabledError,
    WorkspaceIsolationService,
    get_workspace_isolation_service,
)

logger = get_logger(__name__)
router = APIRouter()


def check_feature_flag() -> None:
    """Check if sessions API v1 feature is enabled."""
    if not is_feature_enabled("sessions_api_v1"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace isolation API not available",
        )


def get_service() -> WorkspaceIsolationService:
    """Get workspace isolation service instance."""
    return get_workspace_isolation_service()


class WorkspaceSettingsRequest(BaseModel):
    """Request model for creating or updating workspace settings."""

    workspace_id: UUID = Field(..., description="Workspace ID")
    environment_id: Optional[UUID] = Field(None, description="Environment to inject")
    egress_proxy_config: dict = Field(
        default_factory=dict,
        description="Workspace-scoped egress proxy configuration",
    )


class CredentialAccessRequest(BaseModel):
    """Request model for validating credential access."""

    workspace_id: UUID = Field(..., description="Workspace ID")
    credential_binding_ids: list[UUID] = Field(
        default_factory=list,
        description="Credential binding IDs requested by the session",
    )


class WorkspaceSettingsResponse(BaseModel):
    """Response model for workspace settings."""

    workspace_id: UUID
    storage_path: str
    environment_id: Optional[UUID]
    egress_proxy_config: dict
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, settings: WorkspaceSettings) -> "WorkspaceSettingsResponse":
        return cls(
            workspace_id=settings.workspace_id,
            storage_path=settings.storage_path,
            environment_id=settings.environment_id,
            egress_proxy_config=settings.egress_proxy_config or {},
            created_at=settings.created_at.isoformat(),
            updated_at=settings.updated_at.isoformat(),
        )


class WorkspaceRuntimeResponse(BaseModel):
    """Response model for non-secret workspace runtime isolation data."""

    workspace_id: UUID
    storage_path: str
    environment_variable_names: list[str]
    credential_variable_names: list[str]
    egress_variable_names: list[str]


@router.post("/settings", status_code=status.HTTP_201_CREATED)
async def upsert_workspace_settings(
    request: WorkspaceSettingsRequest = Body(...),
) -> WorkspaceSettingsResponse:
    """Create or update workspace isolation settings."""
    check_feature_flag()
    try:
        settings = get_service().upsert_settings(
            workspace_id=request.workspace_id,
            environment_id=request.environment_id,
            egress_proxy_config=request.egress_proxy_config,
        )
        return WorkspaceSettingsResponse.from_model(settings)
    except WorkspaceIsolationFeatureDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Failed to upsert workspace settings", error=str(exc), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to upsert workspace settings",
        )


@router.get("/{workspace_id}/settings")
async def get_workspace_settings(workspace_id: UUID) -> WorkspaceSettingsResponse:
    """Get workspace settings, creating defaults if absent."""
    check_feature_flag()
    try:
        settings = get_service().get_or_create_settings(workspace_id=workspace_id)
        return WorkspaceSettingsResponse.from_model(settings)
    except WorkspaceIsolationFeatureDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to get workspace settings", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workspace settings",
        )


@router.post("/credentials/validate")
async def validate_credential_access(
    request: CredentialAccessRequest = Body(...),
) -> dict:
    """Validate that requested credentials are scoped to a workspace."""
    check_feature_flag()
    try:
        bindings = get_service().validate_credential_access(
            workspace_id=request.workspace_id,
            credential_binding_ids=request.credential_binding_ids,
        )
        return {"valid": True, "credential_count": len(bindings)}
    except CrossWorkspaceCredentialError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except WorkspaceIsolationFeatureDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{workspace_id}/runtime")
async def get_workspace_runtime(
    workspace_id: UUID,
    environment_id: Optional[UUID] = Query(None, description="Optional environment ID"),
) -> WorkspaceRuntimeResponse:
    """Preview non-secret runtime isolation keys for a workspace."""
    check_feature_flag()
    try:
        context = get_service().prepare_session_isolation(
            workspace_id=workspace_id,
            environment_id=environment_id,
        )
        return WorkspaceRuntimeResponse(
            workspace_id=workspace_id,
            storage_path=context.storage_path,
            environment_variable_names=sorted(context.environment_variables.keys()),
            credential_variable_names=sorted(
                context.credential_environment_variables.keys()
            ),
            egress_variable_names=sorted(context.egress_environment_variables.keys()),
        )
    except WorkspaceIsolationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
