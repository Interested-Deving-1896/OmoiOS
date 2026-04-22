"""GitHub-backed git provider wrapping GitHubAPIService."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from omoi_os.services.git_provider import BranchInfo, PullRequestInfo


class GitHubProvider:
    """GitProvider backed by GitHub API. Wraps existing GitHubAPIService."""

    def __init__(self, github_api, user_id: Optional[UUID | str] = None):
        """Initialize the GitHubProvider.

        Args:
            github_api: GitHubAPIService instance for GitHub operations
            user_id: User ID for authentication (UUID or string)
        """
        self._api = github_api
        self._user_id = user_id

    def _split_repo(self, repo_full_name: str) -> tuple[str, str]:
        """Split 'owner/repo' into (owner, repo)."""
        owner, repo = repo_full_name.split("/", 1)
        return owner, repo

    def _get_user_id(self) -> UUID:
        """Get the user ID as UUID."""
        if self._user_id is None:
            raise ValueError("GitHubProvider requires a user_id for API operations")
        if isinstance(self._user_id, str):
            return UUID(self._user_id)
        return self._user_id

    async def create_branch(
        self, repo_full_name: str, branch_name: str, source_sha: str
    ) -> BranchInfo:
        """Create a new branch."""
        owner, repo = self._split_repo(repo_full_name)
        result = await self._api.create_branch(
            self._get_user_id(), owner, repo, branch_name, source_sha
        )
        sha = result.sha if hasattr(result, "sha") else source_sha
        return BranchInfo(name=branch_name, sha=sha)

    async def delete_branch(self, repo_full_name: str, branch_name: str) -> None:
        """Delete a branch."""
        owner, repo = self._split_repo(repo_full_name)
        await self._api.delete_branch(self._get_user_id(), owner, repo, branch_name)

    async def get_branch(
        self, repo_full_name: str, branch_name: str
    ) -> Optional[BranchInfo]:
        """Get branch info by name."""
        owner, repo = self._split_repo(repo_full_name)
        try:
            # Try to get branch via list_branches and filter
            branches = await self._api.list_branches(self._get_user_id(), owner, repo)
            for b in branches:
                if b.name == branch_name:
                    return BranchInfo(name=b.name, sha=b.sha, is_protected=b.protected)
            return None
        except Exception:
            return None

    async def list_branches(self, repo_full_name: str) -> list[BranchInfo]:
        """List all branches."""
        owner, repo = self._split_repo(repo_full_name)
        try:
            branches = await self._api.list_branches(self._get_user_id(), owner, repo)
            return [
                BranchInfo(name=b.name, sha=b.sha, is_protected=b.protected)
                for b in branches
            ]
        except Exception:
            return []

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        source_branch: str,
        target_branch: str,
        body: str = "",
    ) -> PullRequestInfo:
        """Create a pull request."""
        owner, repo = self._split_repo(repo_full_name)
        result = await self._api.create_pull_request(
            self._get_user_id(),
            owner,
            repo,
            title,
            source_branch,
            target_branch,
            body,
        )
        pr_number = result.number if hasattr(result, "number") else 0
        return PullRequestInfo(
            id=str(pr_number),
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            status="open",
        )

    async def merge_pull_request(
        self, repo_full_name: str, pr_id: str, merge_method: str = "merge"
    ) -> PullRequestInfo:
        """Merge a pull request."""
        owner, repo = self._split_repo(repo_full_name)
        try:
            result = await self._api.merge_pull_request(
                self._get_user_id(), owner, repo, int(pr_id), merge_method=merge_method
            )
            merge_sha = result.sha if hasattr(result, "sha") else None
            return PullRequestInfo(
                id=pr_id,
                title="",
                source_branch="",
                target_branch="",
                status="merged",
                merge_sha=merge_sha,
            )
        except Exception:
            return PullRequestInfo(
                id=pr_id,
                title="",
                source_branch="",
                target_branch="",
                status="merged",
            )

    async def get_default_branch(self, repo_full_name: str) -> str:
        """Get the default branch name."""
        owner, repo = self._split_repo(repo_full_name)
        try:
            repo_info = await self._api.get_repository(self._get_user_id(), owner, repo)
            return (
                repo_info.get("default_branch", "main")
                if isinstance(repo_info, dict)
                else "main"
            )
        except Exception:
            return "main"

    async def clone_repo(self, repo_full_name: str, target_dir: str) -> str:
        """Clone a repository to a directory."""
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            f"https://github.com/{repo_full_name}.git",
            target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return target_dir
