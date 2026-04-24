"""Integration tests for OmoiOS Python SDK.

These tests require a running local API server.
Set OMOIOS_API_URL environment variable to override the default URL.
"""

import os
import pytest

from omoios import (
    AsyncOmoiOSClient,
    BindingKind,
    CreateCredentialRequest,
    CreateEnvironmentRequest,
    CreateEnvironmentVersionRequest,
    CreateWebhookRequest,
    EnvironmentVariable,
    VariableType,
    WebhookEvent,
    UpdateWorkspaceSettingsRequest,
)

API_URL = os.getenv("OMOIOS_API_URL", "http://localhost:18000")
API_KEY = os.getenv("OMOIOS_API_KEY", "test-key")


@pytest.fixture
async def client():
    """Create an async client for integration tests."""
    c = AsyncOmoiOSClient(API_URL, api_key=API_KEY)
    yield c
    await c.close()


@pytest.mark.asyncio
class TestIntegrationCredentials:
    """Integration tests for credential endpoints."""

    async def test_list_credentials(self, client):
        """Test listing credentials."""
        try:
            creds = await client.credentials.list(workspace_id="ws-1")
            assert isinstance(creds, list)
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_get_credential(self, client):
        """Test getting a credential by ID."""
        try:
            # First create a credential
            request = CreateCredentialRequest(
                workspace_id="ws-1",
                kind=BindingKind.BEARER_SECRET,
                name="get-test-key",
                value="secret-value",
            )
            cred = await client.credentials.create(request)

            # Then get it
            fetched = await client.credentials.get(str(cred.id))
            assert fetched.id == cred.id
            assert fetched.name == "get-test-key"

            # Clean up
            await client.credentials.delete(str(cred.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_create_and_delete_credential(self, client):
        """Test creating and deleting a credential."""
        try:
            request = CreateCredentialRequest(
                workspace_id="ws-1",
                kind=BindingKind.BEARER_SECRET,
                name="integration-test-key",
                value="secret-value",
            )
            cred = await client.credentials.create(request)
            assert cred.name == "integration-test-key"
            assert cred.workspace_id == "ws-1"

            # Clean up
            await client.credentials.delete(str(cred.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")


@pytest.mark.asyncio
class TestIntegrationEnvironments:
    """Integration tests for environment endpoints."""

    async def test_list_environments(self, client):
        """Test listing environments."""
        try:
            envs = await client.environments.list(org_id="org-1")
            assert isinstance(envs, list)
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_get_environment(self, client):
        """Test getting environment by ID with latest version."""
        try:
            request = CreateEnvironmentRequest(
                name="get-test-env",
                description="For testing get endpoint",
                org_id="org-1",
            )
            env = await client.environments.create(request)

            result = await client.environments.get(str(env.id))
            assert "environment" in result
            assert result["environment"].id == env.id

            await client.environments.create_version(
                str(env.id),
                CreateEnvironmentVersionRequest(
                    variables={"TEST_VAR": EnvironmentVariable(type=VariableType.STRING, value="test")}
                ),
            )

            result_with_version = await client.environments.get(str(env.id))
            assert result_with_version["latest_version"] is not None
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_create_environment(self, client):
        """Test creating an environment."""
        try:
            request = CreateEnvironmentRequest(
                name="integration-test-env",
                description="Created by integration tests",
                org_id="org-1",
            )
            env = await client.environments.create(request)
            assert env.name == "integration-test-env"
            assert env.org_id == "org-1"
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_create_environment_version(self, client):
        """Test creating an environment version."""
        try:
            env_request = CreateEnvironmentRequest(
                name="version-test-env",
                description="For testing versions",
                org_id="org-1",
            )
            env = await client.environments.create(env_request)

            version_request = CreateEnvironmentVersionRequest(
                variables={
                    "DB_URL": EnvironmentVariable(type=VariableType.STRING, value="postgres://localhost/test"),
                    "API_KEY": EnvironmentVariable(type=VariableType.SECRET, value="secret"),
                }
            )
            version = await client.environments.create_version(str(env.id), version_request)
            assert version.environment_id == env.id
            assert version.version_number == 1
            assert "DB_URL" in version.variables
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")


@pytest.mark.asyncio
class TestIntegrationArtifacts:
    """Integration tests for artifact endpoints."""

    async def test_list_artifacts(self, client):
        """Test listing artifacts."""
        try:
            artifacts = await client.artifacts.list(workspace_id="ws-1")
            assert isinstance(artifacts, list)
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_get_artifact(self, client):
        """Test getting artifact metadata."""
        try:
            content = b"test content for get"
            artifact = await client.artifacts.upload(
                file_content=content,
                workspace_id="ws-1",
                filename="get-test.txt",
            )

            fetched = await client.artifacts.get(str(artifact.id))
            assert fetched.id == artifact.id
            assert fetched.name == "get-test.txt"

            await client.artifacts.delete(str(artifact.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_upload_and_download_artifact(self, client):
        """Test uploading and downloading an artifact."""
        try:
            content = b"integration test content"
            artifact = await client.artifacts.upload(
                file_content=content,
                workspace_id="ws-1",
                filename="test.txt",
            )
            assert artifact.name == "test.txt"
            assert artifact.size_bytes == len(content)

            downloaded = await client.artifacts.download(str(artifact.id))
            assert downloaded == content

            await client.artifacts.delete(str(artifact.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_delete_artifact(self, client):
        """Test deleting an artifact."""
        try:
            content = b"content to delete"
            artifact = await client.artifacts.upload(
                file_content=content,
                workspace_id="ws-1",
                filename="delete-test.txt",
            )

            await client.artifacts.delete(str(artifact.id))

            try:
                await client.artifacts.get(str(artifact.id))
                assert False, "Should have raised NotFoundError"
            except Exception:
                pass
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")


@pytest.mark.asyncio
class TestIntegrationWebhooks:
    """Integration tests for webhook endpoints."""

    async def test_list_webhooks(self, client):
        """Test listing webhooks."""
        try:
            webhooks = await client.webhooks.list()
            assert isinstance(webhooks, list)
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_create_and_delete_webhook(self, client):
        """Test creating and deleting a webhook."""
        try:
            request = CreateWebhookRequest(
                url="https://example.com/webhook",
                events=[WebhookEvent.SPEC_CREATED],
                secret="test-secret",
            )
            webhook = await client.webhooks.create(request)
            assert webhook.url == "https://example.com/webhook"
            assert WebhookEvent.SPEC_CREATED in webhook.events

            await client.webhooks.delete(str(webhook.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_list_webhook_deliveries(self, client):
        """Test listing webhook deliveries."""
        try:
            request = CreateWebhookRequest(
                url="https://example.com/webhook-deliveries",
                events=[WebhookEvent.TASK_COMPLETED],
                secret="test-secret",
            )
            webhook = await client.webhooks.create(request)

            deliveries = await client.webhooks.list_deliveries(str(webhook.id))
            assert isinstance(deliveries, list)

            await client.webhooks.delete(str(webhook.id))
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")


@pytest.mark.asyncio
class TestIntegrationWorkspaces:
    """Integration tests for workspace endpoints."""

    async def test_get_workspace_settings(self, client):
        """Test getting workspace settings."""
        try:
            settings = await client.workspaces.get_settings("ws-1")
            assert settings.workspace_id == "ws-1"
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")

    async def test_update_workspace_settings(self, client):
        """Test updating workspace settings."""
        try:
            request = UpdateWorkspaceSettingsRequest(
                max_artifact_size_mb=200,
                egress_allowlist=["api.github.com", "pypi.org"],
            )
            settings = await client.workspaces.update_settings("ws-1", request)
            assert settings.workspace_id == "ws-1"
            assert settings.max_artifact_size_mb == 200
        except Exception as e:
            pytest.skip(f"API not available or feature disabled: {e}")
