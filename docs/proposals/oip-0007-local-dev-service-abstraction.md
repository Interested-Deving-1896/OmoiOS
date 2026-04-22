# OIP-0007: Local Development Service Abstraction Layer

```
OIP: 0007
Title: Local Development Service Abstraction Layer
Description: Replace external service dependencies with local alternatives for fully offline development and testing
Author: Kevin Hill
Status: Draft
Type: Standards Track
Created: 2026-03-01
Requires: 0006
```

## Abstract

Introduce a **Local Development Service Abstraction Layer** — a suite of seven capabilities that eliminate the dependency on external services (LLM APIs, GitHub, Daytona) for local development and testing. This complements [OIP-0006](oip-0006-local-orchestration-dev-mode.md) (which provides orchestration observability) by replacing the services themselves: (F) an LLM recording/replay layer so the server boots without API keys, (G) a local Git provider so branch/merge workflows run without GitHub, (H) a spec pipeline fixture mode so spec logic is testable without live Claude, (I) a monitoring dry-run mode so Guardian/Conductor are testable without running agents, (J) a dev bootstrap and health dashboard so developers know what to start and what's broken, (K) a unified mock service layer so tests stop using ad-hoc MagicMock, and (L) a frontend event replay so UI development doesn't require the full backend. Together with OIP-0006, these twelve capabilities make OmoiOS fully testable and runnable on a developer's laptop.

## Motivation

### The Problem

[OIP-0006](oip-0006-local-orchestration-dev-mode.md) addresses orchestration observability — seeing the DAG, agent execution, task updates, and branch strategy. But observability alone isn't enough if the services themselves won't run locally. The current codebase has three categories of external dependency:

1. **Hard dependencies that crash on startup** — PostgreSQL, Redis, and an LLM API key (Fireworks.ai) are required for the server to boot. Missing any of these produces a crash, not a graceful degradation. The LLM service (`backend/omoi_os/services/pydantic_ai_service.py`) raises `ValueError` if no API key is configured.

2. **Functional dependencies that block workflows** — GitHub OAuth tokens are required for branch creation, PR workflows, and repo operations (`backend/omoi_os/services/github_api.py`). Without a token, the entire branch → sandbox → merge pipeline is blocked. Spec execution requires Claude Agent SDK calls for 5 of 6 phases (`subsystems/spec-sandbox/src/spec_sandbox/worker/state_machine.py`).

3. **Test infrastructure gaps** — 113 test files use ad-hoc `MagicMock` with no reusable mock implementations. LLM tests make real API calls. There's no `@pytest.mark.requires_llm` marker. No shared mock fixtures. Every test file reinvents its own mocking strategy.

### What This Means in Practice

A developer returning to OmoiOS after time away faces this experience:

1. Run `just dev-all` → server crashes because no Fireworks.ai API key
2. Add API key → server starts, but spec workflows fail because no GitHub token
3. Add GitHub token → specs fail because no Claude API key for agent SDK
4. Add Claude key → agents fail because no Daytona sandbox
5. Configure Daytona → can finally iterate, but each cycle takes minutes

**Result**: It takes 30+ minutes of configuration hunting before writing a single line of code, and iteration cycles are measured in minutes, not seconds.

### Relationship to OIP-0006

OIP-0006 and OIP-0007 form a complementary pair:

| | OIP-0006 | OIP-0007 |
|---|----------|----------|
| **Focus** | Orchestration observability | Service independence |
| **Answers** | "What is the orchestrator doing?" | "Can I run this without external services?" |
| **Parts** | A-E (SandboxProvider, Dry-Run, Events, Branch Preview, Context Inspector) | F-L (LLM Replay, Git Provider, Spec Fixtures, Monitoring Dry-Run, Bootstrap, Mocks, Frontend Replay) |
| **Prerequisite** | PostgreSQL + Redis running | Nothing — Part J bootstraps everything |

