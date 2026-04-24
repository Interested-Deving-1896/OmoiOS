"""Abstract base client for OmoiOS API."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from omoios.types import (
    Artifact,
    BindingKind,
    CreateCredentialRequest,
    CreateEnvironmentRequest,
    CreateEnvironmentVersionRequest,
    CreateWebhookRequest,
    Credential,
    Environment,
    EnvironmentVersion,
    WebhookDelivery,
    WebhookSubscription,
    WorkspaceSettings,
)


class OmoiOSClient(ABC):
    """Abstract base class for OmoiOS API clients.

    Implementations must provide concrete methods for all API operations.
    This base class defines the interface for both real and mock clients.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """Initialize the client.

        Args:
            base_url: API base URL
            api_key: Optional API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key

    # Credentials

    @abstractmethod
    def list_credentials(self, workspace_id: Optional[str] = None) -> List[Credential]:
        """List credentials.

        Args:
            workspace_id: Optional workspace ID to filter by

        Returns:
            List of credentials
        """
        pass

    @abstractmethod
    def get_credential(self, credential_id: str) -> Credential:
        """Get a credential by ID.

        Args:
            credential_id: Credential ID

        Returns:
            Credential object

        Raises:
            NotFoundError: If credential doesn't exist
        """
        pass

    @abstractmethod
    def create_credential(self, request: CreateCredentialRequest) -> Credential:
        """Create a new credential.

        Args:
            request: Create credential request

        Returns:
            Created credential
        """
        pass

    @abstractmethod
    def delete_credential(self, credential_id: str) -> None:
        """Delete a credential.

        Args:
            credential_id: Credential ID to delete

        Raises:
            NotFoundError: If credential doesn't exist
        """
        pass

    # Environments

    @abstractmethod
    def list_environments(self) -> List[Environment]:
        """List all environments.

        Returns:
            List of environments
        """
        pass

    @abstractmethod
    def get_environment(
        self, environment_id: str
    ) -> Dict[str, Union[Environment, Optional[EnvironmentVersion]]]:
        """Get environment with latest version.

        Args:
            environment_id: Environment ID

        Returns:
            Dict with 'environment' and 'latestVersion' keys

        Raises:
            NotFoundError: If environment doesn't exist
        """
        pass

    @abstractmethod
    def create_environment(self, request: CreateEnvironmentRequest) -> Environment:
        """Create a new environment.

        Args:
            request: Create environment request

        Returns:
            Created environment
        """
        pass

    @abstractmethod
    def create_environment_version(
        self, environment_id: str, request: CreateEnvironmentVersionRequest
    ) -> EnvironmentVersion:
        """Create a new environment version.

        Args:
            environment_id: Environment ID
            request: Create version request

        Returns:
            Created environment version

        Raises:
            NotFoundError: If environment doesn't exist
        """
        pass

    # Artifacts

    @abstractmethod
    def upload_artifact(
        self, file_content: bytes, workspace_id: Optional[str] = None
    ) -> Artifact:
        """Upload an artifact.

        Args:
            file_content: Raw file bytes
            workspace_id: Optional workspace ID

        Returns:
            Created artifact
        """
        pass

    @abstractmethod
    def list_artifacts(self, workspace_id: Optional[str] = None) -> List[Artifact]:
        """List artifacts.

        Args:
            workspace_id: Optional workspace ID to filter by

        Returns:
            List of artifacts
        """
        pass

    @abstractmethod
    def get_artifact(self, artifact_id: str) -> Artifact:
        """Get an artifact by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact object

        Raises:
            NotFoundError: If artifact doesn't exist
        """
        pass

    @abstractmethod
    def download_artifact(self, artifact_id: str) -> bytes:
        """Download artifact content.

        Args:
            artifact_id: Artifact ID

        Returns:
            Raw file bytes

        Raises:
            NotFoundError: If artifact doesn't exist
        """
        pass

    @abstractmethod
    def delete_artifact(self, artifact_id: str) -> None:
        """Delete an artifact.

        Args:
            artifact_id: Artifact ID to delete

        Raises:
            NotFoundError: If artifact doesn't exist
        """
        pass

    # Webhooks

    @abstractmethod
    def list_webhooks(self) -> List[WebhookSubscription]:
        """List webhook subscriptions.

        Returns:
            List of webhook subscriptions
        """
        pass

    @abstractmethod
    def create_webhook(self, request: CreateWebhookRequest) -> WebhookSubscription:
        """Create a webhook subscription.

        Args:
            request: Create webhook request

        Returns:
            Created webhook subscription
        """
        pass

    @abstractmethod
    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook subscription.

        Args:
            webhook_id: Webhook ID to delete

        Raises:
            NotFoundError: If webhook doesn't exist
        """
        pass

    @abstractmethod
    def list_webhook_deliveries(self, subscription_id: str) -> List[WebhookDelivery]:
        """List webhook deliveries for a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            List of webhook deliveries

        Raises:
            NotFoundError: If subscription doesn't exist
        """
        pass

    # Workspace Settings

    @abstractmethod
    def get_workspace_settings(self, workspace_id: str) -> WorkspaceSettings:
        """Get workspace settings.

        Args:
            workspace_id: Workspace ID

        Returns:
            Workspace settings

        Raises:
            NotFoundError: If workspace doesn't exist
        """
        pass
