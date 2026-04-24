"""Mock client for OmoiOS API - returns fixture data for development."""

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from omoios.client import OmoiOSClient
from omoios.exceptions import NotFoundError
from omoios.types import (
    Artifact,
    BindingKind,
    CreateCredentialRequest,
    CreateEnvironmentRequest,
    CreateEnvironmentVersionRequest,
    CreateWebhookRequest,
    Credential,
    Environment,
    EnvironmentVariable,
    EnvironmentVersion,
    VariableType,
    WebhookDelivery,
    WebhookEvent,
    WebhookSubscription,
    WorkspaceSettings,
)


class MockOmoiOSClient(OmoiOSClient):
    """Mock client that returns fixture data.

    Use this for development while the backend is being built.
    All methods return typed fixture data.
    """

    def __init__(self):
        """Initialize mock client with fixture data."""
        super().__init__(base_url="https://api.omoios.dev", api_key="mock-key")
        self._credentials: Dict[str, Credential] = {}
        self._environments: Dict[str, Environment] = {}
        self._environment_versions: Dict[str, List[EnvironmentVersion]] = {}
        self._artifacts: Dict[str, Artifact] = {}
        self._webhooks: Dict[str, WebhookSubscription] = {}
        self._webhook_deliveries: Dict[str, List[WebhookDelivery]] = {}
        self._workspace_settings: Dict[str, WorkspaceSettings] = {}

        # Initialize with fixture data
        self._init_fixtures()

    def _init_fixtures(self) -> None:
        """Initialize fixture data."""
        now = datetime.now()

        # Credentials
        cred = Credential(
            id="cred_1",
            workspace_id="ws_1",
            kind=BindingKind.BEARER_SECRET,
            name="test-api-key",
            config={},
            version=1,
            created_at=now,
            rotated_at=None,
        )
        self._credentials[cred.id] = cred

        # Environments
        env = Environment(
            id="env_1",
            org_id="org_1",
            name="staging",
            description="Staging environment",
            created_at=now,
            updated_at=now,
        )
        self._environments[env.id] = env

        # Environment version
        version = EnvironmentVersion(
            id="ver_1",
            environment_id=env.id,
            version_number=1,
            variables={
                "DB_URL": EnvironmentVariable(
                    type=VariableType.STRING, value="postgres://localhost:5432/staging"
                ),
                "API_KEY": EnvironmentVariable(type=VariableType.SECRET, value="***"),
            },
            created_at=now,
        )
        self._environment_versions[env.id] = [version]

        # Artifacts
        artifact = Artifact(
            id="art_1",
            workspace_id="ws_1",
            name="test-file.txt",
            storage_backend="local",
            storage_path="/artifacts/art_1",
            checksum="sha256:" + "a" * 64,
            size_bytes=1024,
            content_type="text/plain",
            artifact_metadata={"source": "test"},
            created_at=now,
            updated_at=now,
        )
        self._artifacts[artifact.id] = artifact

        # Webhooks
        webhook = WebhookSubscription(
            id="wh_1",
            org_id="org_1",
            url="https://example.com/webhook",
            events=[WebhookEvent.TASK_COMPLETED, WebhookEvent.ARTIFACT_UPLOADED],
            active=True,
            created_at=now,
        )
        self._webhooks[webhook.id] = webhook

        # Webhook deliveries
        delivery = WebhookDelivery(
            id="wd_1",
            subscription_id=webhook.id,
            event=WebhookEvent.TASK_COMPLETED,
            payload={"task_id": "task_1", "status": "success"},
            status="delivered",
            attempts=1,
            next_retry_at=None,
            created_at=now,
        )
        self._webhook_deliveries[webhook.id] = [delivery]

        # Workspace settings
        settings = WorkspaceSettings(
            id="ws_settings_1",
            workspace_id="ws_1",
            egress_allowlist=["api.github.com", "pypi.org"],
            max_artifact_size_mb=100,
            allowed_binding_kinds=[
                BindingKind.BEARER_SECRET,
                BindingKind.USER_OAUTH,
            ],
        )
        self._workspace_settings[settings.workspace_id] = settings

    # Credentials

    def list_credentials(self, workspace_id: Optional[str] = None) -> List[Credential]:
        """List credentials."""
        creds = list(self._credentials.values())
        if workspace_id:
            creds = [c for c in creds if c.workspace_id == workspace_id]
        return creds

    def get_credential(self, credential_id: str) -> Credential:
        """Get a credential by ID."""
        if credential_id not in self._credentials:
            raise NotFoundError(f"Credential not found: {credential_id}")
        return self._credentials[credential_id]

    def create_credential(self, request: CreateCredentialRequest) -> Credential:
        """Create a new credential."""
        now = datetime.now()
        cred = Credential(
            id=f"cred_{uuid.uuid4().hex[:8]}",
            workspace_id=request.workspace_id,
            kind=request.kind,
            name=request.name,
            config=request.config or {},
            version=1,
            created_at=now,
            rotated_at=None,
        )
        self._credentials[cred.id] = cred
        return cred

    def delete_credential(self, credential_id: str) -> None:
        """Delete a credential."""
        if credential_id not in self._credentials:
            raise NotFoundError(f"Credential not found: {credential_id}")
        del self._credentials[credential_id]

    # Environments

    def list_environments(self) -> List[Environment]:
        """List all environments."""
        return list(self._environments.values())

    def get_environment(
        self, environment_id: str
    ) -> Dict[str, Union[Environment, Optional[EnvironmentVersion]]]:
        """Get environment with latest version."""
        if environment_id not in self._environments:
            raise NotFoundError(f"Environment not found: {environment_id}")
        env = self._environments[environment_id]
        versions = self._environment_versions.get(environment_id, [])
        latest = versions[-1] if versions else None
        return {"environment": env, "latestVersion": latest}

    def create_environment(self, request: CreateEnvironmentRequest) -> Environment:
        """Create a new environment."""
        now = datetime.now()
        env = Environment(
            id=f"env_{uuid.uuid4().hex[:8]}",
            org_id=request.org_id,
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
        )
        self._environments[env.id] = env
        self._environment_versions[env.id] = []
        return env

    def create_environment_version(
        self, environment_id: str, request: CreateEnvironmentVersionRequest
    ) -> EnvironmentVersion:
        """Create a new environment version."""
        if environment_id not in self._environments:
            raise NotFoundError(f"Environment not found: {environment_id}")

        versions = self._environment_versions.get(environment_id, [])
        version_number = len(versions) + 1

        version = EnvironmentVersion(
            id=f"ver_{uuid.uuid4().hex[:8]}",
            environment_id=environment_id,
            version_number=version_number,
            variables=request.variables,
            created_at=datetime.now(),
        )
        versions.append(version)
        self._environment_versions[environment_id] = versions
        return version

    # Artifacts

    def upload_artifact(
        self, file_content: bytes, workspace_id: Optional[str] = None
    ) -> Artifact:
        """Upload an artifact."""
        now = datetime.now()
        artifact_id = f"art_{uuid.uuid4().hex[:8]}"
        checksum = hashlib.sha256(file_content).hexdigest()

        artifact = Artifact(
            id=artifact_id,
            workspace_id=workspace_id or "ws_1",
            name="uploaded-file.bin",
            storage_backend="local",
            storage_path=f"/artifacts/{artifact_id}",
            checksum=f"sha256:{checksum}",
            size_bytes=len(file_content),
            content_type="application/octet-stream",
            artifact_metadata=None,
            created_at=now,
            updated_at=now,
        )
        self._artifacts[artifact.id] = artifact
        return artifact

    def list_artifacts(self, workspace_id: Optional[str] = None) -> List[Artifact]:
        """List artifacts."""
        artifacts = list(self._artifacts.values())
        if workspace_id:
            artifacts = [a for a in artifacts if a.workspace_id == workspace_id]
        return artifacts

    def get_artifact(self, artifact_id: str) -> Artifact:
        """Get an artifact by ID."""
        if artifact_id not in self._artifacts:
            raise NotFoundError(f"Artifact not found: {artifact_id}")
        return self._artifacts[artifact_id]

    def download_artifact(self, artifact_id: str) -> bytes:
        """Download artifact content."""
        if artifact_id not in self._artifacts:
            raise NotFoundError(f"Artifact not found: {artifact_id}")
        # Return mock content
        return b"mock artifact content"

    def delete_artifact(self, artifact_id: str) -> None:
        """Delete an artifact."""
        if artifact_id not in self._artifacts:
            raise NotFoundError(f"Artifact not found: {artifact_id}")
        del self._artifacts[artifact_id]

    # Webhooks

    def list_webhooks(self) -> List[WebhookSubscription]:
        """List webhook subscriptions."""
        return list(self._webhooks.values())

    def create_webhook(self, request: CreateWebhookRequest) -> WebhookSubscription:
        """Create a webhook subscription."""
        now = datetime.now()
        webhook = WebhookSubscription(
            id=f"wh_{uuid.uuid4().hex[:8]}",
            org_id="org_1",
            url=request.url,
            events=request.events,
            active=True,
            created_at=now,
        )
        self._webhooks[webhook.id] = webhook
        self._webhook_deliveries[webhook.id] = []
        return webhook

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook subscription."""
        if webhook_id not in self._webhooks:
            raise NotFoundError(f"Webhook not found: {webhook_id}")
        del self._webhooks[webhook_id]
        del self._webhook_deliveries[webhook_id]

    def list_webhook_deliveries(self, subscription_id: str) -> List[WebhookDelivery]:
        """List webhook deliveries for a subscription."""
        if subscription_id not in self._webhooks:
            raise NotFoundError(f"Webhook subscription not found: {subscription_id}")
        return self._webhook_deliveries.get(subscription_id, [])

    # Workspace Settings

    def get_workspace_settings(self, workspace_id: str) -> WorkspaceSettings:
        """Get workspace settings."""
        if workspace_id not in self._workspace_settings:
            raise NotFoundError(f"Workspace not found: {workspace_id}")
        return self._workspace_settings[workspace_id]
