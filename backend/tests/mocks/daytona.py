"""Mock Daytona service for testing.

Provides in-memory sandbox tracking without actual Daytona API calls.
"""

from uuid import uuid4


class MockDaytonaService:
    """Mock Daytona service with in-memory sandbox tracking.

    Simulates Daytona sandbox operations in memory for testing
    without making actual API calls.
    """

    def __init__(self):
        """Initialize the mock Daytona service."""
        self.sandboxes: dict[str, dict] = {}
        self.operations: list[dict] = []

    async def create_sandbox(
        self, workspace_id: str, image: str | None = None, **kwargs
    ) -> dict:
        """Create a mock sandbox in memory.

        Args:
            workspace_id: Workspace identifier
            image: Optional sandbox image
            **kwargs: Additional sandbox configuration

        Returns:
            Sandbox info dict
        """
        sandbox_id = f"sandbox-{uuid4().hex[:8]}"
        sandbox_info = {
            "id": sandbox_id,
            "workspace_id": workspace_id,
            "image": image or "default:latest",
            "status": "running",
            **kwargs,
        }
        self.sandboxes[sandbox_id] = sandbox_info
        self.operations.append(
            {
                "type": "create_sandbox",
                "sandbox_id": sandbox_id,
                "workspace_id": workspace_id,
                "image": image,
                "kwargs": kwargs,
            }
        )
        return sandbox_info

    async def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete a sandbox from memory.

        Args:
            sandbox_id: ID of the sandbox to delete

        Returns:
            True if deleted, False if not found
        """
        if sandbox_id in self.sandboxes:
            del self.sandboxes[sandbox_id]
            self.operations.append(
                {
                    "type": "delete_sandbox",
                    "sandbox_id": sandbox_id,
                }
            )
            return True
        return False

    async def get_sandbox(self, sandbox_id: str) -> dict | None:
        """Get sandbox info from memory.

        Args:
            sandbox_id: ID of the sandbox

        Returns:
            Sandbox info or None if not found
        """
        return self.sandboxes.get(sandbox_id)

    async def list_sandboxes(self) -> list[dict]:
        """List all sandboxes in memory.

        Returns:
            List of sandbox info dicts
        """
        return list(self.sandboxes.values())

    def assert_sandbox_created(self, workspace_id: str | None = None) -> None:
        """Assert that a sandbox was created.

        Args:
            workspace_id: Optional specific workspace to check

        Raises:
            AssertionError: If no sandbox was created
        """
        if not self.sandboxes:
            raise AssertionError("No sandboxes were created")
        if workspace_id:
            for sandbox in self.sandboxes.values():
                if sandbox.get("workspace_id") == workspace_id:
                    return
            raise AssertionError(f"No sandbox created for workspace '{workspace_id}'")

    def reset(self) -> None:
        """Clear all sandboxes and operations."""
        self.sandboxes.clear()
        self.operations.clear()
