"""Credentials resource for OmoiOS API."""

from typing import List, Optional

from omoios.resources.base import BaseResource
from omoios.types import CreateCredentialRequest, Credential


class CredentialsResource(BaseResource):
    """Resource for managing credentials.

    Example:
        >>> client = AsyncOmoiOSClient("https://api.omoios.dev", api_key="key")
        >>> creds = await client.credentials.list(workspace_id="ws-1")
        >>> print(creds[0].name)
    """

    async def list(self, workspace_id: str) -> List[Credential]:
        """List credentials in a workspace.

        Args:
            workspace_id: Workspace ID to filter by

        Returns:
            List of credentials

        Example:
            >>> creds = await client.credentials.list(workspace_id="ws-1")
        """
        response = await self._client._request(
            "GET", "/api/v1/credentials", params={"workspace_id": workspace_id}
        )
        return [Credential.model_validate(item) for item in response.json()]

    async def get(self, credential_id: str) -> Credential:
        """Get a credential by ID.

        Args:
            credential_id: Credential ID

        Returns:
            Credential object

        Raises:
            NotFoundError: If credential doesn't exist

        Example:
            >>> cred = await client.credentials.get("cred-1")
        """
        response = await self._client._request("GET", f"/api/v1/credentials/{credential_id}")
        return Credential.model_validate(response.json())

    async def create(self, request: CreateCredentialRequest) -> Credential:
        """Create a new credential.

        Args:
            request: Create credential request

        Returns:
            Created credential

        Example:
            >>> request = CreateCredentialRequest(
            ...     workspace_id="ws-1",
            ...     kind=BindingKind.BEARER_SECRET,
            ...     name="api-key",
            ...     value="secret-value",
            ... )
            >>> cred = await client.credentials.create(request)
        """
        response = await self._client._request(
            "POST",
            "/api/v1/credentials",
            json=request.model_dump(mode="json"),
        )
        return Credential.model_validate(response.json())

    async def delete(self, credential_id: str) -> None:
        """Delete a credential.

        Args:
            credential_id: Credential ID to delete

        Raises:
            NotFoundError: If credential doesn't exist

        Example:
            >>> await client.credentials.delete("cred-1")
        """
        await self._client._request("DELETE", f"/api/v1/credentials/{credential_id}")
