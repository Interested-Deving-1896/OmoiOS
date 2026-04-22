"""Tests for sandbox provider abstraction."""

import pytest
from unittest.mock import MagicMock, patch

from omoi_os.services.sandbox_provider import (
    SandboxResult,
    SandboxStatus,
    SandboxProvider,
)
from omoi_os.services.local_docker_provider import LocalDockerProvider, ContainerInfo
from omoi_os.services.daytona_provider import DaytonaProvider


class TestSandboxResult:
    def test_creation(self):
        r = SandboxResult(sandbox_id="sb-1", status="running")
        assert r.sandbox_id == "sb-1"
        assert r.connection_info == {}

    def test_with_connection_info(self):
        r = SandboxResult(
            sandbox_id="sb-1", status="running", connection_info={"provider": "local"}
        )
        assert r.connection_info["provider"] == "local"


class TestSandboxStatus:
    def test_creation(self):
        s = SandboxStatus(sandbox_id="sb-1", status="running")
        assert s.started_at is None
        assert s.error is None

    def test_with_error(self):
        s = SandboxStatus(sandbox_id="sb-1", status="failed", error="OOM")
        assert s.error == "OOM"


class TestContainerInfo:
    def test_creation(self):
        c = ContainerInfo(container_id="abc123", sandbox_id="sb-1", task_id="t-1")
        assert c.container_id == "abc123"


class TestLocalDockerProvider:
    def test_init_defaults(self):
        provider = LocalDockerProvider()
        assert provider._image == LocalDockerProvider.DEFAULT_IMAGE
        assert provider._active == {}

    def test_init_custom(self):
        provider = LocalDockerProvider(
            image="custom:latest",
            mount_workspace="/tmp/ws",
        )
        assert provider._image == "custom:latest"
        assert provider._mount_workspace == "/tmp/ws"

    @pytest.mark.asyncio
    async def test_terminate_unknown_sandbox_is_noop(self):
        provider = LocalDockerProvider()
        # Should not raise
        await provider.terminate_sandbox("nonexistent")

    @pytest.mark.asyncio
    async def test_list_active_empty(self):
        provider = LocalDockerProvider()
        result = await provider.list_active()
        assert result == []


class TestDaytonaProvider:
    def test_init(self):
        mock_spawner = MagicMock()
        provider = DaytonaProvider(mock_spawner)
        assert provider._spawner is mock_spawner


class TestSandboxFactory:
    def test_local_provider(self):
        mock_settings = MagicMock()
        mock_settings.sandbox.provider = "local"
        mock_settings.sandbox.local_image = "test:latest"
        mock_settings.sandbox.local_mount_workspace = None
        mock_settings.sandbox.local_api_base_url = "http://localhost:18000"

        with patch("omoi_os.config.get_app_settings", return_value=mock_settings):
            from omoi_os.services.sandbox_factory import create_sandbox_provider

            provider = create_sandbox_provider()
            assert isinstance(provider, LocalDockerProvider)

    def test_daytona_requires_db(self):
        mock_settings = MagicMock()
        mock_settings.sandbox.provider = "daytona"

        with patch("omoi_os.config.get_app_settings", return_value=mock_settings):
            from omoi_os.services.sandbox_factory import create_sandbox_provider

            with pytest.raises(ValueError, match="requires"):
                create_sandbox_provider()


class TestSandboxSettings:
    def test_defaults(self):
        from omoi_os.config import SandboxSettings

        s = SandboxSettings(provider="daytona")
        assert s.provider == "daytona"
        assert s.local_image == "nikolaik/python-nodejs:python3.12-nodejs22"
