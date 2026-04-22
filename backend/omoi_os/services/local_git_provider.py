"""Local Git provider using bare repositories for development."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from omoi_os.services.git_provider import BranchInfo, PullRequestInfo


class LocalGitProvider:
    """GitProvider using local bare Git repositories. Dev-only."""

    def __init__(self, repos_dir: str = ".local-repos"):
        """Initialize the LocalGitProvider.

        Args:
            repos_dir: Directory to store bare repositories
        """
        self._repos_dir = Path(repos_dir)
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._pull_requests: dict[str, PullRequestInfo] = {}
        self._pr_counter = 0

    def _repo_path(self, repo_full_name: str) -> Path:
        """Get the path to a bare repo."""
        safe_name = repo_full_name.replace("/", "--")
        return self._repos_dir / f"{safe_name}.git"

    async def _ensure_repo(self, repo_full_name: str) -> Path:
        """Ensure a bare repo exists, creating if necessary."""
        path = self._repo_path(repo_full_name)
        if not path.exists():
            await self._run_git(None, "init", "--bare", str(path))
            # Create an initial commit on main branch
            await self._create_initial_commit(path)
        return path

    async def _create_initial_commit(self, repo_path: Path) -> None:
        """Create an initial commit on the main branch."""
        # Create a temporary worktree to make an initial commit
        temp_dir = repo_path.parent / f".temp-{repo_path.stem}"
        try:
            await self._run_git(None, "clone", str(repo_path), str(temp_dir))
            # Create a dummy file
            dummy_file = temp_dir / "README.md"
            dummy_file.write_text("# Initial commit\n")
            await self._run_git(temp_dir, "add", "README.md")
            await self._run_git(
                temp_dir,
                "-c",
                "user.email=local@omoi.dev",
                "-c",
                "user.name=Local Dev",
                "commit",
                "-m",
                "Initial commit",
            )
            await self._run_git(temp_dir, "push", "origin", "main")
        finally:
            # Clean up temp directory
            if temp_dir.exists():
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _run_git(
        self, repo_path: Optional[Path], *args, check: bool = True
    ) -> asyncio.subprocess.Process:
        """Run a git command.

        Args:
            repo_path: Path to repo (None for global commands)
            *args: Git command arguments
            check: Whether to raise on non-zero exit

        Returns:
            Process result with stdout attached
        """
        cmd = ["git"]
        if repo_path:
            cmd.extend(["-C", str(repo_path)])
        cmd.extend(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"Git command failed: {' '.join(cmd)}\n{stderr.decode()}"
            )
        # Attach stdout to result for easier access
        proc.stdout = stdout  # type: ignore[attr-defined]
        return proc

    async def create_branch(
        self, repo_full_name: str, branch_name: str, source_sha: str
    ) -> BranchInfo:
        """Create a new branch."""
        repo_path = await self._ensure_repo(repo_full_name)
        await self._run_git(repo_path, "branch", branch_name, source_sha)
        return BranchInfo(name=branch_name, sha=source_sha)

    async def delete_branch(self, repo_full_name: str, branch_name: str) -> None:
        """Delete a branch."""
        repo_path = self._repo_path(repo_full_name)
        if repo_path.exists():
            await self._run_git(repo_path, "branch", "-D", branch_name)

    async def get_branch(
        self, repo_full_name: str, branch_name: str
    ) -> Optional[BranchInfo]:
        """Get branch info by name."""
        repo_path = self._repo_path(repo_full_name)
        if not repo_path.exists():
            return None
        result = await self._run_git(
            repo_path,
            "rev-parse",
            "--verify",
            f"refs/heads/{branch_name}",
            check=False,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.decode().strip()
        return BranchInfo(name=branch_name, sha=sha)

    async def list_branches(self, repo_full_name: str) -> list[BranchInfo]:
        """List all branches."""
        repo_path = self._repo_path(repo_full_name)
        if not repo_path.exists():
            return []
        result = await self._run_git(
            repo_path,
            "branch",
            "--format=%(refname:short) %(objectname)",
            check=False,
        )
        branches = []
        output = result.stdout.decode().strip()
        if not output:
            return []
        for line in output.split("\n"):
            if not line.strip():
                continue
            parts = line.strip().split()
            branches.append(
                BranchInfo(name=parts[0], sha=parts[1] if len(parts) > 1 else "")
            )
        return branches

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        source_branch: str,
        target_branch: str,
        body: str = "",
    ) -> PullRequestInfo:
        """Create a pull request (stored in-memory)."""
        self._pr_counter += 1
        pr_id = f"local-pr-{self._pr_counter}"
        pr = PullRequestInfo(
            id=pr_id,
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            status="open",
        )
        self._pull_requests[pr_id] = pr
        return pr

    async def merge_pull_request(
        self, repo_full_name: str, pr_id: str, merge_method: str = "merge"
    ) -> PullRequestInfo:
        """Merge a pull request."""
        pr = self._pull_requests.get(pr_id)
        if not pr:
            raise ValueError(f"PR {pr_id} not found")
        pr.status = "merged"
        repo_path = self._repo_path(repo_full_name)
        if repo_path.exists():
            result = await self._run_git(
                repo_path, "rev-parse", pr.source_branch, check=False
            )
            if result.returncode == 0:
                pr.merge_sha = result.stdout.decode().strip()
        return pr

    async def get_default_branch(self, repo_full_name: str) -> str:
        """Get the default branch name."""
        repo_path = self._repo_path(repo_full_name)
        if not repo_path.exists():
            return "main"
        result = await self._run_git(
            repo_path, "symbolic-ref", "--short", "HEAD", check=False
        )
        if result.returncode == 0:
            return result.stdout.decode().strip()
        return "main"

    async def clone_repo(self, repo_full_name: str, target_dir: str) -> str:
        """Clone a repository to a directory."""
        repo_path = await self._ensure_repo(repo_full_name)
        await self._run_git(None, "clone", str(repo_path), target_dir)
        return target_dir
