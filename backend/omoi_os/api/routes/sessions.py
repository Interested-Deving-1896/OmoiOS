"""Session API routes - aliases for task endpoints.

This module provides thin alias routes that map /api/v1/sessions/* to 
existing /api/v1/tasks/* handlers for backward compatibility.

All routes are deprecated and will be removed in v2.0.
Use /api/v1/tasks directly instead.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from omoi_os.api.dependencies import (
    get_current_user,
    get_db_service,
    get_task_queue,
    verify_task_access,
    verify_ticket_access,
    get_accessible_project_ids,
)
from omoi_os.api.routes import tasks as tasks_router
from omoi_os.config import is_feature_enabled
from omoi_os.models.user import User
from omoi_os.services.database import DatabaseService
from omoi_os.services.task_queue import TaskQueueService

router = APIRouter()

# Deprecation header value
DEPRECATION_HEADER = "Use /api/v1/tasks instead. Removed in v2.0."


# ============================================================================
# Request/Response Models (aliases for task models with session_id support)
# ============================================================================

class SessionCreate(BaseModel):
    """Request model for creating a session (alias for task)."""

    model_config = {"populate_by_name": True}

    ticket_id: str
    title: str
    description: str
    session_type: str = Field(default="implementation", alias="task_type")
    priority: str = "MEDIUM"
    phase_id: str = "PHASE_IMPLEMENTATION"
    dependencies: Optional[Dict[str, Any]] = None
    execution_config: Optional[tasks_router.ExecutionConfig] = None


class SessionUpdate(BaseModel):
    """Request model for updating a session (alias for task)."""

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


# ============================================================================
# Feature Flag Guard
# ============================================================================

def check_feature_flag() -> None:
    """Check if sessions API v1 feature is enabled.

    Raises:
        HTTPException: 404 if feature flag is disabled
    """
    if not is_feature_enabled("sessions_api_v1"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessions API not available",
        )


# ============================================================================
# Response Transformation Helpers
# ============================================================================

def _add_session_id_to_response(data: Any) -> Any:
    """Add session_id field alongside id field in response data.

    This ensures backward compatibility by providing both id and session_id
    fields in responses, where session_id is an alias for task_id.
    """
    if isinstance(data, dict):
        result = dict(data)
        if "id" in result and "session_id" not in result:
            result["session_id"] = result["id"]
        return result
    elif isinstance(data, list):
        return [_add_session_id_to_response(item) for item in data]
    return data


def _transform_request_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """Transform request body to convert session_id to task_id.

    This allows clients to use either session_id or task_id in requests.
    """
    result = dict(body)
    # Convert session_id to task_id if present
    if "session_id" in result and "task_id" not in result:
        result["task_id"] = result.pop("session_id")
    # Convert session_type to task_type if present
    if "session_type" in result and "task_type" not in result:
        result["task_type"] = result.pop("session_type")
    return result


def _set_deprecation_header(response: Response) -> None:
    """Set the X-Deprecated header on the response."""
    response.headers["X-Deprecated"] = DEPRECATION_HEADER


# ============================================================================
# API Endpoints (Aliases for Task Endpoints)
# ============================================================================

@router.get("", response_model=List[dict])
async def list_sessions(
    request: Request,
    response: Response,
    status: str | None = None,
    phase_id: str | None = None,
    has_sandbox: bool | None = None,
    ticket_id: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """List sessions (alias for list_tasks).

    Deprecated: Use GET /api/v1/tasks instead.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        status: Filter by status
        phase_id: Filter by phase ID
        has_sandbox: Filter to only sessions with sandbox
        ticket_id: Filter by ticket ID
        limit: Maximum number of sessions to return
        current_user: Authenticated user
        db: Database service

    Returns:
        List of sessions with both id and session_id fields
    """
    check_feature_flag()
    _set_deprecation_header(response)

    # Call the tasks handler directly
    result = await tasks_router.list_tasks(
        status=status,
        phase_id=phase_id,
        has_sandbox=has_sandbox,
        ticket_id=ticket_id,
        limit=limit,
        current_user=current_user,
        db=db,
    )

    # Add session_id to each item
    return _add_session_id_to_response(result)


@router.get("/{session_id}", response_model=dict)
async def get_session(
    request: Request,
    response: Response,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """Get session by ID (alias for get_task).

    Deprecated: Use GET /api/v1/tasks/{id} instead.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        session_id: Session UUID (maps to task_id)
        current_user: Authenticated user
        db: Database service

    Returns:
        Session data with both id and session_id fields
    """
    check_feature_flag()
    _set_deprecation_header(response)

    # Call the tasks handler directly
    result = await tasks_router.get_task(
        task_id=session_id,
        current_user=current_user,
        db=db,
    )

    # Add session_id to response
    return _add_session_id_to_response(result)


@router.post("", response_model=dict, status_code=201)
async def create_session(
    request: Request,
    response: Response,
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
    queue: TaskQueueService = Depends(get_task_queue),
):
    """Create a new session (alias for create_task).

    Deprecated: Use POST /api/v1/tasks instead.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        session_data: Session creation data
        current_user: Authenticated user
        db: Database service
        queue: Task queue service

    Returns:
        Created session with both id and session_id fields
    """
    check_feature_flag()
    _set_deprecation_header(response)

    # Convert session data to task data
    task_data = tasks_router.TaskCreate(
        ticket_id=session_data.ticket_id,
        title=session_data.title,
        description=session_data.description,
        task_type=session_data.session_type,
        priority=session_data.priority,
        phase_id=session_data.phase_id,
        dependencies=session_data.dependencies,
        execution_config=session_data.execution_config,
    )

    # Call the tasks handler directly
    result = await tasks_router.create_task(
        task_data=task_data,
        current_user=current_user,
        db=db,
        queue=queue,
    )

    # Add session_id to response
    return _add_session_id_to_response(result)


@router.delete("/{session_id}", response_model=dict)
async def delete_session(
    request: Request,
    response: Response,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
    queue: TaskQueueService = Depends(get_task_queue),
):
    """Cancel/delete a session (alias for cancel_task).

    Deprecated: Use POST /api/v1/tasks/{id}/cancel instead.

    Note: Since tasks cannot be truly deleted, this endpoint cancels the task.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        session_id: Session UUID (maps to task_id)
        current_user: Authenticated user
        db: Database service
        queue: Task queue service

    Returns:
        Cancellation result with session_id
    """
    check_feature_flag()
    _set_deprecation_header(response)

    # Verify user has access to this session/task
    await verify_task_access(session_id, current_user, db)

    # Cancel the task using the queue service
    success = queue.cancel_task(session_id, reason="cancelled_by_session_api")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or not cancellable",
        )

    return {
        "session_id": session_id,
        "task_id": session_id,
        "cancelled": True,
        "reason": "cancelled_by_session_api",
    }


@router.patch("/{session_id}", response_model=dict)
async def update_session(
    request: Request,
    response: Response,
    session_id: str,
    update: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db_service),
):
    """Update session by ID (alias for update_task).

    Deprecated: Use PATCH /api/v1/tasks/{id} instead.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        session_id: Session UUID (maps to task_id)
        update: Fields to update
        current_user: Authenticated user
        db: Database service

    Returns:
        Updated session data with both id and session_id fields
    """
    check_feature_flag()
    _set_deprecation_header(response)

    # Convert to TaskUpdateRequest
    task_update = tasks_router.TaskUpdateRequest(
        title=update.title,
        description=update.description,
        priority=update.priority,
        status=update.status,
    )

    # Call the tasks handler directly
    result = await tasks_router.update_task(
        task_id=session_id,
        update=task_update,
        current_user=current_user,
        db=db,
    )

    # Add session_id to response
    return _add_session_id_to_response(result)