OIP-0006's `LocalDockerProvider` (Part A) uses the LLM recording layer from this proposal (Part F) to run agents locally without live API keys. OIP-0006's Terminal Event Stream (Part C) uses the event persistence from this proposal (Part K's mock event bus) for replay. The two proposals are designed to be implemented together.

### Priority Tiers

**Tier 1 — Can't even start without these:**
- **Part F** (LLM Recording/Replay) — Server crashes without API key
- **Part J** (Dev Bootstrap & Health Dashboard) — Nobody knows what to start

**Tier 2 — Can start but can't test end-to-end:**
- **Part G** (Local Git Provider) — Branch/merge cycle blocked without GitHub
- **Part H** (Spec Pipeline Fixture Mode) — Can't iterate on spec logic without live Claude
- **Part K** (Unified Mock Service Layer) — Tests are fragile, ad-hoc mocks everywhere

**Tier 3 — Polish and completeness:**
- **Part I** (Monitoring Dry-Run) — Guardian/Conductor observability
- **Part L** (Frontend Event Replay) — UI testing without full backend

## Specification

### Part F: LLM Recording/Replay Layer

Replace live LLM calls with recorded responses so the server boots and workflows execute without API keys, and so LLM-dependent tests are deterministic and fast.

#### F.1 LLM Service Modes

**Modified file**: `backend/config/base.yaml`

```yaml
llm:
  mode: "live"          # "live" | "record" | "replay" | "null"
  recording_dir: ".llm-recordings"
  replay_strict: false  # If true, fail on cache miss. If false, return placeholder.
```

Four modes, all implementing the existing `structured_output()` interface:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `live` | Normal — calls Fireworks.ai (current behavior) | Production, active development |
| `record` | Calls live API, saves prompt+response to disk | Building a recording library |
| `replay` | Returns cached responses, no API calls | Offline dev, CI, deterministic tests |
| `null` | Returns empty/default responses, never crashes | Server bootstrap, startup testing |

#### F.2 Recording Format

**New directory**: `.llm-recordings/`

Recordings are JSON files keyed by a content hash of the prompt + model + output type:

```python
# Hash key = sha256(model + prompt_text + output_type_name)
# File: .llm-recordings/{hash_key}.json

{
    "hash": "a1b2c3...",
    "model": "accounts/fireworks/models/minimax-m2p1",
    "prompt": "Analyze the following task requirements...",
    "output_type": "TaskRequirements",
    "response": { ... },  # The structured output result
    "recorded_at": "2026-03-01T14:23:01Z",
    "latency_ms": 1234,
    "tokens": {"input": 500, "output": 200}
}
```

For the Claude Agent SDK (used by spec phases), recordings capture the full turn sequence:

```python
# File: .llm-recordings/agent-sessions/{session_id}.json

{
    "session_id": "spec-explore-abc123",
    "phase": "explore",
    "turns": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "...", "tool_calls": [...]},
        {"role": "tool", "tool_call_id": "...", "content": "..."},
        ...
    ],
    "final_result": { ... },
    "recorded_at": "2026-03-01T14:23:01Z",
    "total_turns": 12
}
```

#### F.3 RecordingLLMService

**New file**: `backend/omoi_os/services/recording_llm_service.py`

```python
from omoi_os.services.llm_service import LLMService
from omoi_os.services.pydantic_ai_service import PydanticAIService
import hashlib, json
from pathlib import Path


class RecordingLLMService:
    """Wraps a live LLM service and records all prompt/response pairs to disk.

    Recordings are stored as JSON files in the configured recording directory,
    keyed by content hash for deterministic replay.
    """

    def __init__(self, inner: PydanticAIService, recording_dir: str = ".llm-recordings"):
        self._inner = inner
        self._recording_dir = Path(recording_dir)
        self._recording_dir.mkdir(parents=True, exist_ok=True)

    async def structured_output(self, prompt: str, output_type: type, **kwargs):
        """Call live LLM, record the result, return it."""
        result = await self._inner.structured_output(prompt=prompt, output_type=output_type, **kwargs)

        hash_key = self._compute_hash(prompt, output_type, kwargs.get("model"))
        recording = {
            "hash": hash_key,
            "model": kwargs.get("model", self._inner.default_model),
            "prompt": prompt,
            "output_type": output_type.__name__,
            "response": result.model_dump() if hasattr(result, "model_dump") else result,
            "recorded_at": utc_now().isoformat(),
        }
        recording_path = self._recording_dir / f"{hash_key}.json"
        recording_path.write_text(json.dumps(recording, indent=2, default=str))

        return result

    def _compute_hash(self, prompt: str, output_type: type, model: str | None) -> str:
        content = f"{model or 'default'}::{output_type.__name__}::{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

#### F.4 ReplayLLMService

**New file**: `backend/omoi_os/services/replay_llm_service.py`

```python
class ReplayLLMService:
    """Returns cached LLM responses from recordings. Zero API calls.

    In strict mode, raises an error on cache miss.
    In lenient mode, returns a placeholder response.
    """

    def __init__(self, recording_dir: str = ".llm-recordings", strict: bool = False):
        self._recording_dir = Path(recording_dir)
        self._strict = strict
        self._cache: dict[str, dict] = {}
        self._load_recordings()

    def _load_recordings(self):
        """Load all recordings into memory on startup."""
        if not self._recording_dir.exists():
            return
        for path in self._recording_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                self._cache[data["hash"]] = data
            except (json.JSONDecodeError, KeyError):
                continue

    async def structured_output(self, prompt: str, output_type: type, **kwargs):
        """Return cached response or placeholder."""
        hash_key = self._compute_hash(prompt, output_type, kwargs.get("model"))

        if hash_key in self._cache:
            recording = self._cache[hash_key]
            return output_type.model_validate(recording["response"])

        if self._strict:
            raise LookupError(
                f"No recording found for hash {hash_key} "
                f"(model={kwargs.get('model')}, output_type={output_type.__name__}). "
                f"Run in 'record' mode first to capture this interaction."
            )

        # Lenient mode: return a default instance
        return self._create_placeholder(output_type)

    def _create_placeholder(self, output_type: type):
        """Create a minimal valid instance of the output type."""
        # Use Pydantic's model_construct for zero-validation instantiation
        fields = {}
        for name, field in output_type.model_fields.items():
            if field.default is not None:
                fields[name] = field.default
            elif field.annotation == str:
                fields[name] = f"[placeholder: {name}]"
            elif field.annotation == list:
                fields[name] = []
            elif field.annotation == dict:
                fields[name] = {}
            elif field.annotation == bool:
                fields[name] = False
            elif field.annotation in (int, float):
                fields[name] = 0
        return output_type.model_construct(**fields)
```

#### F.5 NullLLMService

**New file**: `backend/omoi_os/services/null_llm_service.py`

```python
class NullLLMService:
    """LLM service that never crashes and never makes API calls.

    Returns empty/default responses for any request. Used for:
    - Server bootstrap testing (does the app start?)
    - Endpoint testing that doesn't depend on LLM output
    - CI smoke tests
    """

    async def structured_output(self, prompt: str, output_type: type, **kwargs):
        """Return a default instance of the output type."""
        return self._create_default(output_type)

    def _create_default(self, output_type: type):
        """Same logic as ReplayLLMService._create_placeholder."""
        # ... (same implementation as F.4 placeholder)
```

#### F.6 LLM Service Factory

**New file**: `backend/omoi_os/services/llm_factory.py`

```python
def create_llm_service(mode: str | None = None) -> LLMService:
    """Create the appropriate LLM service based on config.

    Reads `llm.mode` from config/base.yaml:
    - "live" (default) → PydanticAIService (production)
    - "record" → RecordingLLMService wrapping PydanticAIService
    - "replay" → ReplayLLMService (offline, deterministic)
    - "null" → NullLLMService (bootstrap, startup testing)
    """
    settings = get_app_settings()
    llm_mode = mode or getattr(settings.llm, "mode", "live")

    if llm_mode == "null":
        return NullLLMService()
    elif llm_mode == "replay":
        return ReplayLLMService(
            recording_dir=settings.llm.recording_dir,
            strict=settings.llm.replay_strict,
        )
    elif llm_mode == "record":
        inner = PydanticAIService()  # Live service
        return RecordingLLMService(inner=inner, recording_dir=settings.llm.recording_dir)
    else:
        return PydanticAIService()  # Live (default)
```

#### F.7 Integration Points

**Modified file**: `backend/omoi_os/api/main.py`

Replace direct `PydanticAIService()` instantiation with the factory:

```python
# Current:
# llm_service = PydanticAIService()

# New:
from omoi_os.services.llm_factory import create_llm_service
llm_service = create_llm_service()
```

**Modified file**: `backend/omoi_os/workers/orchestrator_worker.py`

Same change — the orchestrator worker's LLM service initialization uses the factory.

**Modified file**: `backend/omoi_os/config.py`

```python
class LLMSettings(OmoiBaseSettings):
    yaml_section = "llm"
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")
    mode: str = "live"
    recording_dir: str = ".llm-recordings"
    replay_strict: bool = False
```

#### F.8 Agent SDK Recording (Spec Phases)

Spec phases use the Claude Agent SDK (`claude_sdk.query()`) instead of `structured_output()`. Recording these requires intercepting at a different level.

**Modified file**: `subsystems/spec-sandbox/src/spec_sandbox/worker/state_machine.py`

Add a recording wrapper around the agent SDK client:

```python
class RecordingAgentClient:
    """Wraps claude_sdk.ClaudeSDKClient to record full turn sequences."""

    def __init__(self, inner_client, recording_dir: str):
        self._inner = inner_client
        self._recording_dir = Path(recording_dir) / "agent-sessions"
        self._recording_dir.mkdir(parents=True, exist_ok=True)

    async def query(self, prompt: str, **kwargs):
        session_id = f"{kwargs.get('phase', 'unknown')}-{uuid4().hex[:8]}"
        result = await self._inner.query(prompt=prompt, **kwargs)

        recording = {
            "session_id": session_id,
            "phase": kwargs.get("phase"),
            "prompt": prompt,
            "final_result": result,
            "recorded_at": utc_now().isoformat(),
        }
        path = self._recording_dir / f"{session_id}.json"
        path.write_text(json.dumps(recording, indent=2, default=str))

        return result
```

In replay mode, the spec state machine loads reference outputs from `subsystems/spec-sandbox/src/spec_sandbox/references/` (which already exist) instead of calling the agent SDK.

---

### Part G: Local Git Provider

Abstract Git operations behind a provider protocol so branch creation, merging, and PR workflows run against local bare repos instead of requiring GitHub OAuth tokens.

#### G.1 GitProvider Protocol

**New file**: `backend/omoi_os/services/git_provider.py`

```python
from typing import Protocol, Optional
from dataclasses import dataclass


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
    conflict_files: list[str] | None = None


class GitProvider(Protocol):
    """Protocol for Git hosting operations.

    Abstracts GitHub API calls so workflows can run against
    local bare repos in development.
    """

    async def create_branch(
        self, repo_full_name: str, branch_name: str, source_sha: str
    ) -> BranchInfo:
        """Create a new branch from a source commit."""
        ...

    async def delete_branch(self, repo_full_name: str, branch_name: str) -> None:
        """Delete a branch."""
        ...

    async def get_branch(self, repo_full_name: str, branch_name: str) -> Optional[BranchInfo]:
        """Get branch info, or None if it doesn't exist."""
        ...

    async def list_branches(self, repo_full_name: str) -> list[BranchInfo]:
        """List all branches in the repository."""
        ...

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        source_branch: str,
        target_branch: str,
        body: str = "",
    ) -> PullRequestInfo:
        """Create a pull request (or local merge request)."""
        ...

    async def merge_pull_request(
        self, repo_full_name: str, pr_id: str, merge_method: str = "merge"
    ) -> PullRequestInfo:
        """Merge a pull request."""
        ...

    async def get_default_branch(self, repo_full_name: str) -> str:
        """Get the name of the default branch (e.g., 'main')."""
        ...

    async def clone_repo(self, repo_full_name: str, target_dir: str) -> str:
        """Clone the repository to a local directory. Returns the path."""
        ...
