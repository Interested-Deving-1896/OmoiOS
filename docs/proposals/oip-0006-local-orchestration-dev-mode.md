# OIP-0006: Local Orchestration Dev Mode

```
OIP: 0006
Title: Local Orchestration Dev Mode
Description: Full local observability for DAG dispatch, agent execution, branch strategy, and task context — without needing remote sandboxes
Author: Kevin Hill
Status: Draft
Type: Standards Track
Created: 2026-03-01
Companion: 0007
```

## Abstract

Introduce a **Local Orchestration Dev Mode** — a suite of five capabilities that make the full agent execution pipeline inspectable and debuggable on a developer's machine. This includes: (A) a `SandboxProvider` protocol with a `LocalDockerProvider` for running agents locally, (B) a dry-run mode for the orchestrator that validates DAG dispatch without creating sandboxes, (C) a CLI event stream that subscribes to the EventBus from a terminal, (D) a branch strategy preview that shows what branches would be created and how they'd merge, and (E) a task context inspector that dumps the exact payload an agent would receive. Together, these address the four visibility gaps that make orchestration debugging painful: you can't see the DAG, can't see execution, can't see task updates, and can't see branch strategy. See [OIP-0007](oip-0007-local-dev-service-abstraction.md) for the companion proposal covering external service abstractions (LLM replay, local Git, spec fixtures, mock layer, dev bootstrap).

## Motivation

### The Problem

Debugging OmoiOS's agent execution pipeline is painful. The current architecture hard-couples the orchestrator to Daytona Cloud sandboxes, and the entire pipeline lacks observability tooling for local development. Specifically:

1. **Can't see if the DAG is correct** — When tasks are dispatched, there's no way to see the dependency graph, which tasks are eligible, what concurrency limits are blocking, or why a specific task was chosen. The orchestrator makes dispatch decisions silently, and the only evidence is database state changes.

2. **Can't see agent execution** — Logs are buried inside remote Daytona sandboxes. Getting stdout/stderr requires API calls to a remote service, not `docker logs` or a local terminal. When an agent fails, you can't `docker exec` into the container to inspect the filesystem.

3. **Can't see ticket and task updates** — Events flow through Redis pub/sub to WebSocket to the frontend, but there's no way to observe them from a terminal. Events are fire-and-forget — they aren't persisted to the database (the `Event` model exists but is never written to), so you can't replay or query historical events.

4. **Can't see if the branch strategy is correct** — Branches are created before sandbox spawn. Convergence merges use a least-conflicts-first ordering (not DAG topology). There's no way to preview what branches will be created, what the merge order will be, or whether conflicts will arise — without actually running the full pipeline against GitHub.

### Why This Matters Now

Per the analysis in Kyle Mathews' ["Amdahl's Law for AI Agents"](https://electric-sql.com/blog/2026/02/19/amdahls-law-for-ai-agents), the bottleneck in multi-agent systems isn't agent capability — it's the human fraction (H). Debugging friction is a major component of H. Every hour spent debugging a remote sandbox failure or guessing at DAG state is an hour not spent on the orchestration logic itself. A local dev mode directly reduces H by making the full pipeline inspectable and reproducible.

### What Already Exists

The codebase is well-positioned for these changes:

- **`backend/omoi_os/workspace/managers.py`** already defines `CommandExecutor` (ABC) with `LocalCommandExecutor`, `DockerCommandExecutor`, and working implementations
- **`backend/omoi_os/workers/claude_sandbox_worker.py`** is explicitly a standalone script with zero Daytona coupling — reads env vars, communicates via HTTP
- **`backend/omoi_os/workers/orchestrator_worker.py`** already has a `sandbox_execution` config flag and a hybrid event+polling loop
- **`backend/omoi_os/services/event_bus.py`** publishes ~40+ event types via Redis pub/sub with `SystemEvent` payloads
- **`backend/omoi_os/services/sandbox_git_operations.py`** already has `count_conflicts_dry_run()` using `git merge-tree`
- **`backend/omoi_os/services/task_context_builder.py`** already has `to_dict()` and `to_markdown()` for full task context serialization
- **`backend/omoi_os/api/routes/debug.py`** has basic debug endpoints for queue stats and task listings
- **`backend/omoi_os/models/event.py`** defines an `Event` model — but nothing writes to it

The gap: these capabilities aren't wired together into a coherent local development experience.

## Specification

### Part A: SandboxProvider Interface

Abstract sandbox lifecycle management behind a provider protocol so the orchestrator doesn't depend on Daytona directly.

#### A.1 SandboxProvider Protocol

**New file**: `backend/omoi_os/services/sandbox_provider.py`

