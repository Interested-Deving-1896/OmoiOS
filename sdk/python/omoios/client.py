"""Async HTTP client for OmoiOS API.

Provides AsyncOmoiOSClient for making async HTTP requests to the OmoiOS API,
along with the legacy OmoiOSClient abstract base class for backwards compatibility.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

import httpx

from omoios.exceptions import AuthError, NotFoundError, ServerError, ValidationError
from omoios.resources import (
    ArtifactsResource,
    CredentialsResource,
    EnvironmentsResource,
    WebhooksResource,
    WorkspacesResource,
)
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

    @abstractmethod
    def list_credentials(self, workspace_id: Optional[str] = None) -> List[Credential]:
        """List credentials."""
        pass

    @abstractmethod
    def get_credential(self, credential_id: str) -> Credential:
        """Get a credential by ID."""
        pass

    @abstractmethod
    def create_credential(self, request: CreateCredentialRequest) -> Credential:
        """Create a new credential."""
        pass

    @abstractmethod
    def delete_credential(self, credential_id: str) -> None:
        """Delete a credential."""
        pass

    @abstractmethod
    def list_environments(self) -> List[Environment]:
        """List all environments."""
        pass

    @abstractmethod
    def get_environment(
        self, environment_id: str
    ) -> Dict[str, Union[Environment, Optional[EnvironmentVersion]]]:
        """Get environment with latest version."""
        pass

    @abstractmethod
    def create_environment(self, request: CreateEnvironmentRequest) -> Environment:
        """Create a new environment."""
        pass

    @abstractmethod
    def create_environment_version(
        self, environment_id: str, request: CreateEnvironmentVersionRequest
    ) -> EnvironmentVersion:
        """Create a new environment version."""
        pass

    @abstractmethod
    def upload_artifact(
        self, file_content: bytes, workspace_id: Optional[str] = None
    ) -> Artifact:
        """Upload an artifact."""
        pass

    @abstractmethod
    def list_artifacts(self, workspace_id: Optional[str] = None) -> List[Artifact]:
        """List artifacts."""
        pass

    @abstractmethod
    def get_artifact(self, artifact_id: str) -> Artifact:
        """Get an artifact by ID."""
        pass

    @abstractmethod
    def download_artifact(self, artifact_id: str) -> bytes:
        """Download artifact content."""
        pass

    @abstractmethod
    def delete_artifact(self, artifact_id: str) -> None:
        """Delete an artifact."""
        pass

    @abstractmethod
    def list_webhooks(self) -> List[WebhookSubscription]:
        """List webhook subscriptions."""
        pass

    @abstractmethod
    def create_webhook(self, request: CreateWebhookRequest) -> WebhookSubscription:
        """Create a webhook subscription."""
        pass

    @abstractmethod
    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook subscription."""
        pass

    @abstractmethod
    def list_webhook_deliveries(self, subscription_id: str) -> List[WebhookDelivery]:
        """List webhook deliveries for a subscription."""
        pass

    @abstractmethod
    def get_workspace_settings(self, workspace_id: str) -> WorkspaceSettings:
        """Get workspace settings."""
        pass


class AsyncOmoiOSClient:
    """Async HTTP client for the OmoiOS Agent Workspace Platform.

    Uses httpx.AsyncClient for async HTTP requests. Supports both API key
    and JWT token authentication.

    Example:
        >>> async with AsyncOmoiOSClient("https://api.omoios.dev", api_key="key") as client:
        ...     creds = await client.credentials.list(workspace_id="ws-1")
        ...     print(creds[0].name)
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        jwt_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """Initialize the async client.

        Args:
            base_url: API base URL (e.g., "https://api.omoios.dev")
            api_key: API key for authentication (X-API-Key header)
            jwt_token: JWT token for authentication (Authorization: Bearer header)
            timeout: HTTP request timeout in seconds (default: 30.0)

        Raises:
            ValueError: If neither api_key nor jwt_token is provided
        """
        if not api_key and not jwt_token:
            raise ValueError("Either api_key or jwt_token must be provided")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.jwt_token = jwt_token
        self._http = httpx.AsyncClient(timeout=timeout)

        self.credentials = CredentialsResource(self)
        self.environments = EnvironmentsResource(self)
        self.artifacts = ArtifactsResource(self)
        self.webhooks = WebhooksResource(self)
        self.workspaces = WorkspacesResource(self)

    def _headers(self) -> Dict[str, str]:
        """Build request headers with authentication.

        Returns:
            Dict of HTTP headers
        """
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def _handle_errors(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to SDK exceptions.

        Args:
            response: httpx Response object

        Raises:
            AuthError: For 401 responses
            NotFoundError: For 404 responses
            ValidationError: For 400/422 responses
            ServerError: For 5xx responses
        """
        if response.status_code == 401:
            raise AuthError("Authentication failed")
        elif response.status_code == 404:
            detail = "Resource not found"
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise NotFoundError(detail)
        elif response.status_code in (400, 422):
            detail = "Validation failed"
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise ValidationError(detail)
        elif response.status_code >= 500:
            detail = "Server error"
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise ServerError(detail)

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an authenticated HTTP request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., "/api/v1/credentials")
            **kwargs: Additional arguments passed to httpx

        Returns:
            httpx Response object

        Raises:
            AuthError, NotFoundError, ValidationError, ServerError
        """
        url = f"{self.base_url}{path}"
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        response = await self._http.request(method, url, headers=headers, **kwargs)
        self._handle_errors(response)
        return response

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncOmoiOSClient":
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager, closing the client."""
        await self.close()
