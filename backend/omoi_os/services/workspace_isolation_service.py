"""Workspace isolation service for session runtime boundaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from omoi_os.config import is_feature_enabled
from omoi_os.logging import get_logger
from omoi_os.models.credential_binding import CredentialBinding
from omoi_os.models.environment import EnvironmentVersion
from omoi_os.models.workspace_settings import WorkspaceSettings
from omoi_os.services.credential_broker import (
    CredentialBrokerService,
    CredentialNotFoundError,
    get_credential_broker_service,
)
from omoi_os.services.database import DatabaseService
from omoi_os.services.environment_service import (
    EnvironmentService,
    EnvironmentServiceError,
    get_environment_service,
)
from omoi_os.utils.datetime import utc_now

logger = get_logger(__name__)


class WorkspaceIsolationError(Exception):
    """Base exception for workspace isolation errors."""


class WorkspaceIsolationFeatureDisabledError(WorkspaceIsolationError):
    """Raised when workspace isolation is used while sessions API v1 is disabled."""


class CrossWorkspaceCredentialError(WorkspaceIsolationError):
    """Raised when a session requests credentials outside its workspace."""


@dataclass(frozen=True)
class WorkspaceIsolationContext:
    """Resolved isolation context for a sandbox session."""

    workspace_id: UUID
    storage_path: str
    environment_variables: dict[str, str]
    credential_environment_variables: dict[str, str]
    egress_environment_variables: dict[str, str]

    @property
    def execution_environment(self) -> dict[str, str]:
        """Return the complete environment to inject into the session."""
        return {
            "OMOIOS_WORKSPACE_ID": str(self.workspace_id),
            "OMOIOS_WORKSPACE_PATH": self.storage_path,
            **self.environment_variables,
            **self.credential_environment_variables,
            **self.egress_environment_variables,
        }


class WorkspaceIsolationService:
    """Enforces file, credential, environment, and egress isolation per workspace."""

    def __init__(
        self,
        db: Optional[DatabaseService] = None,
        credential_broker: Optional[CredentialBrokerService] = None,
        environment_service: Optional[EnvironmentService] = None,
    ) -> None:
        self._db = db
        self._credential_broker = credential_broker
        self._environment_service = environment_service

    def _get_db(self) -> DatabaseService:
        if self._db is None:
            from omoi_os.config import get_app_settings

            settings = get_app_settings()
            self._db = DatabaseService(connection_string=settings.database.url)
        return self._db

    def _get_credential_broker(self) -> CredentialBrokerService:
        if self._credential_broker is None:
            self._credential_broker = get_credential_broker_service()
        return self._credential_broker

    def _get_environment_service(self) -> EnvironmentService:
        if self._environment_service is None:
            self._environment_service = get_environment_service()
        return self._environment_service

    def _ensure_feature_enabled(self) -> None:
        if not is_feature_enabled("sessions_api_v1"):
            raise WorkspaceIsolationFeatureDisabledError(
                "Workspace isolation requires sessions_api_v1"
            )

    def storage_path_for_workspace(self, workspace_id: UUID) -> str:
        """Return the isolated storage path for a workspace."""
        return f"/workspaces/{workspace_id}"

    def upsert_settings(
        self,
        workspace_id: UUID,
        environment_id: Optional[UUID] = None,
        egress_proxy_config: Optional[dict] = None,
        storage_path: Optional[str] = None,
    ) -> WorkspaceSettings:
        """Create or update workspace isolation settings."""
        self._ensure_feature_enabled()
        db = self._get_db()
        resolved_storage_path = storage_path or self.storage_path_for_workspace(
            workspace_id
        )

        with db.get_session() as session:
            settings = session.get(WorkspaceSettings, workspace_id)
            if settings is None:
                settings = WorkspaceSettings(
                    workspace_id=workspace_id,
                    storage_path=resolved_storage_path,
                    environment_id=environment_id,
                    egress_proxy_config=egress_proxy_config or {},
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(settings)
            else:
                settings.storage_path = resolved_storage_path
                settings.environment_id = environment_id
                settings.egress_proxy_config = egress_proxy_config or {}
                settings.updated_at = utc_now()

            session.commit()
            session.refresh(settings)
            session.expunge(settings)
            return settings

    def get_or_create_settings(
        self,
        workspace_id: UUID,
        environment_id: Optional[UUID] = None,
    ) -> WorkspaceSettings:
        """Return workspace settings, creating default isolation settings if absent."""
        self._ensure_feature_enabled()
        db = self._get_db()
        with db.get_session() as session:
            settings = session.get(WorkspaceSettings, workspace_id)
            if settings is None:
                settings = WorkspaceSettings(
                    workspace_id=workspace_id,
                    storage_path=self.storage_path_for_workspace(workspace_id),
                    environment_id=environment_id,
                    egress_proxy_config={},
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(settings)
                session.commit()
                session.refresh(settings)
            elif (
                environment_id is not None and settings.environment_id != environment_id
            ):
                settings.environment_id = environment_id
                settings.updated_at = utc_now()
                session.commit()
                session.refresh(settings)

            session.expunge(settings)
            return settings

    def validate_credential_access(
        self,
        workspace_id: UUID,
        credential_binding_ids: Optional[list[UUID]],
        actor: Optional[str] = None,
    ) -> list[CredentialBinding]:
        """Ensure requested credentials are bound to the session workspace."""
        self._ensure_feature_enabled()
        if not credential_binding_ids:
            return []

        broker = self._get_credential_broker()
        bindings: list[CredentialBinding] = []
        for binding_id in credential_binding_ids:
            try:
                binding = broker.get_binding(binding_id=binding_id, actor=actor)
            except CredentialNotFoundError as exc:
                raise CrossWorkspaceCredentialError(
                    f"Credential binding is not accessible in workspace {workspace_id}"
                ) from exc

            if binding.workspace_id != workspace_id:
                raise CrossWorkspaceCredentialError(
                    f"Credential binding {binding_id} belongs to a different workspace"
                )
            bindings.append(binding)
        return bindings

    def build_environment_variables(
        self,
        workspace_id: UUID,
        environment_id: Optional[UUID] = None,
    ) -> dict[str, str]:
        """Resolve workspace environment variables from the latest environment version."""
        settings = self.get_or_create_settings(
            workspace_id=workspace_id,
            environment_id=environment_id,
        )
        resolved_environment_id = environment_id or settings.environment_id
        if resolved_environment_id is None:
            return {}

        environment_service = self._get_environment_service()
        try:
            _environment, latest_version = environment_service.get_environment(
                resolved_environment_id
            )
        except EnvironmentServiceError as exc:
            raise WorkspaceIsolationError(
                f"Workspace environment not found: {resolved_environment_id}"
            ) from exc

        if latest_version is None:
            return {}
        return self._flatten_environment_version(latest_version, environment_service)

    def _flatten_environment_version(
        self,
        version: EnvironmentVersion,
        environment_service: EnvironmentService,
    ) -> dict[str, str]:
        variables = environment_service.get_decrypted_variables(version)
        flattened: dict[str, str] = {}
        for name, variable in variables.items():
            value = variable.get("value")
            if variable.get("type") == "json":
                flattened[name] = json.dumps(value, sort_keys=True)
            else:
                flattened[name] = str(value)
        return flattened

    def build_egress_environment(self, workspace_id: UUID) -> dict[str, str]:
        """Build proxy environment variables from workspace egress settings."""
        settings = self.get_or_create_settings(workspace_id)
        config = settings.egress_proxy_config or {}
        if not config or not config.get("enabled", False):
            return {}

        proxy_url = config.get("proxy_url") or config.get("http_proxy")
        https_proxy = config.get("https_proxy") or proxy_url
        egress_env = {"OMOIOS_EGRESS_PROXY_ENABLED": "true"}
        if proxy_url:
            egress_env["HTTP_PROXY"] = str(proxy_url)
            egress_env["http_proxy"] = str(proxy_url)
        if https_proxy:
            egress_env["HTTPS_PROXY"] = str(https_proxy)
            egress_env["https_proxy"] = str(https_proxy)
        if config.get("no_proxy"):
            egress_env["NO_PROXY"] = str(config["no_proxy"])
            egress_env["no_proxy"] = str(config["no_proxy"])
        return egress_env

    def prepare_session_isolation(
        self,
        workspace_id: UUID,
        credential_binding_ids: Optional[list[UUID]] = None,
        environment_id: Optional[UUID] = None,
        actor: Optional[str] = None,
    ) -> WorkspaceIsolationContext:
        """Validate and resolve all workspace isolation data for a session."""
        self._ensure_feature_enabled()
        settings = self.get_or_create_settings(
            workspace_id=workspace_id,
            environment_id=environment_id,
        )
        self.validate_credential_access(
            workspace_id=workspace_id,
            credential_binding_ids=credential_binding_ids,
            actor=actor,
        )
        environment_variables = self.build_environment_variables(
            workspace_id=workspace_id,
            environment_id=environment_id,
        )
        credential_environment_variables = (
            self._get_credential_broker().inject_credentials_by_ids(
                workspace_id=workspace_id,
                binding_ids=credential_binding_ids or [],
                actor=actor,
            )
        )
        egress_environment_variables = self.build_egress_environment(workspace_id)

        return WorkspaceIsolationContext(
            workspace_id=workspace_id,
            storage_path=settings.storage_path,
            environment_variables=environment_variables,
            credential_environment_variables=credential_environment_variables,
            egress_environment_variables=egress_environment_variables,
        )


_service_instance: Optional[WorkspaceIsolationService] = None


def get_workspace_isolation_service() -> WorkspaceIsolationService:
    """Get the global workspace isolation service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WorkspaceIsolationService()
    return _service_instance


def reset_workspace_isolation_service() -> None:
    """Reset the global workspace isolation service instance."""
    global _service_instance
    _service_instance = None