```

#### G.2 GitHubProvider (Wraps Existing Code)

**New file**: `backend/omoi_os/services/github_provider.py`

```python
class GitHubProvider:
    """GitProvider backed by GitHub API. Wraps existing GitHubAPIService."""

    def __init__(self, github_api: GitHubAPIService):
        self._api = github_api

    async def create_branch(self, repo_full_name, branch_name, source_sha):
        owner, repo = repo_full_name.split("/")
        ref = await self._api.create_branch(owner, repo, branch_name, source_sha)
        return BranchInfo(name=branch_name, sha=ref["object"]["sha"])

    async def delete_branch(self, repo_full_name, branch_name):
        owner, repo = repo_full_name.split("/")
        await self._api.delete_branch(owner, repo, branch_name)

    async def create_pull_request(self, repo_full_name, title, source_branch, target_branch, body=""):
        owner, repo = repo_full_name.split("/")
        pr = await self._api.create_pull_request(owner, repo, title, source_branch, target_branch, body)
        return PullRequestInfo(
            id=str(pr["number"]), title=title,
            source_branch=source_branch, target_branch=target_branch,
            status="open",
        )

    # ... remaining methods wrap GitHubAPIService calls
```

#### G.3 LocalGitProvider

**New file**: `backend/omoi_os/services/local_git_provider.py`

```python
import asyncio
from pathlib import Path


class LocalGitProvider:
    """GitProvider using local bare Git repositories. Dev-only.

    Creates bare repos on disk to simulate GitHub. Branches, merges,
    and PR-like records are all local. No network calls.

    Benefits:
    - Zero GitHub dependency — works fully offline
    - Instant operations (no API rate limits)
    - Full git log, diff, merge-tree available locally
    - Repos persist across restarts (in .local-repos/)
    """

    def __init__(self, repos_dir: str = ".local-repos"):
        self._repos_dir = Path(repos_dir)
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._pull_requests: dict[str, PullRequestInfo] = {}
        self._pr_counter = 0

    def _repo_path(self, repo_full_name: str) -> Path:
        """Get the path to a bare repo, creating it if needed."""
        safe_name = repo_full_name.replace("/", "--")
        return self._repos_dir / f"{safe_name}.git"

    async def _ensure_repo(self, repo_full_name: str) -> Path:
        """Ensure a bare repo exists for this repo name."""
        path = self._repo_path(repo_full_name)
        if not path.exists():
            await self._run_git(None, "init", "--bare", str(path))
        return path

    async def create_branch(self, repo_full_name, branch_name, source_sha):
        repo_path = await self._ensure_repo(repo_full_name)
        await self._run_git(repo_path, "branch", branch_name, source_sha)
        return BranchInfo(name=branch_name, sha=source_sha)

    async def delete_branch(self, repo_full_name, branch_name):
        repo_path = self._repo_path(repo_full_name)
        await self._run_git(repo_path, "branch", "-D", branch_name)

    async def get_branch(self, repo_full_name, branch_name):
        repo_path = self._repo_path(repo_full_name)
        result = await self._run_git(
            repo_path, "rev-parse", "--verify", f"refs/heads/{branch_name}",
            check=False,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.decode().strip()
        return BranchInfo(name=branch_name, sha=sha)

    async def list_branches(self, repo_full_name):
        repo_path = self._repo_path(repo_full_name)
        result = await self._run_git(repo_path, "branch", "--format=%(refname:short) %(objectname)")
        branches = []
        for line in result.stdout.decode().strip().split("\n"):
            if not line.strip():
                continue
            parts = line.strip().split()
            branches.append(BranchInfo(name=parts[0], sha=parts[1] if len(parts) > 1 else ""))
        return branches

    async def create_pull_request(self, repo_full_name, title, source_branch, target_branch, body=""):
        """Simulate a pull request as a local record."""
        self._pr_counter += 1
        pr_id = f"local-pr-{self._pr_counter}"
        pr = PullRequestInfo(
            id=pr_id, title=title,
            source_branch=source_branch, target_branch=target_branch,
            status="open",
        )
        self._pull_requests[pr_id] = pr
        return pr

    async def merge_pull_request(self, repo_full_name, pr_id, merge_method="merge"):
        """Perform a local git merge for the PR."""
        pr = self._pull_requests.get(pr_id)
        if not pr:
            raise ValueError(f"PR {pr_id} not found")

        repo_path = self._repo_path(repo_full_name)
        # Perform the actual merge in the bare repo
        result = await self._run_git(
            repo_path, "merge-base", pr.source_branch, pr.target_branch,
            check=False,
        )

        pr.status = "merged"
        merge_result = await self._run_git(
            repo_path, "rev-parse", pr.source_branch, check=False,
        )
        pr.merge_sha = merge_result.stdout.decode().strip()
        return pr

    async def get_default_branch(self, repo_full_name):
        repo_path = self._repo_path(repo_full_name)
        result = await self._run_git(
            repo_path, "symbolic-ref", "--short", "HEAD", check=False,
        )
        if result.returncode == 0:
            return result.stdout.decode().strip()
        return "main"

    async def clone_repo(self, repo_full_name, target_dir):
        """Clone from the local bare repo."""
        repo_path = await self._ensure_repo(repo_full_name)
        await self._run_git(None, "clone", str(repo_path), target_dir)
        return target_dir

    async def _run_git(self, repo_path, *args, check=True):
        cmd = ["git"]
        if repo_path:
            cmd.extend(["-C", str(repo_path)])
        cmd.extend(args)
        result = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()
        if check and result.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{stderr.decode()}")
        result.stdout = stdout
        return result
```

#### G.4 Git Provider Factory

**New file**: `backend/omoi_os/services/git_factory.py`

```python
def create_git_provider(github_api=None) -> GitProvider:
    """Create the appropriate GitProvider based on config.

    Reads `git.provider` from config/base.yaml:
    - "github" (default) → GitHubProvider (production)
    - "local" → LocalGitProvider (development)
    """
    settings = get_app_settings()
    provider_type = getattr(settings.git, "provider", "github")

    if provider_type == "local":
        return LocalGitProvider(repos_dir=settings.git.local_repos_dir)
    else:
        if github_api is None:
            raise ValueError("GitHubProvider requires a GitHubAPIService instance")
        return GitHubProvider(github_api)
```

#### G.5 Configuration

**Modified file**: `backend/config/base.yaml`

```yaml
git:
  provider: "github"         # "github" | "local"
  local_repos_dir: ".local-repos"
```

**Modified file**: `backend/omoi_os/config.py`

```python
class GitSettings(OmoiBaseSettings):
    yaml_section = "git"
    model_config = SettingsConfigDict(env_prefix="GIT_", extra="ignore")
    provider: str = "github"
    local_repos_dir: str = ".local-repos"
```

#### G.6 Integration Points

The `GitProvider` replaces direct `GitHubAPIService` calls in:

| File | Current Usage | New Usage |
|------|---------------|-----------|
| `backend/omoi_os/services/branch_workflow.py` | `self.github_api.create_branch(...)` | `self.git_provider.create_branch(...)` |
| `backend/omoi_os/services/convergence_merge_service.py` | `self.github_api.create_pull_request(...)` | `self.git_provider.create_pull_request(...)` |
| `backend/omoi_os/workers/orchestrator_worker.py` | Branch creation before sandbox spawn | Uses `git_provider` from factory |

Note: `backend/omoi_os/services/sandbox_git_operations.py` already uses local git commands (no GitHub API). It doesn't need changes.

---

### Part H: Spec Pipeline Fixture Mode

Run the spec state machine against pre-recorded reference outputs so spec logic (evaluators, transitions, task generation) is testable without live Claude Agent SDK calls.

#### H.1 What Already Exists

The spec pipeline has excellent fixture infrastructure that's currently unused:

- **Reference outputs**: `subsystems/spec-sandbox/src/spec_sandbox/references/explore_output.json`, `requirements_output.json`, `design_output.json`, `tasks_output.json` — complete phase output examples
- **Phase evaluators**: `subsystems/spec-sandbox/src/spec_sandbox/evaluators/phases.py` — all pure logic, no LLM calls
- **SYNC phase**: `backend/omoi_os/services/spec_sync.py` — pure DB logic, no LLM calls
- **Task generation**: `backend/omoi_os/services/spec_task_execution.py` — SpecTask → Task conversion, no LLM

The gap: there's no way to feed these fixtures through the pipeline and verify the downstream logic works correctly.

#### H.2 Fixture Mode Configuration

**Modified file**: `backend/config/base.yaml`

```yaml
spec:
  fixture_mode: false        # Use reference outputs instead of live Claude
  fixture_dir: "subsystems/spec-sandbox/src/spec_sandbox/references"
```

#### H.3 FixturePhaseRunner

**New file**: `backend/omoi_os/services/fixture_phase_runner.py`

```python
class FixturePhaseRunner:
    """Runs spec phases using pre-recorded reference outputs instead of Claude.

    This enables testing the full pipeline:
    1. Load fixture output for a phase
    2. Run the phase evaluator against it (pure logic)
    3. If evaluation passes, transition to next phase
    4. At SYNC phase, run real sync logic (SpecSync → task generation)

    The evaluators and sync logic are the same as production —
    only the LLM calls are replaced with fixtures.
    """

    PHASE_ORDER = ["explore", "requirements", "design", "tasks", "sync"]

    def __init__(self, fixture_dir: str, db=None):
        self._fixture_dir = Path(fixture_dir)
        self._db = db
        self._evaluators = self._load_evaluators()

    def _load_fixture(self, phase: str) -> dict:
        """Load reference output for a phase."""
        fixture_path = self._fixture_dir / f"{phase}_output.json"
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"No fixture found for phase '{phase}' at {fixture_path}. "
                f"Available fixtures: {list(self._fixture_dir.glob('*_output.json'))}"
            )
        return json.loads(fixture_path.read_text())

    async def run_phase(self, phase: str, spec_id: str | None = None) -> PhaseResult:
        """Run a single phase using fixtures.

        Returns:
            PhaseResult with fixture output, evaluation score, and pass/fail.
        """
        fixture_output = self._load_fixture(phase)
        evaluator = self._evaluators.get(phase)

        if evaluator:
            evaluation = evaluator.evaluate(fixture_output)
            return PhaseResult(
                phase=phase,
                output=fixture_output,
                evaluation=evaluation,
                passed=evaluation.passed,
                score=evaluation.score,
            )
        else:
            # SYNC phase — no evaluator, just run the sync logic
            return PhaseResult(
                phase=phase,
                output=fixture_output,
                evaluation=None,
                passed=True,
                score=1.0,
            )

    async def run_full_pipeline(self, spec_id: str | None = None) -> PipelineResult:
        """Run all phases sequentially using fixtures.

        This validates:
        1. Each fixture passes its evaluator
        2. Phase transitions are correct
        3. SYNC generates tasks from the design phase output
        4. Generated tasks have valid dependencies
        """
        results = []
        for phase in self.PHASE_ORDER:
            try:
                result = await self.run_phase(phase, spec_id)
                results.append(result)
                if not result.passed:
                    break  # Stop at first failure, just like production
            except FileNotFoundError:
                break  # No fixture for this phase

        return PipelineResult(
            phases_run=[r.phase for r in results],
            phases_passed=[r.phase for r in results if r.passed],
            all_passed=all(r.passed for r in results),
            results=results,
        )
