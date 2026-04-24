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
)
from omoios.client import OmoiOSClient
from omoios.mock_client import MockOmoiOSClient
from omoios.exceptions import OmoiOSError, AuthError, NotFoundError, ValidationError

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
    # Clients
    "OmoiOSClient",
    "MockOmoiOSClient",
    # Exceptions
    "OmoiOSError",
    "AuthError",
    "NotFoundError",
    "ValidationError",
]