```python
from typing import Protocol, Optional, Any
from dataclasses import dataclass


@dataclass
class SandboxResult:
    """Result of spawning a sandbox."""
    sandbox_id: str
    status: str  # "creating" | "running" | "completed" | "failed" | "terminated"
    connection_info: dict[str, Any]  # Provider-specific connection details


@dataclass
class SandboxStatus:
    """Current status of a sandbox."""
    sandbox_id: str
    status: str
    started_at: Optional[str] = None
    error: Optional[str] = None


class SandboxProvider(Protocol):
    """Protocol for sandbox lifecycle management.

    Implementations handle creating, monitoring, and terminating
    isolated execution environments for agent tasks.
    """

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
        """Spawn an isolated sandbox for task execution.

        Args:
            task_id: The task to execute
            agent_id: The agent assigned to this task
            phase_id: Current execution phase
            env_vars: Environment variables to pass to the sandbox
                      (TASK_DATA_BASE64, GITHUB_TOKEN, CALLBACK_URL, etc.)
            runtime: Agent runtime ("claude" or "openhands")
            execution_mode: "exploration", "implementation", or "validation"
            image: Optional Docker image override

        Returns:
            SandboxResult with sandbox_id and status
        """
        ...

    async def terminate_sandbox(self, sandbox_id: str) -> None:
        """Terminate a running sandbox and clean up resources."""
        ...

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        """Get the current status of a sandbox."""
        ...

    async def list_active(self) -> list[SandboxStatus]:
        """List all currently active sandboxes."""
        ...
```

#### A.2 DaytonaProvider (Wraps Existing Code)

**New file**: `backend/omoi_os/services/daytona_provider.py`

Thin adapter wrapping `DaytonaSpawnerService`. No behavior changes from current production.

```python
class DaytonaProvider:
    """SandboxProvider backed by Daytona Cloud. Wraps existing DaytonaSpawnerService."""

    def __init__(self, spawner: DaytonaSpawnerService):
        self._spawner = spawner

    async def spawn_for_task(self, task_id, agent_id, phase_id, env_vars, **kwargs):
        sandbox_id = await self._spawner.spawn_for_task(
            task_id=task_id, agent_id=agent_id, phase_id=phase_id,
            runtime=kwargs.get("runtime", "claude"),
            execution_mode=kwargs.get("execution_mode", "implementation"),
        )
        return SandboxResult(sandbox_id=sandbox_id, status="creating",
                             connection_info={"provider": "daytona"})

    async def terminate_sandbox(self, sandbox_id):
        await self._spawner.terminate_sandbox(sandbox_id)

    async def get_status(self, sandbox_id):
        info = self._spawner.get_sandbox_info(sandbox_id)
        return SandboxStatus(sandbox_id=sandbox_id,
                             status=info.status if info else "unknown")

    async def list_active(self):
        return [SandboxStatus(sandbox_id=sid, status=info.status)
                for sid, info in self._spawner._active_sandboxes.items()]
```

#### A.3 LocalDockerProvider

**New file**: `backend/omoi_os/services/local_docker_provider.py`

Runs `claude_sandbox_worker.py` inside a local Docker container using the existing `DockerCommandExecutor` patterns from `workspace/managers.py`.

```python
class LocalDockerProvider:
    """SandboxProvider using local Docker containers. Dev-only.

    Benefits over Daytona for dev:
    - `docker logs <container>` for real-time output
    - `docker exec -it <container> bash` to inspect state
    - ~1-2s startup vs cloud provisioning latency
    - No API key or cloud infrastructure required
    """

    DEFAULT_IMAGE = "nikolaik/python-nodejs:python3.12-nodejs22"

    def __init__(self, worker_script_path, api_base_url="http://host.docker.internal:18000",
                 image=None, mount_workspace=None):
        self._worker_script = worker_script_path
        self._api_base_url = api_base_url
        self._image = image or self.DEFAULT_IMAGE
        self._mount_workspace = mount_workspace
        self._active: dict[str, ContainerInfo] = {}

    async def spawn_for_task(self, task_id, agent_id, phase_id, env_vars, **kwargs):
        sandbox_id = f"local-{task_id[:8]}-{uuid4().hex[:6]}"
        container_env = {"SANDBOX_ID": sandbox_id, "CALLBACK_URL": self._api_base_url,
                         "IS_SANDBOX": "1", **env_vars}

        env_flags = " ".join(f'-e {k}="{v}"' for k, v in container_env.items())
        mount_flag = f"-v {self._mount_workspace}:/workspace" if self._mount_workspace else ""

        cmd = (f"docker run -d --name {sandbox_id} {env_flags} {mount_flag} "
               f"--add-host=host.docker.internal:host-gateway "
               f"{self._image} python /workspace/claude_sandbox_worker.py")

        result = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {stderr.decode()}")

        container_id = stdout.decode().strip()
        self._active[sandbox_id] = ContainerInfo(container_id=container_id,
                                                  sandbox_id=sandbox_id, task_id=task_id)

        return SandboxResult(sandbox_id=sandbox_id, status="running",
                             connection_info={"provider": "local-docker",
                                              "container_id": container_id,
                                              "logs_cmd": f"docker logs -f {sandbox_id}",
                                              "exec_cmd": f"docker exec -it {sandbox_id} bash"})

    async def terminate_sandbox(self, sandbox_id):
        if sandbox_id in self._active:
            await asyncio.create_subprocess_shell(f"docker rm -f {sandbox_id}",
                                                  stdout=asyncio.subprocess.DEVNULL)
            del self._active[sandbox_id]

    async def get_status(self, sandbox_id):
        result = await asyncio.create_subprocess_shell(
            f'docker inspect -f "{{{{.State.Status}}}}" {sandbox_id}',
            stdout=asyncio.subprocess.PIPE)
        stdout, _ = await result.communicate()
        docker_status = stdout.decode().strip()
        status_map = {"running": "running", "exited": "completed", "dead": "failed"}
        return SandboxStatus(sandbox_id=sandbox_id,
                             status=status_map.get(docker_status, "unknown"))

    async def list_active(self):
        return [await self.get_status(sid) for sid in self._active]
```