```

#### H.4 CLI Tool

**New file**: `backend/omoi_os/cli/spec_fixture.py`

```bash
# Run all phases against fixtures
python -m omoi_os.cli.spec_fixture run-all

# Run a single phase
python -m omoi_os.cli.spec_fixture run-phase explore

# Validate that fixtures pass evaluators
python -m omoi_os.cli.spec_fixture validate

# Show what tasks would be generated from the design fixture
python -m omoi_os.cli.spec_fixture show-tasks

# Output:
# Phase: explore     ✅ score=0.92
# Phase: requirements ✅ score=0.88
# Phase: design      ✅ score=0.95
# Phase: tasks       ✅ score=0.90
# Phase: sync        ✅ generated 8 tasks
#   task/1: "Implement auth middleware" [implementation] depends_on=[]
#   task/2: "Add auth tests"           [validation]     depends_on=[1]
#   ...
```

---

### Part I: Monitoring Dry-Run Mode

Feed recorded agent sessions to Guardian and Conductor so you can see their scoring and intervention decisions without running live agents.

#### I.1 The Problem

The monitoring system (`backend/omoi_os/services/monitoring_loop.py`) runs three loops:
- **Guardian** (every 60s): Scores agent trajectory alignment, detects drift, injects steering interventions
- **Conductor** (every 5min): System-wide coherence analysis, duplicate detection, cross-agent coordination
- **Health Check** (every 30s): Basic liveness checks

All three require running agents to have anything to monitor. There's no way to test Guardian's scoring logic or Conductor's coherence analysis without the full pipeline running.

#### I.2 Monitoring Replay Mode

**Modified file**: `backend/config/base.yaml`

```yaml
monitoring:
  replay_mode: false
  replay_dir: ".monitoring-recordings"
```

#### I.3 Agent Session Snapshots

**New file**: `backend/omoi_os/services/monitoring_replay.py`

```python
@dataclass
class AgentSessionSnapshot:
    """A recorded snapshot of agent state for monitoring replay."""
    agent_id: str
    task_id: str
    sandbox_id: str
    phase: str
    started_at: str
    events: list[dict]          # Chronological agent events
    tool_calls: list[dict]      # Tools used, files touched
    current_output: str         # Latest agent output
    task_description: str       # What the agent was assigned
    elapsed_seconds: int
    status: str                 # "running" | "completed" | "failed"


class MonitoringReplayService:
    """Feeds recorded agent sessions to Guardian and Conductor.

    Workflow:
    1. Record agent sessions during a real run (recording mode)
    2. Replay them through Guardian to see trajectory scores
    3. Replay them through Conductor to see coherence analysis
    4. Iterate on scoring logic without re-running agents
    """

    def __init__(self, replay_dir: str, guardian, conductor):
        self._replay_dir = Path(replay_dir)
        self._guardian = guardian
        self._conductor = conductor

    async def replay_guardian(self, session_file: str) -> GuardianReplayResult:
        """Run Guardian analysis against a recorded session.

        Returns:
            GuardianReplayResult with trajectory score, drift detection,
            and what intervention (if any) Guardian would have made.
        """
        snapshot = self._load_snapshot(session_file)

        # Feed the snapshot to Guardian's trajectory analyzer
        trajectory_score = await self._guardian.analyze_trajectory(
            agent_id=snapshot.agent_id,
            task_description=snapshot.task_description,
            events=snapshot.events,
            tool_calls=snapshot.tool_calls,
            elapsed_seconds=snapshot.elapsed_seconds,
        )

        intervention = None
        if trajectory_score.alignment < self._guardian.alignment_threshold:
            intervention = await self._guardian.generate_intervention(
                agent_id=snapshot.agent_id,
                score=trajectory_score,
                task_description=snapshot.task_description,
            )

        return GuardianReplayResult(
            session_file=session_file,
            agent_id=snapshot.agent_id,
            trajectory_score=trajectory_score,
            would_intervene=intervention is not None,
            intervention=intervention,
        )

    async def replay_conductor(self, session_files: list[str]) -> ConductorReplayResult:
        """Run Conductor analysis against multiple recorded sessions.

        Tests system-wide coherence, duplicate detection, and
        cross-agent coordination logic.
        """
        snapshots = [self._load_snapshot(f) for f in session_files]

        coherence = await self._conductor.analyze_coherence(
            active_agents=[s.agent_id for s in snapshots],
            task_descriptions={s.agent_id: s.task_description for s in snapshots},
            current_outputs={s.agent_id: s.current_output for s in snapshots},
        )

        return ConductorReplayResult(
            sessions_analyzed=len(snapshots),
            coherence_score=coherence.score,
            duplicates_detected=coherence.duplicates,
            coordination_issues=coherence.issues,
            recommended_actions=coherence.actions,
        )
```

#### I.4 Recording Agent Sessions

Agent sessions are recorded automatically when `monitoring.replay_mode: true` and the system is running in `record` mode. The `EventBusService` already publishes agent events — the replay service subscribes and persists them:

```python
class AgentSessionRecorder:
    """Records agent sessions from EventBus for later replay."""

    def __init__(self, event_bus, recording_dir: str):
        self._event_bus = event_bus
        self._recording_dir = Path(recording_dir) / "agent-sessions"
        self._recording_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, AgentSessionSnapshot] = {}

    async def start(self):
        """Subscribe to agent events and record them."""
        await self._event_bus.subscribe(
            pattern="events.agent.*",
            callback=self._on_agent_event,
        )

    async def _on_agent_event(self, event: SystemEvent):
        agent_id = event.entity_id
        if agent_id not in self._active_sessions:
            self._active_sessions[agent_id] = AgentSessionSnapshot(
                agent_id=agent_id, events=[], tool_calls=[], ...
            )
        session = self._active_sessions[agent_id]
        session.events.append(event.payload)

        if event.event_type in ("agent.completed", "agent.failed"):
            # Session ended — write to disk
            self._save_session(session)
            del self._active_sessions[agent_id]
