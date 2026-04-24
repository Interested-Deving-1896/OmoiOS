"""Tests for mock client."""

import pytest
from datetime import datetime

from omoios import MockOmoiOSClient
from omoios.types import (
    BindingKind,
    CreateCredentialRequest,
    CreateEnvironmentRequest,
    CreateEnvironmentVersionRequest,
    CreateWebhookRequest,
    EnvironmentVariable,
    VariableType,
    WebhookEvent,
)
from omoios.exceptions import NotFoundError


class TestMockClientCredentials:
    """Test credential operations."""

    def test_list_credentials_returns_list(self):
        """Test list_credentials returns a list of Credentials."""
        client = MockOmoiOSClient()
        creds = client.list_credentials()

        assert isinstance(creds, list)
        assert len(creds) > 0
        assert creds[0].kind == BindingKind.BEARER_SECRET
        assert creds[0].name == "test-api-key"

    def test_list_credentials_filters_by_workspace(self):
        """Test list_credentials filters by workspace_id."""
        client = MockOmoiOSClient()
        creds = client.list_credentials(workspace_id="ws_1")

        assert isinstance(creds, list)
        assert all(c.workspace_id == "ws_1" for c in creds)

    def test_get_credential_returns_credential(self):
        """Test get_credential returns a Credential."""
        client = MockOmoiOSClient()
        cred = client.get_credential("cred_1")

        assert cred.id == "cred_1"
        assert cred.kind == BindingKind.BEARER_SECRET
        assert isinstance(cred.created_at, datetime)

    def test_get_credential_raises_not_found(self):
        """Test get_credential raises NotFoundError for invalid ID."""
        client = MockOmoiOSClient()

        with pytest.raises(NotFoundError):
            client.get_credential("invalid_id")

    def test_create_credential_returns_credential(self):
        """Test create_credential returns a new Credential."""
        client = MockOmoiOSClient()
        request = CreateCredentialRequest(
            kind=BindingKind.USER_OAUTH,
            name="oauth-token",
            value="secret-value",
            workspace_id="ws_1",
        )
        cred = client.create_credential(request)

        assert cred.kind == BindingKind.USER_OAUTH
        assert cred.name == "oauth-token"
        assert cred.workspace_id == "ws_1"
        assert cred.id.startswith("cred_")
        assert isinstance(cred.created_at, datetime)

    def test_delete_credential_removes_credential(self):
        """Test delete_credential removes the credential."""
        client = MockOmoiOSClient()

        # First create a credential
        request = CreateCredentialRequest(
            kind=BindingKind.BEARER_SECRET,
            name="to-delete",
            value="secret",
        )
        cred = client.create_credential(request)

        # Delete it
        client.delete_credential(cred.id)

        # Verify it's gone
        with pytest.raises(NotFoundError):
            client.get_credential(cred.id)


class TestMockClientEnvironments:
    """Test environment operations."""

    def test_list_environments_returns_list(self):
        """Test list_environments returns a list of Environments."""
        client = MockOmoiOSClient()
        envs = client.list_environments()

        assert isinstance(envs, list)
        assert len(envs) > 0
        assert envs[0].name == "staging"

    def test_get_environment_returns_dict(self):
        """Test get_environment returns environment with latest version."""
        client = MockOmoiOSClient()
        result = client.get_environment("env_1")

        assert "environment" in result
        assert "latestVersion" in result
        assert result["environment"].id == "env_1"
        assert result["latestVersion"] is not None

    def test_get_environment_raises_not_found(self):
        """Test get_environment raises NotFoundError for invalid ID."""
        client = MockOmoiOSClient()

        with pytest.raises(NotFoundError):
            client.get_environment("invalid_id")

    def test_create_environment_returns_environment(self):
        """Test create_environment returns a new Environment."""
        client = MockOmoiOSClient()
        request = CreateEnvironmentRequest(
            name="production",
            description="Production environment",
        )
        env = client.create_environment(request)

        assert env.name == "production"
        assert env.description == "Production environment"
        assert env.id.startswith("env_")
        assert isinstance(env.created_at, datetime)

    def test_create_environment_version_returns_version(self):
        """Test create_environment_version returns a new version."""
        client = MockOmoiOSClient()

        # Create environment first
        env_request = CreateEnvironmentRequest(name="test-env")
        env = client.create_environment(env_request)

        # Create version
        version_request = CreateEnvironmentVersionRequest(
            variables={
                "VAR1": EnvironmentVariable(type=VariableType.STRING, value="value1"),
                "SECRET": EnvironmentVariable(type=VariableType.SECRET, value="***"),
            }
        )
        version = client.create_environment_version(env.id, version_request)

        assert version.environment_id == env.id
        assert version.version_number == 1
        assert "VAR1" in version.variables
        assert version.variables["VAR1"].type == VariableType.STRING

    def test_create_multiple_versions_increments_numbers(self):
        """Test creating multiple versions increments version numbers."""
        client = MockOmoiOSClient()

        # Create environment
        env = client.create_environment(CreateEnvironmentRequest(name="versioned-env"))

        # Create two versions
        v1 = client.create_environment_version(
            env.id,
            CreateEnvironmentVersionRequest(variables={"V": EnvironmentVariable(type=VariableType.STRING, value="1")})
        )
        v2 = client.create_environment_version(
            env.id,
            CreateEnvironmentVersionRequest(variables={"V": EnvironmentVariable(type=VariableType.STRING, value="2")})
        )

        assert v1.version_number == 1
        assert v2.version_number == 2