#### A.4 Provider Factory

**New file**: `backend/omoi_os/services/sandbox_factory.py`

```python
def create_sandbox_provider(db=None, event_bus=None, **kwargs) -> SandboxProvider:
    """Create the appropriate SandboxProvider based on config.

    Reads `sandbox.provider` from config/base.yaml:
    - "daytona" (default) → DaytonaProvider (production)
    - "local" → LocalDockerProvider (development)
    """
    settings = get_app_settings()
    provider_type = getattr(settings.sandbox, "provider", "daytona")

    if provider_type == "local":
        from omoi_os.services.local_docker_provider import LocalDockerProvider
        return LocalDockerProvider(
            worker_script_path="backend/omoi_os/workers/claude_sandbox_worker.py",
            api_base_url=f"http://host.docker.internal:{settings.api_port or 18000}",
        )
    else:
        from omoi_os.services.daytona_spawner import DaytonaSpawnerService
        from omoi_os.services.daytona_provider import DaytonaProvider
        spawner = DaytonaSpawnerService(db=db, event_bus=event_bus, **kwargs)
        return DaytonaProvider(spawner)
```

#### A.5 OrchestratorWorker Integration

**Modified file**: `backend/omoi_os/workers/orchestrator_worker.py`

Replace direct `DaytonaSpawnerService` instantiation with the factory:

```python
# Current (line ~956-966):
# self.daytona_spawner = DaytonaSpawnerService(db=self.db, event_bus=self.event_bus, ...)

# New:
from omoi_os.services.sandbox_factory import create_sandbox_provider
self.sandbox_provider = create_sandbox_provider(db=self.db, event_bus=self.event_bus)
```

The `_spawn_sandbox_for_task` method changes from calling `self.daytona_spawner.spawn_for_task()` to `self.sandbox_provider.spawn_for_task()`. Env var assembly logic stays in the orchestrator — it passes the assembled env dict to whichever provider is configured.

#### A.6 Configuration

**Modified file**: `backend/config/base.yaml`

```yaml
sandbox:
  provider: "daytona"          # "daytona" | "local"
  local:
    image: "nikolaik/python-nodejs:python3.12-nodejs22"
    mount_workspace: null      # Optional: mount a local directory into containers
    api_base_url: "http://host.docker.internal:18000"
```

**Modified file**: `backend/omoi_os/config.py`

```python
class SandboxSettings(OmoiBaseSettings):
    yaml_section = "sandbox"
    model_config = SettingsConfigDict(env_prefix="SANDBOX_", extra="ignore")
    provider: str = "daytona"

class LocalSandboxSettings(OmoiBaseSettings):
    yaml_section = "sandbox.local"
    model_config = SettingsConfigDict(env_prefix="SANDBOX_LOCAL_", extra="ignore")
    image: str = "nikolaik/python-nodejs:python3.12-nodejs22"
    mount_workspace: Optional[str] = None
    api_base_url: str = "http://host.docker.internal:18000"
```

---

### Part B: Orchestrator Dry-Run Mode

A mode where the orchestrator runs its full decision loop — task selection, dependency checking, concurrency enforcement, task requirements analysis — but stops before spawning sandboxes or creating branches. This validates the DAG dispatch logic in isolation.

#### B.1 What the Dry-Run Captures