```

#### I.5 CLI Tool

```bash
# Replay Guardian analysis on a recorded session
python -m omoi_os.cli.monitoring_replay guardian .monitoring-recordings/agent-sessions/agent-7.json

# Output:
# Guardian Replay: agent-7
#   Trajectory Score: 0.73 (threshold: 0.60)
#   Alignment: 0.81
#   Drift Detected: No
#   Would Intervene: No
#   Elapsed: 42s

# Replay Conductor across multiple sessions
python -m omoi_os.cli.monitoring_replay conductor .monitoring-recordings/agent-sessions/

# Output:
# Conductor Replay: 5 sessions
#   Coherence Score: 0.85
#   Duplicates: agent-3 ↔ agent-5 (both editing auth.ts)
#   Coordination Issues: 1
#     - agent-3 and agent-5 have overlapping file edits
#   Recommended Actions:
#     - Pause agent-5, let agent-3 finish first
```

---

### Part J: Dev Bootstrap & Health Dashboard

A single command that checks all dependencies, starts all services in the right order, and shows a live health dashboard so developers know exactly what's running, what's broken, and how to fix it.

#### J.1 The Problem

Starting OmoiOS locally requires:
1. PostgreSQL running on port 15432
2. Redis running on port 16379
3. Environment variables set (API keys, database URL, etc.)
4. Python dependencies installed
5. Database migrations applied
6. API server started
7. Orchestrator worker started (separate process)
8. Frontend started (optional)

If any step fails, the error message rarely tells you what to do next. Missing PostgreSQL gives a connection error. Missing Redis gives a different connection error. Missing API key gives a ValueError deep in a service constructor. Each failure requires different knowledge to diagnose.

#### J.2 Dependency Checker

**New file**: `backend/omoi_os/cli/bootstrap.py`

```python
"""Dev environment bootstrap and health checking.

Usage:
    python -m omoi_os.cli.bootstrap check     # Check all dependencies
    python -m omoi_os.cli.bootstrap start      # Start all services
    python -m omoi_os.cli.bootstrap health     # Live health dashboard
"""

@dataclass
class DependencyCheck:
    name: str
    status: str           # "ok" | "missing" | "wrong_version" | "not_configured"
    required: bool        # True = hard dependency, False = optional
    details: str          # Human-readable explanation
    fix_command: str      # Command to fix the issue
    category: str         # "runtime" | "database" | "service" | "config"


