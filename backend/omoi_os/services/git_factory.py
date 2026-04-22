"""Factory for creating the appropriate GitProvider based on config."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from omoi_os.services.git_provider import GitProvider


def create_git_provider(
    github_api=None, user_id: Optional[UUID | str] = None
) -> "GitProvider":
    """Create GitProvider based on config.

    Reads git.provider from config:
    - "github" (default) → GitHubProvider
    - "local" → LocalGitProvider

    Args:
        github_api: GitHubAPIService instance (required for GitHub provider)
        user_id: User ID for GitHub API authentication (required for GitHub provider)

    Returns:
        GitProvider instance
    """
    from omoi_os.config import get_app_settings

    settings = get_app_settings()
    provider_type = settings.git.provider

    if provider_type == "local":
        from omoi_os.services.local_git_provider import LocalGitProvider

        return LocalGitProvider(repos_dir=settings.git.local_repos_dir)
    else:
        if github_api is None:
            raise ValueError("GitHubProvider requires a GitHubAPIService instance")
        from omoi_os.services.github_provider import GitHubProvider

        return GitHubProvider(github_api, user_id=user_id)
