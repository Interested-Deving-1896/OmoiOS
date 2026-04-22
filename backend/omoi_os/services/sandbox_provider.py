"""Sandbox provider protocol for abstracting Daytona vs local Docker execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Optional, Any, runtime_checkable


@dataclass
class SandboxResult:
    """Result of spawning a sandbox."""

    sandbox_id: str
    status: str  # "creating" | "running" | "completed" | "failed" | "terminated"
    connection_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxStatus:
    """Current status of a sandbox."""

    sandbox_id: str
    status: str
    started_at: Optional[str] = None
    error: Optional[str] = None


@runtime_checkable
class SandboxProvider(Protocol):
    """Protocol for sandbox lifecycle management."""

    async def spawn_for_task(
        self,
        task_id: str,
        agent_id: str,
        phase_id: str,
        env_vars: dict[str, str],
        *,
        runtime: str = "claude",
        execution_mode: str = "implementation",
        image: Optional[str] = None,
    ) -> SandboxResult: ...

    async def terminate_sandbox(self, sandbox_id: str) -> None: ...

    async def get_status(self, sandbox_id: str) -> SandboxStatus: ...

    async def list_active(self) -> list[SandboxStatus]: ...