class BootstrapChecker:
    """Checks all dependencies needed to run OmoiOS locally."""

    async def check_all(self) -> list[DependencyCheck]:
        checks = []

        # Runtime dependencies
        checks.append(await self._check_python())
        checks.append(await self._check_node())
        checks.append(await self._check_docker())
        checks.append(await self._check_uv())

        # Database
        checks.append(await self._check_postgres())
        checks.append(await self._check_redis())

        # Configuration
        checks.append(await self._check_env_file())
        checks.append(await self._check_llm_key())
        checks.append(await self._check_github_token())
        checks.append(await self._check_claude_key())
        checks.append(await self._check_daytona_key())

        # Python environment
        checks.append(await self._check_python_deps())
        checks.append(await self._check_migrations())

        return checks

    async def _check_postgres(self) -> DependencyCheck:
        try:
            result = await asyncio.create_subprocess_exec(
                "pg_isready", "-h", "localhost", "-p", "15432",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            if result.returncode == 0:
                return DependencyCheck("PostgreSQL", "ok", True,
                    "Running on port 15432", "", "database")
            else:
                return DependencyCheck("PostgreSQL", "missing", True,
                    "Not running on port 15432",
                    "docker run -d --name omoios-pg -p 15432:5432 -e POSTGRES_PASSWORD=postgres postgres:16",
                    "database")
        except FileNotFoundError:
            return DependencyCheck("PostgreSQL", "missing", True,
                "pg_isready not found",
                "brew install postgresql@16 (or use Docker)",
                "database")

    async def _check_llm_key(self) -> DependencyCheck:
        """Check LLM config — key is only required in 'live' mode."""
        settings = get_app_settings()
        llm_mode = getattr(settings.llm, "mode", "live")

        if llm_mode in ("null", "replay"):
            return DependencyCheck("LLM API Key", "ok", False,
                f"Not required (llm.mode={llm_mode})", "", "config")

        has_key = bool(os.getenv("FIREWORKS_API_KEY") or os.getenv("LLM_API_KEY"))
        if has_key:
            return DependencyCheck("LLM API Key", "ok", True,
                "Fireworks API key configured", "", "config")
        else:
            return DependencyCheck("LLM API Key", "not_configured", True,
                "No LLM API key found. Server will crash in 'live' mode.",
                "Set FIREWORKS_API_KEY in .env, or set llm.mode to 'null' or 'replay' in config/base.yaml",
                "config")

    # ... similar methods for each dependency
```

#### J.3 Display Output

```bash
$ python -m omoi_os.cli.bootstrap check

OmoiOS Dev Environment Check
═══════════════════════════════════════════════════════════

Runtime
  ✅ Python         3.12.4
  ✅ Node.js        22.11.0
  ✅ Docker         27.4.0
  ✅ uv             0.5.14

Database
  ✅ PostgreSQL     Running on :15432
  ✅ Redis          Running on :16379

Configuration
  ✅ .env file      Found
  ⚠️  LLM API Key   Not set (set llm.mode: "null" to bypass)
  ⚠️  GitHub Token  Not set (set git.provider: "local" to bypass)
  ⚠️  Claude Key    Not set (needed for spec execution only)
  ⚠️  Daytona Key   Not set (set sandbox.provider: "local" to bypass)

Python Environment
  ✅ Dependencies   All installed (uv sync)
  ✅ Migrations     Up to date (73 applied)

═══════════════════════════════════════════════════════════
Status: Ready for local development (with local providers)

Recommended .env additions for full functionality:
  FIREWORKS_API_KEY=...    # For live LLM calls
  GITHUB_TOKEN=...         # For GitHub integration

Or configure local-only mode in config/base.yaml:
  llm.mode: "null"         # Skip LLM calls
  git.provider: "local"    # Use local bare repos
  sandbox.provider: "local" # Use Docker containers
```

#### J.4 Justfile Integration

**Modified file**: `Justfile`

```just
# Check all development dependencies
bootstrap:
    uv run python -m omoi_os.cli.bootstrap check

# Start all services with health monitoring
dev-local:
    uv run python -m omoi_os.cli.bootstrap start --mode local

# Show live health dashboard
health:
    uv run python -m omoi_os.cli.bootstrap health
```

#### J.5 Local-Only Quick Start

**New file**: `backend/config/local.yaml`

A configuration overlay that sets all providers to local mode:

```yaml
# config/local.yaml — Full local development, zero external services
# Usage: OMOIOS_CONFIG=local just dev-all

llm:
  mode: "null"

git:
  provider: "local"

sandbox:
  provider: "local"

event_bus:
  persist_events: true

orchestrator:
  dry_run: true

monitoring:
  replay_mode: true
```

With this config, a developer can `OMOIOS_CONFIG=local just dev-all` and have the entire system running locally with zero API keys.

---

### Part K: Unified Mock Service Layer

Replace ad-hoc `MagicMock` usage across 113 test files with reusable, typed mock implementations that match the actual service interfaces.

#### K.1 The Problem

Current test mocking state:

```python
# Typical test file today (backend/tests/unit/services/test_something.py):
from unittest.mock import MagicMock, AsyncMock, patch

@patch("omoi_os.services.llm_service.get_llm_service")
async def test_something(mock_llm):
    mock_llm.return_value.structured_output = AsyncMock(return_value=SomeModel(...))
    # ... test logic
```

Problems:
- Every test reinvents the mock setup
- Mocks don't verify interface compliance (MagicMock accepts anything)
- No shared fixtures — copy-paste across 113 files
- If `structured_output()` signature changes, mocks still pass (false confidence)
- LLM tests make real API calls — no `@pytest.mark.requires_llm` to skip them

#### K.2 Mock Implementations

**New directory**: `backend/tests/mocks/`

**New file**: `backend/tests/mocks/__init__.py`

```python
from tests.mocks.llm import MockLLMService
from tests.mocks.github import MockGitHubService
from tests.mocks.daytona import MockDaytonaService
from tests.mocks.stripe import MockStripeService
from tests.mocks.event_bus import MockEventBus

__all__ = [
    "MockLLMService",
    "MockGitHubService",
    "MockDaytonaService",
    "MockStripeService",
    "MockEventBus",
]
```

**New file**: `backend/tests/mocks/llm.py`

```python
class MockLLMService:
    """Mock LLM service with canned responses and call tracking.

    Unlike MagicMock, this enforces the structured_output() interface
    and provides useful defaults for common output types.
    """

    def __init__(self):
        self.calls: list[dict] = []
        self._responses: dict[str, Any] = {}
        self._default_responses: dict[type, Any] = {}

    def set_response(self, output_type: type, response: Any):
        """Set a canned response for a specific output type."""
        self._default_responses[output_type] = response

    def set_response_for_prompt(self, prompt_contains: str, response: Any):
        """Set a response triggered by prompt content."""
        self._responses[prompt_contains] = response

    async def structured_output(self, prompt: str, output_type: type, **kwargs) -> Any:
        """Mock structured_output that tracks calls and returns canned responses."""
        self.calls.append({
            "prompt": prompt,
            "output_type": output_type.__name__,
            "kwargs": kwargs,
        })

        # Check prompt-specific responses first
        for trigger, response in self._responses.items():
            if trigger in prompt:
                return response

        # Check type-specific defaults
        if output_type in self._default_responses:
            return self._default_responses[output_type]

        # Generate a minimal valid instance
        return self._create_default(output_type)

    def assert_called_with_type(self, output_type: type):
        """Assert that structured_output was called with a specific output type."""
        types_called = [c["output_type"] for c in self.calls]
        assert output_type.__name__ in types_called, (
            f"Expected call with output_type={output_type.__name__}, "
            f"but only got: {types_called}"
        )

    def assert_call_count(self, expected: int):
        """Assert the number of structured_output calls."""
        assert len(self.calls) == expected, (
            f"Expected {expected} calls, got {len(self.calls)}"
        )
```

**New file**: `backend/tests/mocks/github.py`

```python
class MockGitHubService:
    """Mock GitHub API service with in-memory branch/PR tracking.

    Simulates GitHub operations without network calls.
    Tracks all operations for assertion in tests.
    """

    def __init__(self):
        self.branches: dict[str, dict] = {"main": {"sha": "abc123"}}
        self.pull_requests: list[dict] = []
        self.operations: list[dict] = []

    async def create_branch(self, owner, repo, branch_name, source_sha):
        self.operations.append({"op": "create_branch", "branch": branch_name})
        self.branches[branch_name] = {"sha": source_sha}
        return {"ref": f"refs/heads/{branch_name}", "object": {"sha": source_sha}}

    async def create_pull_request(self, owner, repo, title, head, base, body=""):
        pr = {"number": len(self.pull_requests) + 1, "title": title,
              "head": head, "base": base, "state": "open"}
        self.pull_requests.append(pr)
        self.operations.append({"op": "create_pr", "title": title})
        return pr

    async def get_repository(self, owner, repo):
        return {"full_name": f"{owner}/{repo}", "default_branch": "main"}

    # ... remaining methods mirror GitHubAPIService interface
```

**New file**: `backend/tests/mocks/event_bus.py`

```python
class MockEventBus:
    """Mock EventBus that captures published events for assertion.

    No Redis dependency. Events are stored in memory.
    """

    def __init__(self):
        self.published_events: list[SystemEvent] = []
        self._subscribers: dict[str, list[callable]] = {}

    async def publish(self, event: SystemEvent):
        self.published_events.append(event)
        # Notify in-memory subscribers
        for pattern, callbacks in self._subscribers.items():
            if self._matches(event.event_type, pattern):
                for callback in callbacks:
                    await callback(event)

    async def subscribe(self, pattern: str, callback: callable):
        self._subscribers.setdefault(pattern, []).append(callback)

    def assert_event_published(self, event_type: str):
        types = [e.event_type for e in self.published_events]
        assert event_type in types, f"Expected event {event_type}, published: {types}"

    def get_events_of_type(self, event_type: str) -> list[SystemEvent]:
        return [e for e in self.published_events if e.event_type == event_type]

    def clear(self):
        self.published_events.clear()
```

#### K.3 Pytest Fixtures

**New file**: `backend/tests/mocks/conftest_fixtures.py`

Shared fixtures that any test can import:

```python
import pytest
from tests.mocks import MockLLMService, MockGitHubService, MockEventBus


@pytest.fixture
def mock_llm():
    """Provides a MockLLMService with call tracking."""
    return MockLLMService()


@pytest.fixture
def mock_github():
    """Provides a MockGitHubService with in-memory branch/PR state."""
    return MockGitHubService()


@pytest.fixture
def mock_event_bus():
    """Provides a MockEventBus that captures events without Redis."""
    return MockEventBus()


@pytest.fixture
def mock_daytona():
    """Provides a MockDaytonaService with in-memory sandbox tracking."""
    return MockDaytonaService()
```

These fixtures are registered in `backend/tests/conftest.py` so they're available globally.

#### K.4 Pytest Markers

**Modified file**: `backend/pyproject.toml` (or `pytest.ini`)

```ini
[tool.pytest.ini_options]
markers = [
    "requires_llm: test requires a live LLM API key (deselect with -m 'not requires_llm')",
    "requires_github: test requires a GitHub OAuth token",
    "requires_daytona: test requires Daytona access",
    "requires_redis: test requires a Redis instance",
    "slow: test takes >10s to run",
]
```

**New file**: `backend/tests/markers.py`

```python
import os
import pytest

requires_llm = pytest.mark.skipif(
    not os.getenv("FIREWORKS_API_KEY") and not os.getenv("LLM_API_KEY"),
    reason="Requires LLM API key (set FIREWORKS_API_KEY or LLM_API_KEY)",
)

requires_github = pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="Requires GitHub token (set GITHUB_TOKEN)",
)

requires_daytona = pytest.mark.skipif(
    not os.getenv("DAYTONA_API_KEY"),
    reason="Requires Daytona API key (set DAYTONA_API_KEY)",
)
```

Usage in tests:

```python
from tests.markers import requires_llm

@requires_llm
async def test_real_llm_call():
    """This test only runs when an LLM API key is available."""
    ...
```

#### K.5 Migration Path

Existing tests continue to work unchanged. The migration is incremental:

1. Add `backend/tests/mocks/` with all mock implementations
2. Register fixtures in `conftest.py`
3. Add pytest markers to `pyproject.toml`
4. Migrate tests file-by-file: replace `MagicMock` with typed mocks
5. Add `@requires_llm` markers to tests that make real API calls

No test needs to change immediately — the mocks are additive.

---

### Part L: Frontend Event Replay

Record and replay WebSocket event sequences so the frontend can be developed and tested without running the full backend stack.

#### L.1 The Problem

Frontend development currently requires:
1. Backend API running (FastAPI on :18000)
2. Redis running (for EventBus pub/sub)
3. WebSocket connection to receive real-time events
4. At least one spec/task running to generate events

For UI work on event-driven components (agent monitor, task board, sandbox terminal, spec progress), a developer needs the full stack running just to see data in the UI.

#### L.2 Event Recording

**New file**: `frontend/lib/dev/event-recorder.ts`

```typescript
/**
 * Records WebSocket events to a JSON file for later replay.
 *
 * Usage: Enable with NEXT_PUBLIC_RECORD_EVENTS=true
 * Events are saved to frontend/.event-recordings/{session}.json
 */

interface RecordedEvent {
  timestamp: number;     // ms since recording start
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
}

interface EventRecording {
  recording_id: string;
  started_at: string;
  events: RecordedEvent[];
  metadata: {
    spec_id?: string;
    total_events: number;
    duration_ms: number;
    event_types: string[];
  };
}

class EventRecorder {
  private events: RecordedEvent[] = [];
  private startTime: number = Date.now();

  record(event: SystemEvent): void {
    this.events.push({
      timestamp: Date.now() - this.startTime,
      event_type: event.event_type,
      entity_type: event.entity_type,
      entity_id: event.entity_id,
      payload: event.payload,
    });
  }