At each orchestrator cycle, the dry-run produces a `DryRunDecision` record:

```python
@dataclass
class DryRunDecision:
    """What the orchestrator WOULD do in a real dispatch cycle."""
    cycle_number: int
    timestamp: str

    # Task selection
    eligible_tasks: list[TaskSummary]           # All tasks that passed dependency check
    selected_task: Optional[TaskSummary]         # The task that would be dispatched
    selection_reason: str                        # Why this task was chosen

    # Dependency state
    dependency_graph: dict[str, list[str]]       # task_id → [depends_on_ids]
    blocked_tasks: list[BlockedTaskInfo]          # Tasks blocked + which dependency is incomplete
    completed_predecessors: list[str]             # Recently completed tasks that unblocked work

    # Concurrency enforcement
    running_count_by_project: dict[str, int]     # project_id → running task count
    running_count_by_org: dict[str, int]          # org_id → running task count
    concurrency_limit_hit: bool                   # Whether limits prevented dispatch
    limit_details: Optional[str]                  # Which limit (project/org) and values

    # Task requirements (LLM-analyzed)
    task_requirements: Optional[TaskRequirements] # execution_mode, output_type, etc.

    # What would happen next
    would_spawn_sandbox: bool
    would_create_branch: bool
    branch_name_preview: Optional[str]
    env_vars_preview: dict[str, str]             # Sanitized (no secrets)
```

#### B.2 Orchestrator Integration

**Modified file**: `backend/omoi_os/workers/orchestrator_worker.py`

Add a dry-run flag that intercepts at `_spawn_and_update()` (line ~550):

```python
# In orchestrator_loop():
dry_run = settings.orchestrator.get("dry_run", False) or os.getenv("ORCHESTRATOR_DRY_RUN") == "true"

# In the dispatch path, after task selection but before spawning:
if dry_run:
    decision = DryRunDecision(
        cycle_number=self._poll_count,
        eligible_tasks=eligible,
        selected_task=selected,
        task_requirements=ctx.task_requirements,
        would_spawn_sandbox=True,
        would_create_branch=True,
        branch_name_preview=await self._preview_branch_name(ctx),
        env_vars_preview=self._sanitize_env_vars(ctx.extra_env),
        # ... remaining fields
    )
    await self._publish_dry_run_decision(decision)
    logger.info("dry_run_decision", **decision.to_log_dict())
    continue  # Skip actual spawn, move to next cycle
```

#### B.3 Dry-Run Event Publishing

Dry-run decisions are published as events so the CLI stream (Part C) can display them:

```python
async def _publish_dry_run_decision(self, decision: DryRunDecision):
    await self.event_bus.publish(SystemEvent(
        event_type="orchestrator.dry_run.decision",
        entity_type="orchestrator",
        entity_id="dry-run",
        payload=decision.to_dict(),
    ))
```

#### B.4 Configuration

```yaml
orchestrator:
  dry_run: false  # Also overridable via ORCHESTRATOR_DRY_RUN=true env var
```

---

### Part C: Terminal Event Stream

A CLI tool that subscribes to the EventBus and renders events in real-time with rich formatting. This replaces the need to have the frontend running just to see what's happening.

#### C.1 CLI Tool

**New file**: `backend/omoi_os/cli/event_stream.py`

```python
"""CLI event stream for OmoiOS orchestration.

Usage:
    python -m omoi_os.cli.event_stream                    # All events
    python -m omoi_os.cli.event_stream --filter TASK_*    # Task events only
    python -m omoi_os.cli.event_stream --filter agent.*   # Agent events only
    python -m omoi_os.cli.event_stream --spec <spec_id>   # Events for a specific spec
    python -m omoi_os.cli.event_stream --json             # Raw JSON output
"""
```

The CLI subscribes to Redis pub/sub channels directly (same mechanism as `WebSocketEventManager._listen_to_redis()`) and formats output for the terminal.

#### C.2 Display Modes

**Default (rich)**: Color-coded, grouped by entity, with timestamps and state transitions:

```
[14:23:01] 🔄 TASK_CREATED       task/abc123   "Implement user auth middleware"
[14:23:01] 📋 TASK_ASSIGNED      task/abc123   → agent/agent-7
[14:23:02] 🚀 SANDBOX_SPAWNED    sandbox/sb-1  container=local-abc12345-f3a1b2
[14:23:03] ▶️  TASK_STARTED       task/abc123   mode=implementation
[14:23:15] 🤖 agent.tool_use     agent/agent-7 tool=Read file="src/auth/middleware.ts"
[14:23:18] 🤖 agent.tool_use     agent/agent-7 tool=Edit file="src/auth/middleware.ts"
[14:23:45] ✅ TASK_COMPLETED     task/abc123   duration=42s
[14:23:46] 🔀 coordination.join  join/j-1      waiting=[task/def456] ready=[task/abc123]
```

