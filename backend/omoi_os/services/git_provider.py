"""Git provider protocol for abstracting GitHub vs local git operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class BranchInfo:
    """Information about a Git branch."""

    name: str
    sha: str
    is_default: bool = False
    is_protected: bool = False


@dataclass
class PullRequestInfo:
    """Information about a pull request (or local merge request)."""

    id: str
    title: str
    source_branch: str
    target_branch: str
    status: str  # "open" | "merged" | "closed"
    merge_sha: Optional[str] = None
    conflict_files: Optional[list[str]] = None


@runtime_checkable
class GitProvider(Protocol):
    """Protocol for Git hosting operations."""

    async def create_branch(
        self, repo_full_name: str, branch_name: str, source_sha: str
    ) -> BranchInfo:
        """Create a new branch."""
        ...

    async def delete_branch(self, repo_full_name: str, branch_name: str) -> None:
        """Delete a branch."""
        ...

    async def get_branch(
        self, repo_full_name: str, branch_name: str
    ) -> Optional[BranchInfo]:
        """Get branch info by name."""
        ...

    async def list_branches(self, repo_full_name: str) -> list[BranchInfo]:
        """List all branches."""
        ...

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        source_branch: str,
        target_branch: str,
        body: str = "",
    ) -> PullRequestInfo:
        """Create a pull request."""
        ...

    async def merge_pull_request(
        self, repo_full_name: str, pr_id: str, merge_method: str = "merge"
    ) -> PullRequestInfo:
        """Merge a pull request."""
        ...

    async def get_default_branch(self, repo_full_name: str) -> str:
        """Get the default branch name."""
        ...

    async def clone_repo(self, repo_full_name: str, target_dir: str) -> str:
        """Clone a repository to a directory."""
        ...