  export(): EventRecording {
    return {
      recording_id: crypto.randomUUID(),
      started_at: new Date(this.startTime).toISOString(),
      events: this.events,
      metadata: {
        total_events: this.events.length,
        duration_ms: Date.now() - this.startTime,
        event_types: [...new Set(this.events.map(e => e.event_type))],
      },
    };
  }

  async save(filename?: string): Promise<void> {
    const recording = this.export();
    // In dev mode, POST to a local file-save endpoint
    await fetch('/api/dev/save-recording', {
      method: 'POST',
      body: JSON.stringify(recording),
    });
  }
}
```

#### L.3 Event Replay Provider

**New file**: `frontend/lib/dev/event-replay.ts`

```typescript
/**
 * Replays recorded event sequences through the same hooks
 * the frontend uses for live WebSocket events.
 *
 * Usage: Set NEXT_PUBLIC_EVENT_REPLAY=path/to/recording.json
 */

class EventReplayProvider {
  private recording: EventRecording;
  private eventHandlers: Map<string, Set<(event: SystemEvent) => void>> = new Map();
  private playbackSpeed: number = 1.0;
  private isPlaying: boolean = false;

  constructor(recording: EventRecording) {
    this.recording = recording;
  }

  /**
   * Subscribe to events — same interface as the real WebSocket provider.
   * This means existing hooks work unchanged.
   */
  subscribe(eventType: string, handler: (event: SystemEvent) => void): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);
    return () => this.eventHandlers.get(eventType)?.delete(handler);
  }

  /**
   * Start replaying events with timing preserved.
   */
  async play(speed: number = 1.0): Promise<void> {
    this.playbackSpeed = speed;
    this.isPlaying = true;

    for (const event of this.recording.events) {
      if (!this.isPlaying) break;

      const delay = event.timestamp / this.playbackSpeed;
      await new Promise(resolve => setTimeout(resolve, delay));

      this._emit(event);
    }
  }

  /**
   * Replay all events instantly (for tests).
   */
  replayInstant(): void {
    for (const event of this.recording.events) {
      this._emit(event);
    }
  }

  pause(): void { this.isPlaying = false; }
  resume(): void { this.play(this.playbackSpeed); }

  private _emit(event: RecordedEvent): void {
    const systemEvent: SystemEvent = {
      event_type: event.event_type,
      entity_type: event.entity_type,
      entity_id: event.entity_id,
      payload: event.payload,
    };

    // Emit to specific type subscribers
    this.eventHandlers.get(event.event_type)?.forEach(h => h(systemEvent));
    // Emit to wildcard subscribers
    this.eventHandlers.get('*')?.forEach(h => h(systemEvent));
  }
}
```

#### L.4 Integration with Existing Hooks

**Modified file**: `frontend/providers/websocket-provider.tsx` (or equivalent)

The WebSocket provider checks for replay mode and swaps the data source:

```typescript
function useEventSource() {
  const replayFile = process.env.NEXT_PUBLIC_EVENT_REPLAY;

  if (replayFile) {
    // Dev mode: replay from recording
    const [provider, setProvider] = useState<EventReplayProvider | null>(null);

    useEffect(() => {
      fetch(replayFile)
        .then(r => r.json())
        .then(recording => {
          const replay = new EventReplayProvider(recording);
          setProvider(replay);
          replay.play(1.0); // Real-time replay
        });
    }, [replayFile]);

    return provider;
  }

  // Production: real WebSocket connection
  return useWebSocket();
}
```

Existing hooks (`useAgentMonitor`, `useTaskBoard`, `useSpecProgress`) subscribe through the same interface — they don't know or care whether events come from a WebSocket or a recording.

#### L.5 Sample Recordings

**New directory**: `frontend/.event-recordings/`

Ship a few sample recordings for common workflows:

| Recording | Events | Duration | Description |
|-----------|--------|----------|-------------|
| `spec-explore-complete.json` | ~50 | 2min | Full EXPLORE phase with agent events |
| `multi-task-parallel.json` | ~200 | 5min | 3 agents running in parallel |
| `merge-conflict.json` | ~80 | 3min | Convergence merge with conflict resolution |
| `guardian-intervention.json` | ~60 | 2min | Guardian detects drift and steers agent |

These serve as both test data and onboarding examples.

#### L.6 Configuration

```bash
# Frontend .env.local
NEXT_PUBLIC_EVENT_REPLAY=".event-recordings/multi-task-parallel.json"  # Replay mode
NEXT_PUBLIC_RECORD_EVENTS=true                                         # Recording mode
```

---

### Files Changed Summary

| File | Change Type | Part | Lines (est.) |
|------|-------------|------|-------------|
| `backend/omoi_os/services/recording_llm_service.py` | **New** | F | ~80 |
| `backend/omoi_os/services/replay_llm_service.py` | **New** | F | ~100 |
| `backend/omoi_os/services/null_llm_service.py` | **New** | F | ~30 |
| `backend/omoi_os/services/llm_factory.py` | **New** | F | ~40 |
| `backend/omoi_os/config.py` | Modified | F+G+J | ~40 |
| `backend/config/base.yaml` | Modified | F+G+H+I+J | ~25 |
| `backend/config/local.yaml` | **New** | J | ~20 |
| `backend/omoi_os/api/main.py` | Modified | F+G | ~15 |
| `backend/omoi_os/services/git_provider.py` | **New** | G | ~80 |
| `backend/omoi_os/services/github_provider.py` | **New** | G | ~60 |
| `backend/omoi_os/services/local_git_provider.py` | **New** | G | ~150 |
| `backend/omoi_os/services/git_factory.py` | **New** | G | ~30 |
| `backend/omoi_os/services/fixture_phase_runner.py` | **New** | H | ~120 |
| `backend/omoi_os/cli/spec_fixture.py` | **New** | H | ~80 |
| `backend/omoi_os/services/monitoring_replay.py` | **New** | I | ~180 |
| `backend/omoi_os/cli/monitoring_replay.py` | **New** | I | ~60 |
| `backend/omoi_os/cli/bootstrap.py` | **New** | J | ~300 |
| `backend/tests/mocks/__init__.py` | **New** | K | ~10 |
| `backend/tests/mocks/llm.py` | **New** | K | ~80 |
| `backend/tests/mocks/github.py` | **New** | K | ~80 |
| `backend/tests/mocks/event_bus.py` | **New** | K | ~60 |
| `backend/tests/mocks/conftest_fixtures.py` | **New** | K | ~30 |
| `backend/tests/markers.py` | **New** | K | ~25 |
| `backend/pyproject.toml` | Modified | K | ~10 |
| `frontend/lib/dev/event-recorder.ts` | **New** | L | ~80 |
| `frontend/lib/dev/event-replay.ts` | **New** | L | ~100 |
| `frontend/providers/websocket-provider.tsx` | Modified | L | ~30 |
| `Justfile` | Modified | J | ~15 |
| `backend/tests/unit/services/test_llm_factory.py` | **New** | F | ~80 |
| `backend/tests/unit/services/test_git_provider.py` | **New** | G | ~80 |
| `backend/tests/unit/services/test_fixture_runner.py` | **New** | H | ~60 |
| **Total** | | | **~2,120** |

## Rationale

### Why a Service Abstraction Layer, Not Just Mocks

Mocks (Part K) are for tests. The service abstraction layer (Parts F, G) is for running the actual application locally. These serve different purposes:

| | Mocks (Part K) | Service Abstractions (Parts F, G) |
|---|---|---|
| **Used by** | pytest | Running application |
| **Replaces** | Individual method calls | Entire service implementations |
| **Lifecycle** | Per-test | Application lifetime |
| **State** | Reset each test | Persists across requests |
| **Purpose** | Isolation, speed | End-to-end local workflows |

Both are needed. Mocks alone don't let you run the application. Service abstractions alone don't make tests fast.

### Why Four LLM Modes, Not Just Live/Mock

| Mode | Why It Exists |
|------|---------------|
| `live` | Production and active development with real LLM |
| `record` | Capture real responses to build a replay library |
| `replay` | Deterministic testing, CI, offline development |
| `null` | Startup testing — does the app boot? Do routes work? |

The `null` mode is critical because the current server crashes on startup without an API key. A developer who just wants to test a new endpoint shouldn't need a Fireworks.ai account.

The `record` → `replay` cycle enables a workflow where one developer records LLM interactions, commits the recordings, and all other developers (and CI) use them deterministically.

### Why Not a Generic Mock Layer (e.g., Mockoon, WireMock)

External mock servers add infrastructure complexity. The provider pattern keeps mocking in-process:
- No additional process to start
- No port configuration
- No serialization overhead
- Typed interfaces catch errors at import time, not runtime
- Mock state is inspectable in the debugger

### Why Fixture Mode for Specs, Not Just LLM Replay

LLM replay (Part F) replays individual `structured_output()` calls. But spec phases run 45-turn agent SDK sessions — replaying those is complex and brittle. Fixture mode takes a different approach: skip the LLM entirely and feed pre-computed phase outputs directly to the evaluators and downstream logic. This is faster, more deterministic, and tests what actually matters (the evaluation and task generation logic).

### Why the Bootstrap Tool (Part J) Is Tier 1

Developer experience follows a funnel: **discover → setup → first run → iterate → contribute**. If setup fails, nothing else matters. The bootstrap tool addresses the #1 barrier to contribution: "I cloned the repo, now what?" The health dashboard addresses the #2 barrier: "Something broke, but what?"

### Alternative Considered: Dev Containers / Codespaces

A devcontainer would bundle all dependencies (PostgreSQL, Redis, Python, Node) into a single Docker image. This was considered but rejected because:
- Large image size (~5GB with all dependencies)
- Slow initial build
- Poor IDE integration for some developers
- Doesn't solve the LLM/GitHub/Daytona key problem
- Still need local provider abstractions for the agent execution pipeline

A devcontainer config could be added in the future as a complementary option but doesn't replace the need for service abstractions.

## Backwards Compatibility

**No breaking changes.** All new capabilities are opt-in:

| Capability | Default | How to Enable |
|-----------|---------|---------------|
| LLM Mode | `mode: "live"` | Set `llm.mode` in base.yaml or `LLM_MODE=null` env |
| Git Provider | `provider: "github"` | Set `git.provider: "local"` in base.yaml |
| Spec Fixture Mode | `fixture_mode: false` | Set `spec.fixture_mode: true` |
| Monitoring Replay | `replay_mode: false` | Set `monitoring.replay_mode: true` |
| Dev Bootstrap | Not running | Run `just bootstrap` or `just health` |
| Mock Service Layer | Additive | Import from `tests.mocks` in test files |
| Frontend Event Replay | Disabled | Set `NEXT_PUBLIC_EVENT_REPLAY=path` |
| Local-Only Config | Not active | Use `OMOIOS_CONFIG=local` |

The existing `PydanticAIService` continues to work unchanged as the default LLM service. The existing `GitHubAPIService` continues to work unchanged as the default git provider. No existing test changes required.

## Security Considerations

### LLM Recordings

- Recordings may contain prompt content that includes user data, code snippets, or business logic. The `.llm-recordings/` directory should be in `.gitignore` by default.
- If recordings are committed for CI (shared replay library), they should be reviewed for sensitive content.
- The recording format does NOT include API keys — only prompt/response pairs.

### Local Git Provider

- Local bare repos (`.local-repos/`) contain repository data on disk. This is equivalent to having a local clone — no additional exposure.
- The `LocalGitProvider` does NOT store GitHub tokens — it doesn't need them.

### Mock Services

- Mock services in `backend/tests/mocks/` are test-only code. They should never be used in production paths.
- The `create_llm_service()` factory logs a warning if `mode` is anything other than `live` when `OMOIOS_ENV=production`.

### Frontend Event Recordings

- Event recordings may contain entity IDs, task descriptions, and agent output. These should be sanitized before sharing publicly.
- The recording/replay mechanism runs entirely client-side — no new server endpoints with sensitive data.

### Config Guard

All provider factories include a production guard:

```python
if settings.env == "production" and provider_type != "default_production_provider":
    logger.warning(
        "Non-production provider configured in production environment",
        provider=provider_type,
        service="llm|git|sandbox",
    )
