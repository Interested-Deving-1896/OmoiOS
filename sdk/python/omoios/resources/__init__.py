"""Resource modules for OmoiOS API."""

from omoios.resources.artifacts import ArtifactsResource
from omoios.resources.credentials import CredentialsResource
from omoios.resources.environments import EnvironmentsResource
from omoios.resources.webhooks import WebhooksResource
from omoios.resources.workspaces import WorkspacesResource

__all__ = [
    "ArtifactsResource",
    "CredentialsResource",
    "EnvironmentsResource",
    "WebhooksResource",
    "WorkspacesResource",
]
