"""Credential broker service for secure credential storage and injection.

Provides:
- Credential CRUD operations with encryption
- Workspace-scoped credential binding
- Audit logging for all access
- Secure injection into sandboxes
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from omoi_os.logging import get_logger
from omoi_os.models.credential_access_log import CredentialAccessLog
from omoi_os.models.credential_binding import CredentialBinding
from omoi_os.services.credential_encryption import (
    CredentialEncryptionService,
    get_credential_encryption_service,
)
from omoi_os.services.database import DatabaseService
from omoi_os.utils.datetime import utc_now

logger = get_logger(__name__)

# Valid binding kinds
VALID_BINDING_KINDS = {"bearer_secret", "user_oauth", "github_app"}


class CredentialBrokerError(Exception):
    """Base exception for credential broker errors."""

    pass


class InvalidBindingKindError(CredentialBrokerError):
    """Raised when an invalid binding kind is specified."""

    pass


class CredentialNotFoundError(CredentialBrokerError):
    """Raised when a credential is not found."""

    pass


class CredentialBrokerService:
    """Service for managing encrypted credentials bound to workspaces.

    Provides secure storage and injection of credentials with:
    - Fernet AES-256-GCM encryption
    - Workspace-scoped access control
    - Comprehensive audit logging
    - Support for multiple binding kinds
    """

    def __init__(
        self,
        db: Optional[DatabaseService] = None,
        encryption: Optional[CredentialEncryptionService] = None,
    ):
        """Initialize credential broker service.

        Args:
            db: Database service (optional, for testing)
            encryption: Encryption service (optional, for testing)
        """
        self._db = db
        self._encryption = encryption

    def _get_db(self) -> DatabaseService:
        """Get database service, initializing if needed."""
        if self._db is None:
            from omoi_os.config import get_app_settings

            settings = get_app_settings()
            self._db = DatabaseService(connection_string=settings.database.url)
        return self._db

    def _get_encryption(self) -> CredentialEncryptionService:
        """Get encryption service, initializing if needed."""
        if self._encryption is None:
            self._encryption = get_credential_encryption_service()
        return self._encryption

    def _write_access_log(
        self,
        workspace_id: UUID,
        action: str,
        credential_binding_id: Optional[UUID] = None,
        actor: Optional[str] = None,
        access_metadata: Optional[dict] = None,
    ) -> None:
        """Write an access log entry.

        Args:
            workspace_id: Workspace ID for scoping
            action: Action type (create, read, delete, inject)
            credential_binding_id: Optional credential binding ID
            actor: Optional user ID or agent ID
            access_metadata: Optional additional metadata
        """
        db = self._get_db()
        with db.get_session() as session:
            log_entry = CredentialAccessLog(
                credential_binding_id=credential_binding_id,
                workspace_id=workspace_id,
                action=action,
                actor=actor,
                accessed_at=utc_now(),
                access_metadata=access_metadata or {},
            )
            session.add(log_entry)
            session.commit()

    def create_binding(
        self,
        workspace_id: UUID,
        kind: str,
        name: str,
        value: str,
        config: Optional[dict] = None,
        actor: Optional[str] = None,
    ) -> CredentialBinding:
        """Create a new credential binding.

        Args:
            workspace_id: Workspace ID that owns this credential
            kind: Binding kind (bearer_secret, user_oauth, github_app)
            name: Human-readable name for the credential
            value: Plaintext credential value (will be encrypted)
            config: Optional additional configuration
            actor: Optional user ID or agent ID for audit log

        Returns:
            Created CredentialBinding model

        Raises:
            InvalidBindingKindError: If kind is not valid
            CredentialBrokerError: If encryption is not configured
        """
        # Validate kind
        if kind not in VALID_BINDING_KINDS:
            raise InvalidBindingKindError(
                f"Invalid binding kind '{kind}'. Must be one of: {VALID_BINDING_KINDS}"
            )

        # Get encryption service
        encryption = self._get_encryption()
        if not encryption.is_configured:
            raise CredentialBrokerError(
                "Credential encryption is not configured. "
                "Set CREDENTIAL_ENCRYPTION_KEY environment variable."
            )

        # Encrypt the value
        try:
            encrypted_value = encryption.encrypt(value)
        except Exception as e:
            logger.error("Failed to encrypt credential value", error=str(e))
            raise CredentialBrokerError("Failed to encrypt credential value") from e

        db = self._get_db()
        with db.get_session() as session:
            binding = CredentialBinding(
                workspace_id=workspace_id,
                kind=kind,
                name=name,
                encrypted_value=encrypted_value,
                config=config or {},
                version=1,
                created_at=utc_now(),
                rotated_at=None,
            )
            session.add(binding)
            session.commit()
            session.refresh(binding)

            logger.info(
                "Credential binding created",
                binding_id=str(binding.id),
                workspace_id=str(workspace_id),
                kind=kind,
                name=name,
            )

            # Write audit log
            self._write_access_log(
                workspace_id=workspace_id,
                action="create",
                credential_binding_id=binding.id,
                actor=actor,
                access_metadata={"kind": kind, "name": name},
            )

            session.expunge(binding)
            return binding

    def list_bindings(
        self,
        workspace_id: UUID,
        actor: Optional[str] = None,
    ) -> list[CredentialBinding]:
        """List all credential bindings in a workspace.

        Args:
            workspace_id: Workspace ID to filter by
            actor: Optional user ID or agent ID for audit log

        Returns:
            List of CredentialBinding models (without decrypted values)
        """
        db = self._get_db()
        with db.get_session() as session:
            bindings = (
                session.query(CredentialBinding)
                .filter(CredentialBinding.workspace_id == workspace_id)
                .order_by(CredentialBinding.created_at.desc())
                .all()
            )

            # Write audit log for list operation (no specific binding ID)
            self._write_access_log(
                workspace_id=workspace_id,
                action="read",
                credential_binding_id=None,
                actor=actor,
                access_metadata={"count": len(bindings)},
            )

            for binding in bindings:
                session.expunge(binding)
            return bindings

    def get_binding(
        self,
        binding_id: UUID,
        actor: Optional[str] = None,
    ) -> CredentialBinding:
        """Get a credential binding by ID.

        Args:
            binding_id: Credential binding ID
            actor: Optional user ID or agent ID for audit log

        Returns:
            CredentialBinding model

        Raises:
            CredentialNotFoundError: If binding not found
        """
        db = self._get_db()
        with db.get_session() as session:
            binding = (
                session.query(CredentialBinding)
                .filter(CredentialBinding.id == binding_id)
                .first()
            )

            if binding is None:
                raise CredentialNotFoundError(
                    f"Credential binding not found: {binding_id}"
                )

            # Write audit log
            self._write_access_log(
                workspace_id=binding.workspace_id,
                action="read",
                credential_binding_id=binding.id,
                actor=actor,
                access_metadata={"kind": binding.kind, "name": binding.name},
            )

            session.expunge(binding)
            return binding

    def delete_binding(
        self,
        binding_id: UUID,
        actor: Optional[str] = None,
    ) -> None:
        """Delete a credential binding.

        Args:
            binding_id: Credential binding ID
            actor: Optional user ID or agent ID for audit log

        Raises:
            CredentialNotFoundError: If binding not found
        """
        db = self._get_db()
        with db.get_session() as session:
            binding = (
                session.query(CredentialBinding)
                .filter(CredentialBinding.id == binding_id)
                .first()
            )

            if binding is None:
                raise CredentialNotFoundError(
                    f"Credential binding not found: {binding_id}"
                )

            workspace_id = binding.workspace_id
            kind = binding.kind
            name = binding.name

            session.delete(binding)
            session.commit()

            logger.info(
                "Credential binding deleted",
                binding_id=str(binding_id),
                workspace_id=str(workspace_id),
            )

            # Write audit log
            self._write_access_log(
                workspace_id=workspace_id,
                action="delete",
                credential_binding_id=binding_id,
                actor=actor,
                access_metadata={"kind": kind, "name": name},
            )

    def inject_credentials(
        self,
        workspace_id: UUID,
        actor: Optional[str] = None,
    ) -> dict[str, str]:
        """Get decrypted credentials for injection into a sandbox.

        Returns a dictionary mapping environment variable names to
        decrypted credential values. Each credential is logged as
        an inject action in the audit log.

        Args:
            workspace_id: Workspace ID to get credentials for
            actor: Optional user ID or agent ID for audit log

        Returns:
            Dictionary of {env_var_name: decrypted_value}

        Raises:
            CredentialBrokerError: If decryption fails
        """
        db = self._get_db()
        encryption = self._get_encryption()

        if not encryption.is_configured:
            raise CredentialBrokerError(
                "Credential encryption is not configured. "
                "Set CREDENTIAL_ENCRYPTION_KEY environment variable."
            )

        with db.get_session() as session:
            bindings = (
                session.query(CredentialBinding)
                .filter(CredentialBinding.workspace_id == workspace_id)
                .all()
            )

            result = {}
            for binding in bindings:
                # Decrypt the value
                try:
                    decrypted_value = encryption.decrypt(binding.encrypted_value)
                except Exception as e:
                    logger.error(
                        "Failed to decrypt credential",
                        binding_id=str(binding.id),
                        error=str(e),
                    )
                    raise CredentialBrokerError(
                        f"Failed to decrypt credential '{binding.name}'"
                    ) from e

                # Build env var name: OMOIOS_CRED_<KIND>_<NAME>
                # Replace non-alphanumeric with underscore
                safe_name = "".join(
                    c if c.isalnum() else "_" for c in binding.name
                ).upper()
                env_var_name = f"OMOIOS_CRED_{binding.kind.upper()}_{safe_name}"
                result[env_var_name] = decrypted_value

                # Write audit log for each injected credential
                self._write_access_log(
                    workspace_id=workspace_id,
                    action="inject",
                    credential_binding_id=binding.id,
                    actor=actor,
                    access_metadata={
                        "kind": binding.kind,
                        "name": binding.name,
                        "env_var": env_var_name,
                    },
                )

            logger.info(
                "Credentials injected for workspace",
                workspace_id=str(workspace_id),
                count=len(bindings),
            )

            return result

    def inject_credentials_by_ids(
        self,
        workspace_id: UUID,
        binding_ids: list[UUID],
        actor: Optional[str] = None,
    ) -> dict[str, str]:
        """Get selected decrypted workspace credentials for sandbox injection.

        Args:
            workspace_id: Workspace ID that must own every requested credential
            binding_ids: Credential binding IDs to inject
            actor: Optional user ID or agent ID for audit log

        Returns:
            Dictionary of {env_var_name: decrypted_value}

        Raises:
            CredentialNotFoundError: If a requested binding is missing or out of scope
            CredentialBrokerError: If decryption fails
        """
        if not binding_ids:
            return {}

        db = self._get_db()
        encryption = self._get_encryption()

        if not encryption.is_configured:
            raise CredentialBrokerError(
                "Credential encryption is not configured. "
                "Set CREDENTIAL_ENCRYPTION_KEY environment variable."
            )

        requested_ids = set(binding_ids)
        with db.get_session() as session:
            bindings = (
                session.query(CredentialBinding)
                .filter(
                    CredentialBinding.workspace_id == workspace_id,
                    CredentialBinding.id.in_(requested_ids),
                )
                .all()
            )
            found_ids = {binding.id for binding in bindings}
            missing_ids = requested_ids - found_ids
            if missing_ids:
                raise CredentialNotFoundError(
                    "Credential binding not found in requested workspace"
                )

            result = {}
            for binding in bindings:
                try:
                    decrypted_value = encryption.decrypt(binding.encrypted_value)
                except Exception as e:
                    logger.error(
                        "Failed to decrypt credential",
                        binding_id=str(binding.id),
                        error=str(e),
                    )
                    raise CredentialBrokerError(
                        f"Failed to decrypt credential '{binding.name}'"
                    ) from e

                safe_name = "".join(
                    c if c.isalnum() else "_" for c in binding.name
                ).upper()
                env_var_name = f"OMOIOS_CRED_{binding.kind.upper()}_{safe_name}"
                result[env_var_name] = decrypted_value

                self._write_access_log(
                    workspace_id=workspace_id,
                    action="inject",
                    credential_binding_id=binding.id,
                    actor=actor,
                    access_metadata={
                        "kind": binding.kind,
                        "name": binding.name,
                        "env_var": env_var_name,
                    },
                )

            return result


# Global singleton instance
_service_instance: Optional[CredentialBrokerService] = None


def get_credential_broker_service() -> CredentialBrokerService:
    """Get the global credential broker service instance (singleton pattern).

    Returns:
        CredentialBrokerService instance
    """
    global _service_instance

    if _service_instance is None:
        _service_instance = CredentialBrokerService()

    return _service_instance


def reset_credential_broker_service() -> None:
    """Reset the global credential broker service instance.

    Useful for testing to ensure clean state between tests.
    """
    global _service_instance
    _service_instance = None