```

## Impact Assessment

**Effort**: Medium-High (~2,120 lines of new code across 7 parts). Parts are independent and can be implemented incrementally.

**Recommended Implementation Order** (combined with OIP-0006):

| Priority | Part | OIP | Lines | Description |
|----------|------|-----|-------|-------------|
| 1 | **J** | 0007 | ~300 | Dev Bootstrap — unblocks every developer |
| 2 | **F** | 0007 | ~250 | LLM Null/Replay — server boots without API keys |
| 3 | **E** | 0006 | ~80 | Task Context Inspector — immediate debug value |
| 4 | **K** | 0007 | ~285 | Mock Service Layer — tests become reliable |
| 5 | **B** | 0006 | ~80 | Dry-Run Mode — validate DAG without sandboxes |
| 6 | **C** | 0006 | ~250 | Terminal Event Stream — runtime observability |
| 7 | **G** | 0007 | ~320 | Local Git Provider — offline branch/merge |
| 8 | **H** | 0007 | ~200 | Spec Fixture Mode — spec logic without Claude |
| 9 | **A** | 0006 | ~290 | SandboxProvider — full local agent execution |
| 10 | **D** | 0006 | ~100 | Branch Strategy Preview — merge prediction |
| 11 | **I** | 0007 | ~240 | Monitoring Dry-Run — Guardian/Conductor testing |
| 12 | **L** | 0007 | ~210 | Frontend Event Replay — UI without backend |

**Infrastructure**: Zero additional infrastructure. All local providers use Docker (already required for Part A) or filesystem.

**Developer Impact**: Transformative. Combined with OIP-0006, a developer can:
1. `just bootstrap` to check all dependencies
2. `OMOIOS_CONFIG=local just dev-all` to start everything locally
3. See the full pipeline running without any API keys
4. Run tests without mocking boilerplate
5. Iterate on spec logic, orchestration logic, and UI independently

**Production Impact**: None. All features are opt-in. Default configuration unchanged.

**Success Metrics**:
- Server boots with `llm.mode: "null"` and no API keys configured
- `just bootstrap` correctly identifies all missing dependencies with fix instructions
- Tests using `MockLLMService` run 10x faster than tests with real API calls
- Spec fixture pipeline produces the same tasks as live execution
- Frontend event replay renders the same UI state as live WebSocket events
- A new developer can go from `git clone` to running system in under 5 minutes

## Open Issues

1. **LLM recording granularity**: Should recordings be per-prompt (fine-grained, large library) or per-workflow (coarse-grained, fewer files)? Current design is per-prompt. Per-workflow would be simpler to manage but less reusable.

2. **Agent SDK recording complexity**: The Claude Agent SDK uses multi-turn conversations with tool calls. Recording and replaying these faithfully is significantly more complex than recording `structured_output()` calls. The current design uses a simplified approach (record final result only). Full turn-by-turn replay is a future enhancement.

3. **Recording library maintenance**: As prompts change, recordings become stale. Options: (a) automated staleness detection via prompt hash comparison, (b) CI job that re-records periodically, (c) accept some staleness in replay mode. Recommendation: (a) with warnings, not failures.

4. **Local Git Provider fidelity**: The `LocalGitProvider` simulates GitHub PRs as local records. Some GitHub-specific features (PR checks, status checks, review comments) aren't simulated. Tests that depend on these features still need `@requires_github`.

5. **Frontend recording format**: Should event recordings use the same format as the backend event persistence (Part C in OIP-0006), or a separate frontend-optimized format? Current design uses separate formats. Unifying them would enable backend recordings to be replayed in the frontend.

6. **Config overlay mechanism**: Part J introduces `config/local.yaml` as a config overlay. The current `OmoiBaseSettings` system loads from `config/base.yaml`. Need to verify that the config loader supports overlay files, or implement a simple merge strategy.

7. **Mock service completeness**: The initial mock implementations (Part K) cover LLM, GitHub, EventBus, Daytona, and Stripe. Other services (Sentry, PostHog, Logfire) gracefully degrade when unconfigured and may not need mocks. Should we mock them anyway for completeness?

8. **Cross-OIP dependency**: OIP-0006 Part A (LocalDockerProvider) benefits significantly from OIP-0007 Part F (LLM null mode) — local containers still need an LLM service. Implementation of Part A should wait for Part F, or use `LLM_MODE=null` as a workaround.
