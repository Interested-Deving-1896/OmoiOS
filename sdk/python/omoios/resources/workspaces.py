"""Workspaces resource for OmoiOS API."""

from omoios.resources.base import BaseResource
from omoios.types import UpdateWorkspaceSettingsRequest, WorkspaceSettings


class WorkspacesResource(BaseResource):
    """Resource for managing workspace settings.

    Example:
        >>> client = AsyncOmoiOSClient("https://api.omoios.dev", api_key="key")
        >>> settings = await client.workspaces.get_settings("ws-1")
        >>> print(settings.egress_allowlist)
    """

    async def get_settings(self, workspace_id: str) -> WorkspaceSettings:
        """Get workspace settings.

        Args:
            workspace_id: Workspace ID

        Returns:
            Workspace settings

        Raises:
            NotFoundError: If workspace doesn't exist

        Example:
            >>> settings = await client.workspaces.get_settings("ws-1")
            >>> print(settings.max_artifact_size_mb)
        """
        response = await self._client._request(
            "GET", f"/api/v1/workspaces/{workspace_id}/settings"
        )
        return WorkspaceSettings.model_validate(response.json())

    async def update_settings(
        self, workspace_id: str, request: UpdateWorkspaceSettingsRequest
    ) -> WorkspaceSettings:
        """Update workspace settings.

        Args:
            workspace_id: Workspace ID
            request: Update settings request (only provided fields are updated)

        Returns:
            Updated workspace settings

        Raises:
            NotFoundError: If workspace doesn't exist
            ValidationError: If request is invalid

        Example:
            >>> request = UpdateWorkspaceSettingsRequest(
            ...     max_artifact_size_mb=200,
            ...     egress_allowlist=["api.github.com", "pypi.org"],
            ... )
            >>> settings = await client.workspaces.update_settings("ws-1", request)
        """
        response = await self._client._request(
            "PUT",
            f"/api/v1/workspaces/{workspace_id}/settings",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return WorkspaceSettings.model_validate(response.json())
