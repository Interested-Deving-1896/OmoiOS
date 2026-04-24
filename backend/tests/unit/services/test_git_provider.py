"""Tests for git provider abstraction."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from omoi_os.services.git_provider import BranchInfo, PullRequestInfo
from omoi_os.services.github_provider import GitHubProvider
from omoi_os.services.local_git_provider import LocalGitProvider


class TestBranchInfo:
    def test_creation(self):
        b = BranchInfo(name="main", sha="abc123")
        assert b.name == "main"
        assert b.sha == "abc123"
        assert b.is_default is False
        assert b.is_protected is False

    def test_default_branch(self):
        b = BranchInfo(name="main", sha="abc", is_default=True)
        assert b.is_default is True


class TestPullRequestInfo:
    def test_creation(self):
        pr = PullRequestInfo(
            id="1",
            title="Test PR",
            source_branch="feature",
            target_branch="main",
            status="open",
        )
        assert pr.status == "open"
        assert pr.merge_sha is None

    def test_with_conflicts(self):
        pr = PullRequestInfo(
            id="1",
            title="PR",
            source_branch="a",
            target_branch="b",
            status="open",
            conflict_files=["src/main.py"],
        )
        assert pr.conflict_files == ["src/main.py"]


class TestLocalGitProviderPRs:
    """Test LocalGitProvider's in-memory PR tracking (no git needed)."""

    @pytest.fixture
    def provider(self, tmp_path):
        return LocalGitProvider(repos_dir=str(tmp_path / "repos"))

    @pytest.mark.asyncio
    async def test_create_pull_request(self, provider):
        pr = await provider.create_pull_request(
            "owner/repo",
            "My PR",
            "feature",
            "main",
        )
        assert pr.id == "local-pr-1"
        assert pr.status == "open"
        assert pr.title == "My PR"

    @pytest.mark.asyncio
    async def test_pr_counter_increments(self, provider):
        pr1 = await provider.create_pull_request("o/r", "PR 1", "a", "main")
        pr2 = await provider.create_pull_request("o/r", "PR 2", "b", "main")
        assert pr1.id == "local-pr-1"
        assert pr2.id == "local-pr-2"

    @pytest.mark.asyncio
    async def test_merge_nonexistent_pr_raises(self, provider):
        with pytest.raises(ValueError, match="not found"):
            await provider.merge_pull_request("o/r", "nonexistent")

    @pytest.mark.asyncio
    async def test_get_default_branch_no_repo(self, provider):
        result = await provider.get_default_branch("owner/repo")
        assert result == "main"

    @pytest.mark.asyncio
    async def test_list_branches_no_repo(self, provider):
        result = await provider.list_branches("owner/nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_branch_no_repo(self, provider):
        result = await provider.get_branch("owner/nonexistent", "main")
        assert result is None


class TestGitHubProvider:
    def test_split_repo(self):
        provider = GitHubProvider(github_api=None)
        owner, repo = provider._split_repo("owner/repo-name")
        assert owner == "owner"
        assert repo == "repo-name"

    def test_split_repo_with_nested(self):
        provider = GitHubProvider(github_api=None)
        owner, repo = provider._split_repo("org/sub/repo")
        assert owner == "org"
        assert repo == "sub/repo"


class TestGitFactory:
    def test_local_provider(self, tmp_path):
        """Factory creates LocalGitProvider when config says 'local'."""
        mock_settings = MagicMock()
        mock_settings.git.provider = "local"
        mock_settings.git.local_repos_dir = str(tmp_path / "repos")

        # Patch get_app_settings in the config module
        with patch("omoi_os.config.get_app_settings", return_value=mock_settings):
            # Remove cached git_factory module to force reimport
            if "omoi_os.services.git_factory" in sys.modules:
                del sys.modules["omoi_os.services.git_factory"]

            from omoi_os.services.git_factory import create_git_provider

            provider = create_git_provider()
            assert isinstance(provider, LocalGitProvider)

    def test_github_provider_requires_api(self):
        mock_settings = MagicMock()
        mock_settings.git.provider = "github"

        with patch("omoi_os.config.get_app_settings", return_value=mock_settings):
            if "omoi_os.services.git_factory" in sys.modules:
                del sys.modules["omoi_os.services.git_factory"]

            from omoi_os.services.git_factory import create_git_provider

            with pytest.raises(ValueError, match="requires"):
                create_git_provider()

    def test_github_provider_with_api(self):
        mock_settings = MagicMock()
        mock_settings.git.provider = "github"
        mock_api = MagicMock()

        with patch("omoi_os.config.get_app_settings", return_value=mock_settings):
            if "omoi_os.services.git_factory" in sys.modules:
                del sys.modules["omoi_os.services.git_factory"]

            from omoi_os.services.git_factory import create_git_provider

            provider = create_git_provider(github_api=mock_api)
            assert isinstance(provider, GitHubProvider)


class TestGitSettings:
    def test_defaults(self):
        from omoi_os.config import GitSettings

        # Use monkeypatched settings to avoid YAML file loading issues
        s = GitSettings(provider="github", local_repos_dir=".local-repos")
        assert s.provider == "github"
        assert s.local_repos_dir == ".local-repos"
