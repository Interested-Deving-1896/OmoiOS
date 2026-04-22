"""Local Docker sandbox provider for development."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from omoi_os.services.sandbox_provider import SandboxResult, SandboxStatus


@dataclass
class ContainerInfo:
    """Tracking info for a local Docker container."""

    container_id: str
    sandbox_id: str
    task_id: str


class LocalDockerProvider:
    """SandboxProvider using local Docker containers. Dev-only."""

    DEFAULT_IMAGE = "nikolaik/python-nodejs:python3.12-nodejs22"

    def __init__(
        self,
        worker_script_path: str = "backend/omoi_os/workers/claude_sandbox_worker.py",
        api_base_url: str = "http://host.docker.internal:18000",
        image: Optional[str] = None,
        mount_workspace: Optional[str] = None,
    ):
        self._worker_script = worker_script_path
        self._api_base_url = api_base_url
        self._image = image or self.DEFAULT_IMAGE
        self._mount_workspace = mount_workspace
        self._active: dict[str, ContainerInfo] = {}

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
        sandbox_id = f"local-{task_id[:8]}-{uuid4().hex[:6]}"
        container_env = {
            "SANDBOX_ID": sandbox_id,
            "CALLBACK_URL": self._api_base_url,
            "IS_SANDBOX": "1",
            **env_vars,
        }

        env_flags = " ".join(f'-e {k}="{v}"' for k, v in container_env.items())
        mount_flag = (
            f"-v {self._mount_workspace}:/workspace" if self._mount_workspace else ""
        )
        use_image = image or self._image

        cmd = (
            f"docker run -d --name {sandbox_id} {env_flags} {mount_flag} "
            f"--add-host=host.docker.internal:host-gateway "
            f"{use_image} python /workspace/claude_sandbox_worker.py"
        )

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start container: {stderr.decode()}")

        container_id = stdout.decode().strip()
        self._active[sandbox_id] = ContainerInfo(
            container_id=container_id,
            sandbox_id=sandbox_id,
            task_id=task_id,
        )

        return SandboxResult(
            sandbox_id=sandbox_id,
            status="running",
            connection_info={
                "provider": "local-docker",
                "container_id": container_id,
                "logs_cmd": f"docker logs -f {sandbox_id}",
                "exec_cmd": f"docker exec -it {sandbox_id} bash",
            },
        )

    async def terminate_sandbox(self, sandbox_id: str) -> None:
        if sandbox_id in self._active:
            await asyncio.create_subprocess_shell(
                f"docker rm -f {sandbox_id}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            del self._active[sandbox_id]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        proc = await asyncio.create_subprocess_shell(
            f'docker inspect -f "{{{{.State.Status}}}}" {sandbox_id}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        docker_status = stdout.decode().strip()
        status_map = {"running": "running", "exited": "completed", "dead": "failed"}
        return SandboxStatus(
            sandbox_id=sandbox_id,
            status=status_map.get(docker_status, "unknown"),
        )

    async def list_active(self) -> list[SandboxStatus]:
        results = []
        for sid in list(self._active.keys()):
            status = await self.get_status(sid)
            results.append(status)
        return results