class TestMockClientArtifacts:
    """Test artifact operations."""

    def test_upload_artifact_returns_artifact(self):
        """Test upload_artifact returns an Artifact."""
        client = MockOmoiOSClient()
        content = b"test file content"
        artifact = client.upload_artifact(content, workspace_id="ws_1")

        assert artifact.workspace_id == "ws_1"
        assert artifact.size_bytes == len(content)
        assert artifact.checksum.startswith("sha256:")
        assert artifact.id.startswith("art_")

    def test_list_artifacts_returns_list(self):
        """Test list_artifacts returns a list of Artifacts."""
        client = MockOmoiOSClient()
        artifacts = client.list_artifacts()

        assert isinstance(artifacts, list)
        assert len(artifacts) > 0

    def test_list_artifacts_filters_by_workspace(self):
        """Test list_artifacts filters by workspace_id."""
        client = MockOmoiOSClient()
        artifacts = client.list_artifacts(workspace_id="ws_1")

        assert all(a.workspace_id == "ws_1" for a in artifacts)

    def test_get_artifact_returns_artifact(self):
        """Test get_artifact returns an Artifact."""
        client = MockOmoiOSClient()
        artifact = client.get_artifact("art_1")

        assert artifact.id == "art_1"
        assert artifact.name == "test-file.txt"

    def test_get_artifact_raises_not_found(self):
        """Test get_artifact raises NotFoundError for invalid ID."""
        client = MockOmoiOSClient()

        with pytest.raises(NotFoundError):
            client.get_artifact("invalid_id")

    def test_download_artifact_returns_bytes(self):
        """Test download_artifact returns bytes."""
        client = MockOmoiOSClient()
        content = client.download_artifact("art_1")

        assert isinstance(content, bytes)

    def test_delete_artifact_removes_artifact(self):
        """Test delete_artifact removes the artifact."""
        client = MockOmoiOSClient()

        # Upload an artifact
        artifact = client.upload_artifact(b"content", workspace_id="ws_1")

        # Delete it
        client.delete_artifact(artifact.id)

        # Verify it's gone
        with pytest.raises(NotFoundError):
            client.get_artifact(artifact.id)


class TestMockClientWebhooks:
    """Test webhook operations."""

    def test_list_webhooks_returns_list(self):
        """Test list_webhooks returns a list of WebhookSubscriptions."""
        client = MockOmoiOSClient()
        webhooks = client.list_webhooks()

        assert isinstance(webhooks, list)
        assert len(webhooks) > 0
        assert webhooks[0].url == "https://example.com/webhook"

    def test_create_webhook_returns_subscription(self):
        """Test create_webhook returns a new WebhookSubscription."""
        client = MockOmoiOSClient()
        request = CreateWebhookRequest(
            url="https://myapp.com/webhook",
            events=[WebhookEvent.SPEC_CREATED, WebhookEvent.TASK_STARTED],
            secret="webhook-secret",
        )
        webhook = client.create_webhook(request)

        assert webhook.url == "https://myapp.com/webhook"
        assert WebhookEvent.SPEC_CREATED in webhook.events
        assert webhook.active is True
        assert webhook.id.startswith("wh_")

    def test_delete_webhook_removes_webhook(self):
        """Test delete_webhook removes the webhook."""
        client = MockOmoiOSClient()

        # Create a webhook
        request = CreateWebhookRequest(
            url="https://temp.com/webhook",
            events=[WebhookEvent.TASK_COMPLETED],
            secret="secret",
        )
        webhook = client.create_webhook(request)

        # Delete it
        client.delete_webhook(webhook.id)

        # Verify it's gone
        webhooks = client.list_webhooks()
        assert webhook.id not in [w.id for w in webhooks]

    def test_list_webhook_deliveries_returns_list(self):
        """Test list_webhook_deliveries returns a list of WebhookDeliveries."""
        client = MockOmoiOSClient()
        deliveries = client.list_webhook_deliveries("wh_1")

        assert isinstance(deliveries, list)
        assert len(deliveries) > 0
        assert deliveries[0].subscription_id == "wh_1"

    def test_list_webhook_deliveries_raises_not_found(self):
        """Test list_webhook_deliveries raises NotFoundError for invalid ID."""
        client = MockOmoiOSClient()

        with pytest.raises(NotFoundError):
            client.list_webhook_deliveries("invalid_id")


class TestMockClientWorkspaceSettings:
    """Test workspace settings operations."""

    def test_get_workspace_settings_returns_settings(self):
        """Test get_workspace_settings returns WorkspaceSettings."""
        client = MockOmoiOSClient()
        settings = client.get_workspace_settings("ws_1")

        assert settings.workspace_id == "ws_1"
        assert settings.max_artifact_size_mb == 100
        assert "api.github.com" in settings.egress_allowlist
        assert BindingKind.BEARER_SECRET in settings.allowed_binding_kinds

    def test_get_workspace_settings_raises_not_found(self):
        """Test get_workspace_settings raises NotFoundError for invalid ID."""
        client = MockOmoiOSClient()

        with pytest.raises(NotFoundError):
            client.get_workspace_settings("invalid_id")