**JSON mode** (`--json`): Raw `SystemEvent` payloads, one per line, suitable for piping to `jq`.

**DAG mode** (`--dag`): Periodically refreshes an ASCII DAG showing task states:

```
DAG State (cycle 12):
  ✅ task/abc123 "Auth middleware"
  ✅ task/def456 "Auth tests"
  🔄 task/ghi789 "API integration" [running, 45s]
     └─ depends_on: abc123 ✅, def456 ✅
  ⏳ task/jkl012 "E2E tests" [blocked]
     └─ depends_on: ghi789 🔄
```

#### C.3 Event Filtering

Filters map to Redis pub/sub channel subscriptions:

| Filter | Channels Subscribed |
|--------|-------------------|
| `--filter TASK_*` | `events.TASK_CREATED`, `events.TASK_ASSIGNED`, `events.TASK_STARTED`, etc. |
| `--filter agent.*` | `events.agent.started`, `events.agent.tool_use`, etc. |
| `--spec <id>` | All channels, but client-side filter on `payload.spec_id` |
| `--task <id>` | All channels, but client-side filter on `entity_id` match |
| (none) | `events.*` (all events) |

#### C.4 Event Persistence (Optional Enhancement)

To support replay and historical queries, add a middleware that persists events to the existing `Event` model:

**Modified file**: `backend/omoi_os/services/event_bus.py`

```python
class PersistentEventBus(EventBusService):
    """EventBus that also writes events to the database for replay."""

    async def publish(self, event: SystemEvent):
        await super().publish(event)  # Redis pub/sub (existing)
        if self._persist_enabled:
            await self._persist_event(event)  # DB write (new)
```

This is opt-in via config:

```yaml
event_bus:
  persist_events: false  # Enable for dev/debug, keep off for production
```

---

### Part D: Branch Strategy Preview

Preview what branches would be created, what the merge order would be, and whether conflicts are likely — without touching GitHub.

#### D.1 Branch Preview

**Modified file**: `backend/omoi_os/services/branch_workflow.py`

Add a preview method that runs the same branch naming logic but doesn't create anything:

```python
async def preview_branch_creation(self, ticket_id: str) -> BranchPreview:
    """Preview what branch would be created for this ticket.

    Returns:
        BranchPreview with generated name, source branch, and collision check.
    """
    ticket = await self._get_ticket(ticket_id)
    branch_name = self._generate_branch_name(ticket)
    source_branch = await self._determine_source_branch()
    collision = await self._check_branch_exists(branch_name)

    return BranchPreview(
        branch_name=branch_name,
        source_branch=source_branch,
        would_collide=collision,
        ticket_type=ticket.type,
        naming_rule=f"{self._get_prefix(ticket)}/{{ticket_id}}-{{slug}}",
    )
```

#### D.2 Merge Strategy Preview

**Modified file**: `backend/omoi_os/services/convergence_merge_service.py`

Add a dry-run method that scores source branches and predicts merge outcomes:

```python
async def preview_convergence_merge(
    self,
    source_task_ids: list[str],
    target_branch: str,
    sandbox: Sandbox,
) -> MergePreview:
    """Preview what would happen in a convergence merge.

    Uses git merge-tree (dry-run) to predict conflicts without
    modifying the working tree.
    """
    git_ops = SandboxGitOperations(sandbox)
    scorer = ConflictScorer(git_ops)

    scored_order = await self._score_source_tasks(
        scorer=scorer,
        source_task_ids=source_task_ids,
        target_branch=target_branch,
    )

    predictions = {}
    for task_id, score in scored_order:
        branch = await self._get_task_branch(task_id)
        conflicts = await git_ops.count_conflicts_dry_run(branch)
        predictions[task_id] = ConflictPrediction(
            branch_name=branch,
            would_conflict=conflicts.would_conflict,
            conflict_count=conflicts.conflict_count,
            conflict_files=conflicts.conflict_files,
        )

    total_conflicts = sum(p.conflict_count for p in predictions.values())

    return MergePreview(
        merge_order=[task_id for task_id, _ in scored_order],
        conflict_predictions=predictions,
        total_predicted_conflicts=total_conflicts,
        would_succeed=total_conflicts == 0,
        requires_manual_review=total_conflicts > self.config.max_conflicts_auto_resolve,
        recommendation="proceed" if total_conflicts == 0 else
                       "review" if total_conflicts <= self.config.max_conflicts_auto_resolve else
                       "abort",
    )
```

#### D.3 Full Strategy Preview Endpoint

**New route**: `backend/omoi_os/api/routes/debug.py` (additions)

