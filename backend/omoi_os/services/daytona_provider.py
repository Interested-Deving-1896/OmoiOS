"""Daytona-backed sandbox provider wrapping DaytonaSpawnerService."""

from __future__ import annotations
from typing import Optional
from omoi_os.services.sandbox_provider import SandboxResult, SandboxStatus


class DaytonaProvider:
    """SandboxProvider backed by Daytona Cloud."""

    def __init__(self, spawner):
        self._spawner = spawner

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
    ) -> SandboxResult:
        sandbox_id = await self._spawner.spawn_for_task(
            task_id=task_id,
            agent_id=agent_id,
            phase_id=phase_id,
            runtime=runtime,
            execution_mode=execution_mode,
            extra_env=env_vars,
        )
        return SandboxResult(
            sandbox_id=sandbox_id,
            status="creating",
            connection_info={"provider": "daytona"},
        )

    async def terminate_sandbox(self, sandbox_id: str) -> None:
        await self._spawner.terminate_sandbox(sandbox_id)

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        try:
            info = self._spawner.get_sandbox_info(sandbox_id)
            return SandboxStatus(
                sandbox_id=sandbox_id,
                status=info.status if info else "unknown",
            )
        except Exception:
            return SandboxStatus(sandbox_id=sandbox_id, status="unknown")

    async def list_active(self) -> list[SandboxStatus]:
        try:
            active = getattr(self._spawner, "_active_sandboxes", {})
            return [
                SandboxStatus(sandbox_id=sid, status=getattr(info, "status", "unknown"))
                for sid, info in active.items()
            ]
        except Exception:
            return []
