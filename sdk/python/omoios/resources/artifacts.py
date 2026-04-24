"""Artifacts resource for OmoiOS API."""

from typing import List, Optional

from omoios.resources.base import BaseResource
from omoios.types import Artifact


class ArtifactsResource(BaseResource):
    """Resource for managing artifacts.

    Example:
        >>> client = AsyncOmoiOSClient("https://api.omoios.dev", api_key="key")
        >>> artifacts = await client.artifacts.list(workspace_id="ws-1")
        >>> print(artifacts[0].name)
    """

    async def upload(
        self,
        file_content: bytes,
        workspace_id: str,
        filename: str = "uploaded-file.bin",
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Artifact:
        """Upload an artifact.

        Args:
            file_content: Raw file bytes
            workspace_id: Workspace ID
            filename: Name for the uploaded file
            content_type: MIME type override (optional)
            metadata: JSON-serializable metadata (optional)

        Returns:
            Created artifact metadata

        Example:
            >>> with open("report.pdf", "rb") as f:
            ...     artifact = await client.artifacts.upload(
            ...         file_content=f.read(),
            ...         workspace_id="ws-1",
            ...         filename="report.pdf",
            ...     )
        """
        files = {"file": (filename, file_content, content_type or "application/octet-stream")}
        data = {"workspace_id": workspace_id}
        if content_type:
            data["content_type"] = content_type
        if metadata:
            import json

            data["metadata"] = json.dumps(metadata)

        response = await self._client._request(
            "POST",
            "/api/v1/artifacts/upload",
            data=data,
            files=files,
        )
        return Artifact.model_validate(response.json())

    async def list(
        self,
        workspace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Artifact]:
        """List artifacts in a workspace.

        Args:
            workspace_id: Workspace ID to filter by
            limit: Maximum number of results (1-1000)
            offset: Number of results to skip

        Returns:
            List of artifacts

        Example:
            >>> artifacts = await client.artifacts.list(workspace_id="ws-1", limit=50)
        """
        response = await self._client._request(
            "GET",
            "/api/v1/artifacts",
            params={"workspace_id": workspace_id, "limit": limit, "offset": offset},
        )
        return [Artifact.model_validate(item) for item in response.json()]

    async def get(self, artifact_id: str) -> Artifact:
        """Get artifact metadata by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact metadata

        Raises:
            NotFoundError: If artifact doesn't exist

        Example:
            >>> artifact = await client.artifacts.get("art-1")
        """
        response = await self._client._request("GET", f"/api/v1/artifacts/{artifact_id}")
        return Artifact.model_validate(response.json())

    async def download(self, artifact_id: str) -> bytes:
        """Download artifact content.

        Args:
            artifact_id: Artifact ID

        Returns:
            Raw file bytes

        Raises:
            NotFoundError: If artifact doesn't exist

        Example:
            >>> content = await client.artifacts.download("art-1")
            >>> with open("downloaded.txt", "wb") as f:
            ...     f.write(content)
        """
        response = await self._client._request("GET", f"/api/v1/artifacts/{artifact_id}/download")
        return response.content

    async def delete(self, artifact_id: str) -> None:
        """Delete an artifact.

        Args:
            artifact_id: Artifact ID to delete

        Raises:
            NotFoundError: If artifact doesn't exist

        Example:
            >>> await client.artifacts.delete("art-1")
        """
        await self._client._request("DELETE", f"/api/v1/artifacts/{artifact_id}")