```python
@router.get("/debug/branch-strategy/{spec_id}")
async def preview_branch_strategy(spec_id: str):
    """Preview the full branch strategy for a spec's tasks.

    Returns:
    - Per-task branch names that would be created
    - Predicted merge order at each convergence point
    - Conflict predictions between parallel branches
    - Overall strategy assessment (proceed/review/abort)
    """
```

#### D.4 CLI Integration

The branch preview integrates with the CLI event stream (Part C). When `--dag` mode is active, branch information is overlaid:

```
Branch Strategy Preview:
  feature/t-abc123-auth-middleware     ← task/abc123
  feature/t-def456-auth-tests         ← task/def456
  Convergence at task/ghi789:
    merge order: [abc123, def456] (least-conflicts-first)
    predicted conflicts: 0
    recommendation: proceed ✅
```

---

### Part E: Task Context Inspector

Dump the exact `FullTaskContext` that would be sent to an agent, so you can verify the agent gets the right instructions before spending compute on execution.

#### E.1 Inspection Endpoint

**New route**: `backend/omoi_os/api/routes/debug.py` (additions)

```python
@router.get("/debug/tasks/{task_id}/context")
async def inspect_task_context(task_id: str, format: str = "markdown"):
    """Inspect the full context that would be sent to an agent for this task.

    This runs the same pipeline as the orchestrator:
    1. TaskContextBuilder.build_context() → FullTaskContext
    2. TaskRequirementsAnalyzer.analyze() → execution_mode, output_type, etc.
    3. Env var assembly (TASK_DATA_BASE64, branch name, etc.)

    Args:
        format: "markdown" (human-readable) | "json" (raw dict) | "base64" (exact TASK_DATA_BASE64)
    """
    context_builder = TaskContextBuilder(db=db)
    full_context = await context_builder.build_context(task_id)

    task_requirements = await analyze_task_requirements(
        task_description=full_context.task_description,
        task_type=full_context.task_type,
    )

    if format == "markdown":
        return {"context": full_context.to_markdown(),
                "requirements": task_requirements.dict()}
    elif format == "json":
        return {"context": full_context.to_dict(),
                "requirements": task_requirements.dict()}
    elif format == "base64":
        task_data = full_context.to_dict()
        task_data["_markdown_context"] = full_context.to_markdown()
        encoded = base64.b64encode(json.dumps(task_data).encode()).decode()
        return {"task_data_base64": encoded,
                "requirements": task_requirements.dict(),
                "decoded_size_bytes": len(json.dumps(task_data).encode())}
```

#### E.2 What's Inspectable

| Data | Source | Description |
|------|--------|-------------|
| Task | `task_data["task"]` | id, type, description, priority, phase |
| Ticket | `task_data["ticket"]` | id, title, description, priority, context |
| Spec | `task_data["spec"]` | id, title, phase, spec_task_id |
| Requirements | `task_data["requirements"]` | id, title, description, type, priority, acceptance_criteria[] |
| Design | `task_data["design"]` | architecture, data_model, interfaces, error_handling, security |
| Spec Tasks | `task_data["spec_tasks"]` | All spec tasks with status, dependencies |
| Current Spec Task | `task_data["current_spec_task"]` | The specific spec task this maps to |
| Revision Feedback | `task_data["revision"]` | If previously failed validation |
| Synthesis Context | `task_data["synthesis_context"]` | Merged results from parallel predecessors |
| Markdown Context | `task_data["_markdown_context"]` | Full human-readable system prompt injection |
| Task Requirements | LLM-analyzed | execution_mode, output_type, requires_code_changes, requires_git_commit, etc. |

#### E.3 CLI Integration

```bash
# Human-readable context
python -m omoi_os.cli.inspect_context <task_id>

# Raw JSON (pipe to jq)
python -m omoi_os.cli.inspect_context <task_id> --json

# Show what the agent's system prompt would contain
python -m omoi_os.cli.inspect_context <task_id> --system-prompt

# Show TASK_DATA_BASE64 exactly as it would be encoded
python -m omoi_os.cli.inspect_context <task_id> --base64
```

---

### Files Changed Summary

