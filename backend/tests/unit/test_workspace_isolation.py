"""Unit tests for workspace isolation service.

Tests Requirements:
- REQ-ISO-001: Workspace storage path is isolated under /workspaces/{id}/
- REQ-ISO-002: Sessions cannot access cross-workspace credentials
- REQ-ISO-003: Sessions receive workspace environment variables
- REQ-ISO-004: Sessions inherit workspace egress proxy configuration
- REQ-ISO-005: Isolation is guarded by sessions_api_v1
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Table

from omoi_os.models.workspace_settings import WorkspaceSettings
from omoi_os.services.credential_broker import CredentialBrokerService
from omoi_os.services.credential_encryption import CredentialEncryptionService
from omoi_os.services.database import DatabaseService
from omoi_os.services.environment_service import EnvironmentService
from omoi_os.services.workspace_isolation_service import (
    CrossWorkspaceCredentialError,
    WorkspaceIsolationFeatureDisabledError,
    WorkspaceIsolationService,
)


@pytest.fixture
def encryption_service() -> CredentialEncryptionService:
    """Create an encryption service with a valid test key."""
    return CredentialEncryptionService(encryption_key="b" * 64)


@pytest.fixture
def credential_broker_service(
    db_service: DatabaseService,
    encryption_service: CredentialEncryptionService,
) -> CredentialBrokerService:
    """Create credential broker service with test dependencies."""
    return CredentialBrokerService(db=db_service, encryption=encryption_service)


@pytest.fixture
def environment_service(
    db_service: DatabaseService,
    encryption_service: CredentialEncryptionService,
) -> EnvironmentService:
    """Create environment service with test dependencies."""
    return EnvironmentService(db=db_service, encryption=encryption_service)


@pytest.fixture
def isolation_service(
    db_service: DatabaseService,
    credential_broker_service: CredentialBrokerService,
    environment_service: EnvironmentService,
    monkeypatch: pytest.MonkeyPatch,
) -> WorkspaceIsolationService:
    """Create workspace isolation service with enabled feature flag."""
    workspace_settings_table = WorkspaceSettings.__table__
    assert isinstance(workspace_settings_table, Table)
    workspace_settings_table.create(db_service.engine, checkfirst=True)
    monkeypatch.setattr(
        "omoi_os.services.workspace_isolation_service.is_feature_enabled",
        lambda flag_name: flag_name == "sessions_api_v1",
    )
    return WorkspaceIsolationService(
        db=db_service,
        credential_broker=credential_broker_service,
        environment_service=environment_service,
    )


@pytest.fixture
def workspace_id() -> UUID:
    """Create a workspace ID for tests."""
    return uuid4()


class TestWorkspaceStorageIsolation:
    """Tests for workspace file-level isolation."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_get_or_create_settings_uses_isolated_storage_path(
        self,
        isolation_service: WorkspaceIsolationService,
        workspace_id: UUID,
    ):
        """Workspace settings default to /workspaces/{workspace_id}."""
        settings = isolation_service.get_or_create_settings(workspace_id)

        assert isinstance(settings, WorkspaceSettings)
        assert settings.workspace_id == workspace_id
        assert settings.storage_path == f"/workspaces/{workspace_id}"


class TestWorkspaceCredentialIsolation:
    """Tests for workspace-scoped credential access."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_session_cannot_access_cross_workspace_credentials(
        self,
        isolation_service: WorkspaceIsolationService,
        credential_broker_service: CredentialBrokerService,
        workspace_id: UUID,
    ):
        """Credential validation rejects bindings owned by a different workspace."""
        other_workspace_id = uuid4()
        other_binding = credential_broker_service.create_binding(
            workspace_id=other_workspace_id,
            kind="bearer_secret",
            name="external-api-key",
            value="secret-from-other-workspace",
        )

        with pytest.raises(CrossWorkspaceCredentialError):
            isolation_service.prepare_session_isolation(
                workspace_id=workspace_id,
                credential_binding_ids=[other_binding.id],
            )

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_session_receives_requested_workspace_credentials(
        self,
        isolation_service: WorkspaceIsolationService,
        credential_broker_service: CredentialBrokerService,
        workspace_id: UUID,
    ):
        """Selected credentials from the same workspace are injected."""
        binding = credential_broker_service.create_binding(
            workspace_id=workspace_id,
            kind="bearer_secret",
            name="api-key",
            value="workspace-secret",
        )

        context = isolation_service.prepare_session_isolation(
            workspace_id=workspace_id,
            credential_binding_ids=[binding.id],
        )

        assert context.credential_environment_variables == {
            "OMOIOS_CRED_BEARER_SECRET_API_KEY": "workspace-secret"
        }


class TestWorkspaceEnvironmentIsolation:
    """Tests for workspace environment variable injection."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_session_receives_workspace_environment_variables(
        self,
        isolation_service: WorkspaceIsolationService,
        environment_service: EnvironmentService,
        workspace_id: UUID,
    ):
        """Latest environment version is flattened into session env vars."""
        environment = environment_service.create_environment(
            org_id=uuid4(),
            name="workspace-runtime",
        )
        environment_service.create_version(
            env_id=environment.id,
            variables={
                "PLAIN_VALUE": {"type": "string", "value": "visible"},
                "SECRET_VALUE": {"type": "secret", "value": "decrypted-at-runtime"},
                "JSON_VALUE": {"type": "json", "value": {"enabled": True}},
            },
        )
        isolation_service.upsert_settings(
            workspace_id=workspace_id,
            environment_id=environment.id,
        )

        context = isolation_service.prepare_session_isolation(workspace_id=workspace_id)

        assert context.environment_variables["PLAIN_VALUE"] == "visible"
        assert context.environment_variables["SECRET_VALUE"] == "decrypted-at-runtime"
        assert context.environment_variables["JSON_VALUE"] == '{"enabled": true}'


class TestWorkspaceEgressIsolation:
    """Tests for workspace egress proxy inheritance."""

    @pytest.mark.unit
    @pytest.mark.requires_db
    def test_session_inherits_workspace_egress_proxy_config(
        self,
        isolation_service: WorkspaceIsolationService,
        workspace_id: UUID,
    ):
        """Enabled egress config is converted into proxy environment variables."""
        isolation_service.upsert_settings(
            workspace_id=workspace_id,
            egress_proxy_config={
                "enabled": True,
                "proxy_url": "http://egress-proxy.internal:8080",
                "no_proxy": "localhost,127.0.0.1",
            },
        )

        context = isolation_service.prepare_session_isolation(workspace_id=workspace_id)

        assert (
            context.egress_environment_variables["OMOIOS_EGRESS_PROXY_ENABLED"]
            == "true"
        )
        assert (
            context.egress_environment_variables["HTTP_PROXY"]
            == "http://egress-proxy.internal:8080"
        )
        assert (
            context.egress_environment_variables["HTTPS_PROXY"]
            == "http://egress-proxy.internal:8080"
        )
        assert context.egress_environment_variables["NO_PROXY"] == "localhost,127.0.0.1"


class TestWorkspaceIsolationFeatureFlag:
    """Tests for sessions_api_v1 feature flag guard."""

    @pytest.mark.unit
    def test_isolation_requires_sessions_api_v1(
        self,
        db_service: DatabaseService,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Isolation service refuses to run when sessions API is disabled."""
        monkeypatch.setattr(
            "omoi_os.services.workspace_isolation_service.is_feature_enabled",
            lambda _flag_name: False,
        )
        service = WorkspaceIsolationService(db=db_service)

        with pytest.raises(WorkspaceIsolationFeatureDisabledError):
            service.get_or_create_settings(uuid4())
