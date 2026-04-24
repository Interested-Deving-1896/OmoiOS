"""OmoiOS SDK - Python client for the OmoiOS Agent Workspace Platform."""

from omoios.types import (
    BindingKind,
    Credential,
    CreateCredentialRequest,
    VariableType,
    EnvironmentVariable,
    Environment,
    EnvironmentVersion,
    CreateEnvironmentRequest,
    CreateEnvironmentVersionRequest,
    Artifact,
    WebhookEvent,
    WebhookSubscription,
    WebhookDelivery,
    CreateWebhookRequest,
    WorkspaceSettings,
    UpdateWorkspaceSettingsRequest,
)
from omoios.client import OmoiOSClient, AsyncOmoiOSClient
from omoios.mock_client import MockOmoiOSClient
from omoios.exceptions import OmoiOSError, AuthError, NotFoundError, ValidationError, ServerError

__version__ = "0.1.0"
__all__ = [
    # Types
    "BindingKind",
    "Credential",
    "CreateCredentialRequest",
    "VariableType",
    "EnvironmentVariable",
    "Environment",
    "EnvironmentVersion",
    "CreateEnvironmentRequest",
    "CreateEnvironmentVersionRequest",
    "Artifact",
    "WebhookEvent",
    "WebhookSubscription",
    "WebhookDelivery",
    "CreateWebhookRequest",
    "WorkspaceSettings",
    "UpdateWorkspaceSettingsRequest",
    # Clients
    "OmoiOSClient",
    "AsyncOmoiOSClient",
    "MockOmoiOSClient",
    # Exceptions
    "OmoiOSError",
    "AuthError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
]