| File | Change Type | Part | Lines (est.) |
|------|-------------|------|-------------|
| `backend/omoi_os/services/sandbox_provider.py` | **New** | A | ~60 |
| `backend/omoi_os/services/local_docker_provider.py` | **New** | A | ~150 |
| `backend/omoi_os/services/daytona_provider.py` | **New** | A | ~50 |
| `backend/omoi_os/services/sandbox_factory.py` | **New** | A | ~30 |
| `backend/omoi_os/workers/orchestrator_worker.py` | Modified | A+B | ~80 |
| `backend/omoi_os/config.py` | Modified | A+B+C | ~40 |
| `backend/config/base.yaml` | Modified | A+B+C | ~15 |
| `backend/omoi_os/cli/event_stream.py` | **New** | C | ~250 |
| `backend/omoi_os/services/event_bus.py` | Modified | C | ~40 |
| `backend/omoi_os/services/branch_workflow.py` | Modified | D | ~40 |
| `backend/omoi_os/services/convergence_merge_service.py` | Modified | D | ~60 |
| `backend/omoi_os/api/routes/debug.py` | Modified | D+E | ~120 |
| `backend/omoi_os/cli/inspect_context.py` | **New** | E | ~80 |
| `backend/tests/unit/services/test_sandbox_provider.py` | **New** | A | ~100 |
| `backend/tests/unit/services/test_dry_run.py` | **New** | B | ~80 |
| `backend/tests/unit/cli/test_event_stream.py` | **New** | C | ~60 |
| **Total** | | | **~1,255** |

## Rationale

### Why Five Parts, Not Just a Local Sandbox Provider

The original scope (SandboxProvider only) addresses agent execution visibility but doesn't help with the orchestration layer above it. The four visibility gaps are distinct problems:

| Gap | Part That Addresses It |
|-----|----------------------|
| "Can't see the DAG" | Part B (Dry-Run Mode) |
| "Can't see execution" | Part A (LocalDockerProvider) + Part C (Terminal Event Stream) |
| "Can't see task updates" | Part C (Terminal Event Stream) |
| "Can't see branch strategy" | Part D (Branch Strategy Preview) |

Part E (Task Context Inspector) cuts across all four — it lets you verify what would be sent to an agent before any execution happens.

### Why a Provider Interface, Not Just a Config Flag

The existing `sandbox_execution` boolean in the orchestrator is a blunt instrument — it switches between "use Daytona" and "use legacy polling." A provider interface enables:

- Adding future providers (E2B, Firecracker, Kubernetes Jobs) without touching the orchestrator
- Testing with mock providers in CI
- Gradual migration between providers
- Per-task provider selection (e.g., heavy tasks get Daytona, light tasks run locally)

### Why Docker for Local, Not Process-Level Isolation

| Option | Pros | Cons |
|--------|------|------|
| **Docker containers** | Familiar tooling, `docker logs`, `docker exec`, matches production env | Requires Docker daemon |
| Raw subprocess | Zero overhead, simplest | No isolation, agent can trash host filesystem |
| bubblewrap/nsjail | Lightweight, fast | Linux-only, unfamiliar |
| Firecracker | Strong isolation | Overkill for dev, complex setup |

Docker is the right balance: familiar, cross-platform, provides meaningful isolation, and matches how SWE-agent and OpenHands handle local execution.

### Why a CLI Event Stream, Not Just the Frontend

The frontend WebSocket subscription works well for visual monitoring, but developers debugging the orchestrator often don't have the frontend running — or they're SSH'd into a server, or they want to pipe events through `jq` and `grep`. A CLI tool is the standard observability primitive.

### Why Not Rust + PyO3 (Yet)

A Rust-based orchestration core with Python bindings was considered. The current bottleneck is debugging friction, not orchestrator performance. The Python orchestrator handles the current scale fine. Rust becomes interesting when concurrent agent count exceeds ~50+ or the orchestration state machine needs formal verification. This proposal establishes the interfaces that a future Rust orchestrator would implement against.

### Alternative Considered: Daytona Local Mode

Daytona offers a self-hosted option, but it still requires running the Daytona server locally — significant infrastructure overhead for a dev loop. A local Docker container achieves the same isolation with zero additional infrastructure.

## Backwards Compatibility

**No breaking changes.** All new capabilities are opt-in:

| Capability | Default | How to Enable |
|-----------|---------|---------------|
| SandboxProvider | `provider: "daytona"` | Set `sandbox.provider: "local"` in base.yaml |
| Dry-Run Mode | `dry_run: false` | Set `ORCHESTRATOR_DRY_RUN=true` or config |
| Terminal Event Stream | Not running | Run `python -m omoi_os.cli.event_stream` |
| Event Persistence | Disabled | Set `event_bus.persist_events: true` |
| Branch/Merge Preview | Not called | Hit debug endpoints or use CLI |
| Task Context Inspector | Not called | Hit debug endpoint or use CLI |

The `DaytonaProvider` wraps `DaytonaSpawnerService` with zero behavior changes. Production behavior is identical.

## Security Considerations

### Local Provider Security

- **API keys in env vars**: The local provider passes `ANTHROPIC_API_KEY` and `GITHUB_TOKEN` to Docker containers via `-e` flags. These are visible in `docker inspect`. Acceptable for local dev — the local provider must NOT be used in production.
- **Config guard**: The factory logs a warning if `provider: "local"` is used with `OMOIOS_ENV=production`.
- **Network exposure**: Containers use `host.docker.internal` to reach the local API. Localhost-only — no external exposure.

### Dry-Run Mode Security

- Dry-run decisions include sanitized env vars (secrets redacted) in event payloads.
- The `env_vars_preview` field in `DryRunDecision` strips `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, and any key containing `SECRET`, `PASSWORD`, or `TOKEN`.

### Debug Endpoints Security

- Branch preview and task context inspector endpoints are added to the existing `/debug/` route prefix, which should be restricted to development environments via middleware or auth.
- The task context endpoint does NOT return secret env vars — it returns the `FullTaskContext` object (task data, requirements, design), not the full env var dict.

### Event Persistence Security

- Persisted events may contain entity IDs and payload data. The event persistence feature should only be enabled in development environments.
- The `PersistentEventBus` should strip sensitive payload fields before writing to the database.

### Sandbox Isolation

The local Docker provider provides weaker isolation than Daytona Cloud (shared Docker daemon, no hardware-level isolation). This is explicitly a dev-only mode documented in config.

## Impact Assessment

**Effort**: Medium (~1,255 lines of new code across 5 parts). Parts are independent and can be implemented incrementally.

**Recommended Implementation Order**:

1. **Part E** (Task Context Inspector) — Smallest, highest immediate value. Can debug context assembly today.
2. **Part B** (Dry-Run Mode) — Next highest value. Validate DAG dispatch without sandboxes.
3. **Part C** (Terminal Event Stream) — Foundation for all runtime observability.
4. **Part A** (SandboxProvider + LocalDockerProvider) — Full local execution.
5. **Part D** (Branch Strategy Preview) — Most complex, depends on having tasks to preview.

**Infrastructure**: Zero additional infrastructure. Uses Docker (already installed) and Redis (already running).

**Developer Impact**: High. Addresses the four core visibility gaps that make orchestration debugging painful. Expected to reduce debugging iteration time from "deploy to Daytona, wait, check logs, repeat" to "run locally, see everything, iterate in seconds."

**Production Impact**: None. All features are opt-in. Default configuration unchanged.

**Success Metrics**:
- Developers can validate DAG dispatch logic without spawning any sandboxes (`ORCHESTRATOR_DRY_RUN=true`)
- `python -m omoi_os.cli.event_stream` shows real-time task state transitions in the terminal
- Branch strategy preview correctly predicts merge conflicts before execution
- Task context inspector shows exact payload an agent receives, matching production output
- Local Docker execution works for the full spec → task → agent → callback pipeline

## Open Issues

1. **Worker script packaging**: `claude_sandbox_worker.py` needs to be available inside the Docker container. Options: (a) mount the backend directory, (b) build a custom Docker image with the worker baked in, (c) pip-installable entrypoint. Recommendation: mount for dev, custom image for CI.

2. **MCP server connectivity**: The local agent needs to reach MCP tools. If MCP tools are part of the API on `:18000`, `host.docker.internal:18000` works. If MCP tools are Daytona-specific (e.g., Daytona filesystem tools), those need local equivalents.

3. **Git operations in dry-run**: The branch strategy preview (Part D) needs a Git repo to run `git merge-tree` against. For fully local dry-run (no GitHub), we'd need a local clone. Should the preview endpoint require a sandbox, or use a temporary clone?

4. **Event persistence performance**: Writing every event to the database could add latency. Options: batch writes, async queue, or write-behind cache. The `persist_events` flag should default to off.

5. **CLI tool distribution**: The event stream CLI (`python -m omoi_os.cli.event_stream`) requires the backend Python environment. Could also be a standalone script that connects directly to Redis, reducing setup friction.

6. **Per-task provider selection**: The current design is global (one provider for all tasks). Future extension could allow per-spec or per-task provider selection (e.g., "run EXPLORE locally, run IMPLEMENTATION in Daytona"). The interface supports this but this proposal doesn't implement it.

7. **Sandbox event persistence gap**: `SandboxEvent` records are persisted (via POST to `/api/v1/sandboxes/{id}/events`), but `SystemEvent` records are not. Part C's optional persistence addresses this, but should this be the default behavior regardless of dev mode?

8. **Companion proposal**: [OIP-0007](oip-0007-local-dev-service-abstraction.md) covers the service abstraction layer (Parts F-L) that complements this proposal. Part A (LocalDockerProvider) benefits significantly from OIP-0007 Part F (LLM null mode) — local containers still need an LLM service. Implementation order should interleave both proposals per the combined priority table in OIP-0007's Impact Assessment.
